"""Metadata autofill helpers for Job Log dialogs."""

from __future__ import annotations

import base64
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from .image_io import render_page_image_data_url
from .openai_client import OpenAIResponsesClient
from .pdf_text_order import extract_ordered_page_text

GENERIC_CASE_ENTITIES = {"", "unknown", "desconhecido", "n/a", "na", "sem informação", "sem informacao"}

CASE_NUMBER_PATTERNS = [
    re.compile(r"processo\s*(?:n[.ºo]\s*)?[:\-]?\s*([0-9]{1,4}/[0-9]{2}\.[0-9A-Za-z.]{3,})", re.IGNORECASE),
    re.compile(r"\b([0-9]{1,4}/[0-9]{2}\.[0-9A-Za-z.]{3,})\b"),
]

COURT_PATTERNS = [
    re.compile(r"(Ju[ií]zo\s+Local\s+[A-Za-zÀ-ÿ\s]+?\s+de\s+[A-Za-zÀ-ÿ\s\-]+)", re.IGNORECASE),
    re.compile(r"(Tribunal\s+Judicial(?:\s+da\s+Comarca)?\s+de\s+[A-Za-zÀ-ÿ\s\-]+)", re.IGNORECASE),
    re.compile(r"(Tribunal\s+do\s+Trabalho\s+de\s+[A-Za-zÀ-ÿ\s\-]+)", re.IGNORECASE),
    re.compile(r"(Minist[ée]rio\s+P[úu]blico(?:\s+de\s+[A-Za-zÀ-ÿ\s\-]+)?)", re.IGNORECASE),
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

PHOTO_DATE_PATTERNS = [
    "%A, %B %d, %Y",
    "%B %d, %Y",
    "%a, %B %d, %Y",
]


@dataclass(slots=True)
class MetadataSuggestion:
    case_entity: str | None = None
    case_city: str | None = None
    case_number: str | None = None
    service_entity: str | None = None
    service_city: str | None = None
    service_date: str | None = None
    confidence: dict[str, float] | None = None


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


def _build_ai_client(logger=None) -> OpenAIResponsesClient | None:
    try:
        return OpenAIResponsesClient(logger=logger)
    except Exception:
        return None


def _header_ai_assist(
    header_text: str,
    *,
    ai_client: OpenAIResponsesClient | None,
) -> dict[str, str] | None:
    client = ai_client or _build_ai_client()
    if client is None:
        return None
    instructions = (
        "Extract legal case metadata from Portuguese header text. "
        "Return strict JSON only with keys: case_entity, case_city, case_number."
    )
    prompt = (
        "Header text:\n"
        f"{header_text}\n\n"
        'Return exactly one JSON object like {"case_entity":"...","case_city":"...","case_number":"..."}.\n'
        "Use empty string for unknown values."
    )
    try:
        result = client.create_page_response(
            instructions=instructions,
            prompt_text=prompt,
            effort="medium",
            image_data_url=None,
        )
    except Exception:
        return None
    payload = _parse_json_object(result.raw_output)
    if payload is None:
        return None
    output: dict[str, str] = {}
    for key in ("case_entity", "case_city", "case_number"):
        value = payload.get(key)
        output[key] = str(value).strip() if value is not None else ""
    return output


def extract_from_header_text(
    header_text: str,
    *,
    vocab_cities: list[str],
    ai_enabled: bool,
    ai_client: OpenAIResponsesClient | None = None,
) -> MetadataSuggestion:
    text = header_text.strip()
    case_entity = _extract_case_entity(text)
    case_number = _extract_case_number(text)
    case_city = _first_city_match(text, vocab_cities)
    city_conf = 0.9 if case_city else 0.0
    if case_city is None:
        case_city = _extract_city_heuristic(text)
        city_conf = 0.55 if case_city else 0.0

    entity_conf = 0.9 if case_entity else 0.0
    case_no_conf = 0.95 if case_number else 0.0

    low_conf = (entity_conf < 0.6) or (city_conf < 0.6) or (case_no_conf < 0.5)
    if ai_enabled and low_conf and text:
        ai_data = _header_ai_assist(text, ai_client=ai_client)
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
        service_entity=case_entity,
        service_city=case_city,
        confidence={
            "case_entity": entity_conf,
            "case_city": city_conf,
            "case_number": case_no_conf,
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


def _photo_ai_assist(
    ocr_text: str,
    *,
    ai_client: OpenAIResponsesClient | None,
) -> dict[str, str] | None:
    client = ai_client or _build_ai_client()
    if client is None:
        return None
    instructions = (
        "Extract service metadata from OCR text. "
        "Return strict JSON only with keys: service_city, service_date, case_number."
    )
    prompt = (
        "OCR text:\n"
        f"{ocr_text}\n\n"
        'Return exactly one JSON object like {"service_city":"...","service_date":"YYYY-MM-DD","case_number":"..."}.\n'
        "Use empty string for unknown values."
    )
    try:
        result = client.create_page_response(
            instructions=instructions,
            prompt_text=prompt,
            effort="medium",
            image_data_url=None,
        )
    except Exception:
        return None
    payload = _parse_json_object(result.raw_output)
    if payload is None:
        return None
    output: dict[str, str] = {}
    for key in ("service_city", "service_date", "case_number"):
        value = payload.get(key)
        output[key] = str(value).strip() if value is not None else ""
    return output


def extract_from_photo_ocr_text(
    ocr_text: str,
    *,
    vocab_cities: list[str],
    ai_enabled: bool,
    ai_client: OpenAIResponsesClient | None = None,
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

    low_conf = (city_conf < 0.6) or (date_conf < 0.6)
    if ai_enabled and low_conf and text:
        ai_data = _photo_ai_assist(text, ai_client=ai_client)
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


def extract_header_text_from_pdf_first_page(pdf_path: Path, *, max_lines: int = 14) -> str:
    ordered = extract_ordered_page_text(pdf_path, 0)
    lines = [line.strip() for line in ordered.text.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def _image_path_to_data_url(image_path: Path) -> str:
    image = Image.open(image_path)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def extract_ocr_text_from_photo_image(
    image_path: Path,
    *,
    ai_client: OpenAIResponsesClient | None = None,
) -> str:
    client = ai_client or _build_ai_client()
    if client is None:
        raise RuntimeError("Photo metadata OCR requires OpenAI API access.")
    data_url = _image_path_to_data_url(image_path)
    instructions = (
        "Read visible text in this screenshot/photo. "
        "Return plain text only, preserving likely line breaks, no commentary."
    )
    result = client.create_page_response(
        instructions=instructions,
        prompt_text="Transcribe visible text.",
        effort="medium",
        image_data_url=data_url,
    )
    return result.raw_output.strip()


def extract_header_text_from_pdf_with_ocr_fallback(
    pdf_path: Path,
    *,
    ai_client: OpenAIResponsesClient | None = None,
) -> str:
    header_text = extract_header_text_from_pdf_first_page(pdf_path)
    if header_text.strip():
        return header_text
    client = ai_client or _build_ai_client()
    if client is None:
        return ""
    image_data_url, _ = render_page_image_data_url(pdf_path, page_index=0)
    instructions = (
        "Read only the top section/header text of this legal PDF page image. "
        "Return plain text only."
    )
    result = client.create_page_response(
        instructions=instructions,
        prompt_text="Extract the page header text.",
        effort="medium",
        image_data_url=image_data_url,
    )
    return result.raw_output.strip()
