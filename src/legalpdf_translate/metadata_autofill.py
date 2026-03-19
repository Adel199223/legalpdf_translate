"""Metadata autofill helpers for Job Log dialogs."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from .config import DEFAULT_METADATA_AI_TIMEOUT_SECONDS, DEFAULT_OCR_API_TIMEOUT_SECONDS
from .legal_header_glossary import extract_best_case_entity_match
from .ocr_engine import OcrEngineConfig, OcrResult, build_ocr_engine
from .ocr_engine import (
    candidate_ocr_api_env_names,
    default_ocr_api_env_name,
    invoke_ocr_image,
    local_ocr_available,
    normalize_ocr_api_provider,
    resolve_ocr_api_key,
)
from .ocr_helpers import ocr_pdf_page_text
from .pdf_text_order import extract_ordered_page_text, get_page_count
from .runtime_health import degraded_runtime_reason_from_env
from .types import OcrApiProvider, OcrEnginePolicy, OcrMode

GENERIC_CASE_ENTITIES = {"", "unknown", "desconhecido", "n/a", "na", "sem informação", "sem informacao"}

CASE_NUMBER_PATTERNS = [
    re.compile(r"processo\s*(?:n[.ºo]\s*)?[:\-]?\s*([0-9]{1,8}/[0-9]{2}\.[0-9A-Za-z.]{3,})", re.IGNORECASE),
    re.compile(r"\b([0-9]{1,8}/[0-9]{2}\.[0-9A-Za-z.]{3,})\b"),
]

COURT_PATTERNS = [
    re.compile(r"(Ju[ií]zo[ \t]+Local[ \t]+[A-Za-zÀ-ÿ \-]+?[ \t]+de[ \t]+[A-Za-zÀ-ÿ \-]+)", re.IGNORECASE),
    re.compile(r"(Ju[ií]zo[ \t]+de[ \t]+[A-Za-zÀ-ÿ \-]+?[ \t]+de[ \t]+[A-Za-zÀ-ÿ \-]+(?:[ \t]+-[ \t]+Juiz[ \t]+\d+)?)", re.IGNORECASE),
    re.compile(r"(Minist[ée]rio[ \t]+P[úu]blico(?:[ \t]+de[ \t]+[A-Za-zÀ-ÿ \-]+)?)", re.IGNORECASE),
    re.compile(r"(Tribunal[ \t]+Judicial(?:[ \t]+da[ \t]+Comarca)?[ \t]+de[ \t]+[A-Za-zÀ-ÿ \-]+)", re.IGNORECASE),
    re.compile(r"(Tribunal[ \t]+do[ \t]+Trabalho[ \t]+de[ \t]+[A-Za-zÀ-ÿ \-]+)", re.IGNORECASE),
]

COMARCA_PATTERN = re.compile(
    r"comarca\s+de\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{0,60}?)(?=\n|,|$)",
    re.IGNORECASE,
)
DE_CITY_PATTERN = re.compile(
    r"\bde\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{1,40}?)(?=\n|,|$)",
    re.IGNORECASE,
)
PORTUGAL_CITY_PATTERN = re.compile(r",\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{1,50}),\s*Portugal\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(
    r"(?<![\w@])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![\w@])",
    re.IGNORECASE,
)
COURT_EMAIL_DOMAIN = "tribunais.org.pt"
COURT_EMAIL_CITY_ALIASES = {
    "reguengos de monsaraz": "rmonsaraz",
    "foro alentejo": "falentejo",
}

PHOTO_DATE_PATTERNS = [
    "%A, %B %d, %Y",
    "%B %d, %Y",
    "%a, %B %d, %Y",
]
NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b")
INTERPRETATION_SERVICE_DATE_HINTS = (
    "comparecer",
    "presente",
    "audiência",
    "audiencia",
    "diligência",
    "diligencia",
    "interrogatório",
    "interrogatorio",
    "inquirição",
    "inquiricao",
    "sessão",
    "sessao",
    "declarações",
    "declaracoes",
    "acareação",
    "acareacao",
    "ato",
    "acto",
)
INTERPRETATION_NON_SERVICE_DATE_HINTS = (
    "certificação citius",
    "certificacao citius",
    "referência deste documento",
    "referencia deste documento",
    "citius",
    "documento",
    "notificação",
    "notificacao",
    "elaborado",
    "emitido",
    "data:",
)
LAW_ENFORCEMENT_SERVICE_PATTERNS = (
    re.compile(
        r"\b(?:na|no|junto\s+(?:da|do|ao)|nas\s+instalações\s+da|nas\s+instalacoes\s+da|posto(?:\s+territorial)?\s+(?:da|do)|esquadra\s+(?:da|do))?\s*"
        r"(GNR|PSP)\s+(?:de|da|do)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{1,60}?)(?=,|\.|;|\n|\s+no\s+dia\b|\s+às\b|\s+as\b|$)",
        re.IGNORECASE,
    ),
)


@dataclass(slots=True)
class MetadataSuggestion:
    case_entity: str | None = None
    case_city: str | None = None
    case_number: str | None = None
    court_email: str | None = None
    service_entity: str | None = None
    service_city: str | None = None
    service_date: str | None = None
    confidence: dict[str, float] | None = None


@dataclass(slots=True)
class MetadataAutofillConfig:
    ocr_mode: OcrMode = OcrMode.AUTO
    ocr_engine_policy: OcrEnginePolicy = OcrEnginePolicy.LOCAL_THEN_API
    ocr_api_provider: OcrApiProvider = OcrApiProvider.OPENAI
    ocr_api_base_url: str | None = None
    ocr_api_model: str | None = None
    ocr_api_key_env_name: str = default_ocr_api_env_name(OcrApiProvider.OPENAI)
    ocr_api_timeout_seconds: float = float(DEFAULT_OCR_API_TIMEOUT_SECONDS)
    metadata_ai_timeout_seconds: float = float(DEFAULT_METADATA_AI_TIMEOUT_SECONDS)
    metadata_ai_enabled: bool = True
    metadata_allow_header_ocr_even_if_ocr_off: bool = True


@dataclass(slots=True)
class MetadataExtractionDiagnostics:
    page_numbers: tuple[int, ...] = ()
    embedded_text_pages: tuple[int, ...] = ()
    ocr_attempted_pages: tuple[int, ...] = ()
    embedded_text_found: bool = False
    ocr_attempted: bool = False
    local_ocr_available: bool = False
    api_ocr_configured: bool = False
    api_env_names: tuple[str, ...] = ()
    effective_ocr_mode: str = ""
    ocr_failure_reason: str = ""
    runtime_caveat: str = ""
    extracted_fields: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "page_numbers": list(self.page_numbers),
            "embedded_text_pages": list(self.embedded_text_pages),
            "ocr_attempted_pages": list(self.ocr_attempted_pages),
            "embedded_text_found": bool(self.embedded_text_found),
            "ocr_attempted": bool(self.ocr_attempted),
            "local_ocr_available": bool(self.local_ocr_available),
            "api_ocr_configured": bool(self.api_ocr_configured),
            "api_env_names": list(self.api_env_names),
            "effective_ocr_mode": self.effective_ocr_mode,
            "ocr_failure_reason": self.ocr_failure_reason,
            "runtime_caveat": self.runtime_caveat,
            "extracted_fields": list(self.extracted_fields),
        }


@dataclass(slots=True)
class MetadataExtractionResult:
    suggestion: MetadataSuggestion
    diagnostics: MetadataExtractionDiagnostics


def metadata_config_from_settings(settings: dict[str, object]) -> MetadataAutofillConfig:
    ocr_mode_text = str(settings.get("ocr_mode", "auto") or "auto").strip().lower()
    if ocr_mode_text not in {"off", "auto", "always"}:
        ocr_mode_text = "auto"
    ocr_engine_text = str(settings.get("ocr_engine", "local_then_api") or "local_then_api").strip().lower()
    if ocr_engine_text not in {"local", "local_then_api", "api"}:
        ocr_engine_text = "local_then_api"
    provider = normalize_ocr_api_provider(settings.get("ocr_api_provider", settings.get("ocr_api_provider_default", "openai")))
    key_env_name = str(
        settings.get(
            "ocr_api_key_env_name",
            settings.get("ocr_api_key_env", default_ocr_api_env_name(provider)),
        )
        or default_ocr_api_env_name(provider)
    ).strip() or default_ocr_api_env_name(provider)
    if provider == OcrApiProvider.OPENAI and key_env_name in {"", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"}:
        key_env_name = default_ocr_api_env_name(provider)
    return MetadataAutofillConfig(
        ocr_mode=OcrMode(ocr_mode_text),
        ocr_engine_policy=OcrEnginePolicy(ocr_engine_text),
        ocr_api_provider=provider,
        ocr_api_base_url=str(settings.get("ocr_api_base_url", "") or "").strip() or None,
        ocr_api_model=str(settings.get("ocr_api_model", "") or "").strip() or None,
        ocr_api_key_env_name=key_env_name,
        ocr_api_timeout_seconds=float(DEFAULT_OCR_API_TIMEOUT_SECONDS),
        metadata_ai_timeout_seconds=float(DEFAULT_METADATA_AI_TIMEOUT_SECONDS),
        metadata_ai_enabled=bool(settings.get("metadata_ai_enabled", True)),
        metadata_allow_header_ocr_even_if_ocr_off=True,
    )


def normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    ascii_like = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return ascii_like.casefold()


def _first_city_match(text: str, vocab_cities: list[str]) -> str | None:
    lowered = normalize_for_match(text)
    matches: list[tuple[int, str]] = []
    for city in vocab_cities:
        city_clean = city.strip()
        if city_clean == "":
            continue
        city_norm = normalize_for_match(city_clean)
        idx = lowered.find(city_norm)
        if idx >= 0:
            matches.append((idx, city_clean))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def _sanitize_entity(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if cleaned == "":
        return None
    return cleaned


def _sanitize_city(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if cleaned == "":
        return None
    return cleaned


def _extract_case_number(text: str) -> str | None:
    for pattern in CASE_NUMBER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _extract_case_entity(text: str) -> str | None:
    matched = extract_best_case_entity_match(text)
    if matched is not None:
        return _sanitize_entity(matched.source_text)
    for pattern in COURT_PATTERNS:
        match = pattern.search(text)
        if match:
            return _sanitize_entity(match.group(1))
    return None


def _extract_city_heuristic(text: str) -> str | None:
    comarca = COMARCA_PATTERN.search(text)
    if comarca:
        return _sanitize_city(comarca.group(1))
    portugal = PORTUGAL_CITY_PATTERN.search(text)
    if portugal:
        return _sanitize_city(portugal.group(1))
    de_match = DE_CITY_PATTERN.search(text)
    if de_match:
        candidate = _sanitize_city(de_match.group(1))
        if candidate is not None and len(candidate) <= 40:
            return candidate
    return None


def _sanitize_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip("<>[](){}\"'`")
    cleaned = re.sub(r"[.,;:]+$", "", cleaned)
    if cleaned == "":
        return None
    return cleaned


def _extract_court_email_candidates(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, None

    court_line_indexes = [
        idx
        for idx, line in enumerate(lines)
        if extract_best_case_entity_match(line) is not None or any(pattern.search(line) for pattern in COURT_PATTERNS)
    ]
    first_email: str | None = None
    related_candidates: list[tuple[int, int, int, int, str]] = []

    for line_index, line in enumerate(lines):
        for match in EMAIL_PATTERN.finditer(line):
            email = _sanitize_email(match.group(1))
            if email is None:
                continue
            if first_email is None:
                first_email = email
            if not court_line_indexes:
                continue
            nearest_court_line = min(court_line_indexes, key=lambda court_line: abs(line_index - court_line))
            distance = abs(line_index - nearest_court_line)
            if distance <= 2:
                direction_penalty = 0 if line_index >= nearest_court_line else 1
                related_candidates.append((direction_penalty, distance, line_index, match.start(), email))

    if related_candidates:
        related_candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return related_candidates[0][4], first_email
    return None, first_email


def _court_email_local_part(email: str) -> str:
    local, _, _domain = email.partition("@")
    return local.casefold()


def _court_email_city_slug(case_city: str | None, case_entity: str | None) -> str | None:
    city_source = _sanitize_city(case_city)
    if city_source is None and case_entity:
        city_source = _extract_city_heuristic(case_entity)
    normalized = normalize_for_match(city_source or "").strip()
    if normalized == "":
        return None
    if normalized in COURT_EMAIL_CITY_ALIASES:
        return COURT_EMAIL_CITY_ALIASES[normalized]
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return compact or None


def _infer_court_email_candidates(
    *,
    case_entity: str | None,
    case_city: str | None,
) -> list[str]:
    city_slug = _court_email_city_slug(case_city, case_entity)
    if city_slug is None:
        return []

    entity_norm = normalize_for_match(case_entity or "")
    local_parts: list[str] = []

    def _add_local(local_part: str) -> None:
        if local_part in local_parts:
            return
        local_parts.append(local_part)

    if "ministerio publico" in entity_norm:
        if "trabalho" in entity_norm:
            _add_local(f"{city_slug}.trabalho.ministeriopublico")
        if ("familia" in entity_norm) or ("menores" in entity_norm):
            _add_local(f"{city_slug}.familia.ministeriopublico")
        _add_local(f"{city_slug}.ministeriopublico")
    elif any(token in entity_norm for token in ("tribunal", "juizo", "juízo")):
        _add_local(f"{city_slug}.judicial")

    return [f"{local_part}@{COURT_EMAIL_DOMAIN}" for local_part in local_parts]


def rank_court_email_suggestions(
    *,
    exact_email: str | None,
    case_entity: str | None,
    case_city: str | None,
    vocab_court_emails: list[str],
) -> list[str]:
    ranked: list[str] = []
    seen: set[str] = set()

    def _add(email: str | None) -> None:
        cleaned = _sanitize_email(email)
        if cleaned is None:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        ranked.append(cleaned)

    curated = [_sanitize_email(email) for email in vocab_court_emails]
    curated = [email for email in curated if email is not None]
    inferred = _infer_court_email_candidates(case_entity=case_entity, case_city=case_city)
    city_slug = _court_email_city_slug(case_city, case_entity)

    _add(exact_email)

    curated_by_local = {_court_email_local_part(email): email for email in curated}
    for inferred_email in inferred:
        matched_curated = curated_by_local.get(_court_email_local_part(inferred_email))
        if matched_curated is not None:
            _add(matched_curated)

    for email in inferred:
        _add(email)

    if city_slug is not None:
        city_prefix = f"{city_slug}."
        for email in curated:
            local_part = _court_email_local_part(email)
            if local_part == city_slug or local_part.startswith(city_prefix):
                _add(email)

    for email in curated:
        _add(email)

    return ranked


def choose_court_email_suggestion(
    *,
    exact_email: str | None,
    case_entity: str | None,
    case_city: str | None,
    vocab_court_emails: list[str],
) -> str | None:
    ranked = rank_court_email_suggestions(
        exact_email=exact_email,
        case_entity=case_entity,
        case_city=case_city,
        vocab_court_emails=vocab_court_emails,
    )
    return ranked[0] if ranked else None


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    cleaned = raw.strip()
    if cleaned == "":
        return None
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _resolve_api_client(config: MetadataAutofillConfig) -> OpenAI | None:
    if config.ocr_api_provider != OcrApiProvider.OPENAI:
        return None
    key = resolve_ocr_api_key(
        OcrEngineConfig(
            policy=config.ocr_engine_policy,
            api_provider=config.ocr_api_provider,
            api_base_url=config.ocr_api_base_url,
            api_model=config.ocr_api_model,
            api_key_env_name=config.ocr_api_key_env_name,
            api_timeout_seconds=float(config.ocr_api_timeout_seconds),
        )
    )
    if not key:
        return None
    return OpenAI(
        api_key=key,
        base_url=(config.ocr_api_base_url.strip() if config.ocr_api_base_url else None),
        max_retries=0,
        timeout=max(0.1, float(config.metadata_ai_timeout_seconds)),
    )


def _ai_extract_json(
    prompt: str,
    *,
    config: MetadataAutofillConfig,
) -> dict[str, str] | None:
    client = _resolve_api_client(config)
    if client is None:
        return None
    model = (config.ocr_api_model or "").strip() or "gpt-4o-mini"
    try:
        response = client.responses.create(
            model=model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            store=False,
            timeout=max(0.1, float(config.metadata_ai_timeout_seconds)),
        )
    except Exception:
        return None

    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str):
        output_text = ""
    payload = _parse_json_object(output_text)
    if payload is None:
        return None
    return {str(k): str(v).strip() for k, v in payload.items()}


def extract_from_header_text(
    header_text: str,
    *,
    vocab_cities: list[str],
    ai_enabled: bool,
    ai_config: MetadataAutofillConfig | None = None,
) -> MetadataSuggestion:
    text = header_text.strip()
    matched_entity = extract_best_case_entity_match(text)
    case_entity = _extract_case_entity(text)
    case_number = _extract_case_number(text)
    case_city = _first_city_match(text, vocab_cities)
    city_conf = 0.9 if case_city else 0.0
    if matched_entity is not None and matched_entity.case_city:
        case_city = matched_entity.case_city
        city_conf = max(city_conf, 0.95)
    if case_city is None:
        case_city = _extract_city_heuristic(text)
        city_conf = 0.55 if case_city else 0.0

    entity_conf = 0.95 if matched_entity is not None else (0.9 if case_entity else 0.0)
    case_no_conf = 0.95 if case_number else 0.0
    court_email_near, first_email = _extract_court_email_candidates(text)
    court_email = court_email_near or first_email
    email_conf = 0.9 if court_email_near else (0.6 if first_email else 0.0)

    config = ai_config or MetadataAutofillConfig(metadata_ai_enabled=ai_enabled)
    low_conf = (entity_conf < 0.6) or (city_conf < 0.6) or (case_no_conf < 0.5)
    if ai_enabled and config.metadata_ai_enabled and low_conf and text:
        prompt = (
            "Extract legal case metadata from Portuguese header text. "
            "Return strict JSON only with keys: case_entity, case_city, case_number.\n\n"
            f"Header text:\n{text}"
        )
        ai_data = _ai_extract_json(prompt, config=config)
        if ai_data:
            if not case_entity and ai_data.get("case_entity"):
                case_entity = _sanitize_entity(ai_data.get("case_entity"))
                entity_conf = max(entity_conf, 0.65)
            if not case_city and ai_data.get("case_city"):
                case_city = _sanitize_city(ai_data.get("case_city"))
                city_conf = max(city_conf, 0.65)
            if not case_number and ai_data.get("case_number"):
                case_number = _sanitize_entity(ai_data.get("case_number"))
                case_no_conf = max(case_no_conf, 0.7)

    return MetadataSuggestion(
        case_entity=case_entity,
        case_city=case_city,
        case_number=case_number,
        court_email=court_email,
        service_entity=case_entity,
        service_city=case_city,
        confidence={
            "case_entity": entity_conf,
            "case_city": city_conf,
            "case_number": case_no_conf,
            "court_email": email_conf,
        },
    )


def _extract_photo_date(text: str) -> str | None:
    cleaned = text.replace("•", " ")
    line_candidates = [line.strip() for line in cleaned.splitlines() if line.strip()]
    for line in line_candidates:
        head = line
        lower = line.lower()
        if " am" in lower or " pm" in lower:
            split_pos = max(lower.find(" am"), lower.find(" pm"))
            if split_pos > 0:
                comma_idx = line.rfind(",", 0, split_pos)
                if comma_idx > 0:
                    head = line[: comma_idx + 1 + 5]
        for fmt in PHOTO_DATE_PATTERNS:
            try:
                dt = datetime.strptime(head.strip(), fmt)
            except ValueError:
                continue
            return dt.date().isoformat()

    md_y = re.search(r"\b([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b", cleaned)
    if md_y:
        try:
            dt = datetime.strptime(f"{md_y.group(1)} {md_y.group(2)}, {md_y.group(3)}", "%B %d, %Y")
            return dt.date().isoformat()
        except ValueError:
            pass

    dmy = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", cleaned)
    if dmy:
        day = int(dmy.group(1))
        month = int(dmy.group(2))
        year = int(dmy.group(3))
        try:
            dt = datetime(year=year, month=month, day=day)
            return dt.date().isoformat()
        except ValueError:
            return None
    return None


def _parse_numeric_date_token(token: str) -> str | None:
    match = NUMERIC_DATE_PATTERN.search(token.strip())
    if match is None:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    try:
        parsed = datetime(year=year, month=month, day=day)
    except ValueError:
        return None
    return parsed.date().isoformat()


def _context_contains_any(context: str, hints: tuple[str, ...]) -> bool:
    normalized = normalize_for_match(context)
    return any(hint in normalized for hint in hints)


def _extract_interpretation_service_date(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        context_lines = lines[max(0, index - 1) : min(len(lines), index + 2)]
        context = " ".join(context_lines)
        for match in NUMERIC_DATE_PATTERN.finditer(line):
            iso_value = _parse_numeric_date_token(match.group(0))
            if iso_value is None:
                continue
            score = 0
            if _context_contains_any(context, INTERPRETATION_SERVICE_DATE_HINTS):
                score += 10
            if " dia " in f" {normalize_for_match(context)} ":
                score += 2
            if (" às " in f" {normalize_for_match(context)} ") or (" as " in f" {normalize_for_match(context)} "):
                score += 1
            if _context_contains_any(context, INTERPRETATION_NON_SERVICE_DATE_HINTS):
                score -= 10
            if index >= 4:
                score += 1
            candidates.append((score, index, iso_value))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _canonicalize_city_candidate(candidate: str, vocab_cities: list[str]) -> str | None:
    vocab_match = _first_city_match(candidate, vocab_cities)
    if vocab_match is not None:
        return vocab_match
    cleaned = _sanitize_city(candidate)
    if cleaned is None:
        return None
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or None


def _extract_interpretation_service_location(text: str, *, vocab_cities: list[str]) -> tuple[str | None, str | None]:
    for pattern in LAW_ENFORCEMENT_SERVICE_PATTERNS:
        for match in pattern.finditer(text):
            service_entity = str(match.group(1) or "").strip().upper()
            service_city = _canonicalize_city_candidate(str(match.group(2) or ""), vocab_cities)
            if service_entity in {"GNR", "PSP"} and service_city:
                return service_entity, service_city
    return None, None


def extract_interpretation_notification_metadata_from_text(
    text: str,
    *,
    vocab_cities: list[str],
    ai_enabled: bool,
    ai_config: MetadataAutofillConfig | None = None,
) -> MetadataSuggestion:
    base = extract_from_header_text(
        text,
        vocab_cities=vocab_cities,
        ai_enabled=ai_enabled,
        ai_config=ai_config,
    )
    service_date = _extract_interpretation_service_date(text)
    service_entity, service_city = _extract_interpretation_service_location(
        text,
        vocab_cities=vocab_cities,
    )
    suggestion = MetadataSuggestion(
        case_entity=base.case_entity,
        case_city=base.case_city,
        case_number=base.case_number,
        court_email=base.court_email,
        service_entity=service_entity,
        service_city=service_city,
        service_date=service_date,
        confidence=dict(base.confidence or {}),
    )
    if suggestion.case_number is None:
        suggestion.case_number = _extract_case_number(text)
    if suggestion.case_entity is None:
        suggestion.case_entity = _extract_case_entity(text)
    if suggestion.case_entity:
        case_entity_city = _first_city_match(suggestion.case_entity, vocab_cities) or _extract_city_heuristic(suggestion.case_entity)
        if case_entity_city:
            suggestion.case_city = case_entity_city
    if suggestion.case_city is None:
        suggestion.case_city = _first_city_match(text, vocab_cities) or _extract_city_heuristic(text)
    if suggestion.court_email is None:
        related_email, first_email = _extract_court_email_candidates(text)
        suggestion.court_email = related_email or first_email
    if suggestion.confidence is not None:
        if suggestion.service_date:
            suggestion.confidence["service_date"] = 0.9
        if suggestion.service_entity and suggestion.service_city:
            suggestion.confidence["service_location"] = 0.9
    return suggestion


def extract_from_photo_ocr_text(
    ocr_text: str,
    *,
    vocab_cities: list[str],
    ai_enabled: bool,
    ai_config: MetadataAutofillConfig | None = None,
) -> MetadataSuggestion:
    text = ocr_text.strip()
    service_city = _first_city_match(text, vocab_cities)
    city_conf = 0.9 if service_city else 0.0
    if service_city is None:
        portugal = PORTUGAL_CITY_PATTERN.search(text)
        if portugal:
            service_city = _sanitize_city(portugal.group(1))
            city_conf = 0.6

    service_date = _extract_photo_date(text)
    date_conf = 0.9 if service_date else 0.0
    case_number = _extract_case_number(text)
    case_conf = 0.85 if case_number else 0.0

    config = ai_config or MetadataAutofillConfig(metadata_ai_enabled=ai_enabled)
    low_conf = (city_conf < 0.6) or (date_conf < 0.6)
    if ai_enabled and config.metadata_ai_enabled and low_conf and text:
        prompt = (
            "Extract service metadata from OCR text. "
            "Return strict JSON only with keys: service_city, service_date, case_number.\n\n"
            f"OCR text:\n{text}"
        )
        ai_data = _ai_extract_json(prompt, config=config)
        if ai_data:
            if not service_city and ai_data.get("service_city"):
                service_city = _sanitize_city(ai_data.get("service_city"))
                city_conf = max(city_conf, 0.65)
            if not service_date and ai_data.get("service_date"):
                service_date = _sanitize_entity(ai_data.get("service_date"))
                date_conf = max(date_conf, 0.7)
            if not case_number and ai_data.get("case_number"):
                case_number = _sanitize_entity(ai_data.get("case_number"))
                case_conf = max(case_conf, 0.65)

    return MetadataSuggestion(
        service_city=service_city,
        service_date=service_date,
        case_number=case_number,
        confidence={
            "service_city": city_conf,
            "service_date": date_conf,
            "case_number": case_conf,
        },
    )


def apply_service_case_default_rule(
    *,
    case_entity: str | None,
    case_city: str | None,
    service_entity: str | None,
    service_city: str | None,
    case_entity_user_set: bool,
    case_city_user_set: bool,
    non_court_service_entities: list[str] | None = None,
) -> tuple[str | None, str | None]:
    non_court = {normalize_for_match(value) for value in (non_court_service_entities or ["GNR", "PSP"])}
    service_norm = normalize_for_match(service_entity or "")
    if service_norm not in non_court:
        return case_entity, case_city

    new_case_entity = case_entity
    new_case_city = case_city
    if (not case_entity_user_set) and normalize_for_match(case_entity or "") in GENERIC_CASE_ENTITIES:
        new_case_entity = "Ministério Público"
    if (not case_city_user_set) and (not (case_city or "").strip()):
        new_case_city = service_city
    return new_case_entity, new_case_city


def extract_header_text_from_pdf_page(
    pdf_path: Path,
    page_number: int,
    *,
    max_lines: int = 14,
) -> str:
    if page_number <= 0:
        return ""
    try:
        ordered = extract_ordered_page_text(pdf_path, page_number - 1)
    except Exception:
        return ""
    lines = [line.strip() for line in ordered.text.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def extract_header_text_from_pdf_first_page(pdf_path: Path, *, max_lines: int = 14) -> str:
    return extract_header_text_from_pdf_page(pdf_path, 1, max_lines=max_lines)


def _build_ocr_engine_from_config(config: MetadataAutofillConfig):
    return build_ocr_engine(
        OcrEngineConfig(
            policy=config.ocr_engine_policy,
            api_provider=config.ocr_api_provider,
            api_base_url=config.ocr_api_base_url,
            api_model=config.ocr_api_model,
            api_key_env_name=config.ocr_api_key_env_name,
            api_timeout_seconds=float(config.ocr_api_timeout_seconds),
        )
    )


def _metadata_extracted_fields(suggestion: MetadataSuggestion) -> tuple[str, ...]:
    extracted: list[str] = []
    for field_name in (
        "case_entity",
        "case_city",
        "case_number",
        "court_email",
        "service_entity",
        "service_city",
        "service_date",
    ):
        if str(getattr(suggestion, field_name, "") or "").strip():
            extracted.append(field_name)
    return tuple(extracted)


def _interpretation_notice_ocr_config(config: MetadataAutofillConfig) -> MetadataAutofillConfig:
    if config.ocr_mode != OcrMode.OFF:
        return config
    return MetadataAutofillConfig(
        ocr_mode=OcrMode.AUTO,
        ocr_engine_policy=config.ocr_engine_policy,
        ocr_api_provider=config.ocr_api_provider,
        ocr_api_base_url=config.ocr_api_base_url,
        ocr_api_model=config.ocr_api_model,
        ocr_api_key_env_name=config.ocr_api_key_env_name,
        ocr_api_timeout_seconds=float(config.ocr_api_timeout_seconds),
        metadata_ai_timeout_seconds=float(config.metadata_ai_timeout_seconds),
        metadata_ai_enabled=config.metadata_ai_enabled,
        metadata_allow_header_ocr_even_if_ocr_off=config.metadata_allow_header_ocr_even_if_ocr_off,
    )


def extract_header_text_from_pdf_page_with_ocr_fallback(
    pdf_path: Path,
    *,
    page_number: int = 1,
    config: MetadataAutofillConfig | None = None,
) -> str:
    header_text = extract_header_text_from_pdf_page(pdf_path, page_number)
    if header_text.strip():
        return header_text

    effective = config or MetadataAutofillConfig()
    if effective.ocr_mode == OcrMode.OFF and not effective.metadata_allow_header_ocr_even_if_ocr_off:
        return ""
    ocr_mode = OcrMode.ALWAYS if effective.metadata_allow_header_ocr_even_if_ocr_off else effective.ocr_mode
    try:
        engine = _build_ocr_engine_from_config(effective)
    except Exception:
        return ""
    ocr_result = ocr_pdf_page_text(
        pdf_path=pdf_path,
        page_number=page_number,
        mode=ocr_mode,
        engine=engine,
        prefer_header=True,
        lang_hint="PT",
    )
    return ocr_result.text.strip()


def extract_full_text_from_pdf_page_with_ocr_fallback(
    pdf_path: Path,
    *,
    page_number: int = 1,
    config: MetadataAutofillConfig | None = None,
) -> str:
    if page_number <= 0:
        return ""
    try:
        ordered = extract_ordered_page_text(pdf_path, page_number - 1)
    except Exception:
        ordered = None
    if ordered is not None and ordered.text.strip():
        return ordered.text.strip()

    effective = config or MetadataAutofillConfig()
    if effective.ocr_mode == OcrMode.OFF:
        return ""
    try:
        engine = _build_ocr_engine_from_config(effective)
    except Exception:
        return ""
    ocr_result = ocr_pdf_page_text(
        pdf_path=pdf_path,
        page_number=page_number,
        mode=effective.ocr_mode,
        engine=engine,
        prefer_header=False,
        lang_hint="PT",
    )
    return ocr_result.text.strip()


def extract_header_text_from_pdf_with_ocr_fallback(
    pdf_path: Path,
    *,
    config: MetadataAutofillConfig | None = None,
) -> str:
    return extract_header_text_from_pdf_page_with_ocr_fallback(
        pdf_path,
        page_number=1,
        config=config,
    )


def extract_pdf_header_metadata(
    pdf_path: Path,
    *,
    vocab_cities: list[str],
    config: MetadataAutofillConfig | None = None,
    page_number: int = 1,
) -> MetadataSuggestion:
    effective = config or MetadataAutofillConfig()
    header_text = extract_header_text_from_pdf_page_with_ocr_fallback(
        pdf_path,
        page_number=page_number,
        config=effective,
    )
    if not header_text.strip():
        return MetadataSuggestion()
    return extract_from_header_text(
        header_text,
        vocab_cities=vocab_cities,
        ai_enabled=effective.metadata_ai_enabled,
        ai_config=effective,
    )


def extract_pdf_header_metadata_priority_pages(
    pdf_path: Path,
    *,
    vocab_cities: list[str],
    config: MetadataAutofillConfig | None = None,
    page_numbers: tuple[int, ...] = (1, 2),
) -> MetadataSuggestion:
    effective = config or MetadataAutofillConfig()
    ordered_pages: list[int] = []
    seen: set[int] = set()
    for page_number in page_numbers:
        if page_number <= 0 or page_number in seen:
            continue
        seen.add(page_number)
        ordered_pages.append(page_number)
    if not ordered_pages:
        return MetadataSuggestion()

    suggestions: list[MetadataSuggestion] = []
    related_emails_by_page: dict[int, str | None] = {}
    first_emails_by_page: dict[int, str | None] = {}
    for page_number in ordered_pages:
        header_text = extract_header_text_from_pdf_page_with_ocr_fallback(
            pdf_path,
            page_number=page_number,
            config=effective,
        )
        if not header_text.strip():
            suggestions.append(MetadataSuggestion())
            related_emails_by_page[page_number] = None
            first_emails_by_page[page_number] = None
            continue
        related_email, first_email = _extract_court_email_candidates(header_text)
        suggestion = extract_from_header_text(
            header_text,
            vocab_cities=vocab_cities,
            ai_enabled=effective.metadata_ai_enabled,
            ai_config=effective,
        )
        suggestions.append(suggestion)
        related_emails_by_page[page_number] = related_email
        first_emails_by_page[page_number] = first_email

    merged = MetadataSuggestion()
    merged_confidence: dict[str, float] = {}
    for suggestion in suggestions:
        if merged.case_entity is None and suggestion.case_entity:
            merged.case_entity = suggestion.case_entity
        if merged.case_city is None and suggestion.case_city:
            merged.case_city = suggestion.case_city
        if merged.case_number is None and suggestion.case_number:
            merged.case_number = suggestion.case_number
        if merged.service_entity is None and suggestion.service_entity:
            merged.service_entity = suggestion.service_entity
        if merged.service_city is None and suggestion.service_city:
            merged.service_city = suggestion.service_city
        if merged.service_date is None and suggestion.service_date:
            merged.service_date = suggestion.service_date
        if suggestion.confidence:
            for key, value in suggestion.confidence.items():
                merged_confidence.setdefault(key, float(value))

    selected_email: str | None = None
    for page_number in ordered_pages:
        if related_emails_by_page.get(page_number):
            selected_email = related_emails_by_page[page_number]
            break
    if selected_email is None:
        for page_number in ordered_pages:
            if first_emails_by_page.get(page_number):
                selected_email = first_emails_by_page[page_number]
                break
    merged.court_email = selected_email
    if selected_email is not None:
        merged_confidence["court_email"] = 0.9 if selected_email in related_emails_by_page.values() else 0.6
    merged.confidence = merged_confidence or None
    return merged


def extract_interpretation_notification_metadata_from_pdf(
    pdf_path: Path,
    *,
    vocab_cities: list[str],
    config: MetadataAutofillConfig | None = None,
    page_numbers: tuple[int, ...] = (1, 2),
) -> MetadataSuggestion:
    return extract_interpretation_notification_metadata_from_pdf_with_diagnostics(
        pdf_path,
        vocab_cities=vocab_cities,
        config=config,
        page_numbers=page_numbers,
    ).suggestion


def extract_interpretation_notification_metadata_from_pdf_with_diagnostics(
    pdf_path: Path,
    *,
    vocab_cities: list[str],
    config: MetadataAutofillConfig | None = None,
    page_numbers: tuple[int, ...] = (1, 2),
) -> MetadataExtractionResult:
    effective = config or MetadataAutofillConfig()
    notice_config = _interpretation_notice_ocr_config(effective)
    max_page_count = 0
    try:
        max_page_count = max(0, int(get_page_count(pdf_path)))
    except Exception:
        max_page_count = 0
    ordered_pages: list[int] = []
    seen: set[int] = set()
    for page_number in page_numbers:
        if page_number <= 0 or page_number in seen:
            continue
        if max_page_count and page_number > max_page_count:
            continue
        seen.add(page_number)
        ordered_pages.append(page_number)
    if not ordered_pages:
        ordered_pages = [1]

    ocr_engine_config = OcrEngineConfig(
        policy=notice_config.ocr_engine_policy,
        api_provider=notice_config.ocr_api_provider,
        api_base_url=notice_config.ocr_api_base_url,
        api_model=notice_config.ocr_api_model,
        api_key_env_name=notice_config.ocr_api_key_env_name,
        api_timeout_seconds=float(notice_config.ocr_api_timeout_seconds),
    )
    embedded_text_pages: list[int] = []
    ocr_attempted_pages: list[int] = []
    failure_reasons: list[str] = []
    resolved_engine = None
    engine_ready = False
    combined_text_parts: list[str] = []
    for page_number in ordered_pages:
        try:
            ordered = extract_ordered_page_text(pdf_path, page_number - 1)
        except Exception as exc:
            ordered = None
            failure_reasons.append(f"embedded text extraction failed on page {page_number}: {exc}")
        page_text = ordered.text.strip() if ordered is not None else ""
        if page_text:
            embedded_text_pages.append(page_number)
            combined_text_parts.append(page_text)
            continue
        ocr_attempted_pages.append(page_number)
        if not engine_ready:
            try:
                resolved_engine = _build_ocr_engine_from_config(notice_config)
            except Exception as exc:
                resolved_engine = None
                failure_reasons.append(str(exc))
            engine_ready = True
        if resolved_engine is None:
            continue
        ocr_result = ocr_pdf_page_text(
            pdf_path=pdf_path,
            page_number=page_number,
            mode=notice_config.ocr_mode,
            engine=resolved_engine,
            prefer_header=False,
            lang_hint="PT",
        )
        page_text = ocr_result.text.strip()
        if page_text.strip():
            combined_text_parts.append(page_text.strip())
        elif ocr_result.failed_reason:
            failure_reasons.append(ocr_result.failed_reason)
    suggestion = MetadataSuggestion()
    if combined_text_parts:
        combined_text = "\n\n".join(combined_text_parts)
        suggestion = extract_interpretation_notification_metadata_from_text(
            combined_text,
            vocab_cities=vocab_cities,
            ai_enabled=notice_config.metadata_ai_enabled,
            ai_config=notice_config,
        )
    diagnostics = MetadataExtractionDiagnostics(
        page_numbers=tuple(ordered_pages),
        embedded_text_pages=tuple(embedded_text_pages),
        ocr_attempted_pages=tuple(ocr_attempted_pages),
        embedded_text_found=bool(embedded_text_pages),
        ocr_attempted=bool(ocr_attempted_pages),
        local_ocr_available=local_ocr_available(),
        api_ocr_configured=resolve_ocr_api_key(ocr_engine_config) is not None,
        api_env_names=tuple(candidate_ocr_api_env_names(ocr_engine_config)),
        effective_ocr_mode=notice_config.ocr_mode.value,
        ocr_failure_reason="; ".join(dict.fromkeys(reason.strip() for reason in failure_reasons if reason.strip())),
        runtime_caveat=degraded_runtime_reason_from_env(),
        extracted_fields=_metadata_extracted_fields(suggestion),
    )
    return MetadataExtractionResult(suggestion=suggestion, diagnostics=diagnostics)


def _read_exif_date(image_path: Path) -> str | None:
    try:
        image = Image.open(image_path)
    except Exception:
        return None
    try:
        exif = image.getexif()
    except Exception:
        return None
    for tag in (36867, 36868, 306):  # DateTimeOriginal, DateTimeDigitized, DateTime
        raw = exif.get(tag)
        if not raw:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            return datetime.strptime(text, "%Y:%m:%d %H:%M:%S").date().isoformat()
        except ValueError:
            continue
    return None


def _ocr_photo_text(image_path: Path, config: MetadataAutofillConfig) -> OcrResult:
    try:
        engine = _build_ocr_engine_from_config(config)
    except Exception as exc:  # noqa: BLE001
        return OcrResult(text="", engine="none", failed_reason=str(exc), chars=0)
    try:
        image_bytes = image_path.read_bytes()
    except Exception as exc:  # noqa: BLE001
        return OcrResult(text="", engine="none", failed_reason=f"photo read failed: {exc}", chars=0)
    return invoke_ocr_image(engine, image_bytes, lang_hint="PT", source_type="image")


def extract_photo_metadata_from_image(
    image_path: Path,
    *,
    vocab_cities: list[str],
    config: MetadataAutofillConfig | None = None,
) -> MetadataSuggestion:
    effective = config or MetadataAutofillConfig()
    exif_date = _read_exif_date(image_path)
    if effective.ocr_mode == OcrMode.OFF:
        ocr_result = OcrResult(text="", engine="none", failed_reason="ocr disabled by mode=off", chars=0)
    else:
        ocr_result = _ocr_photo_text(image_path, effective)
    suggestion = extract_from_photo_ocr_text(
        ocr_result.text,
        vocab_cities=vocab_cities,
        ai_enabled=effective.metadata_ai_enabled,
        ai_config=effective,
    )
    if exif_date:
        suggestion.service_date = exif_date
        if suggestion.confidence is None:
            suggestion.confidence = {}
        suggestion.confidence["service_date"] = 0.99
    return suggestion


def default_interpretation_case_entity_for_city(case_city: str) -> str:
    cleaned = _sanitize_city(case_city) or ""
    if cleaned == "":
        return ""
    return f"Ministério Público de {cleaned}"


def extract_interpretation_photo_metadata_from_suggestion(suggestion: MetadataSuggestion) -> MetadataSuggestion:
    case_city = _sanitize_city(suggestion.service_city) or _sanitize_city(suggestion.case_city)
    case_entity = default_interpretation_case_entity_for_city(case_city or "") if case_city else None
    confidence = dict(suggestion.confidence or {})
    if case_entity:
        confidence["case_entity"] = 0.55
    if case_city:
        confidence["case_city"] = max(confidence.get("case_city", 0.0), confidence.get("service_city", 0.0))
    return MetadataSuggestion(
        case_entity=case_entity,
        case_city=case_city,
        case_number=_sanitize_entity(suggestion.case_number),
        court_email=None,
        service_entity=None,
        service_city=None,
        service_date=_sanitize_entity(suggestion.service_date),
        confidence=confidence or None,
    )


def extract_interpretation_photo_metadata_from_ocr_text(
    ocr_text: str,
    *,
    vocab_cities: list[str],
    ai_enabled: bool,
    ai_config: MetadataAutofillConfig | None = None,
) -> MetadataSuggestion:
    base = extract_from_photo_ocr_text(
        ocr_text,
        vocab_cities=vocab_cities,
        ai_enabled=ai_enabled,
        ai_config=ai_config,
    )
    return extract_interpretation_photo_metadata_from_suggestion(base)


def extract_interpretation_photo_metadata_from_image(
    image_path: Path,
    *,
    vocab_cities: list[str],
    config: MetadataAutofillConfig | None = None,
) -> MetadataSuggestion:
    base = extract_photo_metadata_from_image(
        image_path,
        vocab_cities=vocab_cities,
        config=config,
    )
    return extract_interpretation_photo_metadata_from_suggestion(base)
