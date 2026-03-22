"""Shared job-log and interpretation-flow helpers used by multiple frontends."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .metadata_autofill import (
    MetadataExtractionDiagnostics,
    MetadataSuggestion,
    choose_court_email_suggestion,
)
from .ocr_engine import default_ocr_api_env_name
from .types import OcrApiProvider

JOBLOG_VOCAB_SETTINGS_MAP = {
    "job_type": "vocab_job_types",
    "case_entity": "vocab_case_entities",
    "case_city": "vocab_cities",
    "service_entity": "vocab_service_entities",
    "service_city": "vocab_cities",
    "court_email": "vocab_court_emails",
}

_WORD_XML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_DOCX_WORD_SEPARATOR_TAGS = {"tab", "br", "cr"}


@dataclass(slots=True)
class JobLogSeed:
    completed_at: str
    translation_date: str
    job_type: str
    case_number: str
    court_email: str
    case_entity: str
    case_city: str
    service_entity: str
    service_city: str
    service_date: str
    lang: str
    pages: int
    word_count: int
    rate_per_word: float
    expected_total: float
    amount_paid: float
    api_cost: float
    run_id: str
    target_lang: str
    total_tokens: int | None
    estimated_api_cost: float | None
    quality_risk_score: float | None
    profit: float
    travel_km_outbound: float | None = None
    travel_km_return: float | None = None
    use_service_location_in_honorarios: bool = False
    include_transport_sentence_in_honorarios: bool = True
    pdf_path: Path | None = None
    output_docx: Path | None = None
    partial_docx: Path | None = None


@dataclass(frozen=True, slots=True)
class JobLogSavedResult:
    row_id: int
    word_count: int
    case_number: str
    case_entity: str
    case_city: str
    court_email: str
    run_id: str
    translated_docx_path: Path | None = None
    payload: Mapping[str, Any] | None = None


def is_interpretation_job_type(value: str) -> bool:
    return value.strip().casefold() == "interpretation"


def hydrate_joblog_seed(payload: Mapping[str, Any]) -> JobLogSeed:
    values = dict(payload)
    values["pdf_path"] = _coerce_joblog_path(values.get("pdf_path"))
    values["output_docx"] = _coerce_joblog_path(values.get("output_docx"))
    values["partial_docx"] = _coerce_joblog_path(values.get("partial_docx"))
    return JobLogSeed(**values)


def _coerce_joblog_path(value: object) -> Path | None:
    cleaned = str(value or "").strip()
    if cleaned == "":
        return None
    return Path(cleaned).expanduser().resolve()


def _coerce_joblog_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    cleaned = str(value or "").strip()
    if cleaned == "":
        return default
    try:
        return int(cleaned)
    except ValueError:
        return default


def _coerce_joblog_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value or "").strip().replace(",", ".")
    if cleaned == "":
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def _parse_joblog_float(value: str, label: str) -> float:
    cleaned = value.strip().replace(",", ".")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be numeric.") from exc


def _parse_joblog_required_int(value: str, label: str) -> int:
    cleaned = value.strip()
    if cleaned == "":
        raise ValueError(f"{label} must be an integer.")
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer.") from exc


def _parse_joblog_optional_int(value: str, label: str) -> int | None:
    cleaned = value.strip()
    if cleaned == "":
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer.") from exc


def _parse_joblog_optional_float(value: str, label: str) -> float | None:
    cleaned = value.strip().replace(",", ".")
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be numeric.") from exc


def _validate_joblog_date(value: str, label: str) -> str:
    cleaned = value.strip()
    if cleaned == "":
        return ""
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD.") from exc
    return cleaned


def _date_from_completed_at(completed_at: str) -> str:
    cleaned = completed_at.strip()
    if cleaned == "":
        return ""
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return cleaned[:10]


def build_seed_from_joblog_row(row: Mapping[str, object]) -> JobLogSeed:
    completed_at = str(row.get("completed_at", "") or "").strip()
    translation_date = str(row.get("translation_date", "") or "").strip()
    if translation_date == "":
        translation_date = _date_from_completed_at(completed_at)
    service_date = str(row.get("service_date", "") or "").strip()
    if service_date == "" and completed_at:
        service_date = _date_from_completed_at(completed_at)
    return JobLogSeed(
        completed_at=completed_at or f"{translation_date}T00:00:00",
        translation_date=translation_date,
        job_type=str(row.get("job_type", "") or "Translation").strip() or "Translation",
        case_number=str(row.get("case_number", "") or "").strip(),
        court_email=str(row.get("court_email", "") or "").strip(),
        case_entity=str(row.get("case_entity", "") or "").strip(),
        case_city=str(row.get("case_city", "") or "").strip(),
        service_entity=str(row.get("service_entity", "") or "").strip(),
        service_city=str(row.get("service_city", "") or "").strip(),
        service_date=service_date,
        travel_km_outbound=(
            None
            if str(row.get("travel_km_outbound", "") or "").strip() == ""
            else _coerce_joblog_float(row.get("travel_km_outbound"))
        ),
        travel_km_return=(
            None
            if str(row.get("travel_km_return", "") or "").strip() == ""
            else _coerce_joblog_float(row.get("travel_km_return"))
        ),
        use_service_location_in_honorarios=bool(int(row.get("use_service_location_in_honorarios", 0) or 0)),
        include_transport_sentence_in_honorarios=bool(
            int(row.get("include_transport_sentence_in_honorarios", 1) or 1)
        ),
        lang=str(row.get("lang", "") or "").strip(),
        pages=_coerce_joblog_int(row.get("pages")),
        word_count=_coerce_joblog_int(row.get("word_count")),
        rate_per_word=_coerce_joblog_float(row.get("rate_per_word")),
        expected_total=_coerce_joblog_float(row.get("expected_total")),
        amount_paid=_coerce_joblog_float(row.get("amount_paid")),
        api_cost=_coerce_joblog_float(row.get("api_cost")),
        run_id=str(row.get("run_id", "") or "").strip(),
        target_lang=str(row.get("target_lang", "") or "").strip(),
        total_tokens=(
            None
            if str(row.get("total_tokens", "") or "").strip() == ""
            else _coerce_joblog_int(row.get("total_tokens"))
        ),
        estimated_api_cost=(
            None
            if str(row.get("estimated_api_cost", "") or "").strip() == ""
            else _coerce_joblog_float(row.get("estimated_api_cost"))
        ),
        quality_risk_score=(
            None
            if str(row.get("quality_risk_score", "") or "").strip() == ""
            else _coerce_joblog_float(row.get("quality_risk_score"))
        ),
        profit=_coerce_joblog_float(row.get("profit")),
        pdf_path=None,
        output_docx=_coerce_joblog_path(row.get("output_docx_path")),
        partial_docx=_coerce_joblog_path(row.get("partial_docx_path")),
    )


def normalize_joblog_payload(
    *,
    seed: JobLogSeed,
    raw_values: Mapping[str, str],
    service_same_checked: bool,
    use_service_location_in_honorarios_checked: bool = False,
    include_transport_sentence_in_honorarios_checked: bool = True,
) -> dict[str, Any]:
    job_type = raw_values["job_type"].strip() or "Translation"
    is_interpretation = is_interpretation_job_type(job_type)

    if is_interpretation:
        rate = _parse_joblog_optional_float(raw_values["rate_per_word"], "Rate/word") or 0.0
        expected_total = _parse_joblog_optional_float(raw_values["expected_total"], "Expected total") or 0.0
        pages = _parse_joblog_optional_int(raw_values["pages"], "Pages") or 0
        word_count = _parse_joblog_optional_int(raw_values["word_count"], "Words") or 0
    else:
        rate = _parse_joblog_float(raw_values["rate_per_word"], "Rate/word")
        expected_total = _parse_joblog_float(raw_values["expected_total"], "Expected total")
        pages = _parse_joblog_required_int(raw_values["pages"], "Pages")
        word_count = _parse_joblog_required_int(raw_values["word_count"], "Words")

    amount_paid = _parse_joblog_float(raw_values["amount_paid"], "Amount paid")
    api_cost = _parse_joblog_float(raw_values["api_cost"], "API cost")
    profit = _parse_joblog_float(raw_values["profit"], "Profit")
    total_tokens = _parse_joblog_optional_int(raw_values["total_tokens"], "Total tokens")
    estimated_api_cost = _parse_joblog_optional_float(raw_values["estimated_api_cost"], "Estimated API cost")
    quality_risk_score = _parse_joblog_optional_float(raw_values["quality_risk_score"], "Quality risk score")
    if include_transport_sentence_in_honorarios_checked:
        travel_km_outbound = _parse_joblog_optional_float(raw_values.get("travel_km_outbound", ""), "KM outbound")
        travel_km_return = _parse_joblog_optional_float(raw_values.get("travel_km_return", ""), "KM return")
    else:
        try:
            travel_km_outbound = _parse_joblog_optional_float(raw_values.get("travel_km_outbound", ""), "KM outbound")
        except ValueError:
            travel_km_outbound = seed.travel_km_outbound
        try:
            travel_km_return = _parse_joblog_optional_float(raw_values.get("travel_km_return", ""), "KM return")
        except ValueError:
            travel_km_return = seed.travel_km_return

    translation_date = _validate_joblog_date(raw_values["translation_date"], "Translation date")
    service_date = _validate_joblog_date(raw_values["service_date"], "Service date")

    case_entity = raw_values["case_entity"].strip()
    case_city = raw_values["case_city"].strip()
    service_entity = raw_values["service_entity"].strip()
    service_city = raw_values["service_city"].strip()
    if is_interpretation and service_same_checked:
        service_entity = case_entity
        service_city = case_city
    if not is_interpretation:
        service_entity = case_entity
        service_city = case_city
        service_date = translation_date

    if expected_total == 0.0 and rate > 0:
        expected_total = round(rate * float(word_count), 2)
    if profit == 0.0:
        if amount_paid > 0:
            profit = round(amount_paid - api_cost, 2)
        else:
            profit = round(expected_total - api_cost, 2)

    return {
        "translation_date": translation_date or seed.translation_date,
        "job_type": job_type,
        "case_number": raw_values["case_number"].strip(),
        "court_email": raw_values["court_email"].strip(),
        "case_entity": case_entity,
        "case_city": case_city,
        "service_entity": service_entity,
        "service_city": service_city,
        "service_date": service_date,
        "travel_km_outbound": travel_km_outbound,
        "travel_km_return": travel_km_return,
        "use_service_location_in_honorarios": 1 if use_service_location_in_honorarios_checked else 0,
        "include_transport_sentence_in_honorarios": 1 if include_transport_sentence_in_honorarios_checked else 0,
        "lang": raw_values["lang"].strip() or seed.lang,
        "target_lang": raw_values["target_lang"].strip() or seed.target_lang,
        "run_id": raw_values["run_id"].strip(),
        "pages": pages,
        "word_count": word_count,
        "total_tokens": total_tokens,
        "rate_per_word": rate,
        "expected_total": expected_total,
        "amount_paid": amount_paid,
        "api_cost": api_cost,
        "estimated_api_cost": estimated_api_cost,
        "quality_risk_score": quality_risk_score,
        "profit": profit,
    }


def ensure_value_in_joblog_bucket(bucket: list[str], value: str) -> list[str]:
    cleaned = value.strip()
    if cleaned == "":
        return list(bucket)
    lowered = {item.casefold() for item in bucket}
    if cleaned.casefold() in lowered:
        return list(bucket)
    return [*bucket, cleaned]


def merge_payload_into_joblog_settings(
    settings: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    service_equals_case_by_default: bool,
    locked_vocab_keys: set[str] | None = None,
) -> dict[str, Any]:
    merged = dict(settings)
    locked = {str(item).strip() for item in (locked_vocab_keys or set()) if str(item).strip()}
    for column, key in JOBLOG_VOCAB_SETTINGS_MAP.items():
        if key in locked:
            continue
        value = str(payload.get(column, "") or "").strip()
        if not value:
            continue
        bucket = [str(item).strip() for item in list(merged.get(key, [])) if str(item).strip()]
        merged[key] = ensure_value_in_joblog_bucket(bucket, value)
    merged["service_equals_case_by_default"] = bool(service_equals_case_by_default)
    return merged


def build_joblog_settings_save_bundle(settings: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "vocab_case_entities": list(settings["vocab_case_entities"]),
        "vocab_service_entities": list(settings["vocab_service_entities"]),
        "vocab_cities": list(settings["vocab_cities"]),
        "vocab_job_types": list(settings["vocab_job_types"]),
        "vocab_court_emails": list(settings["vocab_court_emails"]),
        "default_rate_per_word": dict(settings["default_rate_per_word"]),
        "joblog_visible_columns": list(settings["joblog_visible_columns"]),
        "joblog_column_widths": dict(settings.get("joblog_column_widths", {})),
        "metadata_ai_enabled": settings["metadata_ai_enabled"],
        "metadata_photo_enabled": settings["metadata_photo_enabled"],
        "service_equals_case_by_default": settings["service_equals_case_by_default"],
        "non_court_service_entities": list(settings["non_court_service_entities"]),
        "ocr_mode": settings["ocr_mode"],
        "ocr_engine": settings["ocr_engine"],
        "ocr_api_provider": settings.get("ocr_api_provider", "openai"),
        "ocr_api_base_url": settings["ocr_api_base_url"],
        "ocr_api_model": settings["ocr_api_model"],
        "ocr_api_key_env_name": settings["ocr_api_key_env_name"],
    }


def build_joblog_saved_result(
    *,
    row_id: int,
    payload: Mapping[str, Any],
    translated_docx_path: Path | None,
) -> JobLogSavedResult:
    return JobLogSavedResult(
        row_id=int(row_id),
        word_count=int(payload["word_count"]),
        case_number=str(payload["case_number"] or ""),
        case_entity=str(payload["case_entity"] or ""),
        case_city=str(payload["case_city"] or ""),
        court_email=str(payload["court_email"] or ""),
        run_id=str(payload["run_id"] or ""),
        translated_docx_path=translated_docx_path,
        payload=dict(payload),
    )


def count_words_from_pages_dir(pages_dir: Path) -> int:
    total = 0
    for page_file in sorted(pages_dir.glob("page_*.txt")):
        text = page_file.read_text(encoding="utf-8")
        total += len(text.split())
    return total


def _extract_visible_text_from_docx(docx_path: Path) -> str:
    if not docx_path.exists() or not docx_path.is_file():
        return ""
    try:
        with ZipFile(docx_path) as archive:
            raw_xml = archive.read("word/document.xml")
    except (OSError, KeyError):
        return ""
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return ""

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", _WORD_XML_NS):
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t":
                if node.text:
                    parts.append(node.text)
            elif tag in _DOCX_WORD_SEPARATOR_TAGS:
                parts.append(" ")
        paragraph_text = "".join(parts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)
    return "\n".join(paragraphs)


def count_words_from_docx(docx_path: Path | None) -> int:
    if docx_path is None:
        return 0
    text = _extract_visible_text_from_docx(docx_path)
    return len(text.split()) if text else 0


def count_words_from_output_artifacts(
    *,
    output_docx: Path | None,
    partial_docx: Path | None,
    pages_dir: Path | None,
) -> int:
    final_count = count_words_from_docx(output_docx)
    if final_count > 0:
        return final_count
    partial_count = count_words_from_docx(partial_docx)
    if partial_count > 0:
        return partial_count
    if pages_dir is None:
        return 0
    return count_words_from_pages_dir(pages_dir)


def build_seed_from_run(
    *,
    pdf_path: Path,
    lang: str,
    output_docx: Path | None,
    partial_docx: Path | None,
    pages_dir: Path | None,
    completed_pages: int,
    completed_at: str,
    default_rate_per_word: float,
    api_cost: float = 0.0,
) -> JobLogSeed:
    word_count = count_words_from_output_artifacts(
        output_docx=output_docx,
        partial_docx=partial_docx,
        pages_dir=pages_dir,
    )
    expected_total = round(float(default_rate_per_word) * float(word_count), 2)
    return JobLogSeed(
        completed_at=completed_at,
        translation_date=_date_from_completed_at(completed_at),
        job_type="Translation",
        case_number="",
        court_email="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date=_date_from_completed_at(completed_at),
        travel_km_outbound=None,
        travel_km_return=None,
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        lang=lang,
        pages=int(completed_pages),
        word_count=int(word_count),
        rate_per_word=float(default_rate_per_word),
        expected_total=expected_total,
        amount_paid=0.0,
        api_cost=float(api_cost),
        run_id="",
        target_lang=lang,
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=round(expected_total - float(api_cost), 2),
        pdf_path=pdf_path,
        output_docx=output_docx,
        partial_docx=partial_docx,
    )


def build_blank_interpretation_seed() -> JobLogSeed:
    now = datetime.now()
    return JobLogSeed(
        completed_at=now.replace(microsecond=0).isoformat(),
        translation_date="",
        job_type="Interpretation",
        case_number="",
        court_email="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date="",
        travel_km_outbound=None,
        travel_km_return=None,
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
        pdf_path=None,
        output_docx=None,
        partial_docx=None,
    )


def build_interpretation_seed_from_notification_pdf(
    *,
    pdf_path: Path,
    suggestion: MetadataSuggestion,
    vocab_court_emails: list[str],
) -> JobLogSeed:
    now = datetime.now()
    service_date = str(getattr(suggestion, "service_date", "") or "").strip()
    case_entity = str(getattr(suggestion, "case_entity", "") or "").strip()
    case_city = str(getattr(suggestion, "case_city", "") or "").strip()
    return JobLogSeed(
        completed_at=now.replace(microsecond=0).isoformat(),
        translation_date=service_date,
        job_type="Interpretation",
        case_number=str(getattr(suggestion, "case_number", "") or "").strip(),
        court_email=(
            choose_court_email_suggestion(
                exact_email=getattr(suggestion, "court_email", ""),
                case_entity=case_entity,
                case_city=case_city,
                vocab_court_emails=vocab_court_emails,
            )
            or ""
        ),
        case_entity=case_entity,
        case_city=case_city,
        service_entity=str(getattr(suggestion, "service_entity", "") or "").strip(),
        service_city=str(getattr(suggestion, "service_city", "") or "").strip(),
        service_date=service_date,
        travel_km_outbound=None,
        travel_km_return=None,
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
        pdf_path=pdf_path,
        output_docx=None,
        partial_docx=None,
    )


def build_interpretation_seed_from_photo_screenshot(
    *,
    suggestion: MetadataSuggestion,
    vocab_court_emails: list[str],
) -> JobLogSeed:
    now = datetime.now()
    service_date = str(getattr(suggestion, "service_date", "") or "").strip()
    case_entity = str(getattr(suggestion, "case_entity", "") or "").strip()
    case_city = str(getattr(suggestion, "case_city", "") or "").strip()
    return JobLogSeed(
        completed_at=now.replace(microsecond=0).isoformat(),
        translation_date=service_date,
        job_type="Interpretation",
        case_number=str(getattr(suggestion, "case_number", "") or "").strip(),
        court_email=(
            choose_court_email_suggestion(
                exact_email=getattr(suggestion, "court_email", ""),
                case_entity=case_entity,
                case_city=case_city,
                vocab_court_emails=vocab_court_emails,
            )
            or ""
        ),
        case_entity=case_entity,
        case_city=case_city,
        service_entity=str(getattr(suggestion, "service_entity", "") or "").strip(),
        service_city=str(getattr(suggestion, "service_city", "") or "").strip(),
        service_date=service_date,
        travel_km_outbound=None,
        travel_km_return=None,
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
        pdf_path=None,
        output_docx=None,
        partial_docx=None,
    )


def build_interpretation_notice_diagnostics_text(diagnostics: MetadataExtractionDiagnostics) -> str:
    page_label = ", ".join(str(page) for page in diagnostics.page_numbers) or "1"
    embedded_label = (
        f"found on page(s) {', '.join(str(page) for page in diagnostics.embedded_text_pages)}"
        if diagnostics.embedded_text_pages
        else "not found"
    )
    if diagnostics.api_ocr_configured:
        if diagnostics.runtime_caveat:
            api_label = "configured, but unavailable in this session"
        else:
            api_label = "configured"
    else:
        env_names = ", ".join(diagnostics.api_env_names) or default_ocr_api_env_name(OcrApiProvider.OPENAI)
        api_label = f"not configured (checked stored OCR key and env vars: {env_names})"
    lines = [
        f"Checked notice pages: {page_label}.",
        f"Embedded PDF text: {embedded_label}.",
        (
            f"OCR attempted on page(s) {', '.join(str(page) for page in diagnostics.ocr_attempted_pages)} "
            f"(mode={diagnostics.effective_ocr_mode or 'auto'})."
            if diagnostics.ocr_attempted_pages
            else "OCR was not needed."
        ),
        "Local OCR: available." if diagnostics.local_ocr_available else "Local OCR: unavailable ('tesseract' was not found in PATH).",
        f"API OCR: {api_label}.",
    ]
    if diagnostics.runtime_caveat:
        lines.append(f"Runtime caveat: {diagnostics.runtime_caveat}")
    if diagnostics.ocr_failure_reason:
        lines.append(f"OCR result: {diagnostics.ocr_failure_reason}")
    extracted = ", ".join(diagnostics.extracted_fields)
    if extracted:
        lines.append(f"Recovered fields: {extracted}.")
    else:
        lines.append("No metadata fields were recovered automatically.")
    return "\n".join(lines)
