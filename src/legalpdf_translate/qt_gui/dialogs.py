"""Qt dialogs for settings and job log flows."""

from __future__ import annotations

from collections import OrderedDict
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from openai import OpenAI
from PySide6.QtCore import QEvent, QObject, QSize, QStandardPaths, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDoubleValidator, QFontMetrics, QIcon, QIntValidator, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from legalpdf_translate.config import (
    DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS,
    DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS,
    OPENAI_MODEL,
)
from legalpdf_translate.glossary import (
    GlossaryEntry,
    build_consistency_glossary_markdown,
    builtin_glossary_json,
    coerce_glossary_tier,
    coerce_source_lang,
    default_ar_entries,
    load_glossary_from_text,
    normalize_enabled_tiers_by_target_lang,
    normalize_glossaries,
    serialize_glossaries,
    supported_target_langs,
    valid_glossary_tiers,
    valid_source_langs,
)
from legalpdf_translate.gmail_draft import (
    GMAIL_DRAFTS_URL,
    assess_gmail_draft_prereqs,
    build_honorarios_gmail_request,
    build_manual_interpretation_gmail_request,
    create_gmail_draft_via_gog,
    validate_translated_docx_artifacts_for_gmail_draft,
)
from legalpdf_translate.gmail_batch import (
    FetchedGmailMessage,
    GmailAttachmentCandidate,
    GmailAttachmentSelection,
)
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.honorarios_docx import (
    HonorariosKind,
    HonorariosDraft,
    build_honorarios_draft,
    build_interpretation_honorarios_draft,
    default_interpretation_recipient_block,
    default_honorarios_filename,
    generate_honorarios_docx,
)
from legalpdf_translate.joblog_db import (
    delete_job_runs,
    insert_job_run,
    list_job_runs,
    open_job_log,
    update_job_run,
    update_job_run_output_paths,
    update_joblog_visible_columns,
)
from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    MetadataSuggestion,
    apply_service_case_default_rule,
    choose_court_email_suggestion,
    extract_interpretation_notification_metadata_from_pdf,
    extract_interpretation_photo_metadata_from_image,
    extract_pdf_header_metadata_priority_pages,
    extract_photo_metadata_from_image,
    metadata_config_from_settings,
    rank_court_email_suggestions,
)
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.ocr_engine import (
    OcrEngineConfig,
    default_ocr_api_base_url,
    default_ocr_api_env_name,
    default_ocr_api_model,
    normalize_ocr_api_provider,
    test_ocr_provider_connection,
)
from legalpdf_translate.pdf_text_order import extract_ordered_page_text, get_page_count
from legalpdf_translate.qt_gui.declutter import (
    DeclutterSection,
    build_compact_add_button,
    build_inline_info_button,
)
from legalpdf_translate.qt_gui.guarded_inputs import GuardedDateEdit, NoWheelComboBox, NoWheelSpinBox
from legalpdf_translate.qt_gui.window_adaptive import CollapsibleSection, ResponsiveWindowController
from legalpdf_translate.qt_gui.worker import (
    HonorariosPdfExportResult,
    HonorariosPdfExportWorker,
    GmailAttachmentPreviewBootstrapResult,
    GmailAttachmentPreviewBootstrapWorker,
    GmailAttachmentPreviewPageResult,
    GmailAttachmentPreviewPageWorker,
)
from legalpdf_translate.review_export import export_review_queue
from legalpdf_translate.resources_loader import resource_path
from legalpdf_translate.secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
    set_openai_key,
    set_ocr_key,
)
from legalpdf_translate.study_glossary import (
    StudyCandidate,
    StudyGlossaryEntry,
    apply_subsumption_suppression,
    build_study_glossary_markdown,
    build_entry_from_candidate,
    compute_non_overlapping_tier_assignment,
    create_candidate_stats,
    compute_next_review_date,
    finalize_study_candidates,
    filter_candidates_by_thresholds,
    fill_translations_for_entry,
    merge_study_entries,
    normalize_study_entries,
    serialize_study_entries,
    supported_learning_langs,
    tokenize_page_for_mode,
    update_candidate_stats_from_page,
)
from legalpdf_translate.types import OcrApiProvider
from legalpdf_translate.user_settings import (
    app_data_dir,
    load_gui_settings,
    load_joblog_settings,
    load_profile_settings,
    save_profile_settings,
    save_gui_settings,
    save_joblog_settings,
)
from legalpdf_translate.user_profile import (
    PROFILE_FIELD_LABELS,
    UserProfile,
    blank_profile,
    distance_for_city,
    find_profile,
    missing_required_profile_fields,
    normalize_profiles,
    primary_profile,
)
from legalpdf_translate.word_automation import (
    WordAutomationResult,
    align_right_and_save_docx_in_word,
    open_docx_in_word,
)

JOBLOG_COLUMNS = [
    "translation_date",
    "case_number",
    "court_email",
    "run_id",
    "job_type",
    "case_entity",
    "case_city",
    "service_entity",
    "service_city",
    "service_date",
    "travel_km_outbound",
    "travel_km_return",
    "lang",
    "target_lang",
    "pages",
    "word_count",
    "total_tokens",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "estimated_api_cost",
    "quality_risk_score",
    "profit",
]

JOBLOG_COLUMN_LABELS = {
    "translation_date": "Date",
    "case_number": "Case #",
    "court_email": "Court Email",
    "run_id": "Run ID",
    "job_type": "Job Type",
    "case_entity": "Case Entity",
    "case_city": "Case City",
    "service_entity": "Service Entity",
    "service_city": "Service City",
    "service_date": "Service Date",
    "travel_km_outbound": "KM Out",
    "travel_km_return": "KM Back",
    "lang": "Lang",
    "target_lang": "Target",
    "pages": "Pages",
    "word_count": "Words",
    "total_tokens": "Total Tokens",
    "rate_per_word": "Rate/Word",
    "expected_total": "Expected",
    "amount_paid": "Paid",
    "api_cost": "API Cost",
    "estimated_api_cost": "Est. API Cost",
    "quality_risk_score": "Risk Score",
    "profit": "Profit",
}

JOBLOG_ACTIONS_COLUMN_LABEL = "Actions"
JOBLOG_ACTIONS_COLUMN_KEY = "__actions__"
JOBLOG_COLUMN_WIDTH_PADDING = 24
JOBLOG_INLINE_COMBO_COLUMNS = {
    "job_type",
    "case_entity",
    "case_city",
    "service_entity",
    "service_city",
    "court_email",
    "lang",
    "target_lang",
}
JOBLOG_INLINE_DATE_COLUMNS = {"translation_date", "service_date"}
JOBLOG_INLINE_INTEGER_COLUMNS = {"pages", "word_count", "total_tokens"}
JOBLOG_INLINE_FLOAT_COLUMNS = {
    "travel_km_outbound",
    "travel_km_return",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "estimated_api_cost",
    "quality_risk_score",
    "profit",
}
JOBLOG_VOCAB_SETTINGS_MAP = {
    "job_type": "vocab_job_types",
    "case_entity": "vocab_case_entities",
    "case_city": "vocab_cities",
    "service_entity": "vocab_service_entities",
    "service_city": "vocab_cities",
    "court_email": "vocab_court_emails",
}
JOBLOG_LANG_OPTIONS = ["EN", "FR", "AR"]


def _is_interpretation_job_type(value: str) -> bool:
    return value.strip().casefold() == "interpretation"


def _set_fixed_height_if_needed(widget: QWidget, height: int) -> None:
    resolved = max(0, int(height))
    if widget.minimumHeight() == resolved and widget.maximumHeight() == resolved:
        return
    widget.setFixedHeight(resolved)


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


def _coerce_joblog_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    cleaned = str(value).strip()
    if cleaned == "":
        return default
    try:
        return bool(int(cleaned))
    except ValueError:
        lowered = cleaned.casefold()
        if lowered in {"true", "yes", "on"}:
            return True
        if lowered in {"false", "no", "off"}:
            return False
    return default


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
        use_service_location_in_honorarios=_coerce_joblog_bool(
            row.get("use_service_location_in_honorarios"),
            default=False,
        ),
        include_transport_sentence_in_honorarios=_coerce_joblog_bool(
            row.get("include_transport_sentence_in_honorarios"),
            default=True,
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


def _widget_text_value(widget: Any) -> str:
    if hasattr(widget, "currentText"):
        return str(widget.currentText())
    if hasattr(widget, "text"):
        return str(widget.text())
    return ""


def _normalize_joblog_payload(
    *,
    seed: JobLogSeed,
    raw_values: Mapping[str, str],
    service_same_checked: bool,
    use_service_location_in_honorarios_checked: bool = False,
    include_transport_sentence_in_honorarios_checked: bool = True,
) -> dict[str, Any]:
    job_type = raw_values["job_type"].strip() or "Translation"
    is_interpretation = _is_interpretation_job_type(job_type)

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


def _ensure_value_in_joblog_settings(settings: dict[str, Any], key: str, value: str) -> None:
    cleaned = value.strip()
    if cleaned == "":
        return
    bucket = list(settings[key])
    lowered = {item.casefold() for item in bucket}
    if cleaned.casefold() in lowered:
        return
    bucket.append(cleaned)
    settings[key] = bucket


def _persist_joblog_vocab_settings(settings: dict[str, Any], payload: Mapping[str, Any]) -> None:
    for column, key in JOBLOG_VOCAB_SETTINGS_MAP.items():
        value = str(payload.get(column, "") or "").strip()
        if value:
            _ensure_value_in_joblog_settings(settings, key, value)


def _save_joblog_settings_bundle(settings: dict[str, Any], *, service_equals_case_by_default: bool) -> None:
    save_joblog_settings(
        {
            "vocab_case_entities": settings["vocab_case_entities"],
            "vocab_service_entities": settings["vocab_service_entities"],
            "vocab_cities": settings["vocab_cities"],
            "vocab_job_types": settings["vocab_job_types"],
            "vocab_court_emails": settings["vocab_court_emails"],
            "default_rate_per_word": settings["default_rate_per_word"],
            "joblog_visible_columns": settings["joblog_visible_columns"],
            "joblog_column_widths": settings.get("joblog_column_widths", {}),
            "metadata_ai_enabled": settings["metadata_ai_enabled"],
            "metadata_photo_enabled": settings["metadata_photo_enabled"],
            "service_equals_case_by_default": service_equals_case_by_default,
            "non_court_service_entities": settings["non_court_service_entities"],
            "ocr_mode": settings["ocr_mode"],
            "ocr_engine": settings["ocr_engine"],
            "ocr_api_base_url": settings["ocr_api_base_url"],
            "ocr_api_model": settings["ocr_api_model"],
            "ocr_api_key_env_name": settings["ocr_api_key_env_name"],
        }
    )


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


@dataclass(frozen=True, slots=True)
class GmailBatchReviewResult:
    selections: tuple[GmailAttachmentSelection, ...]
    target_lang: str = ""
    workflow_kind: str = "translation"

    @property
    def attachments(self) -> tuple[GmailAttachmentCandidate, ...]:
        return tuple(selection.candidate for selection in self.selections)


GMAIL_INTAKE_WORKFLOW_TRANSLATION = "translation"
GMAIL_INTAKE_WORKFLOW_INTERPRETATION = "interpretation"


@dataclass(slots=True)
class GmailBatchReviewPreviewCacheTransfer:
    cached_paths: dict[str, Path]
    cached_page_counts: dict[str, int]
    temp_dir: tempfile.TemporaryDirectory[str] | None = field(default=None, repr=False)

    def cleanup(self) -> None:
        temp_dir = self.temp_dir
        self.temp_dir = None
        if temp_dir is not None:
            temp_dir.cleanup()


_WORD_XML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_DOCX_WORD_SEPARATOR_TAGS = {"tab", "br", "cr"}


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


def _date_from_completed_at(completed_at: str) -> str:
    cleaned = completed_at.strip()
    if cleaned == "":
        return ""
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return cleaned[:10]


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
    today = now.date().isoformat()
    return JobLogSeed(
        completed_at=now.replace(microsecond=0).isoformat(),
        translation_date=today,
        job_type="Interpretation",
        case_number="",
        court_email="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date=today,
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
    service_date = str(suggestion.service_date or "").strip() or now.date().isoformat()
    case_entity = str(suggestion.case_entity or "").strip()
    case_city = str(suggestion.case_city or "").strip()
    return JobLogSeed(
        completed_at=now.replace(microsecond=0).isoformat(),
        translation_date=service_date,
        job_type="Interpretation",
        case_number=str(suggestion.case_number or "").strip(),
        court_email=(
            choose_court_email_suggestion(
                exact_email=suggestion.court_email,
                case_entity=case_entity,
                case_city=case_city,
                vocab_court_emails=vocab_court_emails,
            )
            or ""
        ),
        case_entity=case_entity,
        case_city=case_city,
        service_entity=str(suggestion.service_entity or "").strip(),
        service_city=str(suggestion.service_city or "").strip(),
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
    service_date = str(suggestion.service_date or "").strip() or now.date().isoformat()
    case_entity = str(suggestion.case_entity or "").strip()
    case_city = str(suggestion.case_city or "").strip()
    return JobLogSeed(
        completed_at=now.replace(microsecond=0).isoformat(),
        translation_date=service_date,
        job_type="Interpretation",
        case_number=str(suggestion.case_number or "").strip(),
        court_email=(
            choose_court_email_suggestion(
                exact_email=suggestion.court_email,
                case_entity=case_entity,
                case_city=case_city,
                vocab_court_emails=vocab_court_emails,
            )
            or ""
        ),
        case_entity=case_entity,
        case_city=case_city,
        service_entity=str(suggestion.service_entity or "").strip(),
        service_city=str(suggestion.service_city or "").strip(),
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


def _default_documents_dir() -> Path:
    candidate = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if candidate:
        return Path(candidate).expanduser().resolve()
    return (Path.home() / "Documents").expanduser().resolve()


def _default_downloads_dir() -> Path:
    candidate = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    if candidate:
        return Path(candidate).expanduser().resolve()
    return (Path.home() / "Downloads").expanduser().resolve()


def _open_folder_for_path(parent: QWidget, target: Path) -> None:
    folder = target.expanduser().resolve().parent
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", f"/select,{target.expanduser().resolve()}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(parent, "Open folder failed", str(exc))


def _open_path_in_system(parent: QWidget, target: Path) -> None:
    resolved = target.expanduser().resolve()
    if not resolved.exists():
        QMessageBox.critical(parent, "Open file failed", f"Path not found:\n{resolved}")
        return
    try:
        if os.name == "nt":
            os.startfile(str(resolved))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved)])
        else:
            subprocess.Popen(["xdg-open", str(resolved)])
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(parent, "Open file failed", str(exc))


def _profile_missing_fields_message(profile: UserProfile) -> str:
    missing = missing_required_profile_fields(profile)
    return ", ".join(PROFILE_FIELD_LABELS.get(field_name, field_name) for field_name in missing)


def _current_primary_profile() -> UserProfile:
    profiles, primary_profile_id = load_profile_settings()
    return primary_profile(profiles, primary_profile_id)


class QtProfileManagerDialog(QDialog):
    """Manage persisted honorarios identity profiles."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        settings: Mapping[str, object],
        save_callback: Callable[[list[UserProfile], str], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Profiles")
        self.setMinimumSize(860, 480)
        self._save_callback = save_callback
        self._profiles, self._primary_profile_id = normalize_profiles(
            settings.get("profiles"),
            settings.get("primary_profile_id"),
            fallback_email=str(settings.get("gmail_account_email", "") or ""),
        )
        self._profiles_by_id = {profile.id: profile for profile in self._profiles}
        self._current_profile_id = self._primary_profile_id
        self._selection_changing = False
        self._build_ui()
        self._refresh_list()
        self._select_profile(self._primary_profile_id)
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(980, 620),
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        split = QHBoxLayout()
        split.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(QLabel("Saved profiles"))
        self.profile_list = QListWidget()
        left.addWidget(self.profile_list, 1)

        left_actions = QHBoxLayout()
        self.new_profile_btn = QPushButton("New Profile")
        self.set_primary_btn = QPushButton("Set as Primary")
        self.delete_profile_btn = QPushButton("Delete Profile")
        self.delete_profile_btn.setObjectName("DangerButton")
        left_actions.addWidget(self.new_profile_btn)
        left_actions.addWidget(self.set_primary_btn)
        left_actions.addWidget(self.delete_profile_btn)
        left.addLayout(left_actions)

        split.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        form = QFormLayout()
        self.first_name_edit = QLineEdit()
        self.last_name_edit = QLineEdit()
        self.document_name_override_edit = QLineEdit()
        self.document_name_override_edit.setPlaceholderText("Optional override for Nome/signature")
        self.email_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Optional phone for Gmail signature")
        self.postal_address_edit = QPlainTextEdit()
        self.postal_address_edit.setFixedHeight(88)
        self.iban_edit = QLineEdit()
        self.iva_edit = QLineEdit()
        self.irs_edit = QLineEdit()
        self.travel_origin_edit = QLineEdit()
        self.travel_origin_edit.setPlaceholderText("Origin label used in interpretation transport text")
        form.addRow("First name", self.first_name_edit)
        form.addRow("Last name", self.last_name_edit)
        form.addRow("Document name override", self.document_name_override_edit)
        form.addRow("Email", self.email_edit)
        form.addRow("Phone", self.phone_edit)
        form.addRow("Postal address", self.postal_address_edit)
        form.addRow("IBAN", self.iban_edit)
        form.addRow("IVA text", self.iva_edit)
        form.addRow("IRS text", self.irs_edit)
        form.addRow("Travel origin", self.travel_origin_edit)
        right.addLayout(form)

        distance_group = QGroupBox("Interpretation distances")
        distance_layout = QVBoxLayout(distance_group)
        distance_layout.setContentsMargins(10, 10, 10, 10)
        distance_layout.setSpacing(8)
        self.distance_list = QListWidget(distance_group)
        distance_layout.addWidget(self.distance_list, 1)
        distance_actions = QHBoxLayout()
        self.add_distance_btn = QPushButton("Add/Update Distance")
        self.delete_distance_btn = QPushButton("Delete Distance")
        self.delete_distance_btn.setObjectName("DangerButton")
        distance_actions.addWidget(self.add_distance_btn)
        distance_actions.addWidget(self.delete_distance_btn)
        distance_actions.addStretch(1)
        distance_layout.addLayout(distance_actions)
        right.addWidget(distance_group, 1)

        self.profile_status_label = QLabel("")
        self.profile_status_label.setWordWrap(True)
        right.addWidget(self.profile_status_label)
        right.addStretch(1)
        split.addLayout(right, 2)

        root.addLayout(split, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.close_btn = QPushButton("Close")
        actions.addWidget(self.save_btn)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.profile_list.currentItemChanged.connect(self._on_current_item_changed)
        self.new_profile_btn.clicked.connect(self._new_profile)
        self.set_primary_btn.clicked.connect(self._set_primary)
        self.delete_profile_btn.clicked.connect(self._delete_profile)
        self.add_distance_btn.clicked.connect(self._add_or_update_distance)
        self.delete_distance_btn.clicked.connect(self._delete_distance)
        self.save_btn.clicked.connect(self._save)
        self.close_btn.clicked.connect(self.reject)

    def _profile_label(self, profile: UserProfile) -> str:
        base = profile.document_name or "(Unnamed profile)"
        if profile.id == self._primary_profile_id:
            return f"{base} [Primary]"
        return base

    def _refresh_list(self) -> None:
        ordered_profiles = list(self._profiles_by_id.values())
        self.profile_list.clear()
        for profile in ordered_profiles:
            item = QListWidgetItem(self._profile_label(profile))
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self.profile_list.addItem(item)
        self.set_primary_btn.setEnabled(len(ordered_profiles) > 1)
        self.delete_profile_btn.setEnabled(len(ordered_profiles) > 1)

    def _current_profile(self) -> UserProfile | None:
        if not self._current_profile_id:
            return None
        return self._profiles_by_id.get(self._current_profile_id)

    def _select_profile(self, profile_id: str) -> None:
        self._selection_changing = True
        try:
            for index in range(self.profile_list.count()):
                item = self.profile_list.item(index)
                if str(item.data(Qt.ItemDataRole.UserRole) or "") == profile_id:
                    self.profile_list.setCurrentRow(index)
                    break
        finally:
            self._selection_changing = False
        self._load_current_profile()

    def _commit_current_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        updated = UserProfile(
            id=profile.id,
            first_name=self.first_name_edit.text().strip(),
            last_name=self.last_name_edit.text().strip(),
            document_name_override=self.document_name_override_edit.text().strip(),
            email=self.email_edit.text().strip(),
            phone_number=self.phone_edit.text().strip(),
            postal_address=self.postal_address_edit.toPlainText().strip(),
            iban=self.iban_edit.text().strip(),
            iva_text=self.iva_edit.text().strip(),
            irs_text=self.irs_edit.text().strip(),
            travel_origin_label=self.travel_origin_edit.text().strip(),
            travel_distances_by_city=dict(profile.travel_distances_by_city),
        )
        self._profiles_by_id[updated.id] = updated
        self.profile_status_label.setText(
            f"Resolved document name: {updated.document_name or '(missing first/last name)'}"
        )

    def _load_current_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        self.first_name_edit.setText(profile.first_name)
        self.last_name_edit.setText(profile.last_name)
        self.document_name_override_edit.setText(profile.document_name_override)
        self.email_edit.setText(profile.email)
        self.phone_edit.setText(profile.phone_number)
        self.postal_address_edit.setPlainText(profile.postal_address)
        self.iban_edit.setText(profile.iban)
        self.iva_edit.setText(profile.iva_text)
        self.irs_edit.setText(profile.irs_text)
        self.travel_origin_edit.setText(profile.travel_origin_label)
        self._refresh_distance_list(profile)
        self.profile_status_label.setText(
            f"Resolved document name: {profile.document_name or '(missing first/last name)'}"
        )

    def _refresh_distance_list(self, profile: UserProfile) -> None:
        self.distance_list.clear()
        for city in sorted(profile.travel_distances_by_city, key=lambda value: value.casefold()):
            distance = float(profile.travel_distances_by_city[city])
            distance_text = str(int(distance)) if float(distance).is_integer() else f"{distance:.2f}".rstrip("0").rstrip(".")
            item = QListWidgetItem(f"{city} = {distance_text} km")
            item.setData(Qt.ItemDataRole.UserRole, city)
            self.distance_list.addItem(item)
        self.delete_distance_btn.setEnabled(self.distance_list.count() > 0)

    def _add_or_update_distance(self) -> None:
        self._commit_current_profile()
        profile = self._current_profile()
        if profile is None:
            return
        selected = self.distance_list.currentItem()
        initial_city = str(selected.data(Qt.ItemDataRole.UserRole) or "") if selected is not None else ""
        city, ok = QInputDialog.getText(
            self,
            "Distance city",
            "City:",
            text=initial_city,
        )
        if not ok:
            return
        city_clean = " ".join(city.strip().split())
        if city_clean == "":
            return
        current_distance = distance_for_city(profile, city_clean) or 0.0
        distance_value, ok = QInputDialog.getDouble(
            self,
            "One-way distance",
            f"One-way distance from {profile.travel_origin_label or 'origin'} to {city_clean} (km):",
            current_distance,
            0.0,
            10000.0,
            2,
        )
        if not ok:
            return
        profile.travel_distances_by_city[city_clean] = float(distance_value)
        self._profiles_by_id[profile.id] = profile
        self._refresh_distance_list(profile)

    def _delete_distance(self) -> None:
        self._commit_current_profile()
        profile = self._current_profile()
        if profile is None:
            return
        selected = self.distance_list.currentItem()
        if selected is None:
            return
        city = str(selected.data(Qt.ItemDataRole.UserRole) or "").strip()
        if city == "":
            return
        profile.travel_distances_by_city.pop(city, None)
        self._profiles_by_id[profile.id] = profile
        self._refresh_distance_list(profile)

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if self._selection_changing:
            return
        self._commit_current_profile()
        if current is None:
            return
        profile_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if not profile_id:
            return
        self._current_profile_id = profile_id
        self._load_current_profile()

    def _new_profile(self) -> None:
        self._commit_current_profile()
        profile = blank_profile()
        self._profiles_by_id[profile.id] = profile
        self._refresh_list()
        self._current_profile_id = profile.id
        self._select_profile(profile.id)

    def _set_primary(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        self._primary_profile_id = profile.id
        self._refresh_list()
        self._select_profile(profile.id)

    def _delete_profile(self) -> None:
        ordered_profiles = list(self._profiles_by_id.values())
        if len(ordered_profiles) <= 1:
            QMessageBox.information(self, "Profiles", "At least one profile must remain.")
            return
        profile = self._current_profile()
        if profile is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile.document_name or '(Unnamed profile)'}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        del self._profiles_by_id[profile.id]
        remaining_profiles = list(self._profiles_by_id.values())
        if profile.id == self._primary_profile_id:
            self._primary_profile_id = remaining_profiles[0].id
        self._current_profile_id = remaining_profiles[0].id
        self._refresh_list()
        self._select_profile(self._current_profile_id)

    def _save(self) -> None:
        self._commit_current_profile()
        ordered_profiles = list(self._profiles_by_id.values())
        for profile in ordered_profiles:
            missing_message = _profile_missing_fields_message(profile)
            if missing_message:
                self._current_profile_id = profile.id
                self._refresh_list()
                self._select_profile(profile.id)
                QMessageBox.critical(
                    self,
                    "Profiles",
                    (
                        f"Profile '{profile.document_name or '(Unnamed profile)'}' is missing required fields:\n"
                        f"{missing_message}"
                    ),
                )
                return
        self._save_callback([profile for profile in ordered_profiles], self._primary_profile_id)
        self.accept()


class QtHonorariosExportDialog(QDialog):
    """Generate deterministic Requerimento de Honorarios DOCX/PDF files."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        draft: HonorariosDraft,
        default_directory: Path,
        profile_save_callback: Callable[[list[UserProfile], str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gerar Requerimento de Honorários")
        self.setMinimumSize(520, 240)
        self._default_directory = default_directory.expanduser().resolve()
        self._initial_draft = draft
        self._profiles, self._primary_profile_id = load_profile_settings()
        self._profile_save_callback = profile_save_callback or (
            lambda profiles, primary_profile_id: save_profile_settings(
                profiles=profiles,
                primary_profile_id=primary_profile_id,
            )
        )
        self.saved_path: Path | None = None
        self.requested_path: Path | None = None
        self.saved_pdf_path: Path | None = None
        self.pdf_export_error: str = ""
        self.docx_saved_path: Path | None = None
        self.pdf_saved_path: Path | None = None
        self.pdf_failure_code: str = ""
        self.pdf_failure_message: str = ""
        self.pdf_failure_details: str = ""
        self.pdf_export_elapsed_ms: int = 0
        self.pdf_unavailable_explained: bool = False
        self.auto_renamed: bool = False
        self.generated_draft: HonorariosDraft | None = None
        self._recipient_block_user_edited = False
        self._setting_recipient_block = False
        self._distance_sync_in_progress = False
        self._distance_value_city_key = ""
        self._distance_value_profile_id = ""
        self._distance_value_is_manual = False
        self._pdf_export_thread: QThread | None = None
        self._pdf_export_worker: HonorariosPdfExportWorker | None = None
        self._pdf_export_in_flight = False
        self._build_ui()
        self._refresh_profile_selector(self._primary_profile_id)
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(860, 540 if self._initial_draft.kind == HonorariosKind.INTERPRETATION else 300),
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.form_scroll_area = QScrollArea(self)
        self.form_scroll_area.setObjectName("DialogScrollArea")
        self.form_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.form_scroll_area.setWidgetResizable(True)
        self.form_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget(self.form_scroll_area)
        scroll_content.setObjectName("DialogScrollContent")
        scroll_root = QVBoxLayout(scroll_content)
        scroll_root.setContentsMargins(0, 0, 0, 0)
        scroll_root.setSpacing(8)

        general_panel = QFrame(scroll_content)
        general_panel.setObjectName("ShellPanel")
        form = QFormLayout(general_panel)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        profile_row = QHBoxLayout()
        self.profile_combo = NoWheelComboBox()
        self.profile_combo.setEditable(False)
        self.profile_edit_btn = QPushButton("Edit Profiles...")
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.profile_edit_btn)
        profile_wrap = QWidget()
        profile_wrap.setLayout(profile_row)
        self.case_number_edit = QLineEdit(self._initial_draft.case_number)
        self.case_entity_edit = QLineEdit(self._initial_draft.case_entity)
        self.case_city_edit = QLineEdit(self._initial_draft.case_city)
        self.date_preview_label = QLabel("")
        form.addRow("Profile", profile_wrap)
        form.addRow("Número de processo", self.case_number_edit)
        form.addRow("Case Entity", self.case_entity_edit)
        form.addRow("Case City", self.case_city_edit)
        if self._initial_draft.kind == HonorariosKind.INTERPRETATION:
            initial_service_entity = self._initial_draft.service_entity.strip()
            initial_service_city = self._initial_draft.service_city.strip()
            initial_case_entity = self._initial_draft.case_entity.strip()
            initial_case_city = self._initial_draft.case_city.strip()
            has_explicit_different_service = (
                (initial_service_entity != "" and initial_service_entity != initial_case_entity)
                or (initial_service_city != "" and initial_service_city != initial_case_city)
            )
            self.service_same_check = QCheckBox("Service same as Case")
            self.service_same_check.setChecked(not has_explicit_different_service)
            self.service_date_edit = GuardedDateEdit(self._initial_draft.service_date)
            self.service_date_edit.setPlaceholderText("YYYY-MM-DD")
            self.service_entity_edit = QLineEdit(self._initial_draft.service_entity)
            self.service_city_edit = QLineEdit(self._initial_draft.service_city)
            self.use_service_location_check = QCheckBox("Mention service location in text")
            self.use_service_location_check.setChecked(self._initial_draft.use_service_location_in_honorarios)
            self.include_transport_sentence_check = QCheckBox(
                "Include transport sentence"
            )
            self.include_transport_sentence_check.setChecked(
                self._initial_draft.include_transport_sentence_in_honorarios
            )
            distance_value = self._initial_draft.travel_km_outbound
            if distance_value <= 0 and self._initial_draft.travel_km_return > 0:
                distance_value = self._initial_draft.travel_km_return
            self.distance_label = QLabel("KM (one way)")
            self.travel_km_outbound_edit = QLineEdit("" if distance_value <= 0 else str(distance_value))
            self.travel_km_return_edit = self.travel_km_outbound_edit
            self.recipient_block_edit = QPlainTextEdit()
            self.recipient_block_edit.setPlaceholderText("Recipient block")
            self.recipient_block_edit.setMinimumHeight(72)
            self.recipient_block_edit.setMaximumHeight(140)
            self._set_recipient_block_text(
                self._initial_draft.recipient_block
                or default_interpretation_recipient_block(
                    self._initial_draft.case_entity,
                    self._initial_draft.case_city,
                )
            )
        else:
            self.word_count_edit = QLineEdit(str(self._initial_draft.word_count))
            form.addRow("Número de palavras", self.word_count_edit)
        form.addRow("Data", self.date_preview_label)
        scroll_root.addWidget(general_panel)

        if self._initial_draft.kind == HonorariosKind.INTERPRETATION:
            self.service_group = DeclutterSection("SERVICE", expanded=True, parent=scroll_content)
            self.service_group_help_btn = build_inline_info_button(
                tooltip=(
                    "Open when the service differs from the case or when the generated text "
                    "must mention the service location."
                ),
                accessible_name="Service section help",
                parent=self.service_group,
            )
            self.service_group.add_header_widget(self.service_group_help_btn)
            service_content = QWidget(self.service_group)
            service_form = QFormLayout(service_content)
            service_form.setContentsMargins(0, 0, 0, 0)
            service_form.setSpacing(10)
            service_form.addRow("Service date", self.service_date_edit)
            service_form.addRow("", self.service_same_check)
            service_form.addRow("Service entity", self.service_entity_edit)
            service_form.addRow("Service city", self.service_city_edit)
            self.service_group.set_content_widget(service_content)
            scroll_root.addWidget(self.service_group)

            self.text_group = DeclutterSection("TEXT", expanded=True, parent=scroll_content)
            self.text_group_help_btn = build_inline_info_button(
                tooltip=(
                    "These options only change the generated honorários wording. "
                    "The defaults already match the saved row."
                ),
                accessible_name="Text options help",
                parent=self.text_group,
            )
            self.text_group.add_header_widget(self.text_group_help_btn)
            text_content = QWidget(self.text_group)
            text_grid = QGridLayout(text_content)
            text_grid.setContentsMargins(0, 0, 0, 0)
            text_grid.setHorizontalSpacing(10)
            text_grid.setVerticalSpacing(10)
            text_grid.addWidget(self.use_service_location_check, 0, 0, 1, 3)
            text_grid.addWidget(self.include_transport_sentence_check, 1, 0, 1, 3)
            text_grid.addWidget(self.distance_label, 2, 0)
            text_grid.addWidget(self.travel_km_outbound_edit, 2, 1)
            self.distance_hint_label = QLabel("Saved by city.")
            self.distance_hint_info_btn = build_inline_info_button(
                tooltip="Saved per service city and reused automatically for future interpretation drafts.",
                accessible_name="Distance reuse help",
                parent=text_content,
            )
            distance_hint_row = QHBoxLayout()
            distance_hint_row.setContentsMargins(0, 0, 0, 0)
            distance_hint_row.setSpacing(6)
            distance_hint_row.addWidget(self.distance_hint_label, 0, Qt.AlignmentFlag.AlignVCenter)
            distance_hint_row.addWidget(self.distance_hint_info_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            distance_hint_row.addStretch(1)
            text_grid.addLayout(distance_hint_row, 2, 2)
            text_grid.setColumnStretch(1, 1)
            self.text_group.set_content_widget(text_content)
            scroll_root.addWidget(self.text_group)

            self.recipient_group = DeclutterSection("RECIPIENT", expanded=True, parent=scroll_content)
            self.recipient_group_help_btn = build_inline_info_button(
                tooltip="Uses the case entity and city by default. Open only when the recipient block needs editing.",
                accessible_name="Recipient block help",
                parent=self.recipient_group,
            )
            self.recipient_group.add_header_widget(self.recipient_group_help_btn)
            recipient_content = QWidget(self.recipient_group)
            recipient_layout = QVBoxLayout(recipient_content)
            recipient_layout.setContentsMargins(0, 0, 0, 0)
            recipient_layout.setSpacing(8)
            recipient_layout.addWidget(self.recipient_block_edit)
            self.recipient_group.set_content_widget(recipient_content)
            scroll_root.addWidget(self.recipient_group)

        scroll_root.addStretch(1)
        self.form_scroll_area.setWidget(scroll_content)
        root.addWidget(self.form_scroll_area, 1)
        self.export_status_label = QLabel("")
        self.export_status_label.setVisible(False)
        root.addWidget(self.export_status_label)
        self.export_progress = QProgressBar(self)
        self.export_progress.setRange(0, 0)
        self.export_progress.setTextVisible(False)
        self.export_progress.setVisible(False)
        root.addWidget(self.export_progress)

        self.action_bar = QWidget(self)
        self.action_bar.setObjectName("DialogActionBar")
        actions = QHBoxLayout(self.action_bar)
        actions.setContentsMargins(10, 8, 10, 8)
        actions.setSpacing(10)
        actions.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.generate_btn = QPushButton("Gerar DOCX + PDF")
        self.generate_btn.setObjectName("PrimaryButton")
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.generate_btn)
        root.addWidget(self.action_bar)

        self.cancel_btn.clicked.connect(self.reject)
        self.generate_btn.clicked.connect(self._generate)
        self.profile_edit_btn.clicked.connect(self._edit_profiles)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.case_city_edit.textChanged.connect(self._refresh_date_preview)
        if self._initial_draft.kind == HonorariosKind.INTERPRETATION:
            self.case_entity_edit.textChanged.connect(self._sync_interpretation_recipient_block_if_auto)
            self.case_entity_edit.textChanged.connect(self._on_interpretation_case_fields_changed)
            self.case_city_edit.textChanged.connect(self._sync_interpretation_recipient_block_if_auto)
            self.case_city_edit.textChanged.connect(self._on_interpretation_case_fields_changed)
            self.service_date_edit.textChanged.connect(self._refresh_interpretation_service_section_state)
            self.service_same_check.toggled.connect(self._on_interpretation_service_same_toggled)
            self.service_entity_edit.textChanged.connect(self._on_interpretation_service_fields_changed)
            self.service_city_edit.textChanged.connect(self._on_interpretation_service_fields_changed)
            self.use_service_location_check.toggled.connect(self._on_interpretation_use_service_location_toggled)
            self.include_transport_sentence_check.toggled.connect(self._on_interpretation_transport_sentence_toggled)
            self.travel_km_outbound_edit.textEdited.connect(self._on_interpretation_distance_edited)
            self.recipient_block_edit.textChanged.connect(self._on_recipient_block_text_changed)
            self._refresh_interpretation_service_mirror_state()
            self._refresh_interpretation_transport_sentence_state()
            self._apply_interpretation_distance_defaults()
            self._refresh_interpretation_service_section_state()
            self._refresh_recipient_section_state()
        self._refresh_date_preview()

    def _refresh_profile_selector(self, selected_profile_id: str | None = None) -> None:
        selected = selected_profile_id or self._primary_profile_id
        self.profile_combo.clear()
        for profile in self._profiles:
            label = profile.document_name or "(Unnamed profile)"
            if profile.id == self._primary_profile_id:
                label = f"{label} [Primary]"
            self.profile_combo.addItem(label, profile.id)
        index = self.profile_combo.findData(selected)
        if index < 0:
            index = self.profile_combo.findData(self._primary_profile_id)
        if index < 0 and self.profile_combo.count() > 0:
            index = 0
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def _selected_profile(self) -> UserProfile | None:
        selected_profile_id = str(self.profile_combo.currentData() or "").strip()
        profile = find_profile(self._profiles, selected_profile_id)
        if profile is not None:
            return profile
        return primary_profile(self._profiles, self._primary_profile_id)

    def _set_recipient_block_text(self, value: str) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        self._setting_recipient_block = True
        self.recipient_block_edit.setPlainText(value)
        self._setting_recipient_block = False

    def _default_interpretation_recipient_block(self) -> str:
        return default_interpretation_recipient_block(
            self.case_entity_edit.text().strip(),
            self.case_city_edit.text().strip(),
        )

    def _interpretation_service_matches_case(self) -> bool:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return False
        return (
            self.service_entity_edit.text().strip() == self.case_entity_edit.text().strip()
            and self.service_city_edit.text().strip() == self.case_city_edit.text().strip()
        )

    def _service_section_summary_text(self) -> str:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return ""
        service_date = self.service_date_edit.text().strip()
        service_city = self.service_city_edit.text().strip()
        service_entity = self.service_entity_edit.text().strip()
        if self.service_same_check.isChecked() and not self.use_service_location_check.isChecked():
            status = "Same as case"
        elif self.use_service_location_check.isChecked() and service_city:
            status = f"Location: {service_city}"
        else:
            status = ", ".join(part for part in (service_entity, service_city) if part) or "Review service"
        return " · ".join(part for part in (service_date, status) if part)

    def _should_expand_interpretation_service_section(self) -> bool:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return False
        return (
            self.use_service_location_check.isChecked()
            or not self.service_same_check.isChecked()
            or not self._interpretation_service_matches_case()
        )

    def _refresh_interpretation_service_section_state(self, *_args: object, force_expand: bool = False) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        self.service_group.set_summary_text(self._service_section_summary_text())
        self.service_group.set_expanded(force_expand or self._should_expand_interpretation_service_section())

    def _recipient_block_matches_default(self) -> bool:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return False
        current = self.recipient_block_edit.toPlainText().strip()
        default = self._default_interpretation_recipient_block().strip()
        return current == "" or current == default

    def _recipient_block_is_auto(self) -> bool:
        return (
            self._initial_draft.kind == HonorariosKind.INTERPRETATION
            and not self._recipient_block_user_edited
            and self._recipient_block_matches_default()
        )

    def _recipient_section_summary_text(self) -> str:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return ""
        if self._recipient_block_is_auto():
            return "Auto from case"
        if self._recipient_block_matches_default():
            return "Manual copy"
        lines = [line.strip() for line in self.recipient_block_edit.toPlainText().splitlines() if line.strip()]
        if not lines:
            return "Recipient block"
        first_line = lines[0]
        if len(first_line) > 36:
            first_line = f"{first_line[:33]}..."
        if len(lines) > 1:
            return f"{first_line} (+{len(lines) - 1})"
        return first_line

    def _refresh_recipient_section_state(self, *_args: object, force_expand: bool = False) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        self.recipient_group.set_summary_text(self._recipient_section_summary_text())
        self.recipient_group.set_expanded(force_expand or not self._recipient_block_is_auto())

    def _refresh_date_preview(self, *_args: object) -> None:
        city = self.case_city_edit.text().strip() or self._initial_draft.case_city.strip()
        self.date_preview_label.setText(f"{city}, {self._initial_draft.date_pt}" if city else self._initial_draft.date_pt)

    def _reset_pdf_export_state(self) -> None:
        self.saved_path = None
        self.docx_saved_path = None
        self.requested_path = None
        self.saved_pdf_path = None
        self.pdf_saved_path = None
        self.pdf_export_error = ""
        self.pdf_failure_code = ""
        self.pdf_failure_message = ""
        self.pdf_failure_details = ""
        self.pdf_export_elapsed_ms = 0
        self.pdf_unavailable_explained = False
        self.auto_renamed = False

    def _set_pdf_export_busy(self, busy: bool, *, status_text: str = "") -> None:
        self._pdf_export_in_flight = busy
        self.form_scroll_area.setEnabled(not busy)
        self.generate_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(not busy)
        self.export_status_label.setVisible(busy or bool(status_text))
        self.export_status_label.setText(status_text)
        self.export_progress.setVisible(busy)

    def _clear_pdf_export_worker_refs(self) -> None:
        self._pdf_export_worker = None
        self._pdf_export_thread = None

    def _export_result_info_lines(self) -> list[str]:
        lines: list[str] = []
        if self.auto_renamed and self.saved_path is not None and self.saved_path != self.requested_path:
            lines.extend(
                [
                    "DOCX path already existed; saved as:",
                    str(self.saved_path),
                ]
            )
        if self.saved_path is not None:
            lines.append(f"DOCX: {self.saved_path}")
        if self.saved_pdf_path is not None:
            lines.append(f"PDF: {self.saved_pdf_path}")
        return lines

    def _show_pdf_export_success_box(self) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Requerimento de Honorários")
        box.setText("Honorários DOCX and PDF ready.")
        info_lines = self._export_result_info_lines()
        if info_lines:
            box.setInformativeText("\n".join(info_lines))
        open_docx_btn = box.addButton("Open DOCX", QMessageBox.ButtonRole.ActionRole)
        open_folder_btn = box.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
        continue_btn = box.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(continue_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is open_docx_btn:
            return "open_docx"
        if clicked is open_folder_btn:
            return "open_folder"
        return "continue"

    def _show_pdf_export_failure_box(self) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Requerimento de Honorários")
        box.setText("DOCX ready, PDF unavailable.")
        info_lines = [
            self.pdf_failure_message or "Word could not export the PDF.",
            "Gmail draft stays blocked until a valid PDF is available.",
            *self._export_result_info_lines(),
        ]
        box.setInformativeText("\n\n".join(line for line in info_lines if line))
        if self.pdf_failure_details:
            box.setDetailedText(self.pdf_failure_details)
        open_docx_btn = box.addButton("Open DOCX", QMessageBox.ButtonRole.ActionRole)
        open_folder_btn = box.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
        retry_btn = box.addButton("Retry PDF", QMessageBox.ButtonRole.ActionRole)
        select_pdf_btn = box.addButton("Select existing PDF...", QMessageBox.ButtonRole.ActionRole)
        continue_btn = box.addButton("Continue local-only", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(continue_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is open_docx_btn:
            return "open_docx"
        if clicked is open_folder_btn:
            return "open_folder"
        if clicked is retry_btn:
            return "retry_pdf"
        if clicked is select_pdf_btn:
            return "select_existing_pdf"
        return "continue_local"

    def _validate_selected_honorarios_pdf(self, candidate: Path) -> str | None:
        resolved = candidate.expanduser().resolve()
        if resolved.suffix.casefold() != ".pdf":
            return "Selected file must use the .pdf extension."
        if not resolved.exists() or not resolved.is_file():
            return f"Selected PDF was not found:\n{resolved}"
        try:
            header = resolved.read_bytes()[:5]
        except Exception as exc:  # noqa: BLE001
            return f"Could not read the selected PDF:\n{exc}"
        if not header.startswith(b"%PDF"):
            return "Selected file does not appear to be a valid PDF."
        return None

    def _select_existing_honorarios_pdf(self) -> bool:
        base_dir = self._default_directory
        if self.saved_path is not None:
            base_dir = self.saved_path.expanduser().resolve().parent
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select existing honorários PDF",
            str(base_dir),
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not selected:
            return False
        candidate = Path(selected).expanduser().resolve()
        error = self._validate_selected_honorarios_pdf(candidate)
        if error:
            QMessageBox.critical(self, "Requerimento de Honorários", error)
            return False
        self.saved_pdf_path = candidate
        self.pdf_saved_path = candidate
        self.pdf_failure_code = ""
        self.pdf_failure_message = ""
        self.pdf_failure_details = ""
        self.pdf_export_error = ""
        return True

    def _retry_pdf_export(self) -> bool:
        if self.docx_saved_path is None:
            QMessageBox.critical(
                self,
                "Requerimento de Honorários",
                "The DOCX path is unavailable, so the PDF export cannot be retried.",
            )
            return False
        target_pdf = self.docx_saved_path.with_suffix(".pdf")
        self.saved_pdf_path = None
        self.pdf_saved_path = None
        self.pdf_failure_code = ""
        self.pdf_failure_message = ""
        self.pdf_failure_details = ""
        self.pdf_export_error = ""
        self._set_pdf_export_busy(
            True,
            status_text="DOCX saved. Retrying the sibling PDF export in the background...",
        )
        self._begin_pdf_export(docx_path=self.docx_saved_path, pdf_path=target_pdf)
        return True

    def _run_export_result_flow(self) -> None:
        while True:
            if self.saved_pdf_path is not None:
                action = self._show_pdf_export_success_box()
            else:
                self.pdf_unavailable_explained = True
                action = self._show_pdf_export_failure_box()
            target = self.saved_pdf_path or self.saved_path
            if action == "open_docx":
                if self.saved_path is not None:
                    _open_path_in_system(self, self.saved_path)
                continue
            if action == "open_folder":
                if target is not None:
                    _open_folder_for_path(self, target)
                continue
            if action == "retry_pdf":
                if self._retry_pdf_export():
                    return
                continue
            if action == "select_existing_pdf":
                if self._select_existing_honorarios_pdf():
                    continue
                continue
            self.accept()
            return

    def _begin_pdf_export(self, *, docx_path: Path, pdf_path: Path) -> None:
        try:
            thread = QThread(self)
            worker = HonorariosPdfExportWorker(docx_path=docx_path, pdf_path=pdf_path)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_pdf_export_finished)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(self._clear_pdf_export_worker_refs)
            thread.finished.connect(thread.deleteLater)
            self._pdf_export_thread = thread
            self._pdf_export_worker = worker
            thread.start()
        except Exception as exc:  # noqa: BLE001
            self._on_pdf_export_finished(
                HonorariosPdfExportResult(
                    docx_path=docx_path,
                    pdf_path=None,
                    automation=WordAutomationResult(
                        ok=False,
                        action="export_pdf",
                        message="Word PDF export could not be started.",
                        failure_code="unknown",
                        details=str(exc),
                    ),
                )
            )

    def _on_pdf_export_finished(self, result: HonorariosPdfExportResult) -> None:
        self.docx_saved_path = result.docx_path
        self.saved_path = result.docx_path
        self.pdf_saved_path = result.pdf_path
        self.saved_pdf_path = result.pdf_path
        self.pdf_failure_code = ""
        self.pdf_failure_message = ""
        self.pdf_failure_details = ""
        self.pdf_export_error = ""
        self.pdf_export_elapsed_ms = int(result.automation.elapsed_ms)
        if not result.automation.ok:
            self.saved_pdf_path = None
            self.pdf_saved_path = None
            self.pdf_failure_code = str(result.automation.failure_code or "").strip()
            self.pdf_failure_message = str(result.automation.message or "").strip() or "Word could not export the PDF."
            self.pdf_failure_details = str(result.automation.details or "").strip()
            self.pdf_export_error = self.pdf_failure_message
        self._set_pdf_export_busy(False)
        self._run_export_result_flow()

    def _on_recipient_block_text_changed(self) -> None:
        if self._setting_recipient_block or self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        self._recipient_block_user_edited = True
        self._refresh_recipient_section_state(force_expand=True)

    def _sync_interpretation_recipient_block_if_auto(self, *_args: object) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION or self._recipient_block_user_edited:
            return
        self._set_recipient_block_text(self._default_interpretation_recipient_block())
        self._refresh_recipient_section_state()

    def _interpretation_transport_sentence_enabled(self) -> bool:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return False
        checkbox = getattr(self, "include_transport_sentence_check", None)
        if checkbox is None:
            return True
        return checkbox.isChecked()

    def _refresh_interpretation_transport_sentence_state(self) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        enabled = self._interpretation_transport_sentence_enabled()
        distance_label = getattr(self, "distance_label", None)
        distance_edit = getattr(self, "travel_km_outbound_edit", None)
        if distance_label is not None:
            distance_label.setEnabled(enabled)
        if distance_edit is not None:
            distance_edit.setEnabled(enabled)

    def _sync_interpretation_service_with_case(self) -> None:
        self.service_entity_edit.setText(self.case_entity_edit.text().strip())
        self.service_city_edit.setText(self.case_city_edit.text().strip())

    def _refresh_interpretation_service_mirror_state(self) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        same = self.service_same_check.isChecked()
        if same:
            self._sync_interpretation_service_with_case()
        self.service_entity_edit.setEnabled(not same)
        self.service_city_edit.setEnabled(not same)
        self._refresh_interpretation_service_section_state()

    def _on_interpretation_case_fields_changed(self, *_args: object) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        if self.service_same_check.isChecked():
            self._sync_interpretation_service_with_case()
        self._apply_interpretation_distance_defaults()
        self._refresh_interpretation_service_section_state()

    def _on_interpretation_service_fields_changed(self, *_args: object) -> None:
        self._apply_interpretation_distance_defaults()
        self._refresh_interpretation_service_section_state()

    def _on_interpretation_service_same_toggled(self, *_args: object) -> None:
        self._refresh_interpretation_service_mirror_state()
        self._apply_interpretation_distance_defaults()

    def _on_interpretation_use_service_location_toggled(self, *_args: object) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        self._refresh_interpretation_service_section_state()

    def _on_interpretation_transport_sentence_toggled(self, checked: bool) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        self._refresh_interpretation_transport_sentence_state()
        if checked:
            self._apply_interpretation_distance_defaults()

    def _effective_interpretation_travel_city(self) -> str:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return ""
        service_city = self.service_city_edit.text().strip()
        if service_city:
            return service_city
        if self.service_same_check.isChecked():
            return self.case_city_edit.text().strip()
        return ""

    def _persist_profile_distance(self, profile: UserProfile, city: str, distance_value: float) -> None:
        profile.travel_distances_by_city[city] = float(distance_value)
        self._profile_save_callback(self._profiles, self._primary_profile_id)
        self._profiles, self._primary_profile_id = load_profile_settings()
        self._refresh_profile_selector(str(self.profile_combo.currentData() or "").strip())

    def _set_interpretation_distance_text(
        self,
        value: float | None,
        *,
        city_key: str,
        profile_id: str,
        manual: bool,
    ) -> None:
        self._distance_sync_in_progress = True
        try:
            self.travel_km_outbound_edit.setText("" if value is None else f"{float(value):g}")
        finally:
            self._distance_sync_in_progress = False
        self._distance_value_city_key = city_key
        self._distance_value_profile_id = profile_id
        self._distance_value_is_manual = manual

    def _on_interpretation_distance_edited(self, _text: str) -> None:
        if self._distance_sync_in_progress or self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        profile = self._selected_profile()
        city = self._effective_interpretation_travel_city()
        self._distance_value_city_key = city.casefold() if city else ""
        self._distance_value_profile_id = profile.id if profile is not None else ""
        self._distance_value_is_manual = True

    def _apply_interpretation_distance_defaults(self, *_args: object) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        if not self._interpretation_transport_sentence_enabled():
            return
        profile = self._selected_profile()
        city = self._effective_interpretation_travel_city()
        if profile is None or city == "":
            self._set_interpretation_distance_text(
                None,
                city_key=city.casefold() if city else "",
                profile_id=profile.id if profile is not None else "",
                manual=False,
            )
            return
        city_key = city.casefold()
        profile_id = profile.id
        distance_value = distance_for_city(profile, city)
        if distance_value is None:
            if self._distance_value_city_key != city_key or self._distance_value_profile_id != profile_id:
                self._set_interpretation_distance_text(None, city_key=city_key, profile_id=profile_id, manual=False)
            return
        should_replace = (
            self._distance_value_city_key != city_key
            or self._distance_value_profile_id != profile_id
            or not self.travel_km_outbound_edit.text().strip()
            or not self._distance_value_is_manual
        )
        if should_replace:
            self._set_interpretation_distance_text(distance_value, city_key=city_key, profile_id=profile_id, manual=False)

    def _parse_required_float(self, value: str, label: str) -> float:
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            raise ValueError(f"{label} is required.")
        try:
            numeric = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number.") from exc
        if numeric < 0:
            raise ValueError(f"{label} must be zero or greater.")
        return numeric

    def _resolve_interpretation_distance(self, *, profile: UserProfile, city: str, current_value: str, label: str) -> float:
        cleaned = current_value.strip()
        if cleaned:
            distance_value = self._parse_required_float(cleaned, label)
            known_distance = distance_for_city(profile, city)
            if known_distance is None or abs(float(known_distance) - float(distance_value)) >= 1e-9:
                self._persist_profile_distance(profile, city, float(distance_value))
            return float(distance_value)
        known_distance = distance_for_city(profile, city)
        if known_distance is not None:
            return float(known_distance)
        distance_value, ok = QInputDialog.getDouble(
            self,
            "Interpretation distance",
            f"One-way distance from {profile.travel_origin_label} to {city} (km):",
            0.0,
            0.0,
            1_000_000.0,
            2,
        )
        if not ok:
            raise ValueError(f"{label} is required.")
        self._persist_profile_distance(profile, city, float(distance_value))
        return float(distance_value)

    def _on_profile_changed(self, *_args: object) -> None:
        if self._initial_draft.kind == HonorariosKind.INTERPRETATION:
            self._apply_interpretation_distance_defaults()

    def _edit_profiles(self) -> None:
        dialog = QtProfileManagerDialog(
            parent=self,
            settings=load_gui_settings(),
            save_callback=self._profile_save_callback,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._profiles, self._primary_profile_id = load_profile_settings()
        self._refresh_profile_selector(self._primary_profile_id)
        if self._initial_draft.kind == HonorariosKind.INTERPRETATION:
            self._apply_interpretation_distance_defaults()

    def _build_draft(self) -> HonorariosDraft:
        case_number = self.case_number_edit.text().strip()
        case_entity = self.case_entity_edit.text().strip()
        case_city = self.case_city_edit.text().strip()
        if not case_number:
            raise ValueError("Número de processo é obrigatório.")
        if not case_entity:
            raise ValueError("Case Entity is required.")
        if not case_city:
            raise ValueError("Case City is required.")
        selected_profile = self._selected_profile()
        if selected_profile is None:
            raise ValueError("At least one profile is required to generate honorários.")
        missing_message = _profile_missing_fields_message(selected_profile)
        if missing_message:
            raise ValueError(
                f"Selected profile is missing required fields: {missing_message}. Use 'Edit Profiles...' first."
            )
        if self._initial_draft.kind == HonorariosKind.INTERPRETATION:
            include_transport_sentence = self.include_transport_sentence_check.isChecked()
            if include_transport_sentence and not selected_profile.travel_origin_label.strip():
                raise ValueError(
                    "Selected profile is missing an interpretation travel origin label. Use 'Edit Profiles...' first."
                )
            service_date = self.service_date_edit.text().strip()
            if not service_date:
                raise ValueError("Service date is required.")
            service_entity = self.service_entity_edit.text().strip()
            service_city = self.service_city_edit.text().strip()
            use_service_location = self.use_service_location_check.isChecked()
            service_entity_is_law_enforcement = service_entity.casefold() in {"gnr", "psp"}
            if not service_city:
                raise ValueError("Service city is required.")
            if service_entity_is_law_enforcement and (not use_service_location or not service_city):
                raise ValueError("GNR/PSP interpretation rows require a confirmed service city in the honorários text.")
            one_way_distance = self._initial_draft.travel_km_outbound
            if one_way_distance <= 0 and self._initial_draft.travel_km_return > 0:
                one_way_distance = self._initial_draft.travel_km_return
            if include_transport_sentence:
                effective_travel_city = service_city
                if not effective_travel_city:
                    raise ValueError("Service city is required to resolve travel distance.")
                one_way_distance = self._resolve_interpretation_distance(
                    profile=selected_profile,
                    city=effective_travel_city,
                    current_value=self.travel_km_outbound_edit.text(),
                    label="KM (one way)",
                )
                self._set_interpretation_distance_text(
                    one_way_distance,
                    city_key=effective_travel_city.casefold(),
                    profile_id=selected_profile.id,
                    manual=False,
                )
            else:
                try:
                    current_distance = _parse_joblog_optional_float(
                        self.travel_km_outbound_edit.text(),
                        "KM (one way)",
                    )
                except ValueError:
                    current_distance = None
                if current_distance is not None:
                    one_way_distance = current_distance
            recipient_block = self.recipient_block_edit.toPlainText().strip() or self._default_interpretation_recipient_block()
            self._set_recipient_block_text(recipient_block)
            return build_interpretation_honorarios_draft(
                case_number=case_number,
                case_entity=case_entity,
                case_city=case_city,
                service_date=service_date,
                service_entity=service_entity,
                service_city=service_city,
                use_service_location_in_honorarios=use_service_location,
                include_transport_sentence_in_honorarios=include_transport_sentence,
                travel_km_outbound=one_way_distance,
                travel_km_return=one_way_distance,
                recipient_block=recipient_block,
                profile=selected_profile,
            )
        try:
            word_count = int(self.word_count_edit.text().strip())
        except ValueError as exc:
            raise ValueError("Número de palavras must be an integer.") from exc
        if word_count <= 0:
            raise ValueError("Número de palavras must be greater than zero.")
        return build_honorarios_draft(
            case_number=case_number,
            word_count=word_count,
            case_entity=case_entity,
            case_city=case_city,
            profile=selected_profile,
        )

    def _reveal_interpretation_sections_for_error(self, message: str) -> None:
        if self._initial_draft.kind != HonorariosKind.INTERPRETATION:
            return
        lowered = message.casefold()
        if any(token in lowered for token in ("service", "location", "gnr", "psp")):
            self._refresh_interpretation_service_section_state(force_expand=True)
        if any(token in lowered for token in ("transport", "distance", "km")):
            self.text_group.set_expanded(True)
        if "recipient" in lowered:
            self._refresh_recipient_section_state(force_expand=True)

    def _generate(self) -> None:
        self._reset_pdf_export_state()
        try:
            draft = self._build_draft()
        except ValueError as exc:
            self._reveal_interpretation_sections_for_error(str(exc))
            QMessageBox.critical(self, "Requerimento de Honorários", str(exc))
            return
        self.generated_draft = draft

        default_path = self._default_directory / default_honorarios_filename(draft.case_number, kind=draft.kind)
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Requerimento de Honorários",
            str(default_path),
            "Word Document (*.docx)",
        )
        if not selected:
            return
        requested_path = Path(selected).expanduser().resolve()
        self.requested_path = requested_path
        try:
            saved = generate_honorarios_docx(draft, requested_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Requerimento de Honorários", f"Failed to generate DOCX:\n{exc}")
            return
        self.docx_saved_path = saved
        self.saved_path = saved
        self.auto_renamed = saved != requested_path
        pdf_path = saved.with_suffix(".pdf")
        self._set_pdf_export_busy(
            True,
            status_text="DOCX saved. Generating the sibling PDF in the background...",
        )
        self._begin_pdf_export(docx_path=saved, pdf_path=pdf_path)

    def reject(self) -> None:  # type: ignore[override]
        if self._pdf_export_in_flight:
            self.export_status_label.setVisible(True)
            self.export_status_label.setText("PDF generation is still running. Please wait.")
            return
        super().reject()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._pdf_export_in_flight:
            self.export_status_label.setVisible(True)
            self.export_status_label.setText("PDF generation is still running. Please wait.")
            event.ignore()
            return
        super().closeEvent(event)


class QtArabicDocxReviewDialog(QDialog):
    """Arabic-only Word handoff gate before the app continues."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        docx_path: Path,
        is_gmail_batch: bool,
        attachment_label: str | None = None,
        poll_interval_ms: int = 500,
        quiet_period_ms: int = 1500,
        auto_open: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Arabic DOCX review")
        self.setMinimumSize(620, 240)
        self._docx_path = docx_path.expanduser().resolve()
        self._is_gmail_batch = bool(is_gmail_batch)
        self._attachment_label = (attachment_label or "").strip()
        self._poll_interval_ms = max(100, int(poll_interval_ms))
        self._quiet_period_ms = max(self._poll_interval_ms, int(quiet_period_ms))
        self._auto_open = bool(auto_open)
        self._baseline_fingerprint = self._read_fingerprint()
        self._last_seen_fingerprint = self._baseline_fingerprint
        self._save_change_detected = False
        self._last_change_monotonic: float | None = None
        self._opened_once = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._poll_interval_ms)
        self._poll_timer.timeout.connect(self._poll_for_save)
        self._build_ui()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(760, 260),
        )
        QTimer.singleShot(0, self._start_review)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        if self._is_gmail_batch and self._attachment_label:
            header = (
                "Arabic Gmail batch item ready. Review the DOCX in Word, then save it to continue "
                "this batch item automatically."
            )
        else:
            header = (
                "Arabic translation complete. Review the DOCX in Word, then save it to continue "
                "to Save to Job Log."
            )
        if self._attachment_label:
            header += f"\n\nAttachment: {self._attachment_label}"

        self.info_label = QLabel(header)
        self.info_label.setWordWrap(True)
        root.addWidget(self.info_label)

        self.path_label = QLabel(str(self._docx_path))
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setWordWrap(True)
        root.addWidget(self.path_label)

        self.status_label = QLabel(
            "The DOCX will open in Word. Save after editing and the app will continue automatically."
        )
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.align_right_btn = QPushButton("Align Right + Save")
        self.open_word_btn = QPushButton("Open in Word")
        self.continue_without_changes_btn = QPushButton("Continue without changes")
        self.continue_now_btn = QPushButton("Continue now")
        self.cancel_btn = QPushButton("Cancel")
        actions.addWidget(self.align_right_btn)
        actions.addWidget(self.open_word_btn)
        actions.addStretch(1)
        actions.addWidget(self.continue_without_changes_btn)
        actions.addWidget(self.continue_now_btn)
        actions.addWidget(self.cancel_btn)
        root.addLayout(actions)

        self.align_right_btn.clicked.connect(self._align_right_and_save)
        self.open_word_btn.clicked.connect(lambda: self._open_in_word(initial=False))
        self.continue_without_changes_btn.clicked.connect(self.accept)
        self.continue_now_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def done(self, result: int) -> None:
        self._poll_timer.stop()
        super().done(result)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _read_fingerprint(self) -> tuple[int, int] | None:
        try:
            stat = self._docx_path.stat()
        except OSError:
            return None
        return (int(stat.st_mtime_ns), int(stat.st_size))

    def _apply_open_result(self, result: WordAutomationResult, *, initial: bool) -> None:
        if result.ok:
            if initial:
                self._set_status(
                    "DOCX opened in Word. Save after editing and the app will continue automatically."
                )
            else:
                self._set_status("DOCX reopened in Word. Save after editing to continue automatically.")
            return
        fallback_message = result.message.strip() or "Word automation failed."
        if os.name == "nt":
            try:
                os.startfile(str(self._docx_path))  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                self._set_status(
                    f"{fallback_message}\n\nUse 'Continue now' after saving manually if detection misses."
                )
                if not initial:
                    QMessageBox.warning(self, "Arabic review", fallback_message)
                return
            self._set_status(
                "Word automation failed, but the DOCX was opened with the default Windows handler. "
                "Save after editing and the app will continue automatically."
            )
            if not initial:
                QMessageBox.warning(
                    self,
                    "Arabic review",
                    f"{fallback_message}\n\nOpened with the default Windows handler instead.",
                )
            return
        self._set_status(
            f"{fallback_message}\n\nUse 'Continue now' after saving manually if detection misses."
        )
        if not initial:
            QMessageBox.warning(self, "Arabic review", fallback_message)

    def _start_review(self) -> None:
        if self._auto_open and not self._opened_once:
            self._opened_once = True
            self._open_in_word(initial=True)
        self._poll_timer.start()

    def _open_in_word(self, *, initial: bool) -> None:
        self._apply_open_result(open_docx_in_word(self._docx_path), initial=initial)

    def _align_right_and_save(self) -> None:
        result = align_right_and_save_docx_in_word(self._docx_path)
        if result.ok:
            self._set_status("DOCX aligned right and saved in Word. Continuing now.")
            self.accept()
            return
        self._set_status(
            f"{result.message}\n\nYou can keep editing manually in Word and save, or use Continue now."
        )
        QMessageBox.warning(self, "Arabic review", result.message)

    def _poll_for_save(self) -> None:
        current = self._read_fingerprint()
        if current is None:
            return
        if self._baseline_fingerprint is None:
            self._baseline_fingerprint = current
            self._last_seen_fingerprint = current
            return
        if current != self._last_seen_fingerprint:
            self._last_seen_fingerprint = current
            if current != self._baseline_fingerprint or self._save_change_detected:
                self._save_change_detected = True
                self._last_change_monotonic = time.monotonic()
                self._set_status("Save detected. Waiting for Word to finish writing...")
                return
        if self._save_change_detected and self._last_change_monotonic is not None:
            elapsed_ms = (time.monotonic() - self._last_change_monotonic) * 1000.0
            if elapsed_ms >= float(self._quiet_period_ms):
                self._set_status("Save complete. Continuing now.")
                self.accept()


class QtSaveToJobLogDialog(QDialog):
    """Qt equivalent of save-to-joblog flow."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        db_path: Path,
        seed: JobLogSeed,
        on_saved: Callable[[], None] | None = None,
        allow_honorarios_export: bool = True,
        edit_row_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._edit_row_id = int(edit_row_id) if edit_row_id is not None else None
        self.setWindowTitle("Edit Job Log Entry" if self._edit_row_id is not None else "Save to Job Log")
        self.setMinimumSize(620, 460)

        self._db_path = db_path
        self._seed = seed
        self._on_saved = on_saved
        self._allow_honorarios_export = bool(allow_honorarios_export)
        self._saved = False
        self._saved_result: JobLogSavedResult | None = None
        self._settings = load_joblog_settings()
        self._gui_settings = load_gui_settings()
        self._metadata_config: MetadataAutofillConfig = metadata_config_from_settings(self._settings)
        self._case_entity_user_set = False
        self._case_city_user_set = False
        self._distance_prompted_cities: set[str] = set()
        self._distance_sync_in_progress = False
        self._distance_value_city_key = ""
        self._distance_value_is_manual = False
        self._service_section_sync_in_progress = False
        self._service_section_user_overridden = False

        self._build_ui()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(980, 660),
        )
        self._refresh_service_mirror_state()
        self._refresh_photo_controls()

    @property
    def saved(self) -> bool:
        return self._saved

    @property
    def saved_result(self) -> JobLogSavedResult | None:
        return self._saved_result

    def _field_label(self, text: str) -> QLabel:
        return QLabel(text, objectName="FieldLabel")

    def _normalized_combo_values(self, values: list[str], current: str) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            if cleaned and cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)
        current_cleaned = current.strip()
        if current_cleaned and current_cleaned not in seen:
            normalized.append(current_cleaned)
        return normalized

    def _fill_combo(self, combo: QComboBox, values: list[str]) -> None:
        current = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(self._normalized_combo_values(values, current))
        if current:
            index = combo.findText(current)
            if index >= 0:
                combo.setCurrentIndex(index)
            elif combo.isEditable():
                combo.setCurrentText(current)
        else:
            combo.setCurrentIndex(-1)
        combo.blockSignals(False)

    def _selection_combo(self, values: list[str], current: str) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        combo.setEditable(False)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        combo.addItems(self._normalized_combo_values(values, current))
        if current.strip():
            combo.setCurrentText(current.strip())
        else:
            combo.setCurrentIndex(-1)
        return combo

    def _editable_vocab_combo(self, values: list[str], current: str) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.addItems(self._normalized_combo_values(values, current))
        combo.setCurrentText(current.strip())
        return combo

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.form_scroll_area = QScrollArea(self)
        self.form_scroll_area.setObjectName("DialogScrollArea")
        self.form_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.form_scroll_area.setWidgetResizable(True)
        self.form_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget(self.form_scroll_area)
        scroll_content.setObjectName("DialogScrollContent")
        scroll_root = QVBoxLayout(scroll_content)
        scroll_root.setContentsMargins(0, 0, 0, 0)
        scroll_root.setSpacing(10)

        top = QFrame(scroll_content)
        top.setObjectName("ShellPanel")
        top_grid = QGridLayout(top)
        top_grid.setContentsMargins(16, 16, 16, 16)
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(10)
        top_grid.addWidget(self._field_label("Job type"), 0, 0)
        self.job_type_combo = self._selection_combo(
            list(self._settings["vocab_job_types"]),
            self._seed.job_type or "Translation",
        )
        top_grid.addWidget(self.job_type_combo, 0, 1)
        self.primary_date_label = self._field_label("Translation date")
        top_grid.addWidget(self.primary_date_label, 0, 2)
        self.translation_date_edit = GuardedDateEdit(
            self._seed.service_date if _is_interpretation_job_type(self._seed.job_type) else self._seed.translation_date
        )
        self.translation_date_edit.setPlaceholderText("YYYY-MM-DD")
        top_grid.addWidget(self.translation_date_edit, 0, 3)
        self.lang_label = self._field_label("Lang")
        top_grid.addWidget(self.lang_label, 1, 0)
        supported_langs = [str(lang).strip().upper() for lang in supported_target_langs()]
        self.lang_edit = self._selection_combo(supported_langs, self._seed.lang)
        top_grid.addWidget(self.lang_edit, 1, 1)
        self.pages_label = self._field_label("Pages")
        top_grid.addWidget(self.pages_label, 1, 2)
        self.pages_edit = QLineEdit(str(int(self._seed.pages)))
        self.pages_edit.setReadOnly(True)
        top_grid.addWidget(self.pages_edit, 1, 3)
        self.words_label = self._field_label("Words")
        top_grid.addWidget(self.words_label, 1, 4)
        self.word_count_edit = QLineEdit(str(int(self._seed.word_count)))
        top_grid.addWidget(self.word_count_edit, 1, 5)
        top_grid.setColumnStretch(1, 1)
        top_grid.setColumnStretch(3, 1)
        top_grid.setColumnStretch(5, 1)
        scroll_root.addWidget(top)

        case_group = QGroupBox("CASE (belongs to)", scroll_content)
        case_form = QGridLayout(case_group)
        case_form.setContentsMargins(12, 12, 12, 12)
        case_form.setHorizontalSpacing(10)
        case_form.setVerticalSpacing(10)
        case_form.addWidget(self._field_label("Case entity"), 0, 0)
        self.case_entity_combo = self._selection_combo(
            list(self._settings["vocab_case_entities"]),
            self._seed.case_entity,
        )
        case_form.addWidget(self.case_entity_combo, 0, 1)
        self.add_case_entity_btn = build_compact_add_button(
            tooltip="Add case entity",
            accessible_name="Add case entity",
            parent=case_group,
        )
        case_form.addWidget(self.add_case_entity_btn, 0, 2)

        case_form.addWidget(self._field_label("Case city"), 0, 3)
        self.case_city_combo = self._selection_combo(
            list(self._settings["vocab_cities"]),
            self._seed.case_city,
        )
        case_form.addWidget(self.case_city_combo, 0, 4)
        self.add_case_city_btn = build_compact_add_button(
            tooltip="Add case city",
            accessible_name="Add case city",
            parent=case_group,
        )
        case_form.addWidget(self.add_case_city_btn, 0, 5)

        case_form.addWidget(self._field_label("Case number"), 1, 0)
        self.case_number_edit = QLineEdit(self._seed.case_number)
        case_form.addWidget(self.case_number_edit, 1, 1, 1, 2)
        case_form.addWidget(self._field_label("Court Email"), 1, 3)
        self.court_email_combo = self._editable_vocab_combo(
            list(self._settings["vocab_court_emails"]),
            self._seed.court_email,
        )
        case_form.addWidget(self.court_email_combo, 1, 4, 1, 2)
        case_form.setColumnStretch(1, 1)
        case_form.setColumnStretch(4, 1)
        scroll_root.addWidget(case_group)

        service_group = DeclutterSection(
            "SERVICE",
            expanded=True,
            parent=scroll_content,
        )
        self.service_group = service_group
        self.service_group_help_btn = build_inline_info_button(
            tooltip=(
                "Expand this section when the service location differs from the case "
                "or when you want the service location mentioned in the honorários text."
            ),
            accessible_name="Service section help",
            parent=service_group,
        )
        service_group.add_header_widget(self.service_group_help_btn)
        service_content = QWidget(service_group)
        service_grid = QGridLayout(service_content)
        service_grid.setContentsMargins(0, 0, 0, 0)
        service_grid.setHorizontalSpacing(10)
        service_grid.setVerticalSpacing(10)
        self.service_same_check = QCheckBox("Service same as Case")
        has_seed_service_values = any(
            (
                self._seed.case_entity.strip(),
                self._seed.case_city.strip(),
                self._seed.service_entity.strip(),
                self._seed.service_city.strip(),
            )
        )
        if has_seed_service_values:
            self.service_same_check.setChecked(
                self._seed.case_entity.strip() == self._seed.service_entity.strip()
                and self._seed.case_city.strip() == self._seed.service_city.strip()
            )
        else:
            self.service_same_check.setChecked(
                True if _is_interpretation_job_type(self._seed.job_type) else bool(self._settings["service_equals_case_by_default"])
            )
        service_grid.addWidget(self.service_same_check, 0, 0, 1, 2)

        service_grid.addWidget(self._field_label("Service entity"), 1, 0)
        self.service_entity_combo = self._selection_combo(
            list(self._settings["vocab_service_entities"]),
            self._seed.service_entity,
        )
        service_grid.addWidget(self.service_entity_combo, 1, 1)
        self.add_service_entity_btn = build_compact_add_button(
            tooltip="Add service entity",
            accessible_name="Add service entity",
            parent=service_content,
        )
        service_grid.addWidget(self.add_service_entity_btn, 1, 2)

        service_grid.addWidget(self._field_label("Service city"), 1, 3)
        self.service_city_combo = self._selection_combo(
            list(self._settings["vocab_cities"]),
            self._seed.service_city,
        )
        service_grid.addWidget(self.service_city_combo, 1, 4)
        self.add_service_city_btn = build_compact_add_button(
            tooltip="Add service city",
            accessible_name="Add service city",
            parent=service_content,
        )
        service_grid.addWidget(self.add_service_city_btn, 1, 5)

        self.service_date_label = self._field_label("Service date (YYYY-MM-DD)")
        service_grid.addWidget(self.service_date_label, 2, 0)
        self.service_date_edit = GuardedDateEdit(self._seed.service_date)
        self.service_date_edit.setPlaceholderText("YYYY-MM-DD")
        service_grid.addWidget(self.service_date_edit, 2, 1)
        service_grid.setColumnStretch(1, 1)
        service_grid.setColumnStretch(4, 1)
        service_group.set_content_widget(service_content)
        scroll_root.addWidget(service_group)

        interpretation_group = DeclutterSection("INTERPRETATION", expanded=True, parent=scroll_content)
        interpretation_content = QWidget(interpretation_group)
        interpretation_grid = QGridLayout(interpretation_content)
        interpretation_grid.setContentsMargins(0, 0, 0, 0)
        interpretation_grid.setHorizontalSpacing(10)
        interpretation_grid.setVerticalSpacing(10)
        self.use_service_location_check = QCheckBox("Mention service location in text")
        self.use_service_location_check.setChecked(bool(self._seed.use_service_location_in_honorarios))
        interpretation_grid.addWidget(self.use_service_location_check, 0, 0, 1, 2)
        self.include_transport_sentence_check = QCheckBox(
            "Include transport sentence"
        )
        self.include_transport_sentence_check.setChecked(bool(self._seed.include_transport_sentence_in_honorarios))
        interpretation_grid.addWidget(self.include_transport_sentence_check, 1, 0, 1, 2)
        self.distance_label = QLabel("KM (one way)")
        interpretation_grid.addWidget(self.distance_label, 2, 0)
        distance_value = self._seed.travel_km_outbound
        if distance_value is None:
            distance_value = self._seed.travel_km_return
        self.travel_km_outbound_edit = QLineEdit(
            "" if distance_value is None else f"{float(distance_value):g}"
        )
        interpretation_grid.addWidget(self.travel_km_outbound_edit, 2, 1)
        self.travel_km_return_edit = self.travel_km_outbound_edit
        self.interpretation_hint_label = QLabel("Distance saved by city.")
        self.interpretation_hint_info_btn = build_inline_info_button(
            tooltip="Saved per service city and reused automatically for future interpretation rows.",
            accessible_name="Distance reuse help",
            parent=interpretation_content,
        )
        interpretation_hint_row = QHBoxLayout()
        interpretation_hint_row.setContentsMargins(0, 0, 0, 0)
        interpretation_hint_row.setSpacing(6)
        interpretation_hint_row.addWidget(self.interpretation_hint_label, 0, Qt.AlignmentFlag.AlignVCenter)
        interpretation_hint_row.addWidget(self.interpretation_hint_info_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        interpretation_hint_row.addStretch(1)
        interpretation_grid.addLayout(interpretation_hint_row, 3, 0, 1, 2)
        interpretation_grid.setColumnStretch(1, 1)
        self.interpretation_group_help_btn = build_inline_info_button(
            tooltip="Keep transport details compact; the saved distance is reused for future interpretation rows.",
            accessible_name="Interpretation section help",
            parent=interpretation_group,
        )
        interpretation_group.add_header_widget(self.interpretation_group_help_btn)
        interpretation_group.set_content_widget(interpretation_content)
        self.interpretation_group = interpretation_group
        scroll_root.addWidget(interpretation_group)

        autofill_row = QHBoxLayout()
        self.autofill_header_btn = QPushButton("Autofill from PDF header")
        self.autofill_header_btn.setEnabled(self._can_autofill_from_pdf_header())
        self.autofill_photo_btn = QPushButton("Autofill from photo...")
        self.photo_translation_check = QCheckBox("Usually for Interpretation; enable anyway")
        self.photo_hint = QLabel("")
        autofill_row.addWidget(self.autofill_header_btn)
        autofill_row.addWidget(self.autofill_photo_btn)
        autofill_row.addWidget(self.photo_translation_check)
        autofill_row.addStretch(1)
        autofill_row.addWidget(self.photo_hint)
        scroll_root.addLayout(autofill_row)

        metrics_panel = QFrame(scroll_content)
        metrics_panel.setObjectName("ShellPanel")
        metrics_form = QGridLayout(metrics_panel)
        metrics_form.setContentsMargins(12, 12, 12, 12)
        metrics_form.addWidget(self._field_label("Run ID"), 0, 0)
        self.run_id_edit = QLineEdit(self._seed.run_id)
        metrics_form.addWidget(self.run_id_edit, 0, 1)
        metrics_form.addWidget(self._field_label("Target lang"), 0, 2)
        self.target_lang_edit = QLineEdit(self._seed.target_lang)
        metrics_form.addWidget(self.target_lang_edit, 0, 3)
        metrics_form.addWidget(self._field_label("Total tokens"), 1, 0)
        self.total_tokens_edit = QLineEdit(
            "" if self._seed.total_tokens is None else str(int(self._seed.total_tokens))
        )
        metrics_form.addWidget(self.total_tokens_edit, 1, 1)
        metrics_form.addWidget(self._field_label("Est. API cost"), 1, 2)
        self.estimated_api_cost_edit = QLineEdit(
            "" if self._seed.estimated_api_cost is None else f"{float(self._seed.estimated_api_cost):.2f}"
        )
        metrics_form.addWidget(self.estimated_api_cost_edit, 1, 3)
        metrics_form.addWidget(self._field_label("Quality risk score"), 2, 0)
        self.quality_risk_score_edit = QLineEdit(
            "" if self._seed.quality_risk_score is None else f"{float(self._seed.quality_risk_score):.4f}"
        )
        metrics_form.addWidget(self.quality_risk_score_edit, 2, 1)
        metrics_form.setColumnStretch(1, 1)
        metrics_form.setColumnStretch(3, 1)
        self.metrics_section = CollapsibleSection("Run Metrics (auto-filled)", expanded=False, parent=scroll_content)
        self.metrics_section.set_content_widget(metrics_panel)
        scroll_root.addWidget(self.metrics_section)

        finance_panel = QFrame(scroll_content)
        finance_panel.setObjectName("ShellPanel")
        finance_form = QGridLayout(finance_panel)
        finance_form.setContentsMargins(12, 12, 12, 12)
        finance_form.addWidget(self._field_label("Rate/word"), 0, 0)
        self.rate_edit = QLineEdit(f"{self._seed.rate_per_word:.4f}")
        finance_form.addWidget(self.rate_edit, 0, 1)
        finance_form.addWidget(self._field_label("Expected total"), 0, 2)
        self.expected_total_edit = QLineEdit(f"{self._seed.expected_total:.2f}")
        finance_form.addWidget(self.expected_total_edit, 0, 3)
        finance_form.addWidget(self._field_label("Amount paid"), 1, 0)
        self.amount_paid_edit = QLineEdit(f"{self._seed.amount_paid:.2f}")
        finance_form.addWidget(self.amount_paid_edit, 1, 1)
        finance_form.addWidget(self._field_label("API cost"), 1, 2)
        self.api_cost_edit = QLineEdit(f"{self._seed.api_cost:.2f}")
        finance_form.addWidget(self.api_cost_edit, 1, 3)
        finance_form.addWidget(self._field_label("Profit"), 2, 0)
        self.profit_edit = QLineEdit(f"{self._seed.profit:.2f}")
        finance_form.addWidget(self.profit_edit, 2, 1)
        finance_form.setColumnStretch(1, 1)
        finance_form.setColumnStretch(3, 1)
        self.finance_section = CollapsibleSection("Amounts (EUR)", expanded=False, parent=scroll_content)
        self.finance_section.set_content_widget(finance_panel)
        scroll_root.addWidget(self.finance_section)
        scroll_root.addStretch(1)

        self.form_scroll_area.setWidget(scroll_content)
        root.addWidget(self.form_scroll_area, 1)

        self.action_bar = QWidget(self)
        self.action_bar.setObjectName("DialogActionBar")
        actions = QHBoxLayout(self.action_bar)
        actions.setContentsMargins(10, 8, 10, 8)
        actions.setSpacing(10)
        self.open_translation_btn = QPushButton("Open translated DOCX")
        self.open_translation_btn.setEnabled(self._current_translation_docx_path() is not None)
        actions.addWidget(self.open_translation_btn)
        self.honorarios_btn = QPushButton("Gerar Requerimento de Honorários...")
        self.honorarios_btn.setEnabled(self._allow_honorarios_export)
        actions.addWidget(self.honorarios_btn)
        actions.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Update" if self._edit_row_id is not None else "Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setDefault(False)
        self.save_btn.setAutoDefault(False)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.save_btn)
        root.addWidget(self.action_bar)

        self.open_translation_btn.clicked.connect(self._open_translation_docx)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._save)
        self._save_return_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self._save_enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        for shortcut in (self._save_return_shortcut, self._save_enter_shortcut):
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self._trigger_save_shortcut)
        self.honorarios_btn.clicked.connect(self._open_honorarios_dialog)
        self.job_type_combo.currentTextChanged.connect(self._refresh_photo_controls)
        self.job_type_combo.currentTextChanged.connect(self._refresh_interpretation_mode_state)
        self.photo_translation_check.toggled.connect(self._refresh_photo_controls)
        self.case_entity_combo.currentTextChanged.connect(self._on_case_fields_changed)
        self.case_city_combo.currentTextChanged.connect(self._on_case_fields_changed)
        self.service_entity_combo.currentTextChanged.connect(self._on_service_fields_changed)
        self.service_city_combo.currentTextChanged.connect(self._on_service_fields_changed)
        self.translation_date_edit.textChanged.connect(self._on_primary_date_changed)
        self.service_same_check.toggled.connect(self._on_service_same_toggled)
        self.service_group.toggle_button.toggled.connect(self._on_service_section_toggled)
        self.use_service_location_check.toggled.connect(self._on_use_service_location_toggled)
        self.include_transport_sentence_check.toggled.connect(self._on_interpretation_transport_sentence_toggled)
        self.autofill_header_btn.clicked.connect(self._autofill_from_pdf_header)
        self.autofill_photo_btn.clicked.connect(self._autofill_from_photo)
        self.travel_km_outbound_edit.textChanged.connect(lambda _text: self._refresh_interpretation_transport_sentence_state())
        self.travel_km_outbound_edit.textEdited.connect(self._on_interpretation_distance_edited)
        self.add_case_entity_btn.clicked.connect(lambda: self._add_value("Case entity", "vocab_case_entities", self.case_entity_combo))
        self.add_service_entity_btn.clicked.connect(lambda: self._add_value("Service entity", "vocab_service_entities", self.service_entity_combo))
        self.add_case_city_btn.clicked.connect(lambda: self._add_value("City", "vocab_cities", self.case_city_combo))
        self.add_service_city_btn.clicked.connect(lambda: self._add_value("City", "vocab_cities", self.service_city_combo))
        self._refresh_interpretation_mode_state()

    def _add_value(self, title: str, key: str, combo: QComboBox) -> None:
        value, ok = QInputDialog.getText(self, f"Add {title}", f"{title}:")
        if not ok:
            return
        cleaned = value.strip()
        if cleaned == "":
            return
        self._ensure_in_vocab(key, cleaned)
        combo.setCurrentText(cleaned)

    def _ensure_in_vocab(self, key: str, value: str) -> None:
        _ensure_value_in_joblog_settings(self._settings, key, value)
        self._refresh_vocab_widgets()

    def _refresh_vocab_widgets(self) -> None:
        self._fill_combo(self.case_entity_combo, list(self._settings["vocab_case_entities"]))
        self._fill_combo(self.service_entity_combo, list(self._settings["vocab_service_entities"]))
        self._fill_combo(self.case_city_combo, list(self._settings["vocab_cities"]))
        self._fill_combo(self.service_city_combo, list(self._settings["vocab_cities"]))
        self._fill_combo(self.job_type_combo, list(self._settings["vocab_job_types"]))
        self._fill_combo(self.court_email_combo, list(self._settings["vocab_court_emails"]))

    def _set_court_email_from_context(self, *, exact_email: str | None = None, force: bool = False) -> None:
        if not force and exact_email is None and self.court_email_combo.currentText().strip():
            return
        suggestion = choose_court_email_suggestion(
            exact_email=exact_email,
            case_entity=self.case_entity_combo.currentText().strip(),
            case_city=self.case_city_combo.currentText().strip(),
            vocab_court_emails=list(self._settings["vocab_court_emails"]),
        )
        if suggestion:
            self.court_email_combo.setCurrentText(suggestion)

    def _set_service_section_expanded(self, expanded: bool) -> None:
        desired = bool(expanded)
        if self.service_group.is_expanded() == desired:
            return
        self._service_section_sync_in_progress = True
        try:
            self.service_group.set_expanded(desired)
        finally:
            self._service_section_sync_in_progress = False

    def _on_service_section_toggled(self, _checked: bool) -> None:
        if self._service_section_sync_in_progress:
            return
        self._service_section_user_overridden = True
        self.service_group.set_attention_state(False)

    def _service_section_should_expand(self) -> bool:
        return self.use_service_location_check.isChecked() or not self.service_same_check.isChecked()

    def _service_section_summary_text(self) -> str:
        if not _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            return ""
        if self.use_service_location_check.isChecked():
            service_city = self.service_city_combo.currentText().strip()
            if service_city:
                return f"Location: {service_city}"
            return "Location in text"
        if self.service_same_check.isChecked():
            return "Same as case"
        service_city = self.service_city_combo.currentText().strip()
        if service_city:
            return service_city
        service_entity = self.service_entity_combo.currentText().strip()
        if service_entity:
            return service_entity
        return "Custom service"

    def _refresh_service_section_state(self) -> None:
        self.service_group.set_summary_text(self._service_section_summary_text())
        self.service_group.set_attention_state(False)
        should_expand = self._service_section_should_expand()
        if should_expand:
            self._set_service_section_expanded(True)
            return
        if not self._service_section_user_overridden:
            self._set_service_section_expanded(False)

    def _on_use_service_location_toggled(self, _checked: bool) -> None:
        self._refresh_service_section_state()

    def _interpretation_section_summary_text(self) -> str:
        if not _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            return ""
        if not self._interpretation_transport_sentence_enabled():
            return "Transport line off"
        distance_text = self.travel_km_outbound_edit.text().strip()
        if distance_text:
            return f"{distance_text} km one way"
        return "Transport line on"

    def _imported_service_differs_from_case(self, *, service_entity: str, service_city: str) -> bool:
        resolved_service_entity = str(service_entity or "").strip()
        resolved_service_city = str(service_city or "").strip()
        case_entity = self.case_entity_combo.currentText().strip()
        case_city = self.case_city_combo.currentText().strip()
        return (
            (resolved_service_entity != "" and resolved_service_entity != case_entity)
            or (resolved_service_city != "" and resolved_service_city != case_city)
        )

    def _apply_imported_service_fields(self, *, service_entity: str, service_city: str) -> None:
        resolved_service_entity = str(service_entity or "").strip()
        resolved_service_city = str(service_city or "").strip()
        if not _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            self._sync_service_with_case()
            return
        distinct_service = self._imported_service_differs_from_case(
            service_entity=resolved_service_entity,
            service_city=resolved_service_city,
        )
        if distinct_service and self.service_same_check.isChecked():
            self.service_same_check.setChecked(False)
        if self.service_same_check.isChecked():
            self._sync_service_with_case()
            return
        if resolved_service_entity:
            self._ensure_in_vocab("vocab_service_entities", resolved_service_entity)
            self.service_entity_combo.setCurrentText(resolved_service_entity)
        if resolved_service_city:
            self._ensure_in_vocab("vocab_cities", resolved_service_city)
            self.service_city_combo.setCurrentText(resolved_service_city)
        if distinct_service:
            self._refresh_service_section_state()

    def _reveal_validation_context(self, message: str) -> None:
        normalized = message.casefold()
        target_widget: QWidget | None = None
        if "service" in normalized:
            self._set_service_section_expanded(True)
            self.service_group.set_attention_state(True)
            target_widget = self.service_group
        if "km" in normalized or "distance" in normalized or "transport" in normalized:
            self.interpretation_group.set_expanded(True)
            self.interpretation_group.set_attention_state(True)
            target_widget = self.interpretation_group
        if target_widget is not None:
            self.form_scroll_area.ensureWidgetVisible(target_widget, 0, 24)

    def _on_case_fields_changed(self) -> None:
        self._case_entity_user_set = True
        self._case_city_user_set = True
        if self.service_same_check.isChecked():
            self._sync_service_with_case()
        self._set_court_email_from_context()
        self._apply_interpretation_distance_defaults(prompt_if_missing=False)
        self._refresh_service_section_state()

    def _on_service_fields_changed(self) -> None:
        self._apply_non_court_default_rule()
        self._apply_interpretation_distance_defaults(prompt_if_missing=True)
        self._refresh_service_section_state()

    def _on_service_same_toggled(self) -> None:
        self._refresh_service_mirror_state()
        self._settings["service_equals_case_by_default"] = bool(self.service_same_check.isChecked())
        self._apply_interpretation_distance_defaults(prompt_if_missing=False)

    def _sync_service_with_case(self) -> None:
        self.service_entity_combo.setCurrentText(self.case_entity_combo.currentText().strip())
        self.service_city_combo.setCurrentText(self.case_city_combo.currentText().strip())

    def _refresh_service_mirror_state(self) -> None:
        same = self.service_same_check.isChecked()
        if same:
            self._sync_service_with_case()
        self.service_entity_combo.setEnabled(not same)
        self.service_city_combo.setEnabled(not same)
        self.add_service_entity_btn.setEnabled(not same)
        self.add_service_city_btn.setEnabled(not same)
        self._refresh_service_section_state()

    def _refresh_photo_controls(self) -> None:
        photo_enabled = bool(self._settings["metadata_photo_enabled"])
        job_type = self.job_type_combo.currentText().strip()
        if not photo_enabled:
            self.autofill_photo_btn.setEnabled(False)
            self.photo_translation_check.setEnabled(False)
            self.photo_translation_check.setVisible(True)
            self.photo_hint.setText("Photo metadata disabled in settings.")
            return
        if job_type == "Interpretation":
            self.autofill_photo_btn.setEnabled(True)
            self.photo_translation_check.setEnabled(False)
            self.photo_translation_check.setVisible(False)
            self.photo_hint.setText("Photo autofill ready.")
            return
        self.photo_translation_check.setText("Enable photo autofill")
        self.photo_translation_check.setVisible(True)
        self.photo_translation_check.setEnabled(True)
        enabled = self.photo_translation_check.isChecked()
        self.autofill_photo_btn.setEnabled(enabled)
        self.photo_hint.setText("Enable photo autofill for this row.")

    def _refresh_interpretation_mode_state(self) -> None:
        is_interpretation = _is_interpretation_job_type(self.job_type_combo.currentText().strip())
        self.interpretation_group.setVisible(is_interpretation)
        self.service_group.setVisible(is_interpretation)
        self.primary_date_label.setText("Service date" if is_interpretation else "Translation date")
        self.lang_label.setVisible(not is_interpretation)
        self.lang_edit.setVisible(not is_interpretation)
        self.pages_label.setVisible(not is_interpretation)
        self.pages_edit.setVisible(not is_interpretation)
        self.words_label.setVisible(not is_interpretation)
        self.word_count_edit.setVisible(not is_interpretation)
        self.metrics_section.setVisible(not is_interpretation)
        self.finance_section.setVisible(not is_interpretation)
        self.service_date_label.setVisible(not is_interpretation)
        self.service_date_edit.setVisible(not is_interpretation)
        self.word_count_edit.setPlaceholderText("Not used" if is_interpretation else "")
        self.rate_edit.setPlaceholderText("Not used" if is_interpretation else "")
        self.expected_total_edit.setPlaceholderText("Not used" if is_interpretation else "")
        if is_interpretation and not any(
            (
                self.service_entity_combo.currentText().strip(),
                self.service_city_combo.currentText().strip(),
            )
        ):
            self.service_same_check.setChecked(True)
        self._refresh_service_mirror_state()
        if is_interpretation:
            self.service_date_edit.setText(self.translation_date_edit.text().strip())
            self._refresh_interpretation_transport_sentence_state()
        self._apply_interpretation_distance_defaults(prompt_if_missing=False)

    def _interpretation_transport_sentence_enabled(self) -> bool:
        checkbox = getattr(self, "include_transport_sentence_check", None)
        if checkbox is None:
            return True
        return checkbox.isChecked()

    def _refresh_interpretation_transport_sentence_state(self) -> None:
        enabled = self._interpretation_transport_sentence_enabled()
        distance_label = getattr(self, "distance_label", None)
        distance_edit = getattr(self, "travel_km_outbound_edit", None)
        hint_label = getattr(self, "interpretation_hint_label", None)
        if distance_label is not None:
            distance_label.setEnabled(enabled)
        if distance_edit is not None:
            distance_edit.setEnabled(enabled)
        if hint_label is not None:
            hint_label.setEnabled(enabled)
        self.interpretation_group.set_summary_text(self._interpretation_section_summary_text())
        self.interpretation_group.set_attention_state(False)

    def _on_interpretation_transport_sentence_toggled(self, checked: bool) -> None:
        self._refresh_interpretation_transport_sentence_state()
        if checked:
            self._apply_interpretation_distance_defaults(prompt_if_missing=False)

    def _trigger_save_shortcut(self) -> None:
        popup = QApplication.activePopupWidget()
        if popup is not None and popup is not self:
            return
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, QPlainTextEdit):
            return
        if self.save_btn.isEnabled():
            self._save()

    def _can_autofill_from_pdf_header(self) -> bool:
        if self._seed.pdf_path is None:
            return True
        return self._seed.pdf_path.expanduser().resolve().exists()

    def _current_word_count_value(self) -> int:
        try:
            return _parse_joblog_required_int(self.word_count_edit.text(), "Words")
        except ValueError:
            return int(self._seed.word_count)

    def _build_honorarios_draft(self) -> HonorariosDraft:
        case_number = self.case_number_edit.text().strip()
        case_entity = self.case_entity_combo.currentText().strip()
        case_city = self.case_city_combo.currentText().strip()
        profile = _current_primary_profile()
        if _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            include_transport_sentence = self.include_transport_sentence_check.isChecked()
            one_way_distance = 0.0
            if include_transport_sentence:
                one_way_distance = self._parse_optional_float(self.travel_km_outbound_edit.text(), "KM (one way)") or 0.0
            else:
                try:
                    current_distance = self._parse_optional_float(self.travel_km_outbound_edit.text(), "KM (one way)")
                except ValueError:
                    current_distance = None
                if current_distance is not None:
                    one_way_distance = current_distance
            return build_interpretation_honorarios_draft(
                case_number=case_number,
                case_entity=case_entity,
                case_city=case_city,
                service_date=self.translation_date_edit.text().strip(),
                service_entity=self.service_entity_combo.currentText().strip(),
                service_city=self.service_city_combo.currentText().strip(),
                use_service_location_in_honorarios=self.use_service_location_check.isChecked(),
                include_transport_sentence_in_honorarios=include_transport_sentence,
                travel_km_outbound=one_way_distance,
                travel_km_return=one_way_distance,
                recipient_block=default_interpretation_recipient_block(case_entity, case_city),
                profile=profile,
            )
        return build_honorarios_draft(
            case_number=case_number,
            word_count=self._current_word_count_value(),
            case_entity=case_entity,
            case_city=case_city,
            profile=profile,
        )

    def _honorarios_default_directory(self) -> Path:
        for candidate in (self._seed.output_docx, self._seed.partial_docx):
            if isinstance(candidate, Path):
                resolved = candidate.expanduser().resolve()
                if resolved.exists():
                    return resolved.parent
        return _default_documents_dir()

    def _current_translation_docx_path(self) -> Path | None:
        for candidate in (self._seed.output_docx, self._seed.partial_docx):
            if isinstance(candidate, Path):
                resolved = candidate.expanduser().resolve()
                if resolved.exists():
                    return resolved
        return None

    def _offer_gmail_draft_for_honorarios(
        self,
        honorarios_docx: Path,
        honorarios_pdf: Path | None,
        profile: UserProfile,
    ) -> None:
        court_email = self.court_email_combo.currentText().strip()
        if not court_email:
            return
        if honorarios_pdf is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                "The honorários PDF is unavailable for this export. Gmail draft creation requires the PDF.",
            )
            return
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=str(self._gui_settings.get("gmail_gog_path", "") or ""),
            configured_account_email=str(self._gui_settings.get("gmail_account_email", "") or ""),
        )
        if not prereqs.ready or prereqs.gog_path is None or prereqs.account_email is None:
            return
        confirm = QMessageBox.question(
            self,
            "Gmail draft",
            f"Criar rascunho no Gmail para {court_email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        translation_docx = self._current_translation_docx_path()
        if translation_docx is None:
            QMessageBox.critical(
                self,
                "Gmail draft",
                "Translated DOCX is unavailable for this run. The Gmail draft was not created.",
            )
            return
        try:
            validate_translated_docx_artifacts_for_gmail_draft(
                translated_docxs=(translation_docx,),
                honorarios_pdf=honorarios_pdf,
            )
            request = build_honorarios_gmail_request(
                gog_path=prereqs.gog_path,
                account_email=prereqs.account_email,
                to_email=court_email,
                case_number=self.case_number_edit.text().strip(),
                translation_docx=translation_docx,
                honorarios_pdf=honorarios_pdf,
                profile=profile,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Gmail draft", str(exc))
            return
        result = create_gmail_draft_via_gog(request)
        if not result.ok:
            details = result.stderr or result.stdout or result.message
            QMessageBox.critical(
                self,
                "Gmail draft",
                "Failed to create Gmail draft.\n\n"
                f"{details}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        open_gmail = QMessageBox.question(
            self,
            "Gmail draft",
            "Gmail draft created successfully. Abrir Gmail?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if open_gmail == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(GMAIL_DRAFTS_URL))

    def _offer_gmail_draft_for_interpretation_honorarios(
        self,
        honorarios_pdf: Path | None,
        profile: UserProfile,
    ) -> None:
        court_email = self.court_email_combo.currentText().strip()
        if not court_email:
            QMessageBox.information(
                self,
                "Gmail draft",
                "Court Email is missing for this interpretation entry. The Gmail draft was not created.",
            )
            return
        if honorarios_pdf is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                "The honorários PDF is unavailable for this export. Gmail draft creation requires the PDF.",
            )
            return
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=str(self._gui_settings.get("gmail_gog_path", "") or ""),
            configured_account_email=str(self._gui_settings.get("gmail_account_email", "") or ""),
        )
        if not prereqs.ready or prereqs.gog_path is None or prereqs.account_email is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                f"{prereqs.message}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Gmail draft",
            f"Criar rascunho no Gmail para {court_email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            request = build_manual_interpretation_gmail_request(
                gog_path=prereqs.gog_path,
                account_email=prereqs.account_email,
                to_email=court_email,
                case_number=self.case_number_edit.text().strip(),
                honorarios_pdf=honorarios_pdf,
                profile=profile,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Gmail draft", str(exc))
            return
        result = create_gmail_draft_via_gog(request)
        if not result.ok:
            details = result.stderr or result.stdout or result.message
            QMessageBox.critical(
                self,
                "Gmail draft",
                "Failed to create Gmail draft.\n\n"
                f"{details}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        open_gmail = QMessageBox.question(
            self,
            "Gmail draft",
            "Gmail draft created successfully. Abrir Gmail?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if open_gmail == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(GMAIL_DRAFTS_URL))

    def _open_honorarios_dialog(self) -> None:
        if not self._allow_honorarios_export:
            return
        draft = self._build_honorarios_draft()
        dialog = QtHonorariosExportDialog(
            parent=self,
            draft=draft,
            default_directory=self._honorarios_default_directory(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_path is not None:
            generated_draft = getattr(dialog, "generated_draft", None)
            profile = generated_draft.profile if generated_draft is not None else _current_primary_profile()
            final_draft = generated_draft or draft
            if final_draft.kind == HonorariosKind.INTERPRETATION:
                self.include_transport_sentence_check.setChecked(
                    bool(final_draft.include_transport_sentence_in_honorarios)
                )
            saved_pdf_path = getattr(dialog, "saved_pdf_path", None)
            pdf_unavailable_explained = bool(getattr(dialog, "pdf_unavailable_explained", False))
            if final_draft.kind == HonorariosKind.TRANSLATION:
                if saved_pdf_path is not None or not pdf_unavailable_explained:
                    self._offer_gmail_draft_for_honorarios(dialog.saved_path, saved_pdf_path, profile)
            elif final_draft.kind == HonorariosKind.INTERPRETATION and (
                saved_pdf_path is not None or not pdf_unavailable_explained
            ):
                self._offer_gmail_draft_for_interpretation_honorarios(saved_pdf_path, profile)

    def _apply_header_suggestion(self, suggestion: MetadataSuggestion) -> None:
        if suggestion.case_entity:
            self._ensure_in_vocab("vocab_case_entities", suggestion.case_entity)
            self.case_entity_combo.setCurrentText(suggestion.case_entity)
        if suggestion.case_city:
            self._ensure_in_vocab("vocab_cities", suggestion.case_city)
            self.case_city_combo.setCurrentText(suggestion.case_city)
        if suggestion.case_number:
            self.case_number_edit.setText(suggestion.case_number)
        self._apply_imported_service_fields(
            service_entity=suggestion.service_entity,
            service_city=suggestion.service_city,
        )
        self._apply_non_court_default_rule()
        ranked = rank_court_email_suggestions(
            exact_email=suggestion.court_email,
            case_entity=self.case_entity_combo.currentText().strip(),
            case_city=self.case_city_combo.currentText().strip(),
            vocab_court_emails=list(self._settings["vocab_court_emails"]),
        )
        if ranked:
            self.court_email_combo.setCurrentText(ranked[0])
        self._refresh_service_section_state()

    def _autofill_from_pdf_header(self) -> None:
        pdf_path = self._seed.pdf_path.expanduser().resolve() if self._seed.pdf_path is not None else None
        if pdf_path is None or not pdf_path.exists():
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Select PDF for header autofill",
                str(_default_downloads_dir()),
                "PDF Files (*.pdf);;All Files (*.*)",
            )
            if not selected:
                return
            pdf_path = Path(selected).expanduser().resolve()
            self._seed.pdf_path = pdf_path
        suggestion = extract_pdf_header_metadata_priority_pages(
            pdf_path,
            vocab_cities=list(self._settings["vocab_cities"]),
            config=self._metadata_config,
        )
        if not any(
            (
                suggestion.case_entity,
                suggestion.case_city,
                suggestion.case_number,
                suggestion.court_email,
                suggestion.service_entity,
                suggestion.service_city,
            )
        ):
            QMessageBox.warning(self, "Autofill", "No header text could be extracted.")
            return
        self._apply_header_suggestion(suggestion)

    def _autofill_from_photo(self) -> None:
        if not bool(self._settings["metadata_photo_enabled"]):
            QMessageBox.warning(self, "Photo autofill", "Photo autofill is disabled in settings.")
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select photo",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*.*)",
        )
        if not selected:
            return
        self._autofill_from_photo_path(Path(selected).expanduser().resolve(), prompt_for_distance=True)

    def _effective_interpretation_distance_city(self) -> str:
        if not _is_interpretation_job_type(self.job_type_combo.currentText()):
            return ""
        return self.service_city_combo.currentText().strip()

    def _set_interpretation_distance_text(
        self,
        value: float | None,
        *,
        city_key: str,
        manual: bool,
    ) -> None:
        self._distance_sync_in_progress = True
        try:
            self.travel_km_outbound_edit.setText("" if value is None else f"{float(value):g}")
        finally:
            self._distance_sync_in_progress = False
        self._distance_value_city_key = city_key
        self._distance_value_is_manual = manual

    def _on_interpretation_distance_edited(self, _text: str) -> None:
        if self._distance_sync_in_progress:
            return
        city = self._effective_interpretation_distance_city()
        self._distance_value_city_key = city.casefold() if city else ""
        self._distance_value_is_manual = True

    def _apply_interpretation_distance_defaults(self, *, prompt_if_missing: bool) -> None:
        if not self._interpretation_transport_sentence_enabled():
            return
        city = self._effective_interpretation_distance_city()
        if city == "":
            self._set_interpretation_distance_text(None, city_key="", manual=False)
            return
        city_key = city.casefold()
        profile = _current_primary_profile()
        known_distance = distance_for_city(profile, city)
        if known_distance is not None:
            should_replace = (
                self._distance_value_city_key != city_key
                or not self.travel_km_outbound_edit.text().strip()
                or not self._distance_value_is_manual
            )
            if should_replace:
                self._set_interpretation_distance_text(known_distance, city_key=city_key, manual=False)
            return
        if self._distance_value_city_key != city_key:
            self._set_interpretation_distance_text(None, city_key=city_key, manual=False)
        if prompt_if_missing:
            self._prompt_interpretation_distance_for_imported_city()

    def _on_primary_date_changed(self, text: str) -> None:
        if _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            self.service_date_edit.setText(text)

    def _prompt_interpretation_distance_for_imported_city(self) -> None:
        if not _is_interpretation_job_type(self.job_type_combo.currentText()):
            return
        if not self._interpretation_transport_sentence_enabled():
            return
        profiles, primary_profile_id = load_profile_settings()
        profile = primary_profile(profiles, primary_profile_id)
        city = self._effective_interpretation_distance_city() or self.case_city_combo.currentText().strip()
        if not city:
            return
        known_distance = distance_for_city(profile, city)
        if known_distance is not None:
            self._set_interpretation_distance_text(known_distance, city_key=city.casefold(), manual=False)
            return
        if self.travel_km_outbound_edit.text().strip():
            return
        city_key = city.casefold()
        if city_key in self._distance_prompted_cities:
            return
        if not profile.travel_origin_label.strip():
            return
        distance_value, ok = QInputDialog.getDouble(
            self,
            "Interpretation distance",
            f"One-way distance from {profile.travel_origin_label} to {city} (km):",
            0.0,
            0.0,
            1_000_000.0,
            2,
        )
        if not ok:
            return
        self._distance_prompted_cities.add(city_key)
        profile.travel_distances_by_city[city] = float(distance_value)
        save_profile_settings(profiles=profiles, primary_profile_id=primary_profile_id)
        self._set_interpretation_distance_text(distance_value, city_key=city_key, manual=False)

    def _persist_interpretation_distance_for_current_city(self) -> None:
        if not _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            return
        if not self._interpretation_transport_sentence_enabled():
            return
        city = self._effective_interpretation_distance_city()
        distance_text = self.travel_km_outbound_edit.text().strip()
        if city == "" or distance_text == "":
            return
        distance_value = self._parse_optional_float(distance_text, "KM (one way)")
        if distance_value is None:
            return
        profiles, primary_profile_id = load_profile_settings()
        profile = primary_profile(profiles, primary_profile_id)
        existing = distance_for_city(profile, city)
        if existing is not None and abs(existing - distance_value) < 1e-9:
            self._distance_value_city_key = city.casefold()
            self._distance_value_is_manual = False
            return
        profile.travel_distances_by_city[city] = float(distance_value)
        save_profile_settings(profiles=profiles, primary_profile_id=primary_profile_id)
        self._distance_value_city_key = city.casefold()
        self._distance_value_is_manual = False

    def _autofill_from_photo_path(self, image_path: Path, *, prompt_for_distance: bool) -> None:
        if _is_interpretation_job_type(self.job_type_combo.currentText()):
            suggestion = extract_interpretation_photo_metadata_from_image(
                image_path,
                vocab_cities=list(self._settings["vocab_cities"]),
                config=self._metadata_config,
            )
        else:
            suggestion = extract_photo_metadata_from_image(
                image_path,
                vocab_cities=list(self._settings["vocab_cities"]),
                config=self._metadata_config,
            )
        if _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
            self._apply_imported_service_fields(
                service_entity=suggestion.service_entity,
                service_city=suggestion.service_city,
            )
        elif suggestion.service_city:
            self._ensure_in_vocab("vocab_cities", suggestion.service_city)
            self.service_city_combo.setCurrentText(suggestion.service_city)
        if suggestion.service_date:
            if _is_interpretation_job_type(self.job_type_combo.currentText().strip()):
                self.translation_date_edit.setText(suggestion.service_date)
            else:
                self.service_date_edit.setText(suggestion.service_date)
        if suggestion.case_number and not self.case_number_edit.text().strip():
            self.case_number_edit.setText(suggestion.case_number)
        if suggestion.case_entity:
            self._ensure_in_vocab("vocab_case_entities", suggestion.case_entity)
            self.case_entity_combo.setCurrentText(suggestion.case_entity)
        if suggestion.case_city:
            self._ensure_in_vocab("vocab_cities", suggestion.case_city)
            self.case_city_combo.setCurrentText(suggestion.case_city)
        if suggestion.court_email:
            self._ensure_in_vocab("vocab_court_emails", suggestion.court_email)
            self.court_email_combo.setCurrentText(suggestion.court_email)
        self._apply_non_court_default_rule()
        self._refresh_service_section_state()
        if prompt_for_distance:
            self._prompt_interpretation_distance_for_imported_city()

    def _apply_non_court_default_rule(self) -> None:
        case_entity, case_city = apply_service_case_default_rule(
            case_entity=self.case_entity_combo.currentText().strip(),
            case_city=self.case_city_combo.currentText().strip(),
            service_entity=self.service_entity_combo.currentText().strip(),
            service_city=self.service_city_combo.currentText().strip(),
            case_entity_user_set=self._case_entity_user_set,
            case_city_user_set=self._case_city_user_set,
            non_court_service_entities=list(self._settings["non_court_service_entities"]),
        )
        if case_entity is not None and case_entity != self.case_entity_combo.currentText().strip():
            self.case_entity_combo.setCurrentText(case_entity)
            self._ensure_in_vocab("vocab_case_entities", case_entity)
        if case_city is not None and case_city != self.case_city_combo.currentText().strip():
            self.case_city_combo.setCurrentText(case_city)
            self._ensure_in_vocab("vocab_cities", case_city)

    def _parse_float(self, value: str, label: str) -> float:
        return _parse_joblog_float(value, label)

    def _parse_optional_int(self, value: str, label: str) -> int | None:
        return _parse_joblog_optional_int(value, label)

    def _parse_optional_float(self, value: str, label: str) -> float | None:
        return _parse_joblog_optional_float(value, label)

    def _resolved_seed_docx_path(self) -> Path | None:
        for candidate in (self._seed.output_docx, self._seed.partial_docx):
            if isinstance(candidate, Path):
                return candidate.expanduser().resolve()
        return None

    def _collect_raw_values(self) -> dict[str, str]:
        is_interpretation = _is_interpretation_job_type(self.job_type_combo.currentText().strip())
        primary_date = self.translation_date_edit.text()
        return {
            "translation_date": primary_date,
            "job_type": self.job_type_combo.currentText(),
            "case_number": self.case_number_edit.text(),
            "court_email": self.court_email_combo.currentText(),
            "case_entity": self.case_entity_combo.currentText(),
            "case_city": self.case_city_combo.currentText(),
            "service_entity": self.service_entity_combo.currentText(),
            "service_city": self.service_city_combo.currentText(),
            "service_date": primary_date if is_interpretation else self.service_date_edit.text(),
            "travel_km_outbound": self.travel_km_outbound_edit.text(),
            "travel_km_return": self.travel_km_outbound_edit.text(),
            "lang": _widget_text_value(self.lang_edit),
            "target_lang": _widget_text_value(self.target_lang_edit),
            "run_id": self.run_id_edit.text(),
            "pages": self.pages_edit.text(),
            "word_count": self.word_count_edit.text(),
            "total_tokens": self.total_tokens_edit.text(),
            "rate_per_word": self.rate_edit.text(),
            "expected_total": self.expected_total_edit.text(),
            "amount_paid": self.amount_paid_edit.text(),
            "api_cost": self.api_cost_edit.text(),
            "estimated_api_cost": self.estimated_api_cost_edit.text(),
            "quality_risk_score": self.quality_risk_score_edit.text(),
            "profit": self.profit_edit.text(),
        }

    def _normalized_payload(self) -> dict[str, Any]:
        include_transport_sentence_check = getattr(self, "include_transport_sentence_check", None)
        include_transport_sentence = (
            include_transport_sentence_check.isChecked()
            if include_transport_sentence_check is not None
            else bool(getattr(self._seed, "include_transport_sentence_in_honorarios", True))
        )
        return _normalize_joblog_payload(
            seed=self._seed,
            raw_values=self._collect_raw_values(),
            service_same_checked=self.service_same_check.isChecked(),
            use_service_location_in_honorarios_checked=self.use_service_location_check.isChecked(),
            include_transport_sentence_in_honorarios_checked=include_transport_sentence,
        )

    def _open_translation_docx(self) -> None:
        resolved = self._current_translation_docx_path()
        if resolved is None:
            QMessageBox.critical(
                self,
                "Open translated DOCX",
                "No translated DOCX is available for this run.",
            )
            return
        _open_path_in_system(self, resolved)

    def _save(self) -> None:
        try:
            payload = self._normalized_payload()
        except ValueError as exc:
            self._reveal_validation_context(str(exc))
            QMessageBox.critical(self, "Invalid values", str(exc))
            return
        try:
            self._persist_interpretation_distance_for_current_city()
        except ValueError as exc:
            self._reveal_validation_context(str(exc))
            QMessageBox.critical(self, "Invalid values", str(exc))
            return

        with closing(open_job_log(self._db_path)) as conn:
            if self._edit_row_id is not None:
                update_job_run(conn, row_id=self._edit_row_id, values=payload)
                row_id = self._edit_row_id
            else:
                insert_payload = {
                    "completed_at": self._seed.completed_at,
                    **payload,
                    "output_docx_path": (
                        str(self._seed.output_docx.expanduser().resolve())
                        if isinstance(self._seed.output_docx, Path)
                        else None
                    ),
                    "partial_docx_path": (
                        str(self._seed.partial_docx.expanduser().resolve())
                        if isinstance(self._seed.partial_docx, Path)
                        else None
                    ),
                }
                row_id = insert_job_run(conn, insert_payload)

        _persist_joblog_vocab_settings(self._settings, payload)
        self._refresh_vocab_widgets()
        _save_joblog_settings_bundle(
            self._settings,
            service_equals_case_by_default=bool(self.service_same_check.isChecked()),
        )
        translated_docx_path = self._resolved_seed_docx_path()
        self._saved_result = JobLogSavedResult(
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
        self._saved = True
        if self._on_saved is not None:
            self._on_saved()
        self.accept()


class QtJobLogWindow(QDialog):
    """Qt job log table window."""

    def __init__(self, *, parent: QWidget | None, db_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Job Log")
        self.setMinimumSize(760, 420)

        self._db_path = db_path
        self._settings = load_joblog_settings()
        self._gui_settings = load_gui_settings()
        self._visible_columns = update_joblog_visible_columns(self._settings["joblog_visible_columns"])
        if not self._visible_columns:
            self._visible_columns = ["translation_date", "case_number", "job_type"]
        self._rows_data: list[dict[str, object]] = []
        self._inline_edit_row_id: int | None = None
        self._inline_edit_row_index: int | None = None
        self._inline_original_row: dict[str, object] | None = None
        self._inline_edit_widgets: dict[str, QWidget] = {}
        self._selection_guard_active = False
        self._suspend_width_persistence = False
        self._action_icons = {
            "edit": self._joblog_icon("resources/icons/dashboard/edit.svg"),
            "delete": self._joblog_icon("resources/icons/dashboard/delete.svg"),
        }

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.add_btn = QPushButton("Add...")
        self.refresh_btn = QPushButton("Refresh")
        self.columns_btn = QPushButton("Columns...")
        self.delete_selected_btn = QPushButton("Delete selected...", objectName="DangerButton")
        self.delete_selected_btn.setEnabled(False)
        self.honorarios_btn = QPushButton("Gerar Requerimento de Honorários...")
        self.honorarios_btn.setEnabled(False)
        self.add_menu = QMenu(self.add_btn)
        self.add_blank_interpretation_action = self.add_menu.addAction("Blank/manual interpretation entry")
        self.add_notification_interpretation_action = self.add_menu.addAction("From notification PDF...")
        self.add_photo_interpretation_action = self.add_menu.addAction("From photo/screenshot...")
        self.add_btn.setMenu(self.add_menu)
        controls.addWidget(self.add_btn)
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.columns_btn)
        controls.addWidget(self.delete_selected_btn)
        controls.addWidget(self.honorarios_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.table = QTableWidget(0, len(JOBLOG_COLUMNS) + 1, self)
        self.table.setHorizontalHeaderLabels([JOBLOG_ACTIONS_COLUMN_LABEL] + [JOBLOG_COLUMN_LABELS[col] for col in JOBLOG_COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.sectionResized.connect(self._on_header_section_resized)
        if hasattr(header, "sectionHandleDoubleClicked"):
            header.sectionHandleDoubleClicked.connect(self._on_header_handle_double_clicked)
        root.addWidget(self.table, 1)

        self.add_blank_interpretation_action.triggered.connect(self._open_blank_interpretation_dialog)
        self.add_notification_interpretation_action.triggered.connect(self._open_notification_interpretation_dialog)
        self.add_photo_interpretation_action.triggered.connect(self._open_photo_interpretation_dialog)
        self.refresh_btn.clicked.connect(self.refresh_rows)
        self.columns_btn.clicked.connect(self._open_columns_dialog)
        self.delete_selected_btn.clicked.connect(self._confirm_delete_selected_rows)
        self.honorarios_btn.clicked.connect(self._open_honorarios_dialog)
        self.table.itemSelectionChanged.connect(self._refresh_action_state)
        self.table.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
        self._apply_visible_columns()
        self.refresh_rows()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="table",
            preferred_size=QSize(1280, 520),
        )

    def _joblog_icon(self, rel_path: str) -> QIcon:
        return QIcon(str(resource_path(rel_path)))

    def _header_text_width(self, table_column: int) -> int:
        item = self.table.horizontalHeaderItem(table_column)
        label = item.text() if item is not None else ""
        metrics = QFontMetrics(self.table.horizontalHeader().font())
        return metrics.horizontalAdvance(label) + JOBLOG_COLUMN_WIDTH_PADDING

    def _autofit_column(self, table_column: int) -> None:
        if self.table.isColumnHidden(table_column):
            return
        if table_column == 0:
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.table.resizeColumnToContents(0)
            return
        self.table.resizeColumnToContents(table_column)
        self.table.setColumnWidth(
            table_column,
            max(self.table.columnWidth(table_column), self._header_text_width(table_column)),
        )

    def _apply_column_widths(self) -> None:
        saved_widths = dict(self._settings.get("joblog_column_widths", {}))
        self._suspend_width_persistence = True
        try:
            self._autofit_column(0)
            for table_column, column_name in enumerate(JOBLOG_COLUMNS, start=1):
                if self.table.isColumnHidden(table_column):
                    continue
                self._autofit_column(table_column)
                saved_width = int(saved_widths.get(column_name, 0) or 0)
                if saved_width > 0:
                    self.table.setColumnWidth(table_column, saved_width)
        finally:
            self._suspend_width_persistence = False

    def _persist_joblog_column_width(self, column_name: str, width: int) -> None:
        if width <= 0:
            return
        widths = dict(self._settings.get("joblog_column_widths", {}))
        widths[column_name] = int(width)
        self._settings["joblog_column_widths"] = widths
        save_joblog_settings({"joblog_column_widths": widths})

    def _column_name_for_table_column(self, table_column: int) -> str | None:
        if table_column <= 0 or table_column > len(JOBLOG_COLUMNS):
            return None
        return JOBLOG_COLUMNS[table_column - 1]

    def _on_header_section_resized(self, logical_index: int, _old_size: int, new_size: int) -> None:
        if self._suspend_width_persistence or new_size <= 0 or self.table.isColumnHidden(logical_index):
            return
        column_name = self._column_name_for_table_column(logical_index)
        if column_name is None:
            return
        self._persist_joblog_column_width(column_name, new_size)

    def _on_header_handle_double_clicked(self, logical_index: int) -> None:
        if self.table.isColumnHidden(logical_index):
            return
        self._autofit_column(logical_index)

    def _apply_visible_columns(self) -> None:
        visible = set(self._visible_columns)
        header = self.table.horizontalHeader()
        self.table.setColumnHidden(0, False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for idx, col in enumerate(JOBLOG_COLUMNS, start=1):
            self.table.setColumnHidden(idx, col not in visible)
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Interactive)

    def _table_column_index(self, column_name: str) -> int:
        return JOBLOG_COLUMNS.index(column_name) + 1

    def _row_index_for_row_id(self, row_id: int) -> int | None:
        for index, row in enumerate(self._rows_data):
            if int(row.get("id", 0) or 0) == int(row_id):
                return index
        return None

    def _selected_row_indices(self) -> list[int]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            row = self.table.currentRow()
            return [row] if 0 <= row < len(self._rows_data) else []
        selected = sorted({int(index.row()) for index in selection_model.selectedRows()})
        if selected:
            return [row for row in selected if 0 <= row < len(self._rows_data)]
        row = self.table.currentRow()
        return [row] if 0 <= row < len(self._rows_data) else []

    def _selected_row_ids(self) -> list[int]:
        selected_ids: list[int] = []
        for row_index in self._selected_row_indices():
            row_data = self._rows_data[row_index]
            selected_ids.append(int(row_data.get("id", 0) or 0))
        return selected_ids

    def _delete_confirmation_message(self, rows: list[dict[str, object]]) -> str:
        case_numbers = [str(row.get("case_number", "") or "").strip() for row in rows]
        case_numbers = [value for value in case_numbers if value]
        if len(rows) == 1:
            suffix = f" ({case_numbers[0]})" if case_numbers else ""
            return f"Delete this Job Log row{suffix}?"
        preview = ", ".join(case_numbers[:3])
        extra_count = max(0, len(case_numbers) - 3)
        if preview and extra_count > 0:
            preview = f"{preview}, +{extra_count} more"
        suffix = f" ({preview})" if preview else ""
        return f"Delete {len(rows)} Job Log rows{suffix}?"

    def _render_display_row(self, row_index: int, row_data: Mapping[str, object]) -> None:
        for col in JOBLOG_COLUMNS:
            table_col = self._table_column_index(col)
            self.table.removeCellWidget(row_index, table_col)
            raw = row_data.get(col, "")
            text = "" if raw is None else str(raw)
            self.table.setItem(row_index, table_col, QTableWidgetItem(text))
        self._set_row_action_widget(row_index, row_data, editing=False)

    def _set_row_action_widget(self, row_index: int, row_data: Mapping[str, object], *, editing: bool) -> None:
        row_id = int(row_data.get("id", 0) or 0)
        container = QWidget(self.table)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        if editing:
            save_btn = QPushButton("Save", container)
            cancel_btn = QPushButton("Cancel", container)
            save_btn.clicked.connect(lambda _checked=False, rid=row_id: self._save_inline_edit(rid))
            cancel_btn.clicked.connect(lambda _checked=False, rid=row_id: self._cancel_inline_edit(rid))
            layout.addWidget(save_btn)
            layout.addWidget(cancel_btn)
        else:
            actions_enabled = self._inline_edit_row_id in {None, row_id}
            edit_btn = QToolButton(container)
            edit_btn.setAutoRaise(True)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            edit_btn.setIcon(self._action_icons["edit"])
            edit_btn.setIconSize(QSize(14, 14))
            edit_btn.setFixedSize(QSize(22, 22))
            edit_btn.setToolTip("Edit row")
            edit_btn.setEnabled(actions_enabled)
            edit_btn.clicked.connect(lambda _checked=False, rid=row_id: self._open_edit_dialog(rid))
            delete_btn = QToolButton(container)
            delete_btn.setAutoRaise(True)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            delete_btn.setIcon(self._action_icons["delete"])
            delete_btn.setIconSize(QSize(14, 14))
            delete_btn.setFixedSize(QSize(22, 22))
            delete_btn.setToolTip("Delete row")
            delete_btn.setEnabled(actions_enabled)
            delete_btn.clicked.connect(lambda _checked=False, rid=row_id: self._confirm_delete_row(rid))
            layout.addWidget(edit_btn)
            layout.addWidget(delete_btn)
        layout.addStretch(1)
        self.table.setCellWidget(row_index, 0, container)

    def _combo_values_for_column(self, column_name: str) -> list[str]:
        if column_name in {"lang", "target_lang"}:
            return list(JOBLOG_LANG_OPTIONS)
        setting_key = JOBLOG_VOCAB_SETTINGS_MAP.get(column_name)
        if setting_key is None:
            return []
        return list(self._settings[setting_key])

    def _build_inline_editor(self, column_name: str, row_data: Mapping[str, object]) -> QWidget:
        value = "" if row_data.get(column_name) is None else str(row_data.get(column_name))
        if column_name in JOBLOG_INLINE_DATE_COLUMNS:
            edit = GuardedDateEdit(value, self.table)
            edit.setPlaceholderText("YYYY-MM-DD")
            return edit
        if column_name in JOBLOG_INLINE_COMBO_COLUMNS:
            combo = NoWheelComboBox(self.table)
            combo.addItems(self._combo_values_for_column(column_name))
            is_editable = column_name == "court_email"
            combo.setEditable(is_editable)
            if is_editable:
                combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            elif value and combo.findText(value) == -1:
                combo.addItem(value)
            combo.setCurrentText(value)
            return combo
        edit = QLineEdit(value, self.table)
        if column_name in JOBLOG_INLINE_INTEGER_COLUMNS:
            validator = QIntValidator(0, 1_000_000_000, edit)
            edit.setValidator(validator)
        elif column_name in JOBLOG_INLINE_FLOAT_COLUMNS:
            validator = QDoubleValidator(-1_000_000_000.0, 1_000_000_000.0, 6, edit)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            edit.setValidator(validator)
        return edit

    def _begin_inline_edit(self, row_index: int, row_data: Mapping[str, object]) -> None:
        row_id = int(row_data.get("id", 0) or 0)
        self._inline_edit_row_id = row_id
        self._inline_edit_row_index = row_index
        self._inline_original_row = dict(row_data)
        self._inline_edit_widgets = {}
        self.refresh_btn.setEnabled(False)
        self.columns_btn.setEnabled(False)
        self.honorarios_btn.setEnabled(False)
        for column_name in JOBLOG_COLUMNS:
            table_col = self._table_column_index(column_name)
            if self.table.isColumnHidden(table_col):
                continue
            editor = self._build_inline_editor(column_name, row_data)
            self._inline_edit_widgets[column_name] = editor
            self.table.setCellWidget(row_index, table_col, editor)
        self._refresh_action_widgets()
        self.table.selectRow(row_index)
        self._refresh_action_state()

    def _clear_inline_edit_state(self) -> None:
        self._inline_edit_row_id = None
        self._inline_edit_row_index = None
        self._inline_original_row = None
        self._inline_edit_widgets = {}

    def _collect_inline_raw_values(self) -> dict[str, str]:
        if self._inline_original_row is None:
            return {}
        raw_values = {
            column_name: "" if self._inline_original_row.get(column_name) is None else str(self._inline_original_row.get(column_name))
            for column_name in JOBLOG_COLUMNS
        }
        for column_name, widget in self._inline_edit_widgets.items():
            raw_values[column_name] = _widget_text_value(widget)
        return raw_values

    def _save_inline_edit(self, row_id: int) -> None:
        if self._inline_edit_row_id != int(row_id) or self._inline_original_row is None:
            return
        try:
            payload = _normalize_joblog_payload(
                seed=build_seed_from_joblog_row(self._inline_original_row),
                raw_values=self._collect_inline_raw_values(),
                service_same_checked=False,
                use_service_location_in_honorarios_checked=_coerce_joblog_bool(
                    self._inline_original_row.get("use_service_location_in_honorarios"),
                    default=False,
                ),
                include_transport_sentence_in_honorarios_checked=_coerce_joblog_bool(
                    self._inline_original_row.get("include_transport_sentence_in_honorarios"),
                    default=True,
                ),
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid values", str(exc))
            return
        with closing(open_job_log(self._db_path)) as conn:
            update_job_run(conn, row_id=int(row_id), values=payload)
        _persist_joblog_vocab_settings(self._settings, payload)
        _save_joblog_settings_bundle(
            self._settings,
            service_equals_case_by_default=bool(self._settings["service_equals_case_by_default"]),
        )
        self._clear_inline_edit_state()
        self.refresh_rows(selected_row_id=int(row_id), force=True)

    def _cancel_inline_edit(self, row_id: int) -> None:
        if self._inline_edit_row_id != int(row_id) or self._inline_original_row is None:
            return
        row_index = self._inline_edit_row_index
        original_row = dict(self._inline_original_row)
        self._clear_inline_edit_state()
        if row_index is not None and 0 <= row_index < self.table.rowCount():
            self._render_display_row(row_index, original_row)
            self.table.selectRow(row_index)
        self._refresh_action_widgets()
        self._refresh_action_state()

    def _on_table_cell_double_clicked(self, row_index: int, table_column: int) -> None:
        if table_column == 0:
            return
        row_data = self._rows_data[row_index]
        row_id = int(row_data.get("id", 0) or 0)
        if self._inline_edit_row_id is not None:
            if self._inline_edit_row_id == row_id:
                return
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        selected_rows = self._selected_row_indices()
        if len(selected_rows) > 1:
            QMessageBox.information(self, "Job Log", "Select one Job Log row first.")
            return
        if selected_rows != [row_index]:
            self.table.selectRow(row_index)
        self._begin_inline_edit(row_index, row_data)

    def _open_edit_dialog(self, row_id: int) -> None:
        if self._inline_edit_row_id is not None:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        row_index = self._row_index_for_row_id(int(row_id))
        if row_index is None:
            return
        row_data = self._rows_data[row_index]
        dialog = QtSaveToJobLogDialog(
            parent=self,
            db_path=self._db_path,
            seed=build_seed_from_joblog_row(row_data),
            on_saved=lambda rid=int(row_id): self.refresh_rows(selected_row_id=rid, force=True),
            allow_honorarios_export=True,
            edit_row_id=int(row_id),
        )
        dialog.exec()

    def _open_blank_interpretation_dialog(self) -> None:
        if self._inline_edit_row_id is not None:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        dialog = QtSaveToJobLogDialog(
            parent=self,
            db_path=self._db_path,
            seed=build_blank_interpretation_seed(),
            on_saved=lambda: self.refresh_rows(selected_row_index=0, force=True),
            allow_honorarios_export=True,
        )
        dialog.exec()

    def _open_notification_interpretation_dialog(self) -> None:
        if self._inline_edit_row_id is not None:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select interpretation notification PDF",
            str(_default_downloads_dir()),
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not selected:
            return
        pdf_path = Path(selected).expanduser().resolve()
        suggestion = extract_interpretation_notification_metadata_from_pdf(
            pdf_path,
            vocab_cities=list(self._settings["vocab_cities"]),
            config=metadata_config_from_settings(self._settings),
        )
        if not any(
            (
                suggestion.case_entity,
                suggestion.case_city,
                suggestion.case_number,
                suggestion.court_email,
                suggestion.service_entity,
                suggestion.service_city,
                suggestion.service_date,
            )
        ):
            QMessageBox.information(
                self,
                "Interpretation notification",
                "No notification metadata could be extracted automatically. Review the entry manually.",
            )
        dialog = QtSaveToJobLogDialog(
            parent=self,
            db_path=self._db_path,
            seed=build_interpretation_seed_from_notification_pdf(
                pdf_path=pdf_path,
                suggestion=suggestion,
                vocab_court_emails=list(self._settings["vocab_court_emails"]),
            ),
            on_saved=lambda: self.refresh_rows(selected_row_index=0, force=True),
            allow_honorarios_export=True,
        )
        dialog.exec()

    def _open_photo_interpretation_dialog(self) -> None:
        if self._inline_edit_row_id is not None:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        if not bool(self._settings["metadata_photo_enabled"]):
            QMessageBox.warning(self, "Photo autofill", "Photo autofill is disabled in settings.")
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select interpretation photo or screenshot",
            str(_default_downloads_dir()),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*.*)",
        )
        if not selected:
            return
        image_path = Path(selected).expanduser().resolve()
        suggestion = extract_interpretation_photo_metadata_from_image(
            image_path,
            vocab_cities=list(self._settings["vocab_cities"]),
            config=metadata_config_from_settings(self._settings),
        )
        if not any(
            (
                suggestion.case_entity,
                suggestion.case_city,
                suggestion.case_number,
                suggestion.service_date,
            )
        ):
            QMessageBox.information(
                self,
                "Interpretation photo",
                "No photo metadata could be extracted automatically. Review the entry manually.",
            )
        dialog = QtSaveToJobLogDialog(
            parent=self,
            db_path=self._db_path,
            seed=build_interpretation_seed_from_photo_screenshot(
                suggestion=suggestion,
                vocab_court_emails=list(self._settings["vocab_court_emails"]),
            ),
            on_saved=lambda: self.refresh_rows(selected_row_index=0, force=True),
            allow_honorarios_export=True,
        )
        dialog._prompt_interpretation_distance_for_imported_city()
        dialog.exec()

    def _refresh_action_widgets(self) -> None:
        for row_index, row_data in enumerate(self._rows_data):
            row_id = int(row_data.get("id", 0) or 0)
            self._set_row_action_widget(
                row_index,
                row_data,
                editing=self._inline_edit_row_id == row_id,
            )
        self._autofit_column(0)

    def _confirm_delete_row(self, row_id: int) -> None:
        if self._inline_edit_row_id is not None:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        row_index = self._row_index_for_row_id(int(row_id))
        if row_index is None:
            return
        self._confirm_delete_rows([row_index])

    def _confirm_delete_selected_rows(self) -> bool:
        if self._inline_edit_row_id is not None:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return False
        row_indices = self._selected_row_indices()
        if not row_indices:
            return False
        self._confirm_delete_rows(row_indices)
        return True

    def _confirm_delete_rows(self, row_indices: list[int]) -> None:
        normalized_indices = sorted({int(row_index) for row_index in row_indices if 0 <= int(row_index) < len(self._rows_data)})
        if not normalized_indices:
            return
        rows = [self._rows_data[row_index] for row_index in normalized_indices]
        confirmed = QMessageBox.question(
            self,
            "Delete Job Log Row" if len(rows) == 1 else "Delete Job Log Rows",
            self._delete_confirmation_message(rows),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        with closing(open_job_log(self._db_path)) as conn:
            delete_job_runs(conn, row_ids=[int(row.get("id", 0) or 0) for row in rows])
        self.refresh_rows(selected_row_index=normalized_indices[0], force=True)

    def refresh_rows(
        self,
        selected_row_id: int | None = None,
        *,
        selected_row_index: int | None = None,
        force: bool = False,
    ) -> None:
        if self._inline_edit_row_id is not None and not force:
            QMessageBox.information(self, "Job Log", "Finish editing the current row first.")
            return
        if force:
            self._clear_inline_edit_state()
        self.table.setRowCount(0)
        self._rows_data = []
        with closing(open_job_log(self._db_path)) as conn:
            rows = list_job_runs(conn, limit=1000)
        for row in rows:
            row_data = {key: row[key] for key in row.keys()}
            self._rows_data.append(row_data)
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self._render_display_row(row_idx, row_data)
        self._refresh_action_widgets()
        self._apply_column_widths()
        selected_index: int | None = None
        if selected_row_id is not None:
            selected_index = self._row_index_for_row_id(int(selected_row_id))
        elif selected_row_index is not None and self.table.rowCount() > 0:
            selected_index = min(max(int(selected_row_index), 0), self.table.rowCount() - 1)
        if selected_index is not None:
            self.table.selectRow(selected_index)
        self._refresh_action_state()

    def _refresh_action_state(self) -> None:
        if self._inline_edit_row_id is not None and not self._selection_guard_active:
            edit_row_index = self._row_index_for_row_id(self._inline_edit_row_id)
            if edit_row_index is not None and self._selected_row_indices() != [edit_row_index]:
                self._selection_guard_active = True
                self.table.clearSelection()
                self.table.selectRow(edit_row_index)
                self._selection_guard_active = False
        is_editing = self._inline_edit_row_id is not None
        selection_count = len(self._selected_row_indices())
        self.add_btn.setEnabled(not is_editing)
        self.refresh_btn.setEnabled(not is_editing)
        self.columns_btn.setEnabled(not is_editing)
        self.delete_selected_btn.setEnabled(not is_editing and selection_count > 0)
        self.honorarios_btn.setEnabled(not is_editing and selection_count == 1 and self._selected_row_data() is not None)

    def _selected_row_data(self) -> dict[str, object] | None:
        selected_rows = self._selected_row_indices()
        if len(selected_rows) != 1:
            return None
        row = selected_rows[0]
        return self._rows_data[row]

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if (
            event.key() == Qt.Key.Key_Delete
            and self._inline_edit_row_id is None
            and QApplication.focusWidget() in {self.table, self.table.viewport()}
            and self._confirm_delete_selected_rows()
        ):
            event.accept()
            return
        super().keyPressEvent(event)

    def _offer_gmail_draft_for_honorarios(
        self,
        row: dict[str, object],
        honorarios_docx: Path,
        honorarios_pdf: Path | None,
        profile: UserProfile,
    ) -> None:
        court_email = str(row.get("court_email", "") or "").strip()
        if not court_email:
            QMessageBox.information(
                self,
                "Gmail draft",
                "Court Email is missing for this Job Log entry. The Gmail draft was not created.",
            )
            return
        if honorarios_pdf is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                "The honorários PDF is unavailable for this export. Gmail draft creation requires the PDF.",
            )
            return
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=str(self._gui_settings.get("gmail_gog_path", "") or ""),
            configured_account_email=str(self._gui_settings.get("gmail_account_email", "") or ""),
        )
        if not prereqs.ready or prereqs.gog_path is None or prereqs.account_email is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                f"{prereqs.message}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Gmail draft",
            f"Criar rascunho no Gmail para {court_email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        translation_docx = self._historical_translation_docx_path(row, honorarios_docx=honorarios_docx)
        if translation_docx is None:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar DOCX traduzido",
                str(honorarios_docx.expanduser().resolve().parent),
                "Word Document (*.docx)",
            )
            if not selected:
                return
            translation_docx = Path(selected).expanduser().resolve()
            self._persist_historical_translation_docx(row, translation_docx)
        try:
            validate_translated_docx_artifacts_for_gmail_draft(
                translated_docxs=(translation_docx,),
                honorarios_pdf=honorarios_pdf,
            )
            request = build_honorarios_gmail_request(
                gog_path=prereqs.gog_path,
                account_email=prereqs.account_email,
                to_email=court_email,
                case_number=str(row.get("case_number", "") or "").strip(),
                translation_docx=translation_docx,
                honorarios_pdf=honorarios_pdf,
                profile=profile,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Gmail draft", str(exc))
            return
        result = create_gmail_draft_via_gog(request)
        if not result.ok:
            details = result.stderr or result.stdout or result.message
            QMessageBox.critical(
                self,
                "Gmail draft",
                "Failed to create Gmail draft.\n\n"
                f"{details}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        open_gmail = QMessageBox.question(
            self,
            "Gmail draft",
            "Gmail draft created successfully. Abrir Gmail?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if open_gmail == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(GMAIL_DRAFTS_URL))

    def _offer_gmail_draft_for_interpretation_honorarios(
        self,
        row: dict[str, object],
        honorarios_pdf: Path | None,
        profile: UserProfile,
    ) -> None:
        court_email = str(row.get("court_email", "") or "").strip()
        if not court_email:
            QMessageBox.information(
                self,
                "Gmail draft",
                "Court Email is missing for this Job Log entry. The Gmail draft was not created.",
            )
            return
        if honorarios_pdf is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                "The honorários PDF is unavailable for this export. Gmail draft creation requires the PDF.",
            )
            return
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=str(self._gui_settings.get("gmail_gog_path", "") or ""),
            configured_account_email=str(self._gui_settings.get("gmail_account_email", "") or ""),
        )
        if not prereqs.ready or prereqs.gog_path is None or prereqs.account_email is None:
            QMessageBox.warning(
                self,
                "Gmail draft",
                f"{prereqs.message}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Gmail draft",
            f"Criar rascunho no Gmail para {court_email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            request = build_manual_interpretation_gmail_request(
                gog_path=prereqs.gog_path,
                account_email=prereqs.account_email,
                to_email=court_email,
                case_number=str(row.get("case_number", "") or "").strip(),
                honorarios_pdf=honorarios_pdf,
                profile=profile,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Gmail draft", str(exc))
            return
        result = create_gmail_draft_via_gog(request)
        if not result.ok:
            details = result.stderr or result.stdout or result.message
            QMessageBox.critical(
                self,
                "Gmail draft",
                "Failed to create Gmail draft.\n\n"
                f"{details}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            return
        open_gmail = QMessageBox.question(
            self,
            "Gmail draft",
            "Gmail draft created successfully. Abrir Gmail?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if open_gmail == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(GMAIL_DRAFTS_URL))

    def _historical_translation_docx_path(
        self,
        row: dict[str, object],
        *,
        honorarios_docx: Path | None = None,
    ) -> Path | None:
        for key in ("output_docx_path", "partial_docx_path"):
            raw = str(row.get(key, "") or "").strip()
            if raw == "":
                continue
            candidate = Path(raw).expanduser().resolve()
            if candidate.exists():
                return candidate
        recovered = self._recover_historical_translation_docx_path(row, honorarios_docx=honorarios_docx)
        if recovered is not None:
            self._persist_historical_translation_docx(row, recovered)
            return recovered
        return None

    def _recover_historical_translation_docx_path(
        self,
        row: dict[str, object],
        *,
        honorarios_docx: Path | None = None,
    ) -> Path | None:
        run_id = str(row.get("run_id", "") or "").strip()
        if run_id == "":
            return None

        ignored_path = honorarios_docx.expanduser().resolve() if honorarios_docx is not None else None
        search_roots: list[Path] = []
        if honorarios_docx is not None:
            search_roots.append(honorarios_docx.expanduser().resolve().parent)
        search_roots.extend((_default_downloads_dir(), _default_documents_dir()))

        unique_roots: list[Path] = []
        seen_roots: set[Path] = set()
        for root in search_roots:
            resolved_root = root.expanduser().resolve()
            if resolved_root in seen_roots:
                continue
            seen_roots.add(resolved_root)
            unique_roots.append(resolved_root)

        final_matches: list[Path] = []
        partial_matches: list[Path] = []
        final_suffix = f"_{run_id}.docx".lower()
        partial_suffix = f"_{run_id}_partial.docx".lower()

        for root in unique_roots:
            if not root.exists() or not root.is_dir():
                continue
            for candidate in root.glob("*.docx"):
                resolved_candidate = candidate.expanduser().resolve()
                if ignored_path is not None and resolved_candidate == ignored_path:
                    continue
                name_lower = resolved_candidate.name.lower()
                if name_lower.endswith(partial_suffix):
                    partial_matches.append(resolved_candidate)
                elif name_lower.endswith(final_suffix):
                    final_matches.append(resolved_candidate)

        if len(final_matches) == 1:
            return final_matches[0]
        if len(final_matches) > 1:
            return None
        if len(partial_matches) == 1:
            return partial_matches[0]
        return None

    def _persist_historical_translation_docx(self, row: dict[str, object], translation_docx: Path) -> None:
        row_id = row.get("id")
        if row_id is None:
            return
        resolved = translation_docx.expanduser().resolve()
        path_key = "partial_docx_path" if resolved.name.lower().endswith("_partial.docx") else "output_docx_path"
        with closing(open_job_log(self._db_path)) as conn:
            update_job_run_output_paths(
                conn,
                row_id=int(row_id),
                output_docx_path=str(resolved) if path_key == "output_docx_path" else None,
                partial_docx_path=str(resolved) if path_key == "partial_docx_path" else None,
            )
        row[path_key] = str(resolved)

    def _open_honorarios_dialog(self) -> None:
        row = self._selected_row_data()
        if row is None:
            QMessageBox.information(self, "Requerimento de Honorários", "Select one Job Log row first.")
            return
        profile = _current_primary_profile()
        if _is_interpretation_job_type(str(row.get("job_type", "") or "").strip()):
            draft = build_interpretation_honorarios_draft(
                case_number=str(row.get("case_number", "") or "").strip(),
                case_entity=str(row.get("case_entity", "") or "").strip(),
                case_city=str(row.get("case_city", "") or "").strip(),
                service_date=str(row.get("service_date", "") or "").strip(),
                service_entity=str(row.get("service_entity", "") or "").strip(),
                service_city=str(row.get("service_city", "") or "").strip(),
                use_service_location_in_honorarios=_coerce_joblog_bool(
                    row.get("use_service_location_in_honorarios"),
                    default=False,
                ),
                include_transport_sentence_in_honorarios=_coerce_joblog_bool(
                    row.get("include_transport_sentence_in_honorarios"),
                    default=True,
                ),
                travel_km_outbound=_coerce_joblog_float(row.get("travel_km_outbound")),
                travel_km_return=_coerce_joblog_float(row.get("travel_km_return")),
                recipient_block=default_interpretation_recipient_block(
                    str(row.get("case_entity", "") or "").strip(),
                    str(row.get("case_city", "") or "").strip(),
                ),
                profile=profile,
            )
        else:
            try:
                word_count = int(str(row.get("word_count", "") or "0").strip())
            except ValueError:
                word_count = 0
            draft = build_honorarios_draft(
                case_number=str(row.get("case_number", "") or "").strip(),
                word_count=word_count,
                case_entity=str(row.get("case_entity", "") or "").strip(),
                case_city=str(row.get("case_city", "") or "").strip(),
                profile=profile,
            )
        dialog = QtHonorariosExportDialog(
            parent=self,
            draft=draft,
            default_directory=_default_documents_dir(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_path is not None:
            generated_draft = getattr(dialog, "generated_draft", None)
            selected_profile = generated_draft.profile if generated_draft is not None else profile
            final_draft = generated_draft or draft
            saved_pdf_path = getattr(dialog, "saved_pdf_path", None)
            pdf_unavailable_explained = bool(getattr(dialog, "pdf_unavailable_explained", False))
            if final_draft.kind == HonorariosKind.TRANSLATION:
                if saved_pdf_path is not None or not pdf_unavailable_explained:
                    self._offer_gmail_draft_for_honorarios(
                        row,
                        dialog.saved_path,
                        saved_pdf_path,
                        selected_profile,
                    )
            elif final_draft.kind == HonorariosKind.INTERPRETATION:
                include_transport_sentence = bool(final_draft.include_transport_sentence_in_honorarios)
                current_include_transport_sentence = _coerce_joblog_bool(
                    row.get("include_transport_sentence_in_honorarios"),
                    default=True,
                )
                if include_transport_sentence != current_include_transport_sentence:
                    row_id = row.get("id")
                    if row_id is not None:
                        with closing(open_job_log(self._db_path)) as conn:
                            update_job_run(
                                conn,
                                row_id=int(row_id),
                                values={
                                    "include_transport_sentence_in_honorarios": 1
                                    if include_transport_sentence
                                    else 0,
                                },
                            )
                    row["include_transport_sentence_in_honorarios"] = 1 if include_transport_sentence else 0
                if saved_pdf_path is not None or not pdf_unavailable_explained:
                    self._offer_gmail_draft_for_interpretation_honorarios(
                        row,
                        saved_pdf_path,
                        selected_profile,
                    )

    def _open_columns_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Visible Columns")
        layout = QVBoxLayout(dialog)
        checks: dict[str, QCheckBox] = {}
        for col in JOBLOG_COLUMNS:
            check = QCheckBox(JOBLOG_COLUMN_LABELS[col], dialog)
            check.setChecked(col in self._visible_columns)
            checks[col] = check
            layout.addWidget(check)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel", dialog)
        apply_btn = QPushButton("Apply", dialog)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(apply_btn)
        layout.addLayout(button_row)
        cancel_btn.clicked.connect(dialog.reject)

        def apply_columns() -> None:
            selected = [col for col in JOBLOG_COLUMNS if checks[col].isChecked()]
            selected = update_joblog_visible_columns(selected)
            if not selected:
                QMessageBox.warning(dialog, "Columns", "Select at least one column.")
                return
            self._visible_columns = selected
            self._settings["joblog_visible_columns"] = list(selected)
            save_joblog_settings({"joblog_visible_columns": list(selected)})
            self._apply_visible_columns()
            self._apply_column_widths()
            dialog.accept()

        apply_btn.clicked.connect(apply_columns)
        dialog.exec()


REVIEW_QUEUE_COLUMNS = [
    "page_number",
    "score",
    "status",
    "reasons",
    "recommended_action",
]

REVIEW_QUEUE_COLUMN_LABELS = {
    "page_number": "Page",
    "score": "Score",
    "status": "Status",
    "reasons": "Reasons",
    "recommended_action": "Action",
}


def _coerce_queue_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return default
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return default
    return default


def _coerce_queue_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _coerce_queue_text(value: object) -> str:
    return str(value or "").strip()


def normalize_review_queue_entries(review_queue: object) -> list[dict[str, object]]:
    if not isinstance(review_queue, list):
        return []
    entries: list[dict[str, object]] = []
    for raw_item in review_queue:
        if not isinstance(raw_item, dict):
            continue
        page_number = _coerce_queue_int(raw_item.get("page_number", 0), 0)
        if page_number <= 0:
            continue
        reasons_raw = raw_item.get("reasons", [])
        reasons: list[str] = []
        if isinstance(reasons_raw, list):
            for reason in reasons_raw:
                reason_text = _coerce_queue_text(reason)
                if reason_text:
                    reasons.append(reason_text)
        entries.append(
            {
                "page_number": int(page_number),
                "score": round(min(1.0, max(0.0, _coerce_queue_float(raw_item.get("score", 0.0), 0.0))), 4),
                "status": _coerce_queue_text(raw_item.get("status", "")),
                "reasons": reasons,
                "recommended_action": _coerce_queue_text(raw_item.get("recommended_action", "")),
                "retry_reason": _coerce_queue_text(raw_item.get("retry_reason", "")),
            }
        )
    entries.sort(
        key=lambda item: (
            -_coerce_queue_float(item.get("score", 0.0), 0.0),
            _coerce_queue_int(item.get("page_number", 0), 0),
        )
    )
    return entries


def build_review_queue_markdown(entries: list[dict[str, object]]) -> str:
    lines: list[str] = []
    lines.append("# Review Queue")
    lines.append("")
    if not entries:
        lines.append("No flagged pages were found for the current run.")
        lines.append("")
        return "\n".join(lines)
    lines.append("| Page | Score | Status | Action | Reasons |")
    lines.append("|------|-------|--------|--------|---------|")
    for entry in entries:
        reasons = entry.get("reasons", [])
        reason_text = " | ".join(reasons) if isinstance(reasons, list) else str(reasons or "")
        lines.append(
            f"| {entry.get('page_number', '')} | {entry.get('score', '')} "
            f"| {entry.get('status', '') or '-'} | {entry.get('recommended_action', '') or '-'} "
            f"| {reason_text or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


class QtReviewQueueDialog(QDialog):
    """Review queue panel for flagged pages from latest run summary."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        review_queue: object,
        run_dir: Path | None,
        run_summary_path: Path | None,
        open_path_callback: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Queue")
        self.setMinimumSize(720, 420)
        self._entries = normalize_review_queue_entries(review_queue)
        self._run_dir = run_dir.expanduser().resolve() if isinstance(run_dir, Path) else None
        self._run_summary_path = (
            run_summary_path.expanduser().resolve() if isinstance(run_summary_path, Path) else None
        )
        self._open_path_callback = open_path_callback
        self._build_ui()
        self._populate_table()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="table",
            preferred_size=QSize(980, 560),
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.table = QTableWidget(0, len(REVIEW_QUEUE_COLUMNS), self)
        self.table.setHorizontalHeaderLabels([REVIEW_QUEUE_COLUMN_LABELS[col] for col in REVIEW_QUEUE_COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("Export...")
        self.copy_btn = QPushButton("Copy list")
        self.open_page_btn = QPushButton("Open page file")
        self.open_page_btn.setObjectName("PrimaryButton")
        self.close_btn = QPushButton("Close")
        actions.addWidget(self.export_btn)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.open_page_btn)
        actions.addStretch(1)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.export_btn.clicked.connect(self._export_queue)
        self.copy_btn.clicked.connect(self._copy_queue)
        self.open_page_btn.clicked.connect(self._open_selected_page_file)
        self.close_btn.clicked.connect(self.accept)

    def _populate_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for entry in self._entries:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            reasons = entry.get("reasons", [])
            reason_text = " | ".join(reasons) if isinstance(reasons, list) else str(reasons or "")
            values = {
                "page_number": str(int(_coerce_queue_int(entry.get("page_number", 0), 0))),
                "score": f"{_coerce_queue_float(entry.get('score', 0.0), 0.0):.4f}",
                "status": _coerce_queue_text(entry.get("status", "")),
                "reasons": reason_text,
                "recommended_action": _coerce_queue_text(entry.get("recommended_action", "")),
            }
            for col_idx, col in enumerate(REVIEW_QUEUE_COLUMNS):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(values[col]))
        self.table.setSortingEnabled(True)
        if self.table.rowCount() > 0:
            self.table.sortItems(1, Qt.SortOrder.DescendingOrder)
            self.summary_label.setText(f"Flagged pages: {self.table.rowCount()} (sorted by score).")
        else:
            self.summary_label.setText("No flagged pages found for this run.")

    def _selected_entry(self) -> dict[str, object] | None:
        row = self.table.currentRow()
        if row < 0:
            selection_model = self.table.selectionModel()
            if selection_model is not None:
                selected_rows = selection_model.selectedRows()
                if selected_rows:
                    row = int(selected_rows[0].row())
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _copy_queue(self) -> None:
        markdown = build_review_queue_markdown(self._entries)
        QApplication.clipboard().setText(markdown)
        QMessageBox.information(self, "Review Queue", "Review queue copied to clipboard.")

    def _export_queue(self) -> None:
        if self._run_summary_path is None:
            QMessageBox.warning(self, "Review Queue", "Run summary path is unavailable for export.")
            return
        default_base = self._run_summary_path.parent / "review_queue"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Export review queue",
            str(default_base),
            "All Files (*.*)",
        )
        if not selected:
            return
        try:
            csv_path, markdown_path, count = export_review_queue(
                self._run_summary_path,
                Path(selected),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Review Queue", f"Failed to export review queue:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Review Queue",
            f"Exported {count} item(s).\n\nCSV: {csv_path}\nMarkdown: {markdown_path}",
        )

    def _open_selected_page_file(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Review Queue", "Select one row first.")
            return
        if self._run_dir is None:
            QMessageBox.warning(self, "Review Queue", "Run folder is unavailable.")
            return
        page_number = _coerce_queue_int(entry.get("page_number", 0), 0)
        page_file = self._run_dir / "pages" / f"page_{page_number:04d}.txt"
        if not page_file.exists():
            QMessageBox.warning(self, "Review Queue", f"Page file not found:\n{page_file}")
            return
        if self._open_path_callback is not None:
            self._open_path_callback(page_file)
            return
        QMessageBox.information(self, "Review Queue", f"Page file:\n{page_file}")


_ATTACHMENT_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def _is_image_attachment(candidate: GmailAttachmentCandidate) -> bool:
    suffix = Path(candidate.filename).suffix.strip().lower()
    return candidate.mime_type.strip().lower().startswith("image/") or suffix in _ATTACHMENT_IMAGE_SUFFIXES


class _GmailPreviewPageCard(QFrame):
    """Single page card used by the scrolling Gmail preview dialog."""

    _FALLBACK_PAGE_RATIO = 1.41421356237

    def __init__(
        self,
        *,
        page_number: int,
        page_size: tuple[float, float] | None,
        select_page_callback: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.page_number = page_number
        self._original_pixmap: QPixmap | None = None
        self._page_size = self._normalize_page_size(page_size)
        self._target_width = 320
        self.setObjectName("ShellPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel(f"Page {page_number}")
        self.use_page_btn = QPushButton("Start from this page")
        self.use_page_btn.setObjectName("PrimaryButton")
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.use_page_btn)
        root.addLayout(header)

        self.state_label = QLabel("")
        self.state_label.setWordWrap(True)
        self.state_label.setMinimumHeight(max(28, self.fontMetrics().lineSpacing() * 2))
        root.addWidget(self.state_label)

        self.preview_label = QLabel("")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.preview_label.setWordWrap(True)
        root.addWidget(self.preview_label)

        self.use_page_btn.clicked.connect(lambda: select_page_callback(self.page_number))
        self.set_idle_placeholder()

    @staticmethod
    def _normalize_page_size(page_size: tuple[float, float] | None) -> tuple[float, float] | None:
        if not isinstance(page_size, tuple) or len(page_size) != 2:
            return None
        width, height = page_size
        try:
            resolved_width = max(1.0, float(width))
            resolved_height = max(1.0, float(height))
        except (TypeError, ValueError):
            return None
        return resolved_width, resolved_height

    def _reserved_ratio(self) -> float:
        if self._page_size is None:
            return self._FALLBACK_PAGE_RATIO
        width, height = self._page_size
        return max(0.75, min(2.5, height / max(1.0, width)))

    def _reserved_height_for_width(self, target_width: int) -> int:
        width = max(320, int(target_width))
        return max(240, int(round(width * self._reserved_ratio())))

    def _apply_reserved_height(self, target_width: int) -> None:
        self._target_width = max(320, int(target_width))
        _set_fixed_height_if_needed(self.preview_label, self._reserved_height_for_width(self._target_width))

    def _set_state_text(self, message: str) -> None:
        self.state_label.setText(message if message else " ")

    def set_idle_placeholder(self) -> None:
        self._original_pixmap = None
        self._set_state_text("Preview will load when visible.")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("")
        self._apply_reserved_height(self._target_width)

    def set_loading(self) -> None:
        self._set_state_text("Loading preview...")
        if self._original_pixmap is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("")
        self._apply_reserved_height(self._target_width)

    def set_error(self, message: str) -> None:
        self._original_pixmap = None
        self._set_state_text(message)
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("")
        self._apply_reserved_height(self._target_width)

    def set_pixmap(self, pixmap: QPixmap, target_width: int) -> None:
        self._original_pixmap = pixmap
        self._set_state_text("")
        self.preview_label.setText("")
        self.update_scaled_pixmap(target_width)

    def clear_cached_pixmap(self) -> None:
        self._original_pixmap = None
        self._set_state_text("Preview will reload when visible.")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("")
        self._apply_reserved_height(self._target_width)

    def update_scaled_pixmap(self, target_width: int) -> None:
        self._apply_reserved_height(target_width)
        if self._original_pixmap is None:
            return
        width = self._target_width
        pixmap = self._original_pixmap
        if pixmap.width() != width:
            display = pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        else:
            display = pixmap
        self.preview_label.setPixmap(display)
        _set_fixed_height_if_needed(self.preview_label, display.height())


class QtGmailAttachmentPreviewDialog(QDialog):
    """Preview a Gmail attachment before batch preparation."""

    _PAGE_PREFETCH_BUFFER = 1
    _PAGE_RENDER_CONCURRENCY = 1
    _PAGE_CACHE_LIMIT = 16
    _PAGE_REFRESH_DEBOUNCE_MS = 75

    def __init__(
        self,
        *,
        parent: QWidget | None,
        attachment: GmailAttachmentCandidate,
        gog_path: Path,
        account_email: str,
        preview_dir: Path,
        initial_start_page: int,
        cached_path: Path | None = None,
        known_page_count: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Attachment Preview")
        self.setMinimumSize(720, 520)
        self._attachment = attachment
        self._gog_path = gog_path.expanduser().resolve()
        self._account_email = account_email.strip()
        self._preview_dir = preview_dir.expanduser().resolve()
        self._local_path = cached_path.expanduser().resolve() if isinstance(cached_path, Path) else None
        self._page_count = int(known_page_count) if isinstance(known_page_count, int) and known_page_count > 0 else None
        self._is_image = _is_image_attachment(self._attachment)
        self._current_page = 1 if self._is_image else max(1, int(initial_start_page))
        self._closing = False
        self._bootstrap_loading = False
        self._bootstrap_complete = False
        self._bootstrap_thread: QThread | None = None
        self._bootstrap_worker: GmailAttachmentPreviewBootstrapWorker | None = None
        self._page_threads: dict[int, QThread] = {}
        self._page_workers: dict[int, GmailAttachmentPreviewPageWorker] = {}
        self._page_cards: dict[int, _GmailPreviewPageCard] = {}
        self._page_sizes: tuple[tuple[float, float], ...] = ()
        self._page_cache: OrderedDict[int, QPixmap] = OrderedDict()
        self._page_errors: dict[int, str] = {}
        self._queued_pages: list[int] = []
        self._queued_page_set: set[int] = set()
        self._inflight_pages: set[int] = set()
        self._visible_refresh_timer = QTimer(self)
        self._visible_refresh_timer.setSingleShot(True)
        self._visible_refresh_timer.setInterval(self._PAGE_REFRESH_DEBOUNCE_MS)
        self._visible_refresh_timer.timeout.connect(self._refresh_visible_pages)
        self._scaled_preview_timer = QTimer(self)
        self._scaled_preview_timer.setSingleShot(True)
        self._scaled_preview_timer.setInterval(60)
        self._scaled_preview_timer.timeout.connect(self._refresh_scaled_preview)
        self._image_pixmap: QPixmap | None = None
        self._image_display_width: int | None = None
        self.selected_start_page: int | None = None
        self.resolved_local_path: Path | None = self._local_path
        self.resolved_page_count: int | None = self._page_count
        self._build_ui()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="preview",
            preferred_size=QSize(980, 760),
        )
        QTimer.singleShot(0, self._start_bootstrap)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.header_label = QLabel(f"Attachment: {self._attachment.filename}")
        self.header_label.setWordWrap(True)
        root.addWidget(self.header_label)

        self.status_label = QLabel("Loading preview...")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.jump_widget = QWidget(self)
        jump_layout = QHBoxLayout(self.jump_widget)
        jump_layout.setContentsMargins(0, 0, 0, 0)
        jump_layout.setSpacing(8)
        self.jump_label = QLabel("Go to page")
        self.jump_spin = NoWheelSpinBox()
        self.jump_spin.setMinimum(1)
        self.jump_spin.setMaximum(max(1, self._page_count) if isinstance(self._page_count, int) else 1)
        self.jump_spin.setValue(self._current_page)
        self.jump_btn = QPushButton("Go")
        jump_layout.addWidget(self.jump_label)
        jump_layout.addWidget(self.jump_spin)
        jump_layout.addWidget(self.jump_btn)
        jump_layout.addStretch(1)
        root.addWidget(self.jump_widget)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("DialogScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_content = QWidget(self.scroll_area)
        self.preview_content.setObjectName("DialogScrollContent")
        self.preview_layout = QVBoxLayout(self.preview_content)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(12)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview_label = QLabel("Loading preview...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.preview_label.setWordWrap(True)
        self.preview_layout.addWidget(self.preview_label)
        self.scroll_area.setWidget(self.preview_content)
        root.addWidget(self.scroll_area, 1)

        actions = QHBoxLayout()
        self.use_page_btn = QPushButton("Start from this page")
        self.use_page_btn.setObjectName("PrimaryButton")
        self.close_btn = QPushButton("Close")
        actions.addStretch(1)
        actions.addWidget(self.use_page_btn)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.jump_btn.clicked.connect(self._jump_to_page)
        self.use_page_btn.clicked.connect(self._use_current_page)
        self.close_btn.clicked.connect(self.reject)
        self.scroll_area.verticalScrollBar().valueChanged.connect(lambda _value: self._schedule_visible_page_refresh())
        self.scroll_area.viewport().installEventFilter(self)
        self._refresh_controls()

    def done(self, result: int) -> None:
        self._closing = True
        self._visible_refresh_timer.stop()
        self._scaled_preview_timer.stop()
        bootstrap_thread = self._bootstrap_thread
        if bootstrap_thread is not None and bootstrap_thread.isRunning():
            bootstrap_thread.quit()
            bootstrap_thread.wait(1000)
        for thread in list(self._page_threads.values()):
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)
        self._bootstrap_thread = None
        self._bootstrap_worker = None
        self._page_threads.clear()
        self._page_workers.clear()
        super().done(result)

    def eventFilter(self, watched: QObject, event: object) -> bool:
        if watched is self.scroll_area.viewport() and isinstance(event, QEvent):
            if event.type() in {QEvent.Type.Resize, QEvent.Type.Show}:
                self._schedule_scaled_preview_refresh()
                self._schedule_visible_page_refresh()
        return super().eventFilter(watched, event)

    def _refresh_controls(self) -> None:
        jump_enabled = (
            not self._is_image
            and self._bootstrap_complete
            and isinstance(self.resolved_page_count, int)
            and self.resolved_page_count > 0
        )
        self.jump_widget.setVisible(not self._is_image)
        self.jump_spin.setEnabled(jump_enabled)
        self.jump_btn.setEnabled(jump_enabled)
        self.use_page_btn.setVisible(self._is_image)
        self.use_page_btn.setEnabled(self._is_image and self._bootstrap_complete and self._image_pixmap is not None)

    def _set_preview_message(self, message: str) -> None:
        self._clear_preview_layout()
        self.preview_label = QLabel(message)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.preview_label.setWordWrap(True)
        self.preview_layout.addWidget(self.preview_label)
        self._image_display_width = None

    def _clear_preview_layout(self) -> None:
        while self.preview_layout.count() > 0:
            item = self.preview_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._page_cards = {}

    def _start_bootstrap(self) -> None:
        if self._closing or self._bootstrap_loading or self._bootstrap_complete:
            return
        self._bootstrap_loading = True
        self.status_label.setText("Loading preview...")
        self._set_preview_message("Loading preview...")
        self._refresh_controls()

        thread = QThread(self)
        worker = GmailAttachmentPreviewBootstrapWorker(
            gog_path=self._gog_path,
            account_email=self._account_email,
            attachment=self._attachment,
            preview_dir=self._preview_dir,
            local_path=self._local_path,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_bootstrap_loaded)
        worker.error.connect(self._on_bootstrap_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_bootstrap_worker)
        self._bootstrap_thread = thread
        self._bootstrap_worker = worker
        thread.start()

    def _cleanup_bootstrap_worker(self) -> None:
        worker = self._bootstrap_worker
        thread = self._bootstrap_thread
        self._bootstrap_worker = None
        self._bootstrap_thread = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def _on_bootstrap_loaded(self, result_obj: object) -> None:
        self._bootstrap_loading = False
        if not isinstance(result_obj, GmailAttachmentPreviewBootstrapResult):
            self._on_bootstrap_error("Attachment preview returned an invalid result.")
            return
        result = result_obj
        self._local_path = result.local_path
        self.resolved_local_path = result.local_path
        self._page_count = max(1, int(result.page_count))
        self._page_sizes = tuple(result.page_sizes) if len(result.page_sizes) == self._page_count else ()
        self.resolved_page_count = self._page_count
        self._current_page = min(max(1, self._current_page), self._page_count)
        self._bootstrap_complete = True
        self.jump_spin.setMaximum(self._page_count)
        self.jump_spin.blockSignals(True)
        self.jump_spin.setValue(self._current_page)
        self.jump_spin.blockSignals(False)

        if self._is_image:
            self.status_label.setText("Single-image attachment preview.")
            self._set_preview_message("Loading preview...")
            self._queue_page_render(1)
            self._start_next_page_workers()
        else:
            self.status_label.setText(
                f"Page 1 is the default. Scroll to inspect {self._page_count} page(s) and click "
                f"'Start from this page' only when you want to skip earlier pages."
            )
            self._build_pdf_page_cards()
            QTimer.singleShot(0, self._scroll_to_initial_page)
        self._refresh_controls()

    def _on_bootstrap_error(self, message: str) -> None:
        self._bootstrap_loading = False
        self.status_label.setText("Preview unavailable.")
        self._set_preview_message(message)
        self._refresh_controls()
        QMessageBox.warning(self, "Attachment Preview", message)

    def _build_pdf_page_cards(self) -> None:
        self._clear_preview_layout()
        target_width = self._target_page_width()
        for page_number in range(1, max(1, self._page_count) + 1):
            card = _GmailPreviewPageCard(
                page_number=page_number,
                page_size=self._page_sizes[page_number - 1] if page_number - 1 < len(self._page_sizes) else None,
                select_page_callback=self._select_pdf_page,
                parent=self.preview_content,
            )
            if page_number in self._page_cache:
                card.set_pixmap(self._page_cache[page_number], target_width)
            elif page_number in self._page_errors:
                card.set_error(self._page_errors[page_number])
            else:
                card.set_idle_placeholder()
            card.update_scaled_pixmap(target_width)
            self.preview_layout.addWidget(card)
            self._page_cards[page_number] = card
        self.preview_layout.addStretch(1)

    def _scroll_to_initial_page(self) -> None:
        self._scroll_to_page(self._current_page)

    def _target_page_width(self) -> int:
        return max(320, self.scroll_area.viewport().width() - 64)

    def _refresh_scaled_preview(self) -> None:
        target_width = self._target_page_width()
        for card in self._page_cards.values():
            card.update_scaled_pixmap(target_width)
        if self._is_image and self._image_pixmap is not None:
            pixmap = self._image_pixmap
            if self._image_display_width == target_width:
                return
            if pixmap.width() != target_width:
                display = pixmap.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)
            else:
                display = pixmap
            self.preview_label.setPixmap(display)
            _set_fixed_height_if_needed(self.preview_label, display.height())
            self._image_display_width = target_width

    def _schedule_scaled_preview_refresh(self) -> None:
        if self._closing or not self._bootstrap_complete:
            return
        self._scaled_preview_timer.start()

    def _scroll_to_page(self, page_number: int) -> None:
        if self._is_image:
            return
        page = min(max(1, int(page_number)), max(1, self._page_count or 1))
        self._current_page = page
        self.jump_spin.blockSignals(True)
        self.jump_spin.setValue(page)
        self.jump_spin.blockSignals(False)
        card = self._page_cards.get(page)
        if card is None:
            return
        self.scroll_area.verticalScrollBar().setValue(max(0, card.y() - 8))
        self._schedule_visible_page_refresh()

    def _jump_to_page(self) -> None:
        if self._is_image or not self._bootstrap_complete:
            return
        self._scroll_to_page(int(self.jump_spin.value()))

    def _select_pdf_page(self, page_number: int) -> None:
        self.selected_start_page = max(1, int(page_number))
        self.accept()

    def _use_current_page(self) -> None:
        self.selected_start_page = 1 if self._is_image else max(1, self._current_page)
        self.accept()

    def _schedule_visible_page_refresh(self) -> None:
        if self._closing or self._is_image or not self._bootstrap_complete:
            return
        self._visible_refresh_timer.start()

    def _refresh_visible_pages(self) -> None:
        if self._closing or self._is_image or not self._bootstrap_complete:
            return
        desired_pages = self._desired_pages_for_render()
        for page_number in desired_pages:
            self._queue_page_render(page_number)
        self._start_next_page_workers()
        self._trim_page_cache(protected_pages=set(desired_pages))

    def _desired_pages_for_render(self) -> list[int]:
        if self._page_count is None or self._page_count <= 0:
            return []
        scrollbar = self.scroll_area.verticalScrollBar()
        visible_top = scrollbar.value()
        visible_bottom = visible_top + self.scroll_area.viewport().height()
        visible_pages: list[int] = []
        for page_number, card in self._page_cards.items():
            top = card.y()
            bottom = top + card.height()
            if bottom >= visible_top and top <= visible_bottom:
                visible_pages.append(page_number)
        if not visible_pages:
            visible_pages = [min(max(1, self._current_page), self._page_count)]
        first_page = max(1, min(visible_pages) - self._PAGE_PREFETCH_BUFFER)
        last_page = min(self._page_count, max(visible_pages) + self._PAGE_PREFETCH_BUFFER)
        return list(range(first_page, last_page + 1))

    def _queue_page_render(self, page_number: int) -> None:
        if self._closing or self._local_path is None or self._page_count is None:
            return
        page = min(max(1, int(page_number)), self._page_count)
        if page in self._page_cache:
            self._page_cache.move_to_end(page)
            return
        if page in self._inflight_pages or page in self._queued_page_set or page in self._page_errors:
            return
        card = self._page_cards.get(page)
        if card is not None:
            card.set_loading()
        self._queued_pages.append(page)
        self._queued_page_set.add(page)

    def _start_next_page_workers(self) -> None:
        if self._closing or self._local_path is None or self._page_count is None:
            return
        while self._queued_pages and len(self._inflight_pages) < self._PAGE_RENDER_CONCURRENCY:
            page = self._queued_pages.pop(0)
            self._queued_page_set.discard(page)
            self._start_page_worker(page)

    def _start_page_worker(self, page_number: int) -> None:
        if self._local_path is None or self._page_count is None:
            return
        thread = QThread(self)
        worker = GmailAttachmentPreviewPageWorker(
            attachment=self._attachment,
            local_path=self._local_path,
            page_count=self._page_count,
            requested_page=page_number,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_page_loaded)
        worker.error.connect(self._on_page_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(lambda _page, _message: thread.quit())
        thread.finished.connect(lambda page=page_number: self._cleanup_page_worker(page))
        self._page_threads[page_number] = thread
        self._page_workers[page_number] = worker
        self._inflight_pages.add(page_number)
        thread.start()

    def _cleanup_page_worker(self, page_number: int) -> None:
        worker = self._page_workers.pop(page_number, None)
        thread = self._page_threads.pop(page_number, None)
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def _on_page_loaded(self, result_obj: object) -> None:
        if not isinstance(result_obj, GmailAttachmentPreviewPageResult):
            self._on_bootstrap_error("Attachment preview returned an invalid page result.")
            return
        result = result_obj
        page_number = int(result.page_number)
        self._inflight_pages.discard(page_number)
        if self._closing:
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(result.image_bytes):
            self._on_page_error(page_number, "Attachment preview image could not be decoded.")
            return

        if self._is_image:
            self._image_pixmap = pixmap
            self._set_preview_message("")
            self.preview_label.setText("")
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.preview_label.setWordWrap(True)
            self._image_display_width = None
            self._refresh_scaled_preview()
            self.status_label.setText("Single-image attachment preview.")
        else:
            self._page_errors.pop(page_number, None)
            self._page_cache[page_number] = pixmap
            self._page_cache.move_to_end(page_number)
            card = self._page_cards.get(page_number)
            if card is not None:
                card.set_pixmap(pixmap, self._target_page_width())
        self._refresh_controls()
        self._start_next_page_workers()
        self._schedule_visible_page_refresh()

    def _on_page_error(self, page_number: int, message: str) -> None:
        self._inflight_pages.discard(int(page_number))
        if self._closing:
            return
        if self._is_image:
            self.status_label.setText("Preview unavailable.")
            self._set_preview_message(message)
            self._refresh_controls()
            QMessageBox.warning(self, "Attachment Preview", message)
            return
        self._page_errors[int(page_number)] = message
        card = self._page_cards.get(int(page_number))
        if card is not None:
            card.set_error(message)
        self.status_label.setText("Some preview pages failed to render.")
        self._refresh_controls()
        self._start_next_page_workers()

    def _trim_page_cache(self, *, protected_pages: set[int]) -> None:
        while len(self._page_cache) > self._PAGE_CACHE_LIMIT:
            order_index = {page: index for index, page in enumerate(self._page_cache.keys())}
            desired_pages = sorted(protected_pages)
            anchor_page = desired_pages[len(desired_pages) // 2] if desired_pages else self._current_page
            eviction_candidates = [
                candidate_page
                for candidate_page in self._page_cache.keys()
                if candidate_page not in protected_pages
            ]
            if not eviction_candidates:
                eviction_candidates = list(self._page_cache.keys())
            victim_page = max(
                eviction_candidates,
                key=lambda candidate_page: (
                    abs(candidate_page - anchor_page),
                    -order_index[candidate_page],
                ),
            )
            self._page_cache.pop(victim_page, None)
            card = self._page_cards.get(victim_page)
            if card is not None and victim_page not in self._inflight_pages:
                card.clear_cached_pixmap()


class QtGmailBatchReviewDialog(QDialog):
    """Review supported Gmail attachments for the exact fetched message."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        message: FetchedGmailMessage,
        gog_path: Path,
        account_email: str,
        target_lang: str,
        default_start_page: int,
        output_dir_text: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gmail Attachment Review")
        self.setMinimumSize(760, 480)
        self._message = message
        self._gog_path = gog_path.expanduser().resolve()
        self._account_email = account_email.strip()
        self._target_lang = target_lang.strip().upper() or "-"
        self._workflow_kind = GMAIL_INTAKE_WORKFLOW_TRANSLATION
        self._default_start_page = 1
        self._output_dir_text = output_dir_text.strip()
        self._page_counts: list[int | None] = [
            1 if _is_image_attachment(attachment) else None
            for attachment in self._message.attachments
        ]
        self._start_pages: list[int] = [
            1 if _is_image_attachment(attachment) else self._default_start_page
            for attachment in self._message.attachments
        ]
        self._preview_cache: dict[str, Path] = {}
        self._preview_tempdir: tempfile.TemporaryDirectory[str] | None = None
        self.selected_attachments: tuple[GmailAttachmentCandidate, ...] = ()
        self.review_result: GmailBatchReviewResult | None = None
        self._build_ui()
        self._populate_table()
        self._on_workflow_changed()
        self._refresh_actions()
        self._refresh_detail_panel()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="table",
            preferred_size=QSize(980, 620),
        )

    def done(self, result: int) -> None:
        if result != QDialog.DialogCode.Accepted:
            self._cleanup_preview_cache()
        super().done(result)

    def _cleanup_preview_cache(self) -> None:
        preview_tempdir = self._preview_tempdir
        self._preview_tempdir = None
        self._preview_cache = {}
        if preview_tempdir is not None:
            preview_tempdir.cleanup()

    def _ensure_preview_dir(self) -> Path:
        if self._preview_tempdir is None:
            self._preview_tempdir = tempfile.TemporaryDirectory(prefix="legalpdf_gmail_preview_")
        return Path(self._preview_tempdir.name).expanduser().resolve()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.summary_card = QFrame(self)
        self.summary_card.setObjectName("ShellPanel")
        summary_layout = QHBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(10)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.output_dir_label = QLabel("")
        self.output_dir_label.setObjectName("MutedLabel")
        self.output_dir_label.setWordWrap(True)
        self.summary_info_btn = build_inline_info_button(
            tooltip="Message details",
            accessible_name="Message details help",
            parent=self.summary_card,
        )
        summary_layout.addWidget(self.summary_label, 1)
        summary_layout.addWidget(self.output_dir_label, 0)
        summary_layout.addWidget(self.summary_info_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.summary_card)

        context_row = QHBoxLayout()
        context_row.setSpacing(8)
        self.workflow_label = QLabel("Workflow")
        self.workflow_combo = NoWheelComboBox()
        self.workflow_combo.setEditable(False)
        self.workflow_combo.addItem("Translation", GMAIL_INTAKE_WORKFLOW_TRANSLATION)
        self.workflow_combo.addItem("Interpretation notice", GMAIL_INTAKE_WORKFLOW_INTERPRETATION)
        self.target_lang_label = QLabel("Language")
        self.target_lang_combo = NoWheelComboBox()
        self.target_lang_combo.setEditable(False)
        supported_langs = [str(lang).strip().upper() for lang in supported_target_langs()]
        self.target_lang_combo.addItems(supported_langs)
        if self._target_lang in supported_langs:
            self.target_lang_combo.setCurrentText(self._target_lang)
        context_row.addWidget(self.workflow_label)
        context_row.addWidget(self.workflow_combo, 0)
        context_row.addSpacing(12)
        context_row.addWidget(self.target_lang_label)
        context_row.addWidget(self.target_lang_combo, 0)
        context_row.addStretch(1)
        root.addLayout(context_row)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["File", "Type", "Size", "Start"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(8)
        self.detail_attachment_label = QLabel("-")
        self.detail_attachment_label.setWordWrap(True)
        self.pages_value_label = QLabel("-")
        self.start_page_label = QLabel("Start page")
        self.start_page_spin = NoWheelSpinBox()
        self.start_page_spin.setMinimum(1)
        self.start_page_spin.setMaximum(9999)
        self.preview_btn = QPushButton("Preview")
        detail_row.addWidget(self.detail_attachment_label, 1)
        detail_row.addWidget(self.pages_value_label)
        detail_row.addWidget(self.start_page_label)
        detail_row.addWidget(self.start_page_spin)
        detail_row.addWidget(self.preview_btn)
        root.addLayout(detail_row)

        actions = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.prepare_btn = QPushButton("Prepare selected attachments")
        self.prepare_btn.setObjectName("PrimaryButton")
        actions.addStretch(1)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.prepare_btn)
        root.addLayout(actions)

        self.table.itemSelectionChanged.connect(self._refresh_actions)
        self.table.currentCellChanged.connect(lambda *_args: self._refresh_detail_panel())
        self.table.itemDoubleClicked.connect(lambda _item: self._open_preview_for_current_row())
        self.start_page_spin.valueChanged.connect(self._update_current_row_start_page)
        self.preview_btn.clicked.connect(self._open_preview_for_current_row)
        self.workflow_combo.currentIndexChanged.connect(self._on_workflow_changed)
        self.cancel_btn.clicked.connect(self.reject)
        self.prepare_btn.clicked.connect(self._accept_selection)

    def _current_workflow_kind(self) -> str:
        return str(self.workflow_combo.currentData() or GMAIL_INTAKE_WORKFLOW_TRANSLATION).strip()

    def _is_interpretation_workflow(self) -> bool:
        return self._current_workflow_kind() == GMAIL_INTAKE_WORKFLOW_INTERPRETATION

    def _summary_subject_text(self) -> str:
        subject = (self._message.subject or "").strip()
        attachment_count = len(self._message.attachments)
        noun = "file" if attachment_count == 1 else "files"
        if subject:
            return f"{subject} | {attachment_count} {noun}"
        return f"{attachment_count} {noun} ready"

    def _output_dir_summary_text(self) -> str:
        if self._output_dir_text == "":
            return "Folder: not set"
        try:
            display = Path(self._output_dir_text).name or self._output_dir_text
        except Exception:  # noqa: BLE001
            display = self._output_dir_text
        return f"Folder: {display}"

    def _refresh_summary_banner(self) -> None:
        attachment_count = len(self._message.attachments)
        workflow_hint = (
            "Choose 1 file for interpretation notice."
            if self._is_interpretation_workflow()
            else "Choose one or more files to prepare."
        )
        self.summary_label.setText(self._summary_subject_text())
        self.summary_label.setToolTip(self._message.subject or "(no subject)")
        self.output_dir_label.setText(self._output_dir_summary_text())
        self.output_dir_label.setToolTip(self._output_dir_text or "(not set yet)")
        self.summary_info_btn.setToolTip(
            "\n".join(
                (
                    f"Sender: {self._message.from_header or '(unknown sender)'}",
                    f"Gmail account: {self._message.account_email}",
                    f"Supported attachments: {attachment_count}",
                    workflow_hint,
                    f"Output folder: {self._output_dir_text or '(not set yet)'}",
                )
            )
        )

    def _populate_table(self) -> None:
        self._refresh_summary_banner()
        self.table.setRowCount(0)
        for attachment in self._message.attachments:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(attachment.filename))
            self.table.setItem(row_idx, 1, QTableWidgetItem(attachment.mime_type))
            self.table.setItem(row_idx, 2, QTableWidgetItem(_format_bytes(attachment.size_bytes)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(self._start_pages[row_idx])))

    def _selected_rows(self) -> list[int]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return []
        return sorted(index.row() for index in selection_model.selectedRows())

    def _current_row(self) -> int | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._message.attachments):
            return row
        selected_rows = self._selected_rows()
        if selected_rows:
            return selected_rows[0]
        return None

    def _page_count_text_for_row(self, row: int) -> str:
        page_count = self._page_counts[row]
        if isinstance(page_count, int) and page_count > 0:
            return f"{page_count} page" if page_count == 1 else f"{page_count} pages"
        return "Preview for pages"

    def _set_row_start_page(self, row: int, value: int) -> None:
        attachment = self._message.attachments[row]
        if _is_image_attachment(attachment):
            next_value = 1
        else:
            page_count = self._page_counts[row]
            next_value = max(1, int(value))
            if isinstance(page_count, int) and page_count > 0:
                next_value = min(next_value, page_count)
        self._start_pages[row] = next_value
        item = self.table.item(row, 3)
        if item is None:
            item = QTableWidgetItem(str(next_value))
            self.table.setItem(row, 3, item)
        else:
            item.setText(str(next_value))

    def _set_row_page_count(self, row: int, page_count: int) -> None:
        resolved_page_count = max(1, int(page_count))
        self._page_counts[row] = resolved_page_count
        if self._start_pages[row] > resolved_page_count:
            self._set_row_start_page(row, resolved_page_count)

    def _selected_selections(self) -> tuple[GmailAttachmentSelection, ...]:
        rows = self._selected_rows()
        selected: list[GmailAttachmentSelection] = []
        for row in rows:
            if row < 0 or row >= len(self._message.attachments):
                continue
            start_page = 1 if self._is_interpretation_workflow() else int(self._start_pages[row])
            selected.append(
                GmailAttachmentSelection(
                    candidate=self._message.attachments[row],
                    start_page=start_page,
                )
            )
        return tuple(selected)

    def _refresh_actions(self) -> None:
        has_rows = len(self._message.attachments) > 0
        selected_rows = self._selected_rows()
        self.prepare_btn.setEnabled(has_rows and len(selected_rows) > 0)
        if not has_rows:
            self.prepare_btn.setText("No attachments")
        elif self._is_interpretation_workflow():
            self.prepare_btn.setText("Prepare notice")
        else:
            self.prepare_btn.setText("Prepare selected")
        self._refresh_summary_banner()
        self._refresh_detail_panel()

    def _refresh_detail_panel(self) -> None:
        row = self._current_row()
        if row is None:
            self.detail_attachment_label.setText("-")
            self.pages_value_label.setText("-")
            self.start_page_spin.blockSignals(True)
            self.start_page_spin.setValue(1)
            self.start_page_spin.blockSignals(False)
            self.start_page_spin.setEnabled(False)
            self.preview_btn.setEnabled(False)
            return

        attachment = self._message.attachments[row]
        self.detail_attachment_label.setText(attachment.filename)
        self.detail_attachment_label.setToolTip(
            f"{attachment.filename}\n{attachment.mime_type} | {_format_bytes(attachment.size_bytes)}"
        )
        self.pages_value_label.setText(self._page_count_text_for_row(row))
        self.start_page_spin.blockSignals(True)
        self.start_page_spin.setMaximum(
            max(1, self._page_counts[row]) if isinstance(self._page_counts[row], int) else 9999
        )
        self.start_page_spin.setValue(int(self._start_pages[row]))
        self.start_page_spin.blockSignals(False)
        editable = (not self._is_interpretation_workflow()) and (not _is_image_attachment(attachment))
        self.start_page_spin.setEnabled(editable)
        self.preview_btn.setEnabled(True)

    def _update_current_row_start_page(self, value: int) -> None:
        if self._is_interpretation_workflow():
            return
        row = self._current_row()
        if row is None:
            return
        self._set_row_start_page(row, int(value))
        self._refresh_detail_panel()

    def _on_workflow_changed(self, *_args: object) -> None:
        self._workflow_kind = self._current_workflow_kind()
        is_interpretation = self._is_interpretation_workflow()
        self.target_lang_label.setVisible(not is_interpretation)
        self.target_lang_combo.setVisible(not is_interpretation)
        self.start_page_label.setVisible(not is_interpretation)
        self.start_page_spin.setVisible(not is_interpretation)
        self.table.setColumnHidden(3, is_interpretation)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
            if is_interpretation
            else QTableWidget.SelectionMode.MultiSelection
        )
        if is_interpretation:
            selected_rows = self._selected_rows()
            keep_row = selected_rows[0] if selected_rows else self._current_row()
            self.table.clearSelection()
            if keep_row is not None and keep_row >= 0:
                self.table.selectRow(keep_row)
        self._refresh_actions()

    def _open_preview_for_current_row(self) -> None:
        row = self._current_row()
        if row is None:
            QMessageBox.information(
                self,
                "Gmail Attachment Review",
                "Select one attachment row first.",
            )
            return
        attachment = self._message.attachments[row]
        preview = QtGmailAttachmentPreviewDialog(
            parent=self,
            attachment=attachment,
            gog_path=self._gog_path,
            account_email=self._account_email,
            preview_dir=self._ensure_preview_dir(),
            initial_start_page=int(self._start_pages[row]),
            cached_path=self._preview_cache.get(attachment.attachment_id),
            known_page_count=self._page_counts[row],
        )
        if preview.exec() == QDialog.DialogCode.Accepted and preview.selected_start_page is not None:
            self._set_row_start_page(row, int(preview.selected_start_page))
        if isinstance(preview.resolved_local_path, Path):
            self._preview_cache[attachment.attachment_id] = preview.resolved_local_path
        if isinstance(preview.resolved_page_count, int) and preview.resolved_page_count > 0:
            self._set_row_page_count(row, int(preview.resolved_page_count))
        preview.deleteLater()
        self._refresh_detail_panel()

    def take_preview_cache_transfer(self) -> GmailBatchReviewPreviewCacheTransfer | None:
        preview_tempdir = self._preview_tempdir
        cached_paths: dict[str, Path] = {}
        cached_page_counts: dict[str, int] = {}
        for row, attachment in enumerate(self._message.attachments):
            cached_path = self._preview_cache.get(attachment.attachment_id)
            if not isinstance(cached_path, Path):
                continue
            cached_paths[attachment.attachment_id] = cached_path
            page_count = self._page_counts[row]
            if isinstance(page_count, int) and page_count > 0:
                cached_page_counts[attachment.attachment_id] = int(page_count)
        self._preview_tempdir = None
        self._preview_cache = {}
        if not cached_paths:
            if preview_tempdir is not None:
                preview_tempdir.cleanup()
            return None
        return GmailBatchReviewPreviewCacheTransfer(
            cached_paths=cached_paths,
            cached_page_counts=cached_page_counts,
            temp_dir=preview_tempdir,
        )

    def _accept_selection(self) -> None:
        selected = self._selected_selections()
        if not selected:
            QMessageBox.information(
                self,
                "Gmail Attachment Review",
                "Select at least one supported attachment first.",
            )
            return
        if self._is_interpretation_workflow() and len(selected) != 1:
            QMessageBox.information(
                self,
                "Gmail Attachment Review",
                "Interpretation notices require exactly one selected attachment.",
            )
            return
        self.selected_attachments = tuple(selection.candidate for selection in selected)
        self.review_result = GmailBatchReviewResult(
            selections=selected,
            target_lang=(
                self.target_lang_combo.currentText().strip().upper() or self._target_lang
                if not self._is_interpretation_workflow()
                else ""
            ),
            workflow_kind=self._current_workflow_kind(),
        )
        self.accept()


def _validate_url_or_blank(value: str) -> bool:
    cleaned = value.strip()
    if cleaned == "":
        return True
    parsed = urlparse(cleaned)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _format_bytes(value: int) -> str:
    size = max(0, int(value))
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024.0:.1f} KB"
    return f"{size / (1024.0 * 1024.0):.1f} MB"


def _to_int(value: str, *, field: str, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{field} must be between {min_value} and {max_value}.")
    return parsed


def _to_float(value: str, *, field: str, min_value: float, max_value: float) -> float:
    cleaned = value.strip().replace(",", ".")
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{field} must be between {min_value} and {max_value}.")
    return parsed


class QtGlossaryEditorDialog(QDialog):
    """Simple JSON editor for glossary content."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        initial_text: str,
        source_label: str,
        initial_path: Path | None,
        default_save_path: Path,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossary Editor")
        self.setMinimumSize(680, 440)

        self._current_path = initial_path
        self._default_save_path = default_save_path.expanduser().resolve()
        self.saved_path: Path | None = None

        layout = QVBoxLayout(self)
        source = source_label.strip() or "Built-in glossary"
        self.source_label = QLabel(f"Source: {source}")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        self.json_edit = QPlainTextEdit()
        self.json_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.json_edit.setPlainText(initial_text)
        layout.addWidget(self.json_edit, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.validate_btn = QPushButton("Validate")
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_as_btn = QPushButton("Save As...")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.validate_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.save_as_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.validate_btn.clicked.connect(self._validate)
        self.save_btn.clicked.connect(self._save)
        self.save_as_btn.clicked.connect(self._save_as)
        self.cancel_btn.clicked.connect(self.reject)
        self._responsive_window = ResponsiveWindowController(
            self,
            role="table",
            preferred_size=QSize(860, 560),
        )

    @staticmethod
    def _validated_text(text: str, *, source: str) -> str:
        load_glossary_from_text(text, source=source)
        return text

    @staticmethod
    def _write_text_atomically(path: Path, text: str) -> Path:
        target = path.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(f"{target.suffix}.tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(target)
        return target

    def _validate(self) -> None:
        text = self.json_edit.toPlainText()
        source = str(self._current_path) if self._current_path is not None else "editor"
        try:
            self._validated_text(text, source=source)
        except ValueError as exc:
            QMessageBox.critical(self, "Glossary", str(exc))
            return
        QMessageBox.information(self, "Glossary", "Glossary JSON is valid.")

    def _save_to(self, path: Path) -> bool:
        text = self.json_edit.toPlainText()
        target = path.expanduser().resolve()
        try:
            self._validated_text(text, source=str(target))
            written = self._write_text_atomically(target, text)
        except ValueError as exc:
            QMessageBox.critical(self, "Glossary", str(exc))
            return False
        except OSError as exc:
            QMessageBox.critical(self, "Glossary", f"Unable to save glossary file: {target}\n{exc}")
            return False
        self._current_path = written
        self.saved_path = written
        return True

    def _save(self) -> None:
        target = self._current_path if self._current_path is not None else self._default_save_path
        if self._save_to(target):
            self.accept()

    def _save_as(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save glossary JSON",
            str(self._current_path or self._default_save_path),
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not selected:
            return
        if self._save_to(Path(selected)):
            self.accept()


class _StudyTranslationWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        entries: list[StudyGlossaryEntry],
        supported_langs: list[str],
        lemma_effort: str = "medium",
    ) -> None:
        super().__init__()
        self._entries = list(entries)
        self._supported_langs = list(supported_langs)
        self._lemma_effort = lemma_effort

    def run(self) -> None:
        try:
            client = OpenAIResponsesClient()
            updated: list[StudyGlossaryEntry] = []
            total = max(1, len(self._entries))
            for index, entry in enumerate(self._entries, start=1):
                self.progress.emit(
                    int(((index - 1) / float(total)) * 100.0),
                    f"Refreshing translations for '{entry.term_pt}' ({index}/{total})",
                )
                updated.append(
                    fill_translations_for_entry(
                        entry,
                        supported_langs=self._supported_langs,
                        client=client,
                        fill_only_missing=False,
                        effort=self._lemma_effort,
                    )
                )
            self.progress.emit(100, "Translation refresh complete.")
            self.finished.emit(updated)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class _StudyCandidateWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    cancelled = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        source_mode: str,
        run_dirs: list[str],
        pdf_paths: list[str],
        mode: str,
        include_snippets: bool,
        snippet_max_chars: int,
    ) -> None:
        super().__init__()
        self._source_mode = str(source_mode or "run_folders").strip().lower()
        self._run_dirs = list(run_dirs)
        self._pdf_paths = list(pdf_paths)
        self._mode = mode
        self._include_snippets = bool(include_snippets)
        self._snippet_max_chars = int(snippet_max_chars)
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def _iter_page_numbers_from_state(self, state_payload: dict[str, object]) -> list[int]:
        page_numbers: list[int] = []
        pages_payload = state_payload.get("pages")
        if isinstance(pages_payload, dict):
            for key in pages_payload.keys():
                try:
                    value = int(str(key))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    page_numbers.append(value)
        if page_numbers:
            return sorted(set(page_numbers))
        try:
            start = int(state_payload.get("selection_start_page", 1))
            end = int(state_payload.get("selection_end_page", start))
        except (TypeError, ValueError):
            start = 1
            end = 1
        if end < start:
            return []
        return list(range(start, end + 1))

    def _resolve_pdf_path(self, run_dir: Path, state_payload: dict[str, object]) -> Path | None:
        pdf_path_raw = str(state_payload.get("pdf_path", "") or "").strip()
        if pdf_path_raw == "":
            return None
        pdf_path = Path(pdf_path_raw).expanduser()
        if not pdf_path.is_absolute():
            pdf_path = (run_dir / pdf_path).resolve()
        if not pdf_path.exists() or not pdf_path.is_file():
            return None
        return pdf_path

    def _ordered_page_text(self, pdf_path: Path, page_number: int) -> str:
        try:
            ordered = extract_ordered_page_text(pdf_path, page_number - 1)
        except Exception:  # noqa: BLE001
            return ""
        if ordered.extraction_failed:
            return ""
        return str(ordered.text or "")

    def _ingest_page_text(
        self,
        *,
        doc_id: str,
        page_number: int,
        page_text: str,
        stats: dict[str, object],
        pages_tokens: list[list[str]],
    ) -> bool:
        if page_text.strip() == "":
            return False
        page_tokens = tokenize_page_for_mode(
            page_text,
            self._mode if self._mode in {"full_text", "headers_only"} else "full_text",  # type: ignore[arg-type]
        )
        if page_tokens:
            pages_tokens.append(page_tokens)
        update_candidate_stats_from_page(
            doc_id=doc_id,
            page_number=page_number,
            text=page_text,
            mode=self._mode,  # type: ignore[arg-type]
            include_snippets=self._include_snippets,
            snippet_max_chars=self._snippet_max_chars,
            stats=stats,
        )
        return True

    def _scan_pdf_source(
        self,
        *,
        pdf_path: Path,
        doc_id: str,
        stats: dict[str, object],
        pages_tokens: list[list[str]],
    ) -> tuple[int, bool]:
        try:
            page_count = int(get_page_count(pdf_path))
        except Exception:  # noqa: BLE001
            return (0, False)
        if page_count <= 0:
            return (0, False)
        pages_scanned = 0
        for page_number in range(1, page_count + 1):
            if self._cancel_requested:
                return (pages_scanned, True)
            page_text = self._ordered_page_text(pdf_path, page_number)
            if self._ingest_page_text(
                doc_id=doc_id,
                page_number=page_number,
                page_text=page_text,
                stats=stats,
                pages_tokens=pages_tokens,
            ):
                pages_scanned += 1
        return (pages_scanned, False)

    def run(self) -> None:
        try:
            stats = create_candidate_stats()
            pages_tokens: list[list[str]] = []
            total_pages_scanned = 0
            sources_processed = 0
            source_mode = self._source_mode if self._source_mode in {
                "run_folders",
                "current_pdf",
                "select_pdfs",
                "joblog_runs",
            } else "run_folders"

            if source_mode == "run_folders":
                total_sources = max(1, len(self._run_dirs))
                for source_index, raw_dir in enumerate(self._run_dirs, start=1):
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return
                    run_dir = Path(raw_dir).expanduser().resolve()
                    run_state_path = run_dir / "run_state.json"
                    if not run_state_path.exists():
                        sources_processed += 1
                        self.progress.emit(
                            int((sources_processed / float(total_sources)) * 100.0),
                            f"Skipping {run_dir.name}: run_state.json not found ({source_index}/{total_sources}).",
                        )
                        continue
                    try:
                        state_payload = json.loads(run_state_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        sources_processed += 1
                        self.progress.emit(
                            int((sources_processed / float(total_sources)) * 100.0),
                            f"Skipping {run_dir.name}: invalid run_state.json ({source_index}/{total_sources}).",
                        )
                        continue
                    if not isinstance(state_payload, dict):
                        sources_processed += 1
                        continue
                    doc_id = run_dir.name
                    page_numbers = self._iter_page_numbers_from_state(state_payload)
                    pages_dir = run_dir / "pages"
                    pdf_path = self._resolve_pdf_path(run_dir, state_payload)
                    for page_number in page_numbers:
                        if self._cancel_requested:
                            self.cancelled.emit()
                            return
                        page_text = ""
                        page_file = pages_dir / f"page_{page_number:04d}.txt"
                        if page_file.exists():
                            try:
                                page_text = page_file.read_text(encoding="utf-8")
                            except OSError:
                                page_text = ""
                        if page_text.strip() == "" and pdf_path is not None:
                            page_text = self._ordered_page_text(pdf_path, page_number)
                        if self._ingest_page_text(
                            doc_id=doc_id,
                            page_number=page_number,
                            page_text=page_text,
                            stats=stats,
                            pages_tokens=pages_tokens,
                        ):
                            total_pages_scanned += 1
                        if total_pages_scanned > 0 and total_pages_scanned % 10 == 0:
                            source_progress = int(((source_index - 1) / float(total_sources)) * 100.0)
                            self.progress.emit(
                                source_progress,
                                f"Processing {run_dir.name}: {total_pages_scanned} pages scanned.",
                            )
                    sources_processed += 1
                    self.progress.emit(
                        int((sources_processed / float(total_sources)) * 100.0),
                        f"Processed {sources_processed}/{total_sources} sources; pages scanned: {total_pages_scanned}.",
                    )
            else:
                total_sources = max(1, len(self._pdf_paths))
                for source_index, raw_pdf in enumerate(self._pdf_paths, start=1):
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return
                    pdf_path = Path(raw_pdf).expanduser().resolve()
                    if not pdf_path.exists() or not pdf_path.is_file():
                        sources_processed += 1
                        self.progress.emit(
                            int((sources_processed / float(total_sources)) * 100.0),
                            f"Skipping missing PDF ({source_index}/{total_sources}): {pdf_path.name}",
                        )
                        continue
                    scanned, was_cancelled = self._scan_pdf_source(
                        pdf_path=pdf_path,
                        doc_id=pdf_path.stem,
                        stats=stats,
                        pages_tokens=pages_tokens,
                    )
                    if was_cancelled:
                        self.cancelled.emit()
                        return
                    total_pages_scanned += scanned
                    sources_processed += 1
                    self.progress.emit(
                        int((sources_processed / float(total_sources)) * 100.0),
                        f"Processed {sources_processed}/{total_sources} PDFs; pages scanned: {total_pages_scanned}.",
                    )

            candidates = finalize_study_candidates(stats)
            self.finished.emit(
                {
                    "candidates": candidates,
                    "pages_tokens": pages_tokens,
                    "run_folders_processed": int(sources_processed),
                    "total_pages_scanned": int(total_pages_scanned),
                    "source_mode": source_mode,
                }
            )
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class QtSettingsDialog(QDialog):
    """Qt equivalent of the Tk settings dialog."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        settings: dict[str, object],
        apply_callback: Callable[[dict[str, object], bool], None],
        collect_debug_paths: Callable[[], list[Path]],
        current_pdf_path: Path | None = None,
        build_identity: RuntimeBuildIdentity | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(780, 560)

        self._settings = dict(settings)
        self._apply_callback = apply_callback
        self._collect_debug_paths = collect_debug_paths
        self._study_current_pdf_path: Path | None = current_pdf_path
        self._build_identity = build_identity
        self._glossaries_by_lang: dict[str, list[GlossaryEntry]] = normalize_glossaries({}, supported_target_langs())
        self._enabled_glossary_tiers_by_lang: dict[str, list[int]] = normalize_enabled_tiers_by_target_lang(
            {},
            supported_target_langs(),
        )
        self._glossary_current_lang: str | None = None
        self._glossary_selected_tier: int = 1
        self._glossary_search_text: str = ""
        self._glossary_view_keys: list[tuple[str, str, str, str, int]] = []
        self._glossary_seed_version: int = 2
        self._glossary_populating: bool = False
        self._study_supported_langs: list[str] = supported_learning_langs()
        self._study_entries: list[StudyGlossaryEntry] = normalize_study_entries([], self._study_supported_langs)
        self._study_candidate_rows: list[StudyCandidate] = []
        self._study_candidate_keys: list[str] = []
        self._study_entry_view_terms: list[str] = []
        self._study_search_text: str = ""
        self._study_filters: dict[str, str] = {"category": "all", "status": "all", "coverage_tier": "all"}
        self._study_corpus_source: str = "run_folders"
        self._study_pdf_paths: list[str] = []
        self._study_quiz_index: int = 0
        self._study_last_run_folders_processed: int = 0
        self._study_last_total_pages_scanned: int = 0
        self._study_candidate_thread: QThread | None = None
        self._study_candidate_worker: _StudyCandidateWorker | None = None
        self._study_translation_thread: QThread | None = None
        self._study_translation_worker: _StudyTranslationWorker | None = None
        self._build_ui()
        self._set_values_from_settings(self._settings)
        self._refresh_key_status()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(980, 700),
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        _scroll_area = QScrollArea()
        _scroll_area.setObjectName("DialogScrollArea")
        _scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        _scroll_area.setWidgetResizable(True)
        _scroll_content = QWidget()
        _scroll_content.setObjectName("DialogScrollContent")
        scroll_layout = QVBoxLayout(_scroll_content)
        scroll_layout.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget(self)
        scroll_layout.addWidget(self.tabs, 1)

        self.tab_keys = QWidget(self)
        self.tab_ocr = QWidget(self)
        self.tab_appearance = QWidget(self)
        self.tab_behaviour = QWidget(self)
        self.tab_glossary = QWidget(self)
        self.tab_study = QWidget(self)
        self.tab_diag = QWidget(self)
        self.tabs.addTab(self.tab_keys, "Keys & Providers")
        self.tabs.addTab(self.tab_ocr, "OCR Defaults")
        self.tabs.addTab(self.tab_appearance, "Appearance")
        self.tabs.addTab(self.tab_behaviour, "Behaviour & Performance")
        self.tabs.addTab(self.tab_glossary, "Glossary")
        self.tabs.addTab(self.tab_study, "Study Glossary")
        self.tabs.addTab(self.tab_diag, "Diagnostics")

        self._build_tab_keys()
        self._build_tab_ocr_defaults()
        self._build_tab_appearance()
        self._build_tab_behaviour()
        self._build_tab_glossary()
        self._build_tab_study()
        self._build_tab_diagnostics()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.apply_btn = QPushButton("Apply")
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        scroll_layout.addLayout(buttons)

        _scroll_area.setWidget(_scroll_content)
        root.addWidget(_scroll_area)

        self.apply_btn.clicked.connect(self._apply)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _build_tab_keys(self) -> None:
        layout = QVBoxLayout(self.tab_keys)
        openai_group = QGroupBox("OpenAI (Translation)")
        openai_layout = QGridLayout(openai_group)
        openai_layout.addWidget(QLabel("API key"), 0, 0)
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        openai_layout.addWidget(self.openai_key_edit, 0, 1)
        self.openai_toggle_btn = QPushButton("Show")
        self.openai_save_btn = QPushButton("Save")
        self.openai_clear_btn = QPushButton("Clear")
        self.openai_clear_btn.setObjectName("DangerButton")
        self.openai_test_btn = QPushButton("Test")
        openai_layout.addWidget(self.openai_toggle_btn, 0, 2)
        openai_layout.addWidget(self.openai_save_btn, 0, 3)
        openai_layout.addWidget(self.openai_clear_btn, 0, 4)
        openai_layout.addWidget(self.openai_test_btn, 0, 5)
        self.openai_status_label = QLabel("Not stored")
        openai_layout.addWidget(self.openai_status_label, 1, 0, 1, 6)
        openai_layout.setColumnStretch(1, 1)
        layout.addWidget(openai_group)

        ocr_group = QGroupBox("OCR API (Fallback)")
        ocr_layout = QGridLayout(ocr_group)
        ocr_layout.addWidget(QLabel("API key"), 0, 0)
        self.ocr_key_edit = QLineEdit()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ocr_layout.addWidget(self.ocr_key_edit, 0, 1)
        self.ocr_toggle_btn = QPushButton("Show")
        self.ocr_save_btn = QPushButton("Save")
        self.ocr_clear_btn = QPushButton("Clear")
        self.ocr_clear_btn.setObjectName("DangerButton")
        self.ocr_test_btn = QPushButton("Test")
        ocr_layout.addWidget(self.ocr_toggle_btn, 0, 2)
        ocr_layout.addWidget(self.ocr_save_btn, 0, 3)
        ocr_layout.addWidget(self.ocr_clear_btn, 0, 4)
        ocr_layout.addWidget(self.ocr_test_btn, 0, 5)
        self.ocr_status_label = QLabel("Not stored")
        ocr_layout.addWidget(self.ocr_status_label, 1, 0, 1, 6)
        ocr_layout.setColumnStretch(1, 1)
        layout.addWidget(ocr_group)

        provider_group = QGroupBox("Provider Settings")
        provider_form = QFormLayout(provider_group)
        self.ocr_provider_combo = NoWheelComboBox()
        self.ocr_provider_combo.addItems(["openai", "gemini"])
        self.ocr_provider_combo.setEditable(False)
        self.ocr_base_url_edit = QLineEdit()
        self.ocr_model_edit = QLineEdit()
        self.ocr_env_edit = QLineEdit()
        self.provider_summary_label = QLabel("")
        provider_form.addRow("OCR provider", self.ocr_provider_combo)
        provider_form.addRow("OCR base URL", self.ocr_base_url_edit)
        provider_form.addRow("OCR model", self.ocr_model_edit)
        provider_form.addRow("OCR env var name", self.ocr_env_edit)
        provider_form.addRow("Summary", self.provider_summary_label)
        layout.addWidget(provider_group)

        gmail_group = QGroupBox("Gmail Drafts (Windows)")
        gmail_layout = QGridLayout(gmail_group)
        gmail_layout.addWidget(QLabel("gog path"), 0, 0)
        self.gmail_gog_path_edit = QLineEdit()
        gmail_layout.addWidget(self.gmail_gog_path_edit, 0, 1)
        self.gmail_gog_browse_btn = QPushButton("Browse")
        gmail_layout.addWidget(self.gmail_gog_browse_btn, 0, 2)
        gmail_layout.addWidget(QLabel("Gmail account"), 1, 0)
        self.gmail_account_edit = QLineEdit()
        gmail_layout.addWidget(self.gmail_account_edit, 1, 1, 1, 2)
        self.gmail_intake_enabled_check = QCheckBox("Enable localhost Gmail intake bridge")
        gmail_layout.addWidget(self.gmail_intake_enabled_check, 2, 0, 1, 3)
        gmail_layout.addWidget(QLabel("Bridge token"), 3, 0)
        self.gmail_intake_token_edit = QLineEdit()
        self.gmail_intake_token_edit.setPlaceholderText("Auto-generated on Apply/Save when enabled")
        gmail_layout.addWidget(self.gmail_intake_token_edit, 3, 1, 1, 2)
        gmail_layout.addWidget(QLabel("Bridge port"), 4, 0)
        self.gmail_intake_port_spin = NoWheelSpinBox()
        self.gmail_intake_port_spin.setRange(1, 65535)
        gmail_layout.addWidget(self.gmail_intake_port_spin, 4, 1)
        self.gmail_test_btn = QPushButton("Test Gmail draft prerequisites")
        gmail_layout.addWidget(self.gmail_test_btn, 5, 0, 1, 3)
        self.gmail_summary_label = QLabel("")
        self.gmail_summary_label.setWordWrap(True)
        gmail_layout.addWidget(self.gmail_summary_label, 6, 0, 1, 3)
        gmail_layout.setColumnStretch(1, 1)
        layout.addWidget(gmail_group)
        layout.addStretch(1)

        self.openai_toggle_btn.clicked.connect(self._toggle_openai_key)
        self.ocr_toggle_btn.clicked.connect(self._toggle_ocr_key)
        self.openai_save_btn.clicked.connect(self._save_openai_key)
        self.openai_clear_btn.clicked.connect(self._clear_openai_key)
        self.openai_test_btn.clicked.connect(self._test_openai_key)
        self.ocr_save_btn.clicked.connect(self._save_ocr_key)
        self.ocr_clear_btn.clicked.connect(self._clear_ocr_key)
        self.ocr_test_btn.clicked.connect(self._test_ocr_key)
        self.ocr_provider_combo.currentTextChanged.connect(self._refresh_provider_controls)
        self.ocr_base_url_edit.textChanged.connect(self._refresh_provider_controls)
        self.ocr_model_edit.textChanged.connect(self._refresh_provider_controls)
        self.ocr_env_edit.textChanged.connect(self._refresh_provider_controls)
        self.gmail_gog_browse_btn.clicked.connect(self._pick_gmail_gog_path)
        self.gmail_test_btn.clicked.connect(self._test_gmail_draft_prereqs)
        self.gmail_gog_path_edit.textChanged.connect(lambda _text: self._refresh_key_status())
        self.gmail_account_edit.textChanged.connect(lambda _text: self._refresh_key_status())
        self.gmail_intake_enabled_check.stateChanged.connect(lambda _state: self._refresh_gmail_bridge_summary())
        self.gmail_intake_token_edit.textChanged.connect(lambda _text: self._refresh_gmail_bridge_summary())
        self.gmail_intake_port_spin.valueChanged.connect(lambda _value: self._refresh_gmail_bridge_summary())

    def _build_tab_ocr_defaults(self) -> None:
        form = QFormLayout(self.tab_ocr)
        self.ocr_provider_default_combo = NoWheelComboBox()
        self.ocr_provider_default_combo.addItems(["openai", "gemini"])
        self.ocr_provider_default_combo.setEditable(False)
        self.ocr_mode_default_combo = NoWheelComboBox()
        self.ocr_mode_default_combo.addItems(["off", "auto", "always"])
        self.ocr_mode_default_combo.setEditable(False)
        self.ocr_engine_default_combo = NoWheelComboBox()
        self.ocr_engine_default_combo.addItems(["local", "local_then_api", "api"])
        self.ocr_engine_default_combo.setEditable(False)
        self.min_chars_edit = QLineEdit()
        form.addRow("Default OCR provider", self.ocr_provider_default_combo)
        form.addRow("Default OCR mode", self.ocr_mode_default_combo)
        form.addRow("Default OCR engine", self.ocr_engine_default_combo)
        form.addRow("Min chars to accept OCR", self.min_chars_edit)

    def _build_tab_appearance(self) -> None:
        form = QFormLayout(self.tab_appearance)
        self.ui_theme_combo = NoWheelComboBox()
        self.ui_theme_combo.addItems(["dark_futuristic", "dark_simple"])
        self.ui_theme_combo.setEditable(False)
        self.ui_scale_combo = NoWheelComboBox()
        self.ui_scale_combo.addItems(["1.00", "1.10", "1.25"])
        self.ui_scale_combo.setEditable(False)
        form.addRow("Theme", self.ui_theme_combo)
        form.addRow("UI scale", self.ui_scale_combo)

    def _build_tab_behaviour(self) -> None:
        layout = QVBoxLayout(self.tab_behaviour)
        grid = QGridLayout()
        row = 0

        self.default_lang_combo = NoWheelComboBox(); self.default_lang_combo.addItems(["EN", "FR", "AR"])
        self.default_effort_combo = NoWheelComboBox(); self.default_effort_combo.addItems(["high", "xhigh"])
        self.default_effort_policy_combo = NoWheelComboBox(); self.default_effort_policy_combo.addItems(["adaptive", "fixed_high", "fixed_xhigh"])
        self.lemma_effort_combo = NoWheelComboBox(); self.lemma_effort_combo.addItems(["medium", "high", "xhigh"])
        self.default_images_combo = NoWheelComboBox(); self.default_images_combo.addItems(["off", "auto", "always"])
        self.default_workers_combo = NoWheelComboBox(); self.default_workers_combo.addItems(["1", "2", "3", "4", "5", "6"])
        self.default_end_edit = QLineEdit()
        self.default_outdir_edit = QLineEdit()
        self.default_outdir_btn = QPushButton("Browse")
        self.glossary_file_edit = QLineEdit()
        self.glossary_file_btn = QPushButton("Browse")
        self.glossary_edit_btn = QPushButton("View/Edit...")
        self.glossary_builtin_btn = QPushButton("Use built-in")
        self.glossary_builtin_btn.setObjectName("DangerButton")
        self.default_resume_check = QCheckBox("Default resume ON")
        self.default_keep_check = QCheckBox("Default keep intermediates ON")
        self.default_breaks_check = QCheckBox("Default page breaks ON")
        self.retries_edit = QLineEdit()
        self.backoff_cap_edit = QLineEdit()
        self.timeout_text_edit = QLineEdit()
        self.timeout_image_edit = QLineEdit()
        self.allow_xhigh_check = QCheckBox("Allow xhigh escalation (adaptive, image + short text only)")
        self.restore_defaults_btn = QPushButton("Restore defaults")
        self.restore_defaults_btn.setObjectName("DangerButton")

        grid.addWidget(QLabel("Default language"), row, 0); grid.addWidget(self.default_lang_combo, row, 1); row += 1
        grid.addWidget(QLabel("Translation effort"), row, 0); grid.addWidget(self.default_effort_combo, row, 1); row += 1
        grid.addWidget(QLabel("Translation effort policy"), row, 0); grid.addWidget(self.default_effort_policy_combo, row, 1); row += 1
        grid.addWidget(QLabel("Lemma / utility effort"), row, 0); grid.addWidget(self.lemma_effort_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default images mode"), row, 0); grid.addWidget(self.default_images_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default workers"), row, 0); grid.addWidget(self.default_workers_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default end page"), row, 0); grid.addWidget(self.default_end_edit, row, 1); row += 1

        outdir_row = QHBoxLayout()
        outdir_row.addWidget(self.default_outdir_edit, 1)
        outdir_row.addWidget(self.default_outdir_btn)
        outdir_wrap = QWidget()
        outdir_wrap.setLayout(outdir_row)
        grid.addWidget(QLabel("Default output folder"), row, 0)
        grid.addWidget(outdir_wrap, row, 1)
        row += 1

        glossary_row = QHBoxLayout()
        glossary_row.addWidget(self.glossary_file_edit, 1)
        glossary_row.addWidget(self.glossary_file_btn)
        glossary_row.addWidget(self.glossary_edit_btn)
        glossary_row.addWidget(self.glossary_builtin_btn)
        glossary_wrap = QWidget()
        glossary_wrap.setLayout(glossary_row)
        grid.addWidget(QLabel("Glossary JSON file"), row, 0)
        grid.addWidget(glossary_wrap, row, 1)
        row += 1

        grid.addWidget(self.default_resume_check, row, 0, 1, 2); row += 1
        grid.addWidget(self.default_keep_check, row, 0, 1, 2); row += 1
        grid.addWidget(self.default_breaks_check, row, 0, 1, 2); row += 1

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        grid.addWidget(separator, row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Transport retries"), row, 0); grid.addWidget(self.retries_edit, row, 1); row += 1
        grid.addWidget(QLabel("Backoff cap (seconds)"), row, 0); grid.addWidget(self.backoff_cap_edit, row, 1); row += 1
        grid.addWidget(QLabel("Text timeout (seconds)"), row, 0); grid.addWidget(self.timeout_text_edit, row, 1); row += 1
        grid.addWidget(QLabel("Image timeout (seconds)"), row, 0); grid.addWidget(self.timeout_image_edit, row, 1); row += 1
        grid.addWidget(self.allow_xhigh_check, row, 0, 1, 2); row += 1
        grid.addWidget(self.restore_defaults_btn, row, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

        self.default_outdir_btn.clicked.connect(self._pick_default_outdir)
        self.glossary_file_btn.clicked.connect(self._pick_glossary_file)
        self.glossary_edit_btn.clicked.connect(self._open_glossary_editor)
        self.glossary_builtin_btn.clicked.connect(self._use_builtin_glossary)
        self.restore_defaults_btn.clicked.connect(self._restore_defaults)

    def _build_tab_glossary(self) -> None:
        layout = QVBoxLayout(self.tab_glossary)
        top = QHBoxLayout()
        top.addWidget(QLabel("Target language"))
        self.glossary_lang_combo = NoWheelComboBox()
        self.glossary_lang_combo.addItems(supported_target_langs())
        self.glossary_lang_combo.setEditable(False)
        top.addWidget(self.glossary_lang_combo)
        top.addWidget(QLabel("View tier"))
        self.glossary_tier_combo = NoWheelComboBox()
        for tier in valid_glossary_tiers():
            self.glossary_tier_combo.addItem(f"Tier {tier}", tier)
        self.glossary_tier_combo.setCurrentIndex(0)
        self.glossary_tier_combo.setEditable(False)
        top.addWidget(self.glossary_tier_combo)
        self.glossary_tier_counts_label = QLabel("")
        top.addWidget(self.glossary_tier_counts_label, 1)
        top.addStretch(1)
        layout.addLayout(top)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.glossary_search_edit = QLineEdit()
        self.glossary_search_edit.setPlaceholderText("Filter source phrase or preferred translation...")
        search_row.addWidget(self.glossary_search_edit, 1)
        layout.addLayout(search_row)
        self._glossary_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.tab_glossary)
        self._glossary_search_shortcut.activated.connect(self._focus_glossary_search)
        self._shortcut_add_row_ctrl_n = QShortcut(QKeySequence("Ctrl+N"), self.tab_glossary)
        self._shortcut_add_row_ctrl_n.activated.connect(self._add_glossary_row_and_focus)
        self._shortcut_add_row_insert = QShortcut(QKeySequence("Insert"), self.tab_glossary)
        self._shortcut_add_row_insert.activated.connect(self._add_glossary_row_and_focus)

        active_tiers_row = QHBoxLayout()
        active_tiers_row.addWidget(QLabel("Active tiers for prompt"))
        self._glossary_active_tier_checks: dict[int, QCheckBox] = {}
        for tier in valid_glossary_tiers():
            check = QCheckBox(f"T{tier}")
            self._glossary_active_tier_checks[tier] = check
            active_tiers_row.addWidget(check)
        active_tiers_row.addStretch(1)
        layout.addLayout(active_tiers_row)

        self.glossary_table = QTableWidget(0, 5, self.tab_glossary)
        self.glossary_table.setHorizontalHeaderLabels(
            ["Source phrase (PDF text)", "Preferred translation", "Match", "Source lang", "Tier"]
        )
        self.glossary_table.verticalHeader().setVisible(False)
        self.glossary_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.glossary_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.glossary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header = self.glossary_table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.glossary_table.setColumnWidth(2, 110)  # Match
        self.glossary_table.setColumnWidth(3, 90)   # Source lang
        self.glossary_table.setColumnWidth(4, 60)   # Tier
        layout.addWidget(self.glossary_table, 1)

        add_row_inline = QHBoxLayout()
        self.glossary_add_row_top_btn = QPushButton("+")
        self.glossary_add_row_top_btn.setFixedWidth(36)
        self.glossary_add_row_top_btn.setToolTip("Add glossary row (Ctrl+N)")
        add_row_inline.addWidget(self.glossary_add_row_top_btn)
        add_row_inline.addStretch(1)
        layout.addLayout(add_row_inline)

        actions = QHBoxLayout()
        self.glossary_remove_rows_btn = QPushButton("Remove selected")
        self.glossary_remove_rows_btn.setObjectName("DangerButton")
        self.glossary_export_btn = QPushButton("Export...")
        actions.addWidget(self.glossary_remove_rows_btn)
        actions.addWidget(self.glossary_export_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.glossary_hygiene_hint_label = QLabel(
            "Glossary hygiene:\n"
            "1) Add entries for repeated headers/titles/section labels.\n"
            "2) Add entries for ambiguous phrases needing consistency.\n"
            "3) Add entries where legal tone/formality must be stable.\n"
            "4) Add entries for legal formula/boilerplate phrases.\n"
            "Avoid obvious single-word dictionary items. Prefer Exact for short phrases."
        )
        self.glossary_hygiene_hint_label.setWordWrap(True)
        layout.addWidget(self.glossary_hygiene_hint_label)

        self.glossary_warning_label = QLabel("")
        self.glossary_warning_label.setWordWrap(True)
        layout.addWidget(self.glossary_warning_label)

        self.glossary_lang_combo.currentTextChanged.connect(self._on_glossary_language_changed)
        self.glossary_tier_combo.currentIndexChanged.connect(self._on_glossary_tier_changed)
        self.glossary_search_edit.textChanged.connect(self._on_glossary_search_changed)
        self.glossary_add_row_top_btn.clicked.connect(self._add_glossary_row_and_focus)
        self.glossary_remove_rows_btn.clicked.connect(self._remove_selected_glossary_rows)
        self.glossary_export_btn.clicked.connect(self._export_consistency_glossary_markdown)
        for tier, check in self._glossary_active_tier_checks.items():
            check.toggled.connect(lambda checked, tier=tier: self._on_glossary_active_tier_changed(tier, checked))

        self._glossary_auto_save_timer = QTimer(self)
        self._glossary_auto_save_timer.setSingleShot(True)
        self._glossary_auto_save_timer.setInterval(500)
        self._glossary_auto_save_timer.timeout.connect(self._persist_glossary_to_disk)
        self.glossary_table.cellChanged.connect(self._on_glossary_cell_changed)

    def _new_glossary_match_combo(self, selected: str = "exact") -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("GlossaryTableCombo")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.addItem("Exact", "exact")
        combo.addItem("Contains", "contains")
        selected_clean = selected.strip().lower()
        if selected_clean == "contains":
            combo.setCurrentIndex(1)
        else:
            combo.setCurrentIndex(0)
        return combo

    def _glossary_match_value(self, combo: object | None) -> str:
        if combo is None:
            return "exact"
        value = combo.currentData() if hasattr(combo, "currentData") else None
        if isinstance(value, str) and value in {"exact", "contains"}:
            return value
        text = combo.currentText().strip().lower() if hasattr(combo, "currentText") else ""
        return "contains" if text == "contains" else "exact"

    def _new_glossary_source_lang_combo(self, selected: str = "AUTO") -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("GlossaryTableCombo")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for value in valid_source_langs():
            combo.addItem(value, value)
        selected_clean = coerce_source_lang(selected, default="AUTO")
        combo.setCurrentText(selected_clean)
        return combo

    def _new_glossary_tier_combo(self, selected: int = 2) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("GlossaryTableCombo")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for value in valid_glossary_tiers():
            combo.addItem(f"T{value}", value)
        selected_tier = coerce_glossary_tier(selected, default=2)
        if hasattr(combo, "setCurrentData"):
            combo.setCurrentData(selected_tier)
        else:
            idx = combo.findData(selected_tier) if hasattr(combo, "findData") else -1
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    def _glossary_source_lang_value(self, combo: object | None) -> str:
        if combo is None:
            return "AUTO"
        value = combo.currentData() if hasattr(combo, "currentData") else None
        if isinstance(value, str):
            return coerce_source_lang(value, default="AUTO")
        text = combo.currentText().strip().upper() if hasattr(combo, "currentText") else ""
        return coerce_source_lang(text, default="AUTO")

    def _glossary_tier_value(self, combo: object | None) -> int:
        if combo is None:
            return 2
        value = combo.currentData() if hasattr(combo, "currentData") else None
        if value is not None:
            return coerce_glossary_tier(value, default=2)
        text = combo.currentText().strip() if hasattr(combo, "currentText") else ""
        if text.startswith("T"):
            text = text[1:]
        return coerce_glossary_tier(text, default=2)

    def _glossary_entry_key(self, entry: GlossaryEntry) -> tuple[str, str, str, str, int]:
        return (
            entry.source_text,
            entry.preferred_translation,
            entry.match_mode,
            entry.source_lang,
            int(entry.tier),
        )

    def _visible_glossary_rows(self, lang: str) -> list[GlossaryEntry]:
        entries = self._glossaries_by_lang.get(lang, [])
        selected_tier = int(self._glossary_selected_tier)
        search = self._glossary_search_text.strip().casefold()
        filtered = [entry for entry in entries if int(entry.tier) == selected_tier]
        if search:
            filtered = [
                entry
                for entry in filtered
                if search in entry.source_text.casefold() or search in entry.preferred_translation.casefold()
            ]
        return filtered

    def _set_active_tier_checks(self, tiers: list[int]) -> None:
        tier_set = {coerce_glossary_tier(value, default=1) for value in tiers}
        if not tier_set:
            tier_set = {1, 2}
        for tier, check in self._glossary_active_tier_checks.items():
            check.blockSignals(True)
            check.setChecked(tier in tier_set)
            check.blockSignals(False)

    def _read_active_tier_checks(self) -> list[int]:
        tiers = [tier for tier, check in self._glossary_active_tier_checks.items() if check.isChecked()]
        if not tiers:
            tiers = [1, 2]
        return sorted({coerce_glossary_tier(value, default=1) for value in tiers})

    def _refresh_glossary_tier_counts(self) -> None:
        lang = self._glossary_current_lang or "EN"
        counts = {tier: 0 for tier in valid_glossary_tiers()}
        for entry in self._glossaries_by_lang.get(lang, []):
            counts[coerce_glossary_tier(entry.tier, default=2)] += 1
        active = self._enabled_glossary_tiers_by_lang.get(lang, [1, 2])
        counts_text = " | ".join(f"T{tier}:{counts[tier]}" for tier in valid_glossary_tiers())
        active_text = ",".join(f"T{tier}" for tier in sorted(active))
        self.glossary_tier_counts_label.setText(f"{counts_text}   Active: {active_text}")

    def _update_glossary_warning_label(self, rows: list[GlossaryEntry]) -> None:
        warnings: list[str] = []
        for entry in rows:
            source = entry.source_text.strip()
            words = [part for part in source.split() if part]
            if entry.match_mode == "contains" and (len(source) < 10 or len(words) < 2):
                warnings.append("Contains on short phrases may overmatch.")
            if len(words) == 1 and int(entry.tier) <= 2:
                warnings.append("Tier 1-2 should be reserved for high-impact phrases (headers/ambiguous/formulas).")
        if not warnings:
            self.glossary_warning_label.setText("No glossary hygiene warnings for visible rows.")
            return
        unique_warnings = list(dict.fromkeys(warnings))
        self.glossary_warning_label.setText("Warning: " + " ".join(unique_warnings))

    def _refresh_glossary_table_view(self) -> None:
        lang = self._glossary_current_lang or "EN"
        rows = self._visible_glossary_rows(lang)
        self._set_glossary_table_rows(rows)
        self._refresh_glossary_tier_counts()
        self._update_glossary_warning_label(rows)

    def _focus_glossary_search(self) -> None:
        self.glossary_search_edit.setFocus()
        self.glossary_search_edit.selectAll()

    def _set_glossary_table_rows(self, rows: list[GlossaryEntry]) -> None:
        self._glossary_populating = True
        try:
            self.glossary_table.setRowCount(0)
            self._glossary_view_keys = [self._glossary_entry_key(entry) for entry in rows]
            for entry in rows:
                row = self.glossary_table.rowCount()
                self.glossary_table.insertRow(row)
                self.glossary_table.setItem(row, 0, QTableWidgetItem(entry.source_text))
                self.glossary_table.setItem(row, 1, QTableWidgetItem(entry.preferred_translation))
                match_c = self._new_glossary_match_combo(entry.match_mode)
                self.glossary_table.setCellWidget(row, 2, match_c)
                src_c = self._new_glossary_source_lang_combo(entry.source_lang)
                self.glossary_table.setCellWidget(row, 3, src_c)
                tier_c = self._new_glossary_tier_combo(entry.tier)
                self.glossary_table.setCellWidget(row, 4, tier_c)
                match_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
                src_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
                tier_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        finally:
            self._glossary_populating = False

    def _read_glossary_table_rows(self) -> list[GlossaryEntry]:
        rows: list[dict[str, str]] = []
        for row in range(self.glossary_table.rowCount()):
            source_item = self.glossary_table.item(row, 0)
            target_item = self.glossary_table.item(row, 1)
            source = source_item.text().strip() if source_item else ""
            target = target_item.text().strip() if target_item else ""
            if source and not target:
                target = "..."
            match = self._glossary_match_value(self.glossary_table.cellWidget(row, 2))
            source_lang = self._glossary_source_lang_value(self.glossary_table.cellWidget(row, 3))
            tier = self._glossary_tier_value(self.glossary_table.cellWidget(row, 4))
            rows.append(
                {
                    "source_text": source,
                    "preferred_translation": target,
                    "match_mode": match,
                    "source_lang": source_lang,
                    "tier": str(int(tier)),
                }
            )
        normalized = normalize_glossaries(
            {self._glossary_current_lang or "EN": rows},
            [self._glossary_current_lang or "EN"],
        )
        return normalized.get(self._glossary_current_lang or "EN", [])

    def _save_current_glossary_language_rows(self) -> None:
        if self._glossary_current_lang is None:
            return
        lang = self._glossary_current_lang
        existing_rows = list(self._glossaries_by_lang.get(lang, []))
        view_key_set = set(self._glossary_view_keys)
        preserved_rows = [entry for entry in existing_rows if self._glossary_entry_key(entry) not in view_key_set]
        merged_rows = preserved_rows + self._read_glossary_table_rows()
        normalized = normalize_glossaries({lang: merged_rows}, [lang])
        self._glossaries_by_lang[lang] = normalized.get(lang, [])
        self._enabled_glossary_tiers_by_lang[lang] = self._read_active_tier_checks()
        self._glossary_view_keys = [self._glossary_entry_key(e) for e in self._read_glossary_table_rows()]

    def _on_glossary_tier_changed(self, _: int) -> None:
        self._save_current_glossary_language_rows()
        current = self.glossary_tier_combo.currentData()
        self._glossary_selected_tier = coerce_glossary_tier(current, default=1)
        self._refresh_glossary_table_view()

    def _on_glossary_search_changed(self, text: str) -> None:
        self._save_current_glossary_language_rows()
        self._glossary_search_text = str(text or "")
        self._refresh_glossary_table_view()

    def _on_glossary_active_tier_changed(self, tier: int, checked: bool) -> None:
        _ = checked
        if self._glossary_current_lang is None:
            return
        tiers = self._read_active_tier_checks()
        if not tiers:
            check = self._glossary_active_tier_checks.get(tier)
            if check is not None:
                check.blockSignals(True)
                check.setChecked(True)
                check.blockSignals(False)
            tiers = [coerce_glossary_tier(tier, default=1)]
        self._enabled_glossary_tiers_by_lang[self._glossary_current_lang] = sorted(tiers)
        self._refresh_glossary_tier_counts()
        self._schedule_glossary_auto_save()

    def _on_glossary_language_changed(self, lang_text: str) -> None:
        next_lang = str(lang_text or "").strip().upper()
        if next_lang == "":
            return
        self._save_current_glossary_language_rows()
        self._glossary_current_lang = next_lang
        self._set_active_tier_checks(self._enabled_glossary_tiers_by_lang.get(next_lang, [1, 2]))
        self._refresh_glossary_table_view()

    def _set_glossaries_from_settings(self, settings: dict[str, object]) -> None:
        langs = supported_target_langs()
        raw_personal = settings.get("personal_glossaries_by_lang", settings.get("glossaries_by_lang"))
        self._glossaries_by_lang = normalize_glossaries(raw_personal, langs)
        self._enabled_glossary_tiers_by_lang = normalize_enabled_tiers_by_target_lang(
            settings.get("enabled_glossary_tiers_by_target_lang"),
            langs,
        )
        seed_raw = settings.get("glossary_seed_version", 2)
        try:
            self._glossary_seed_version = max(2, int(seed_raw))  # type: ignore[arg-type]
        except Exception:
            self._glossary_seed_version = 2
        preferred = str(settings.get("default_lang", "EN") or "EN").strip().upper()
        if preferred not in langs:
            preferred = langs[0]

        self.glossary_lang_combo.blockSignals(True)
        self.glossary_lang_combo.clear()
        self.glossary_lang_combo.addItems(langs)
        self.glossary_lang_combo.setCurrentText(preferred)
        self.glossary_lang_combo.blockSignals(False)
        self._glossary_current_lang = preferred
        tier_data = self.glossary_tier_combo.currentData()
        self._glossary_selected_tier = coerce_glossary_tier(tier_data, default=1)
        self._glossary_search_text = ""
        self.glossary_search_edit.clear()
        self._set_active_tier_checks(self._enabled_glossary_tiers_by_lang.get(preferred, [1, 2]))
        self._refresh_glossary_table_view()

    def _add_glossary_row(self) -> None:
        row = self.glossary_table.rowCount()
        self.glossary_table.insertRow(row)
        self.glossary_table.setItem(row, 0, QTableWidgetItem(""))
        self.glossary_table.setItem(row, 1, QTableWidgetItem(""))
        match_c = self._new_glossary_match_combo("exact")
        self.glossary_table.setCellWidget(row, 2, match_c)
        src_c = self._new_glossary_source_lang_combo("PT")
        self.glossary_table.setCellWidget(row, 3, src_c)
        tier_c = self._new_glossary_tier_combo(self._glossary_selected_tier)
        self.glossary_table.setCellWidget(row, 4, tier_c)
        match_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        src_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        tier_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        self._schedule_glossary_auto_save()

    def _add_glossary_row_and_focus(self) -> None:
        self._add_glossary_row()
        new_row = self.glossary_table.rowCount() - 1
        self.glossary_table.scrollToItem(self.glossary_table.item(new_row, 0))
        self.glossary_table.setCurrentCell(new_row, 0)
        self.glossary_table.editItem(self.glossary_table.item(new_row, 0))

    def _remove_selected_glossary_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.glossary_table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return
        for row in selected_rows:
            self.glossary_table.removeRow(row)
        self._update_glossary_warning_label(self._read_glossary_table_rows())
        self._schedule_glossary_auto_save()

    def _on_glossary_cell_changed(self, row: int, column: int) -> None:
        _ = row, column
        if self._glossary_populating:
            return
        self._schedule_glossary_auto_save()

    def _schedule_glossary_auto_save(self, *_args: object) -> None:
        if self._glossary_populating:
            return
        timer = getattr(self, "_glossary_auto_save_timer", None)
        if timer is not None:
            timer.start()

    def _commit_glossary_cell_editor(self) -> None:
        """Force any active glossary cell editor to commit its data."""
        # Moving focus away from the table causes the delegate's editor
        # to lose focus, which triggers commitData automatically in Qt.
        if hasattr(self, "apply_btn"):
            self.apply_btn.setFocus()

    def _persist_glossary_to_disk(self) -> None:
        """Save only glossary keys to disk (no full settings validation)."""
        self._commit_glossary_cell_editor()
        timer = getattr(self, "_glossary_auto_save_timer", None)
        if timer is not None:
            timer.stop()
        self._save_current_glossary_language_rows()
        self._propagate_glossary_source_phrases()
        normalized = normalize_glossaries(self._glossaries_by_lang, supported_target_langs())
        norm_tiers = normalize_enabled_tiers_by_target_lang(
            self._enabled_glossary_tiers_by_lang,
            supported_target_langs(),
        )
        glossary_values: dict[str, object] = {
            "personal_glossaries_by_lang": serialize_glossaries(normalized),
            "glossaries_by_lang": serialize_glossaries(normalized),
            "enabled_glossary_tiers_by_target_lang": {
                lang: list(norm_tiers.get(lang, [1, 2]))
                for lang in supported_target_langs()
            },
            "glossary_seed_version": max(2, int(self._glossary_seed_version)),
        }
        try:
            save_gui_settings(glossary_values)
        except Exception:  # noqa: BLE001
            pass  # silent fail on auto-save; user can still Save explicitly

    def _propagate_glossary_source_phrases(self) -> None:
        """Ensure each source phrase exists in all target languages' glossaries."""
        langs = supported_target_langs()

        def _norm_key(text: str) -> str:
            return " ".join(text.strip().casefold().split())

        by_lang: dict[str, dict[str, GlossaryEntry]] = {}
        for lang in langs:
            seen: dict[str, GlossaryEntry] = {}
            for entry in self._glossaries_by_lang.get(lang, []):
                key = _norm_key(entry.source_text)
                if key and key not in seen:
                    seen[key] = entry
            by_lang[lang] = seen

        changed = False
        for lang in langs:
            existing = by_lang[lang]
            additions: list[GlossaryEntry] = []
            for other in langs:
                if other == lang:
                    continue
                for key, entry in by_lang[other].items():
                    if key not in existing:
                        additions.append(
                            GlossaryEntry(
                                source_text=entry.source_text,
                                preferred_translation="...",
                                match_mode=entry.match_mode,
                                source_lang=entry.source_lang,
                                tier=entry.tier,
                            )
                        )
                        existing[key] = additions[-1]
            if additions:
                self._glossaries_by_lang[lang] = list(self._glossaries_by_lang.get(lang, [])) + additions
                changed = True

        if changed:
            for lang in langs:
                norm = normalize_glossaries({lang: self._glossaries_by_lang.get(lang, [])}, [lang])
                self._glossaries_by_lang[lang] = norm.get(lang, [])

    def _export_consistency_glossary_markdown(self) -> None:
        self._save_current_glossary_language_rows()
        normalized_glossaries = normalize_glossaries(self._glossaries_by_lang, supported_target_langs())
        if not any(normalized_glossaries.get(lang) for lang in supported_target_langs()):
            QMessageBox.information(self, "Glossary", "No glossary entries to export.")
            return
        markdown = build_consistency_glossary_markdown(
            normalized_glossaries,
            enabled_tiers_by_lang=self._enabled_glossary_tiers_by_lang,
            generated_at_iso=datetime.now().replace(microsecond=0).isoformat(),
            title="AI Glossary",
        )
        default_name = f"AI_Glossary_{datetime.now().date().isoformat()}.md"
        default_path = (app_data_dir() / default_name).expanduser().resolve()
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AI Glossary",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not selected_path:
            return
        target = Path(selected_path).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Glossary", f"Unable to save export file:\n{target}\n{exc}")
            return
        QMessageBox.information(self, "Glossary", f"Exported:\n{target}")

    def _build_tab_study(self) -> None:
        layout = QVBoxLayout(self.tab_study)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.study_search_edit = QLineEdit()
        self.study_search_edit.setPlaceholderText("Filter PT term or any translation...")
        search_row.addWidget(self.study_search_edit, 1)
        layout.addLayout(search_row)
        self._study_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.tab_study)
        self._study_search_shortcut.activated.connect(self._focus_study_search)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Category"))
        self.study_category_filter_combo = NoWheelComboBox()
        self.study_category_filter_combo.addItems(
            ["all", "headers", "roles", "procedure", "evidence", "reasoning", "decision_costs", "other"]
        )
        self.study_category_filter_combo.setEditable(False)
        filter_row.addWidget(self.study_category_filter_combo)
        filter_row.addWidget(QLabel("Status"))
        self.study_status_filter_combo = NoWheelComboBox()
        self.study_status_filter_combo.addItems(["all", "new", "learning", "known", "hard"])
        self.study_status_filter_combo.setEditable(False)
        filter_row.addWidget(self.study_status_filter_combo)
        filter_row.addWidget(QLabel("Coverage tier"))
        self.study_coverage_filter_combo = NoWheelComboBox()
        self.study_coverage_filter_combo.addItems(["all", "core80", "next15", "long_tail"])
        self.study_coverage_filter_combo.setEditable(False)
        filter_row.addWidget(self.study_coverage_filter_combo)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        builder = QGroupBox("Builder")
        builder_layout = QGridLayout(builder)
        builder_layout.addWidget(QLabel("Corpus source"), 0, 0)
        self.study_corpus_source_combo = NoWheelComboBox()
        self.study_corpus_source_combo.addItem("Run folders (recommended for large corpora)", "run_folders")
        self.study_corpus_source_combo.addItem("Current PDF only", "current_pdf")
        self.study_corpus_source_combo.addItem("Select PDFs...", "select_pdfs")
        self.study_corpus_source_combo.addItem("From Job Log runs (unavailable in this version)", "joblog_runs")
        self.study_corpus_source_combo.setEditable(False)
        self.study_corpus_source_combo.setToolTip(
            "Job Log source is intentionally unavailable in this version (no run/pdf path tracking migration)."
        )
        builder_layout.addWidget(self.study_corpus_source_combo, 0, 1)
        self.study_current_pdf_label = QLabel("Current PDF: not available")
        self.study_current_pdf_label.setWordWrap(True)
        builder_layout.addWidget(self.study_current_pdf_label, 0, 2, 1, 2)

        builder_layout.addWidget(QLabel("Run folders"), 1, 0)
        self.study_run_dirs_list = QListWidget()
        self.study_run_dirs_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        builder_layout.addWidget(self.study_run_dirs_list, 2, 0, 4, 1)
        run_btns = QVBoxLayout()
        self.study_add_run_dir_btn = QPushButton("Add run folder")
        self.study_remove_run_dir_btn = QPushButton("Remove selected")
        self.study_remove_run_dir_btn.setObjectName("DangerButton")
        self.study_clear_run_dirs_btn = QPushButton("Clear")
        self.study_clear_run_dirs_btn.setObjectName("DangerButton")
        run_btns.addWidget(self.study_add_run_dir_btn)
        run_btns.addWidget(self.study_remove_run_dir_btn)
        run_btns.addWidget(self.study_clear_run_dirs_btn)
        run_btns.addStretch(1)
        run_btn_wrap = QWidget()
        run_btn_wrap.setLayout(run_btns)
        builder_layout.addWidget(run_btn_wrap, 2, 1, 4, 1)

        builder_layout.addWidget(QLabel("Selected PDFs"), 6, 0)
        self.study_pdf_paths_list = QListWidget()
        self.study_pdf_paths_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        builder_layout.addWidget(self.study_pdf_paths_list, 7, 0, 3, 1)
        pdf_btns = QVBoxLayout()
        self.study_add_pdf_btn = QPushButton("Add PDF(s)")
        self.study_remove_pdf_btn = QPushButton("Remove selected")
        self.study_remove_pdf_btn.setObjectName("DangerButton")
        self.study_clear_pdf_btn = QPushButton("Clear")
        self.study_clear_pdf_btn.setObjectName("DangerButton")
        pdf_btns.addWidget(self.study_add_pdf_btn)
        pdf_btns.addWidget(self.study_remove_pdf_btn)
        pdf_btns.addWidget(self.study_clear_pdf_btn)
        pdf_btns.addStretch(1)
        pdf_btn_wrap = QWidget()
        pdf_btn_wrap.setLayout(pdf_btns)
        builder_layout.addWidget(pdf_btn_wrap, 7, 1, 3, 1)

        builder_layout.addWidget(QLabel("Mode"), 1, 2)
        self.study_mode_combo = NoWheelComboBox()
        self.study_mode_combo.addItem("Full text", "full_text")
        self.study_mode_combo.addItem("Headers only", "headers_only")
        self.study_mode_combo.setEditable(False)
        builder_layout.addWidget(self.study_mode_combo, 1, 3)

        builder_layout.addWidget(QLabel("Coverage target (%)"), 2, 2)
        self.study_coverage_spin = NoWheelSpinBox()
        self.study_coverage_spin.setRange(50, 95)
        self.study_coverage_spin.setValue(80)
        builder_layout.addWidget(self.study_coverage_spin, 2, 3)

        self.study_include_snippets_check = QCheckBox("Store snippets (privacy-sensitive; capped)")
        builder_layout.addWidget(self.study_include_snippets_check, 3, 2, 1, 2)

        builder_layout.addWidget(QLabel("Snippet max chars"), 4, 2)
        self.study_snippet_chars_spin = NoWheelSpinBox()
        self.study_snippet_chars_spin.setRange(40, 300)
        self.study_snippet_chars_spin.setValue(120)
        builder_layout.addWidget(self.study_snippet_chars_spin, 4, 3)

        self.study_generate_btn = QPushButton("Generate")
        self.study_generate_btn.setObjectName("PrimaryButton")
        self.study_cancel_generate_btn = QPushButton("Cancel")
        self.study_cancel_generate_btn.setEnabled(False)
        self.study_progress = QProgressBar()
        self.study_progress.setRange(0, 100)
        self.study_progress.setValue(0)
        self.study_summary_label = QLabel("No candidates generated yet.")
        builder_layout.addWidget(self.study_generate_btn, 5, 2)
        cancel_progress_row = QHBoxLayout()
        cancel_progress_row.addWidget(self.study_cancel_generate_btn)
        cancel_progress_row.addWidget(self.study_progress, 1)
        cancel_progress_wrap = QWidget()
        cancel_progress_wrap.setLayout(cancel_progress_row)
        builder_layout.addWidget(cancel_progress_wrap, 5, 3)
        builder_layout.addWidget(self.study_summary_label, 10, 0, 1, 4)
        builder_layout.setColumnStretch(0, 2)
        builder_layout.setColumnStretch(3, 1)
        layout.addWidget(builder)

        suggestions_group = QGroupBox("Suggestions")
        suggestions_layout = QVBoxLayout(suggestions_group)
        self.study_candidates_table = QTableWidget(0, 8, self.tab_study)
        self.study_candidates_table.setHorizontalHeaderLabels(
            ["Use", "Portuguese (PT)", "TF", "Pages", "Category", "Coverage", "Confidence", "Snippet"]
        )
        self.study_candidates_table.verticalHeader().setVisible(False)
        self.study_candidates_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.study_candidates_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.study_candidates_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        suggestions_layout.addWidget(self.study_candidates_table, 1)
        self.study_add_selected_btn = QPushButton("Add selected to Study Glossary")
        self.study_add_selected_btn.setObjectName("PrimaryButton")
        suggestions_layout.addWidget(self.study_add_selected_btn)
        layout.addWidget(suggestions_group)

        entries_group = QGroupBox("Study Glossary")
        entries_layout = QVBoxLayout(entries_group)
        self.study_entries_table = QTableWidget(0, 0, self.tab_study)
        self.study_entries_table.verticalHeader().setVisible(False)
        self.study_entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.study_entries_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        entries_layout.addWidget(self.study_entries_table, 1)

        entries_actions = QHBoxLayout()
        self.study_refresh_translations_btn = QPushButton("Refresh translations")
        self.study_export_btn = QPushButton("Export...")
        self.study_copy_to_ai_btn = QPushButton("Copy selected to AI Glossary...")
        self.study_copy_to_ai_btn.setObjectName("PrimaryButton")
        self.study_quiz_btn = QPushButton("Quiz me")
        self.study_stats_label = QLabel("")
        entries_actions.addWidget(self.study_refresh_translations_btn)
        entries_actions.addWidget(self.study_export_btn)
        entries_actions.addWidget(self.study_copy_to_ai_btn)
        entries_actions.addWidget(self.study_quiz_btn)
        entries_actions.addWidget(self.study_stats_label, 1)
        entries_layout.addLayout(entries_actions)
        layout.addWidget(entries_group, 1)

        self.study_search_edit.textChanged.connect(self._on_study_search_changed)
        self.study_category_filter_combo.currentTextChanged.connect(self._on_study_filters_changed)
        self.study_status_filter_combo.currentTextChanged.connect(self._on_study_filters_changed)
        self.study_coverage_filter_combo.currentTextChanged.connect(self._on_study_filters_changed)
        self.study_corpus_source_combo.currentTextChanged.connect(self._on_study_corpus_source_changed)
        self.study_add_run_dir_btn.clicked.connect(self._add_study_run_folder)
        self.study_remove_run_dir_btn.clicked.connect(self._remove_selected_study_run_folders)
        self.study_clear_run_dirs_btn.clicked.connect(self._clear_study_run_folders)
        self.study_add_pdf_btn.clicked.connect(self._add_study_pdf_files)
        self.study_remove_pdf_btn.clicked.connect(self._remove_selected_study_pdf_files)
        self.study_clear_pdf_btn.clicked.connect(self._clear_study_pdf_files)
        self.study_generate_btn.clicked.connect(self._generate_study_candidates)
        self.study_cancel_generate_btn.clicked.connect(self._cancel_study_generation)
        self.study_add_selected_btn.clicked.connect(self._add_selected_candidates_to_study_glossary)
        self.study_refresh_translations_btn.clicked.connect(self._refresh_selected_study_translations)
        self.study_export_btn.clicked.connect(self._export_study_glossary_markdown)
        self.study_copy_to_ai_btn.clicked.connect(self._copy_selected_study_to_ai_glossary)
        self.study_quiz_btn.clicked.connect(self._quiz_study_entry)

    def _focus_study_search(self) -> None:
        self.study_search_edit.setFocus()
        self.study_search_edit.selectAll()

    def _study_entry_key(self, term_pt: str) -> str:
        return str(term_pt or "").strip().casefold()

    def _collect_study_run_dirs(self) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for idx in range(self.study_run_dirs_list.count()):
            item = self.study_run_dirs_list.item(idx)
            if item is None:
                continue
            cleaned = item.text().strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(cleaned)
        return values

    def _set_study_run_dirs(self, run_dirs: list[str]) -> None:
        self.study_run_dirs_list.clear()
        seen: set[str] = set()
        for raw in run_dirs:
            cleaned = str(raw or "").strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            self.study_run_dirs_list.addItem(cleaned)

    def _add_study_run_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select run folder")
        if not selected:
            return
        candidate = str(Path(selected).expanduser().resolve())
        existing = {item.casefold() for item in self._collect_study_run_dirs()}
        if candidate.casefold() in existing:
            return
        self.study_run_dirs_list.addItem(candidate)

    def _remove_selected_study_run_folders(self) -> None:
        for item in self.study_run_dirs_list.selectedItems():
            row = self.study_run_dirs_list.row(item)
            self.study_run_dirs_list.takeItem(row)

    def _clear_study_run_folders(self) -> None:
        self.study_run_dirs_list.clear()

    def _collect_study_pdf_paths(self) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for idx in range(self.study_pdf_paths_list.count()):
            item = self.study_pdf_paths_list.item(idx)
            if item is None:
                continue
            cleaned = item.text().strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(cleaned)
        return values

    def _set_study_pdf_paths(self, pdf_paths: list[str]) -> None:
        self.study_pdf_paths_list.clear()
        seen: set[str] = set()
        for raw in pdf_paths:
            cleaned = str(raw or "").strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            self.study_pdf_paths_list.addItem(cleaned)
        self._study_pdf_paths = self._collect_study_pdf_paths()

    def _add_study_pdf_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF files",
            "",
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not selected:
            return
        existing = {item.casefold() for item in self._collect_study_pdf_paths()}
        for raw in selected:
            cleaned = str(Path(raw).expanduser().resolve())
            if cleaned.casefold() in existing:
                continue
            self.study_pdf_paths_list.addItem(cleaned)
            existing.add(cleaned.casefold())
        self._study_pdf_paths = self._collect_study_pdf_paths()

    def _remove_selected_study_pdf_files(self) -> None:
        for item in self.study_pdf_paths_list.selectedItems():
            row = self.study_pdf_paths_list.row(item)
            self.study_pdf_paths_list.takeItem(row)
        self._study_pdf_paths = self._collect_study_pdf_paths()

    def _clear_study_pdf_files(self) -> None:
        self.study_pdf_paths_list.clear()
        self._study_pdf_paths = []

    def _current_study_corpus_source(self) -> str:
        raw = self.study_corpus_source_combo.currentData()
        value = str(raw or self.study_corpus_source_combo.currentText() or "").strip().lower()
        if value not in {"run_folders", "current_pdf", "select_pdfs", "joblog_runs"}:
            return "run_folders"
        return value

    def _refresh_study_corpus_source_controls(self) -> None:
        mode = self._current_study_corpus_source()
        self._study_corpus_source = mode
        run_enabled = mode == "run_folders"
        pdf_enabled = mode == "select_pdfs"
        self.study_run_dirs_list.setEnabled(run_enabled)
        self.study_add_run_dir_btn.setEnabled(run_enabled)
        self.study_remove_run_dir_btn.setEnabled(run_enabled)
        self.study_clear_run_dirs_btn.setEnabled(run_enabled)
        self.study_pdf_paths_list.setEnabled(pdf_enabled)
        self.study_add_pdf_btn.setEnabled(pdf_enabled)
        self.study_remove_pdf_btn.setEnabled(pdf_enabled)
        self.study_clear_pdf_btn.setEnabled(pdf_enabled)
        if self._study_current_pdf_path is not None and self._study_current_pdf_path.exists():
            self.study_current_pdf_label.setText(f"Current PDF: {self._study_current_pdf_path}")
        else:
            self.study_current_pdf_label.setText("Current PDF: not available")
        if mode == "joblog_runs":
            self.study_current_pdf_label.setText(
                "Current PDF: unavailable for this source mode. Job Log run/pdf mapping is not enabled."
            )

    def _on_study_corpus_source_changed(self, _value: str) -> None:
        self._refresh_study_corpus_source_controls()

    def _resolve_study_corpus_inputs(self) -> tuple[str, list[str], list[str]] | None:
        source_mode = self._current_study_corpus_source()
        run_dirs = self._collect_study_run_dirs()
        pdf_paths: list[str] = []
        if source_mode == "run_folders":
            if not run_dirs:
                QMessageBox.warning(self, "Study Glossary", "Select at least one run folder.")
                return None
            return (source_mode, run_dirs, [])
        if source_mode == "current_pdf":
            current_pdf = self._study_current_pdf_path
            if current_pdf is None or (not current_pdf.exists()) or (not current_pdf.is_file()):
                QMessageBox.warning(self, "Study Glossary", "No active PDF is available. Select a PDF in the main window first.")
                return None
            return (source_mode, [], [str(current_pdf)])
        if source_mode == "select_pdfs":
            pdf_paths = self._collect_study_pdf_paths()
            if not pdf_paths:
                QMessageBox.warning(self, "Study Glossary", "Select one or more PDF files.")
                return None
            return (source_mode, [], pdf_paths)
        QMessageBox.information(
            self,
            "Study Glossary",
            "Job Log source is unavailable in this version (requires run/pdf path tracking in Job Log DB).",
        )
        return None

    def _visible_study_entries(self) -> list[StudyGlossaryEntry]:
        search = self._study_search_text.strip().casefold()
        category = self._study_filters.get("category", "all")
        status = self._study_filters.get("status", "all")
        coverage_tier = self._study_filters.get("coverage_tier", "all")
        visible: list[StudyGlossaryEntry] = []
        for entry in self._study_entries:
            if category != "all" and entry.category != category:
                continue
            if status != "all" and entry.status != status:
                continue
            if coverage_tier != "all" and entry.coverage_tier != coverage_tier:
                continue
            if search:
                haystack = [entry.term_pt]
                haystack.extend(entry.translations_by_lang.get(lang, "") for lang in self._study_supported_langs)
                if not any(search in str(value or "").casefold() for value in haystack):
                    continue
            visible.append(entry)
        return visible

    def _set_study_entries_table_rows(self, rows: list[StudyGlossaryEntry]) -> None:
        headers = ["Portuguese (PT)"] + self._study_supported_langs + [
            "TF",
            "Pages",
            "Docs",
            "Category",
            "Status",
            "Next review",
            "Coverage",
            "Snippet",
        ]
        self.study_entries_table.setColumnCount(len(headers))
        self.study_entries_table.setHorizontalHeaderLabels(headers)
        self.study_entries_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for lang_index in range(len(self._study_supported_langs)):
            self.study_entries_table.horizontalHeader().setSectionResizeMode(
                1 + lang_index,
                QHeaderView.ResizeMode.Stretch,
            )
        self.study_entries_table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        self.study_entries_table.setRowCount(0)
        self._study_entry_view_terms = [entry.term_pt for entry in rows]
        for entry in rows:
            row = self.study_entries_table.rowCount()
            self.study_entries_table.insertRow(row)
            self.study_entries_table.setItem(row, 0, QTableWidgetItem(entry.term_pt))
            for lang_index, lang in enumerate(self._study_supported_langs):
                self.study_entries_table.setItem(
                    row,
                    1 + lang_index,
                    QTableWidgetItem(entry.translations_by_lang.get(lang, "")),
                )
            offset = 1 + len(self._study_supported_langs)
            self.study_entries_table.setItem(row, offset + 0, QTableWidgetItem(str(int(entry.tf))))
            self.study_entries_table.setItem(row, offset + 1, QTableWidgetItem(str(int(entry.df_pages))))
            self.study_entries_table.setItem(row, offset + 2, QTableWidgetItem(str(int(entry.df_docs))))
            self.study_entries_table.setItem(row, offset + 3, QTableWidgetItem(entry.category))
            self.study_entries_table.setItem(row, offset + 4, QTableWidgetItem(entry.status))
            self.study_entries_table.setItem(row, offset + 5, QTableWidgetItem(entry.next_review_date or ""))
            self.study_entries_table.setItem(row, offset + 6, QTableWidgetItem(entry.coverage_tier))
            snippet = entry.sample_snippets[0] if entry.sample_snippets else ""
            self.study_entries_table.setItem(row, offset + 7, QTableWidgetItem(snippet))

    def _read_study_entries_table_rows(self) -> list[StudyGlossaryEntry]:
        rows: list[dict[str, object]] = []
        lang_count = len(self._study_supported_langs)
        for row in range(self.study_entries_table.rowCount()):
            term_item = self.study_entries_table.item(row, 0)
            term_pt = term_item.text().strip() if term_item else ""
            translations: dict[str, str] = {}
            for lang_index, lang in enumerate(self._study_supported_langs):
                item = self.study_entries_table.item(row, 1 + lang_index)
                translations[lang] = item.text().strip() if item else ""
            offset = 1 + lang_count
            tf_item = self.study_entries_table.item(row, offset + 0)
            df_item = self.study_entries_table.item(row, offset + 1)
            docs_item = self.study_entries_table.item(row, offset + 2)
            category_item = self.study_entries_table.item(row, offset + 3)
            status_item = self.study_entries_table.item(row, offset + 4)
            review_item = self.study_entries_table.item(row, offset + 5)
            coverage_item = self.study_entries_table.item(row, offset + 6)
            snippet_item = self.study_entries_table.item(row, offset + 7)
            rows.append(
                {
                    "term_pt": term_pt,
                    "translations_by_lang": translations,
                    "tf": (tf_item.text().strip() if tf_item else "0"),
                    "df_pages": (df_item.text().strip() if df_item else "0"),
                    "df_docs": (docs_item.text().strip() if docs_item else "0"),
                    "category": (category_item.text().strip() if category_item else "other"),
                    "status": (status_item.text().strip() if status_item else "new"),
                    "next_review_date": (review_item.text().strip() if review_item else ""),
                    "coverage_tier": (coverage_item.text().strip() if coverage_item else "long_tail"),
                    "sample_snippets": [snippet_item.text().strip()] if snippet_item and snippet_item.text().strip() else [],
                }
            )
        return normalize_study_entries(rows, self._study_supported_langs)

    def _save_current_study_table_rows(self) -> None:
        visible_rows = self._read_study_entries_table_rows()
        key_to_visible = {self._study_entry_key(entry.term_pt): entry for entry in visible_rows}
        visible_keys = {self._study_entry_key(term) for term in self._study_entry_view_terms}
        hidden = [
            entry
            for entry in self._study_entries
            if self._study_entry_key(entry.term_pt) not in visible_keys
        ]
        merged = hidden + list(key_to_visible.values())
        self._study_entries = normalize_study_entries(
            serialize_study_entries(merged, self._study_supported_langs),
            self._study_supported_langs,
        )

    def _refresh_study_entries_table(self) -> None:
        rows = self._visible_study_entries()
        self._set_study_entries_table_rows(rows)
        self._refresh_study_stats_label()

    def _refresh_study_stats_label(self) -> None:
        total = len(self._study_entries)
        visible = len(self._visible_study_entries())
        self.study_stats_label.setText(f"Entries: {visible}/{total}")

    def _on_study_search_changed(self, text: str) -> None:
        self._save_current_study_table_rows()
        self._study_search_text = str(text or "")
        self._refresh_study_entries_table()

    def _on_study_filters_changed(self, _value: str) -> None:
        self._save_current_study_table_rows()
        self._study_filters["category"] = self.study_category_filter_combo.currentText().strip().lower() or "all"
        self._study_filters["status"] = self.study_status_filter_combo.currentText().strip().lower() or "all"
        self._study_filters["coverage_tier"] = self.study_coverage_filter_combo.currentText().strip().lower() or "all"
        self._refresh_study_entries_table()

    def _set_study_candidates_table_rows(self, rows: list[StudyCandidate], selected_terms: set[str]) -> None:
        self.study_candidates_table.setRowCount(0)
        self._study_candidate_keys = []
        for candidate in rows:
            row = self.study_candidates_table.rowCount()
            self.study_candidates_table.insertRow(row)
            check = QCheckBox()
            check.setChecked(self._study_entry_key(candidate.term_pt) in selected_terms)
            self.study_candidates_table.setCellWidget(row, 0, check)
            self.study_candidates_table.setItem(row, 1, QTableWidgetItem(candidate.term_pt))
            self.study_candidates_table.setItem(row, 2, QTableWidgetItem(str(int(candidate.tf))))
            self.study_candidates_table.setItem(row, 3, QTableWidgetItem(str(int(candidate.df_pages))))
            self.study_candidates_table.setItem(row, 4, QTableWidgetItem(candidate.category))
            self.study_candidates_table.setItem(row, 5, QTableWidgetItem(candidate.coverage_tier))
            self.study_candidates_table.setItem(row, 6, QTableWidgetItem(f"{float(candidate.confidence):.3f}"))
            snippet = candidate.sample_snippets[0] if candidate.sample_snippets else ""
            self.study_candidates_table.setItem(row, 7, QTableWidgetItem(snippet))
            self._study_candidate_keys.append(self._study_entry_key(candidate.term_pt))

    def _set_study_generation_controls_busy(self, busy: bool) -> None:
        enabled = not busy
        self.study_generate_btn.setEnabled(enabled)
        self.study_corpus_source_combo.setEnabled(enabled)
        self.study_mode_combo.setEnabled(enabled)
        self.study_include_snippets_check.setEnabled(enabled)
        self.study_snippet_chars_spin.setEnabled(enabled)
        self.study_coverage_spin.setEnabled(enabled)
        self.study_cancel_generate_btn.setEnabled(busy)
        if enabled:
            self._refresh_study_corpus_source_controls()
        else:
            self.study_run_dirs_list.setEnabled(False)
            self.study_add_run_dir_btn.setEnabled(False)
            self.study_remove_run_dir_btn.setEnabled(False)
            self.study_clear_run_dirs_btn.setEnabled(False)
            self.study_pdf_paths_list.setEnabled(False)
            self.study_add_pdf_btn.setEnabled(False)
            self.study_remove_pdf_btn.setEnabled(False)
            self.study_clear_pdf_btn.setEnabled(False)

    def _generate_study_candidates(self) -> None:
        if self._study_candidate_thread is not None:
            return
        resolved = self._resolve_study_corpus_inputs()
        if resolved is None:
            return
        source_mode, run_dirs, pdf_paths = resolved
        mode = self.study_mode_combo.currentData()
        mode_value = str(mode or "full_text")
        include_snippets = bool(self.study_include_snippets_check.isChecked())
        snippet_max_chars = int(self.study_snippet_chars_spin.value())
        self._set_study_generation_controls_busy(True)
        self.study_progress.setValue(0)
        self.study_summary_label.setText("Generating study glossary candidates...")
        thread = QThread(self)
        worker = _StudyCandidateWorker(
            source_mode=source_mode,
            run_dirs=run_dirs,
            pdf_paths=pdf_paths,
            mode=mode_value,
            include_snippets=include_snippets,
            snippet_max_chars=snippet_max_chars,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_study_candidate_progress)
        worker.finished.connect(self._on_study_candidate_finished)
        worker.cancelled.connect(self._on_study_candidate_cancelled)
        worker.error.connect(self._on_study_candidate_error)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)
        self._study_candidate_thread = thread
        self._study_candidate_worker = worker
        thread.start()

    def _cancel_study_generation(self) -> None:
        worker = self._study_candidate_worker
        if worker is None:
            return
        worker.cancel()
        self.study_cancel_generate_btn.setEnabled(False)
        self.study_summary_label.setText("Cancelling generation...")

    def _on_study_candidate_progress(self, value: int, message: str) -> None:
        self.study_progress.setValue(max(0, min(100, int(value))))
        self.study_summary_label.setText(message)

    def _on_study_candidate_finished(self, payload: object) -> None:
        self._set_study_generation_controls_busy(False)
        data = payload if isinstance(payload, dict) else {}
        candidates_raw = data.get("candidates")
        candidates = candidates_raw if isinstance(candidates_raw, list) else []
        pages_tokens_raw = data.get("pages_tokens")
        pages_tokens: list[list[str]] = []
        if isinstance(pages_tokens_raw, list):
            for page in pages_tokens_raw:
                if not isinstance(page, list):
                    continue
                normalized_page = [str(token).strip().casefold() for token in page if str(token).strip()]
                if normalized_page:
                    pages_tokens.append(normalized_page)
        filtered = filter_candidates_by_thresholds(
            [candidate for candidate in candidates if isinstance(candidate, StudyCandidate)]
        )
        coverage_target = max(50, min(95, int(self.study_coverage_spin.value()))) / 100.0
        tiered = compute_non_overlapping_tier_assignment(
            filtered,
            pages_tokens,
            coverage_target=coverage_target,
            next_target=0.95,
        )
        filtered_for_display = apply_subsumption_suppression(
            tiered,
            pages_tokens,
            threshold=0.80,
        )
        selected_keys = {
            self._study_entry_key(candidate.term_pt)
            for candidate in filtered_for_display
            if candidate.coverage_tier == "core80"
        }
        self._study_candidate_rows = filtered_for_display
        self._set_study_candidates_table_rows(filtered_for_display, selected_keys)
        self._study_last_run_folders_processed = int(data.get("run_folders_processed", 0) or 0)
        self._study_last_total_pages_scanned = int(data.get("total_pages_scanned", 0) or 0)
        source_mode = str(data.get("source_mode", self._study_corpus_source) or "run_folders")
        source_label = "folders" if source_mode == "run_folders" else "sources"
        self.study_progress.setValue(100)
        core_count = len([item for item in filtered_for_display if item.coverage_tier == "core80"])
        self.study_summary_label.setText(
            f"Candidates: {len(filtered_for_display)} | {source_label}: {self._study_last_run_folders_processed} | "
            f"pages: {self._study_last_total_pages_scanned} | core {int(coverage_target * 100)}%: {core_count}."
        )
        self._study_candidate_thread = None
        self._study_candidate_worker = None

    def _on_study_candidate_cancelled(self) -> None:
        self._set_study_generation_controls_busy(False)
        self.study_summary_label.setText("Generation cancelled. Existing study glossary is unchanged.")
        self.study_progress.setValue(0)
        self._study_candidate_thread = None
        self._study_candidate_worker = None

    def _on_study_candidate_error(self, message: str) -> None:
        self._set_study_generation_controls_busy(False)
        self.study_summary_label.setText("Generation failed.")
        self.study_progress.setValue(0)
        self._study_candidate_thread = None
        self._study_candidate_worker = None
        QMessageBox.critical(self, "Study Glossary", message or "Failed to generate study glossary candidates.")

    def _add_selected_candidates_to_study_glossary(self) -> None:
        if not self._study_candidate_rows:
            return
        selected: list[StudyCandidate] = []
        for row in range(self.study_candidates_table.rowCount()):
            check = self.study_candidates_table.cellWidget(row, 0)
            checked = bool(check.isChecked()) if isinstance(check, QCheckBox) else False
            if not checked:
                continue
            if row < len(self._study_candidate_rows):
                selected.append(self._study_candidate_rows[row])
        if not selected:
            QMessageBox.information(self, "Study Glossary", "No candidate selected.")
            return
        new_entries = [
            build_entry_from_candidate(candidate, supported_langs=self._study_supported_langs)
            for candidate in selected
        ]
        self._save_current_study_table_rows()
        self._study_entries = merge_study_entries(
            self._study_entries,
            new_entries,
            supported_langs=self._study_supported_langs,
        )
        self._refresh_study_entries_table()

    def _selected_study_entries_from_table(self) -> list[StudyGlossaryEntry]:
        selected_rows = sorted({index.row() for index in self.study_entries_table.selectedIndexes()})
        if not selected_rows:
            return []
        visible_rows = self._visible_study_entries()
        selected_entries: list[StudyGlossaryEntry] = []
        for row in selected_rows:
            if 0 <= row < len(visible_rows):
                selected_entries.append(visible_rows[row])
        return selected_entries

    def _count_study_to_ai_conflicts(self, selected_entries: list[StudyGlossaryEntry]) -> int:
        supported_langs = supported_target_langs()
        normalized = normalize_glossaries(self._glossaries_by_lang, supported_langs)
        conflicts = 0
        for entry in selected_entries:
            source_text = entry.term_pt.strip()
            if source_text == "":
                continue
            for target_lang in supported_langs:
                preferred = entry.translations_by_lang.get(target_lang, "").strip()
                if preferred == "":
                    continue
                duplicate = any(
                    row.source_text == source_text
                    and row.preferred_translation == preferred
                    and row.match_mode == "exact"
                    and row.source_lang == "PT"
                    and int(row.tier) == 2
                    for row in normalized.get(target_lang, [])
                )
                if duplicate:
                    continue
                has_conflict = any(
                    row.source_text == source_text
                    and row.match_mode == "exact"
                    and row.source_lang == "PT"
                    and int(row.tier) == 2
                    and row.preferred_translation != preferred
                    for row in normalized.get(target_lang, [])
                )
                if has_conflict:
                    conflicts += 1
        return conflicts

    def _merge_study_entries_into_ai_glossary(
        self,
        selected_entries: list[StudyGlossaryEntry],
        *,
        replace_conflicts: bool,
    ) -> tuple[int, int, int]:
        supported_langs = supported_target_langs()
        normalized = normalize_glossaries(self._glossaries_by_lang, supported_langs)
        added = 0
        skipped = 0
        conflicts = 0
        for entry in selected_entries:
            source_text = entry.term_pt.strip()
            if source_text == "":
                continue
            for target_lang in supported_langs:
                preferred = entry.translations_by_lang.get(target_lang, "").strip()
                if preferred == "":
                    continue
                bucket = list(normalized.get(target_lang, []))
                candidate = GlossaryEntry(
                    source_text=source_text,
                    preferred_translation=preferred,
                    match_mode="exact",
                    source_lang="PT",
                    tier=2,
                )
                duplicate = any(
                    row.source_text == candidate.source_text
                    and row.preferred_translation == candidate.preferred_translation
                    and row.match_mode == candidate.match_mode
                    and row.source_lang == candidate.source_lang
                    and int(row.tier) == int(candidate.tier)
                    for row in bucket
                )
                if duplicate:
                    skipped += 1
                    continue
                conflict_indexes = [
                    index
                    for index, row in enumerate(bucket)
                    if row.source_text == candidate.source_text
                    and row.match_mode == candidate.match_mode
                    and row.source_lang == candidate.source_lang
                    and int(row.tier) == int(candidate.tier)
                    and row.preferred_translation != candidate.preferred_translation
                ]
                if conflict_indexes:
                    conflicts += 1
                    if not replace_conflicts:
                        skipped += 1
                        continue
                    for index in reversed(conflict_indexes):
                        bucket.pop(index)
                bucket.append(candidate)
                normalized[target_lang] = normalize_glossaries({target_lang: bucket}, [target_lang]).get(target_lang, [])
                added += 1
        self._glossaries_by_lang = normalize_glossaries(normalized, supported_langs)
        return (added, skipped, conflicts)

    def _copy_selected_study_to_ai_glossary(self) -> None:
        self._save_current_study_table_rows()
        self._save_current_glossary_language_rows()
        selected_entries = self._selected_study_entries_from_table()
        if not selected_entries:
            QMessageBox.information(self, "Study Glossary", "Select one or more Study Glossary rows first.")
            return
        conflicts = self._count_study_to_ai_conflicts(selected_entries)
        replace_conflicts = False
        if conflicts > 0:
            choice = QMessageBox.question(
                self,
                "Copy to AI Glossary",
                (
                    "Conflicts were detected for the default mapping "
                    "(Exact + PT + Tier 2).\n\n"
                    "Yes: replace conflicting AI glossary rows.\n"
                    "No: skip conflicting rows.\n"
                    "Cancel: abort."
                ),
                buttons=(
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                ),
                defaultButton=QMessageBox.StandardButton.No,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            replace_conflicts = choice == QMessageBox.StandardButton.Yes
        else:
            choice = QMessageBox.question(
                self,
                "Copy to AI Glossary",
                (
                    "Copy selected study entries into AI Glossary?\n\n"
                    "Defaults: match=exact, source_lang=PT, tier=2.\n"
                    "Targets: all non-empty target-language translations."
                ),
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.Yes,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        added, skipped, conflict_count = self._merge_study_entries_into_ai_glossary(
            selected_entries,
            replace_conflicts=replace_conflicts,
        )
        self._refresh_glossary_table_view()
        QMessageBox.information(
            self,
            "Copy to AI Glossary",
            f"Added: {added}\nSkipped: {skipped}\nConflicts encountered: {conflict_count}",
        )

    def _refresh_selected_study_translations(self) -> None:
        self._save_current_study_table_rows()
        selected_entries = self._selected_study_entries_from_table()
        if not selected_entries:
            QMessageBox.information(self, "Study Glossary", "Select one or more study rows first.")
            return
        self.study_refresh_translations_btn.setEnabled(False)
        self.study_progress.setValue(0)
        self.study_summary_label.setText("Refreshing translations...")
        thread = QThread(self)
        _lemma_effort = str(self._settings.get("openai_reasoning_effort_lemma", "high") or "high")
        worker = _StudyTranslationWorker(
            entries=selected_entries, supported_langs=self._study_supported_langs, lemma_effort=_lemma_effort,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_study_translation_progress)
        worker.finished.connect(self._on_study_translation_finished)
        worker.error.connect(self._on_study_translation_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)
        self._study_translation_thread = thread
        self._study_translation_worker = worker
        thread.start()

    def _on_study_translation_progress(self, value: int, message: str) -> None:
        self.study_progress.setValue(max(0, min(100, int(value))))
        self.study_summary_label.setText(message)

    def _on_study_translation_finished(self, updated_rows: object) -> None:
        entries = updated_rows if isinstance(updated_rows, list) else []
        keyed_updates = {
            self._study_entry_key(entry.term_pt): entry
            for entry in entries
            if isinstance(entry, StudyGlossaryEntry)
        }
        merged: list[StudyGlossaryEntry] = []
        for entry in self._study_entries:
            key = self._study_entry_key(entry.term_pt)
            merged.append(keyed_updates.get(key, entry))
        self._study_entries = normalize_study_entries(
            serialize_study_entries(merged, self._study_supported_langs),
            self._study_supported_langs,
        )
        self.study_refresh_translations_btn.setEnabled(True)
        self.study_progress.setValue(100)
        self.study_summary_label.setText("Translation refresh complete.")
        self._refresh_study_entries_table()
        self._study_translation_thread = None
        self._study_translation_worker = None

    def _on_study_translation_error(self, message: str) -> None:
        self.study_refresh_translations_btn.setEnabled(True)
        self.study_summary_label.setText("Translation refresh failed.")
        self.study_progress.setValue(0)
        self._study_translation_thread = None
        self._study_translation_worker = None
        QMessageBox.critical(self, "Study Glossary", message or "Failed to refresh translations.")

    def _export_study_glossary_markdown(self) -> None:
        self._save_current_study_table_rows()
        if not self._study_entries:
            QMessageBox.information(self, "Study Glossary", "No study glossary entries to export.")
            return

        chooser = QMessageBox(self)
        chooser.setWindowTitle("Export Study Glossary")
        chooser.setText("Choose export scope.")
        current_btn = chooser.addButton("Current filter (Recommended)", QMessageBox.ButtonRole.AcceptRole)
        all_btn = chooser.addButton("All entries", QMessageBox.ButtonRole.ActionRole)
        chooser.addButton(QMessageBox.StandardButton.Cancel)
        chooser.exec()
        clicked = chooser.clickedButton()
        if clicked is None or clicked == chooser.button(QMessageBox.StandardButton.Cancel):
            return
        if clicked == current_btn:
            export_rows = self._visible_study_entries()
            scope_label = "Current filter"
        else:
            export_rows = list(self._study_entries)
            scope_label = "All entries"
        if not export_rows:
            QMessageBox.information(self, "Study Glossary", "No entries match the selected export scope.")
            return

        generated_at_iso = datetime.now().replace(microsecond=0).isoformat()
        markdown = build_study_glossary_markdown(
            export_rows,
            generated_at_iso=generated_at_iso,
            run_folders_count=self._study_last_run_folders_processed,
            total_pages_scanned=self._study_last_total_pages_scanned,
            include_snippets=bool(self.study_include_snippets_check.isChecked()),
            snippet_max_chars=int(self.study_snippet_chars_spin.value()),
            scope_label=scope_label,
            supported_langs=self._study_supported_langs,
        )
        default_name = f"Study_Glossary_{datetime.now().date().isoformat()}.md"
        default_path = (app_data_dir() / default_name).expanduser().resolve()
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Study Glossary",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not selected_path:
            return
        target = Path(selected_path).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Study Glossary", f"Unable to save export file:\n{target}\n{exc}")
            return
        QMessageBox.information(self, "Study Glossary", f"Exported:\n{target}")

    def _quiz_study_entry(self) -> None:
        self._save_current_study_table_rows()
        rows = self._visible_study_entries() or list(self._study_entries)
        if not rows:
            QMessageBox.information(self, "Study Glossary", "No study entries available.")
            return
        entry = rows[self._study_quiz_index % len(rows)]
        self._study_quiz_index = (self._study_quiz_index + 1) % max(1, len(rows))
        QMessageBox.information(self, "Study Quiz", f"Portuguese term:\n{entry.term_pt}")
        translations = "\n".join(
            f"{lang}: {entry.translations_by_lang.get(lang, '').strip() or '—'}"
            for lang in self._study_supported_langs
        )
        quiz = QMessageBox(self)
        quiz.setWindowTitle("Study Quiz")
        quiz.setText(f"Translations:\n{translations}\n\nHow well do you know this term?")
        known_btn = quiz.addButton("Known", QMessageBox.ButtonRole.AcceptRole)
        learning_btn = quiz.addButton("Learning", QMessageBox.ButtonRole.ActionRole)
        hard_btn = quiz.addButton("Hard", QMessageBox.ButtonRole.DestructiveRole)
        quiz.addButton(QMessageBox.StandardButton.Cancel)
        quiz.exec()
        clicked = quiz.clickedButton()
        if clicked is None or clicked == quiz.button(QMessageBox.StandardButton.Cancel):
            return
        if clicked == known_btn:
            new_status = "known"
        elif clicked == hard_btn:
            new_status = "hard"
        else:
            new_status = "learning"
        key = self._study_entry_key(entry.term_pt)
        updated_entries: list[StudyGlossaryEntry] = []
        for existing in self._study_entries:
            if self._study_entry_key(existing.term_pt) != key:
                updated_entries.append(existing)
                continue
            updated_entries.append(
                StudyGlossaryEntry(
                    term_pt=existing.term_pt,
                    translations_by_lang=dict(existing.translations_by_lang),
                    tf=existing.tf,
                    df_pages=existing.df_pages,
                    sample_snippets=list(existing.sample_snippets),
                    category=existing.category,
                    status=new_status,  # type: ignore[arg-type]
                    next_review_date=compute_next_review_date(new_status),  # type: ignore[arg-type]
                    coverage_tier=existing.coverage_tier,
                    confidence=existing.confidence,
                )
            )
        self._study_entries = updated_entries
        self._refresh_study_entries_table()

    def _set_study_from_settings(self, settings: dict[str, object]) -> None:
        self._study_supported_langs = supported_learning_langs()
        self._study_entries = normalize_study_entries(
            settings.get("study_glossary_entries"),
            self._study_supported_langs,
        )
        self.study_include_snippets_check.setChecked(bool(settings.get("study_glossary_include_snippets", False)))
        try:
            snippet_max = int(settings.get("study_glossary_snippet_max_chars", 120))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            snippet_max = 120
        try:
            coverage_percent = int(settings.get("study_glossary_default_coverage_percent", 80))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            coverage_percent = 80
        self.study_snippet_chars_spin.setValue(max(40, min(300, snippet_max)))
        self.study_coverage_spin.setValue(max(50, min(95, coverage_percent)))
        run_dirs_raw = settings.get("study_glossary_last_run_dirs")
        run_dirs = [str(item).strip() for item in run_dirs_raw] if isinstance(run_dirs_raw, list) else []
        source_raw = str(settings.get("study_glossary_corpus_source", "run_folders") or "").strip().lower()
        if source_raw not in {"run_folders", "current_pdf", "select_pdfs", "joblog_runs"}:
            source_raw = "run_folders"
        self._study_corpus_source = source_raw
        pdf_paths_raw = settings.get("study_glossary_pdf_paths")
        pdf_paths = [str(item).strip() for item in pdf_paths_raw] if isinstance(pdf_paths_raw, list) else []
        self._set_study_run_dirs(run_dirs)
        self._set_study_pdf_paths(pdf_paths)
        self.study_corpus_source_combo.blockSignals(True)
        for idx in range(self.study_corpus_source_combo.count()):
            if str(self.study_corpus_source_combo.itemData(idx) or "").strip().lower() == source_raw:
                self.study_corpus_source_combo.setCurrentIndex(idx)
                break
        self.study_corpus_source_combo.blockSignals(False)
        self._study_search_text = ""
        self.study_search_edit.clear()
        self.study_category_filter_combo.setCurrentText("all")
        self.study_status_filter_combo.setCurrentText("all")
        self.study_coverage_filter_combo.setCurrentText("all")
        self._study_filters = {"category": "all", "status": "all", "coverage_tier": "all"}
        self._study_candidate_rows = []
        self._study_quiz_index = 0
        self._study_last_run_folders_processed = 0
        self._study_last_total_pages_scanned = 0
        self.study_candidates_table.setRowCount(0)
        self.study_progress.setValue(0)
        self.study_summary_label.setText("No candidates generated yet.")
        self._set_study_generation_controls_busy(False)
        self._refresh_study_corpus_source_controls()
        self._refresh_study_entries_table()

    def _collect_study_settings_values(self) -> dict[str, object]:
        self._save_current_study_table_rows()
        return {
            "study_glossary_entries": serialize_study_entries(self._study_entries, self._study_supported_langs),
            "study_glossary_include_snippets": bool(self.study_include_snippets_check.isChecked()),
            "study_glossary_snippet_max_chars": int(self.study_snippet_chars_spin.value()),
            "study_glossary_last_run_dirs": self._collect_study_run_dirs(),
            "study_glossary_corpus_source": self._current_study_corpus_source(),
            "study_glossary_pdf_paths": self._collect_study_pdf_paths(),
            "study_glossary_default_coverage_percent": int(self.study_coverage_spin.value()),
        }

    def _build_tab_diagnostics(self) -> None:
        layout = QVBoxLayout(self.tab_diag)
        build_group = QGroupBox("Build under test")
        build_layout = QVBoxLayout(build_group)
        self.build_identity_label = QLabel("")
        self.build_identity_label.setWordWrap(True)
        build_layout.addWidget(self.build_identity_label)
        layout.addWidget(build_group)
        self.diag_cost_summary_check = QCheckBox("Show cost summary")
        self.diag_verbose_meta_check = QCheckBox("Verbose metadata logs")
        self.diag_admin_mode_check = QCheckBox("Admin diagnostics mode")
        self.diag_snippets_check = QCheckBox("Include small sanitized snippets (first 200 chars per page)")
        self.create_bundle_btn = QPushButton("Create debug bundle")
        self.create_bundle_btn.setObjectName("PrimaryButton")
        hint = QLabel("Bundle excludes page text files and all credentials.")
        layout.addWidget(self.diag_cost_summary_check)
        layout.addWidget(self.diag_verbose_meta_check)
        layout.addWidget(self.diag_admin_mode_check)
        layout.addWidget(self.diag_snippets_check)
        layout.addWidget(self.create_bundle_btn)
        layout.addWidget(hint)
        layout.addStretch(1)
        self.diag_admin_mode_check.toggled.connect(self.diag_snippets_check.setEnabled)
        self.create_bundle_btn.clicked.connect(self._create_debug_bundle)

    def _set_values_from_settings(self, settings: dict[str, object]) -> None:
        self.ui_theme_combo.setCurrentText(str(settings.get("ui_theme", "dark_futuristic")))
        self.ui_scale_combo.setCurrentText(f"{float(settings.get('ui_scale', 1.0)):.2f}")
        self.default_lang_combo.setCurrentText(str(settings.get("default_lang", "EN")))
        self.default_effort_combo.setCurrentText(str(settings.get("default_effort", "high")))
        self.default_effort_policy_combo.setCurrentText(str(settings.get("default_effort_policy", "adaptive")))
        self.lemma_effort_combo.setCurrentText(str(settings.get("openai_reasoning_effort_lemma", "high")))
        self.default_images_combo.setCurrentText(str(settings.get("default_images_mode", "off")))
        self.default_workers_combo.setCurrentText(str(settings.get("default_workers", 3)))
        self.default_resume_check.setChecked(bool(settings.get("default_resume", True)))
        self.default_keep_check.setChecked(bool(settings.get("default_keep_intermediates", True)))
        self.default_breaks_check.setChecked(bool(settings.get("default_page_breaks", True)))
        default_end = settings.get("default_end_page")
        self.default_end_edit.setText("" if default_end in (None, "") else str(default_end))
        self.default_outdir_edit.setText(str(settings.get("default_outdir", "")))
        self.glossary_file_edit.setText(str(settings.get("glossary_file_path", "")))
        current_provider = str(settings.get("ocr_api_provider", settings.get("ocr_api_provider_default", "openai")) or "openai")
        self.ocr_provider_combo.setCurrentText(current_provider)
        self.ocr_provider_default_combo.setCurrentText(
            str(settings.get("ocr_api_provider_default", current_provider) or current_provider)
        )
        self.ocr_mode_default_combo.setCurrentText(str(settings.get("ocr_mode_default", "auto")))
        self.ocr_engine_default_combo.setCurrentText(str(settings.get("ocr_engine_default", "local_then_api")))
        self.min_chars_edit.setText(str(settings.get("min_chars_to_accept_ocr", 200)))
        self.ocr_base_url_edit.setText(str(settings.get("ocr_api_base_url", "")))
        self.ocr_model_edit.setText(str(settings.get("ocr_api_model", "")))
        provider = normalize_ocr_api_provider(current_provider)
        self.ocr_env_edit.setText(str(settings.get("ocr_api_key_env_name", default_ocr_api_env_name(provider))))
        self.gmail_gog_path_edit.setText(str(settings.get("gmail_gog_path", "")))
        self.gmail_account_edit.setText(str(settings.get("gmail_account_email", "")))
        self.gmail_intake_enabled_check.setChecked(bool(settings.get("gmail_intake_bridge_enabled", False)))
        self.gmail_intake_token_edit.setText(str(settings.get("gmail_intake_bridge_token", "")))
        self.gmail_intake_port_spin.setValue(int(settings.get("gmail_intake_port", 8765)))
        self.retries_edit.setText(str(settings.get("perf_max_transport_retries", 4)))
        self.backoff_cap_edit.setText(str(settings.get("perf_backoff_cap_seconds", 12.0)))
        self.timeout_text_edit.setText(
            str(settings.get("perf_timeout_text_seconds", DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS))
        )
        self.timeout_image_edit.setText(
            str(settings.get("perf_timeout_image_seconds", DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS))
        )
        self.allow_xhigh_check.setChecked(bool(settings.get("allow_xhigh_escalation", False)))
        self.diag_cost_summary_check.setChecked(bool(settings.get("diagnostics_show_cost_summary", True)))
        self.diag_verbose_meta_check.setChecked(bool(settings.get("diagnostics_verbose_metadata_logs", False)))
        self.diag_admin_mode_check.setChecked(bool(settings.get("diagnostics_admin_mode", True)))
        self.diag_snippets_check.setChecked(bool(settings.get("diagnostics_include_sanitized_snippets", False)))
        self.diag_snippets_check.setEnabled(self.diag_admin_mode_check.isChecked())
        self._set_glossaries_from_settings(settings)
        self._set_study_from_settings(settings)
        self._refresh_provider_controls()
        self._refresh_build_identity()

    def _current_ocr_provider(self) -> OcrApiProvider:
        provider_value = getattr(self, "ocr_provider_combo", None)
        current_text = provider_value.currentText() if provider_value is not None else "openai"
        return normalize_ocr_api_provider(current_text)

    def _refresh_provider_controls(self) -> None:
        provider_value = getattr(self, "ocr_provider_combo", None)
        current_text = provider_value.currentText() if provider_value is not None else "openai"
        provider = normalize_ocr_api_provider(current_text)
        model_default = default_ocr_api_model(provider)
        env_default = default_ocr_api_env_name(provider)
        base_default = default_ocr_api_base_url(provider)
        model_edit = getattr(self, "ocr_model_edit", None)
        env_edit = getattr(self, "ocr_env_edit", None)
        base_edit = getattr(self, "ocr_base_url_edit", None)
        if model_edit is not None:
            model_edit.setPlaceholderText(model_default)
        if env_edit is not None:
            env_edit.setPlaceholderText(env_default)
        if base_edit is not None:
            base_edit.setPlaceholderText(base_default or "Provider default")
        summary = getattr(self, "provider_summary_label", None)
        if summary is None:
            return
        try:
            openai_stored = bool(get_openai_key())
            ocr_stored = bool(get_ocr_key())
        except RuntimeError:
            openai_stored = False
            ocr_stored = False
        resolved_model = model_edit.text().strip() if model_edit is not None else ""
        resolved_env = env_edit.text().strip() if env_edit is not None else ""
        resolved_base = base_edit.text().strip() if base_edit is not None else ""
        resolved_model = resolved_model or model_default
        resolved_env = resolved_env or env_default
        resolved_base = resolved_base or (base_default or "provider default")
        summary.setText(
            f"OCR provider: {provider.value}; model: {resolved_model}; env: {resolved_env}; "
            f"base URL: {resolved_base}; OpenAI credentials {'present' if openai_stored else 'missing'}, "
            f"OCR credentials {'present' if ocr_stored else 'missing'}."
        )
        QtSettingsDialog._refresh_gmail_bridge_summary(self)

    def _refresh_gmail_bridge_summary(self) -> None:
        summary = getattr(self, "gmail_summary_label", None)
        if summary is None:
            return

        configured_path = self.gmail_gog_path_edit.text().strip() if hasattr(self, "gmail_gog_path_edit") else ""
        configured_account = self.gmail_account_edit.text().strip() if hasattr(self, "gmail_account_edit") else ""
        bridge_enabled = (
            bool(self.gmail_intake_enabled_check.isChecked())
            if hasattr(self, "gmail_intake_enabled_check")
            else False
        )
        bridge_token = (
            self.gmail_intake_token_edit.text().strip()
            if hasattr(self, "gmail_intake_token_edit")
            else ""
        )
        bridge_port = (
            int(self.gmail_intake_port_spin.value())
            if hasattr(self, "gmail_intake_port_spin")
            else 8765
        )
        summary.setText(
            f"Configured gog path: {configured_path or 'auto-detect'}\n"
            f"Configured Gmail account: {configured_account or 'auto-detect'}\n"
            f"Localhost bridge: {'enabled' if bridge_enabled else 'disabled'}\n"
            f"Bridge endpoint: http://127.0.0.1:{bridge_port}/gmail-intake\n"
            f"Bridge token: {'present' if bridge_token else 'missing'}"
        )

    def _refresh_build_identity(self) -> None:
        if not hasattr(self, "build_identity_label"):
            return
        if self._build_identity is None:
            self.build_identity_label.setText("Build identity unavailable.")
            return
        self.build_identity_label.setText(self._build_identity.summary_text())

    def _pick_gmail_gog_path(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select gog.exe",
            "",
            "Executable Files (*.exe);;All Files (*.*)",
        )
        if selected:
            self.gmail_gog_path_edit.setText(selected)
            self._refresh_key_status()

    def _test_gmail_draft_prereqs(self) -> None:
        status = assess_gmail_draft_prereqs(
            configured_gog_path=self.gmail_gog_path_edit.text().strip(),
            configured_account_email=self.gmail_account_edit.text().strip(),
        )
        self._refresh_key_status()
        if status.ready:
            path_text = str(status.gog_path) if status.gog_path is not None else "auto-detect"
            QMessageBox.information(
                self,
                "Gmail draft",
                (
                    f"{status.message}\n\n"
                    f"gog path: {path_text}\n"
                    f"Gmail account: {status.account_email}"
                ),
            )
            return
        details = status.message
        if status.accounts:
            details += "\n\nAuthenticated Gmail accounts:\n- " + "\n- ".join(status.accounts)
        QMessageBox.warning(self, "Gmail draft", details)

    def _pick_default_outdir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose default output folder")
        if chosen:
            self.default_outdir_edit.setText(chosen)

    def _pick_glossary_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select glossary JSON file",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if selected:
            self.glossary_file_edit.setText(selected)

    def _resolve_glossary_path(self) -> Path | None:
        raw = self.glossary_file_edit.text().strip()
        if raw == "":
            return None
        return Path(raw).expanduser().resolve()

    def _default_glossary_save_path(self) -> Path:
        return (app_data_dir() / "glossary.json").expanduser().resolve()

    def _load_glossary_editor_text(self, glossary_path: Path | None) -> tuple[str, str]:
        if glossary_path is None:
            return builtin_glossary_json(indent=2), "Built-in glossary"
        try:
            raw = glossary_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Unable to read glossary file: {glossary_path}") from exc
        return raw, str(glossary_path)

    def _open_glossary_editor(self) -> None:
        glossary_path = self._resolve_glossary_path()
        try:
            initial_text, source_label = self._load_glossary_editor_text(glossary_path)
        except ValueError as exc:
            QMessageBox.critical(self, "Glossary", str(exc))
            return

        editor = QtGlossaryEditorDialog(
            parent=self,
            initial_text=initial_text,
            source_label=source_label,
            initial_path=glossary_path,
            default_save_path=self._default_glossary_save_path(),
        )
        if editor.exec() == QDialog.DialogCode.Accepted and editor.saved_path is not None:
            self.glossary_file_edit.setText(str(editor.saved_path))

    def _use_builtin_glossary(self) -> None:
        if self.glossary_file_edit.text().strip() == "":
            QMessageBox.information(self, "Glossary", "Built-in glossary is already active.")
            return
        confirm = QMessageBox.question(
            self,
            "Use built-in glossary",
            "Clear custom glossary path and use built-in glossary rules?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Ok:
            return
        self.glossary_file_edit.clear()
        QMessageBox.information(self, "Glossary", "Using built-in glossary rules.")

    def _toggle_openai_key(self) -> None:
        if self.openai_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            confirm = QMessageBox.question(
                self,
                "Reveal OpenAI key",
                "Reveal stored OpenAI API key in plain text?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Ok:
                return
            try:
                stored = get_openai_key()
            except RuntimeError as exc:
                QMessageBox.critical(self, "Settings", str(exc))
                return
            if not stored:
                QMessageBox.warning(self, "Settings", "OpenAI key is not stored.")
                self._refresh_key_status()
                return
            self.openai_key_edit.setText(stored)
            self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.openai_toggle_btn.setText("Hide")
        else:
            self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.openai_toggle_btn.setText("Show")

    def _toggle_ocr_key(self) -> None:
        if self.ocr_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            confirm = QMessageBox.question(
                self,
                "Reveal OCR key",
                "Reveal stored OCR API key in plain text?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Ok:
                return
            try:
                stored = get_ocr_key()
            except RuntimeError as exc:
                QMessageBox.critical(self, "Settings", str(exc))
                return
            if not stored:
                QMessageBox.warning(self, "Settings", "OCR key is not stored.")
                self._refresh_key_status()
                return
            self.ocr_key_edit.setText(stored)
            self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.ocr_toggle_btn.setText("Hide")
        else:
            self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.ocr_toggle_btn.setText("Show")

    def _refresh_key_status(self) -> None:
        try:
            openai_stored = bool(get_openai_key())
            ocr_stored = bool(get_ocr_key())
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            openai_stored = False
            ocr_stored = False
        self.openai_status_label.setText("Stored" if openai_stored else "Not stored")
        self.ocr_status_label.setText("Stored" if ocr_stored else "Not stored")
        self.openai_toggle_btn.setEnabled(openai_stored)
        self.ocr_toggle_btn.setEnabled(ocr_stored)
        if not openai_stored:
            self.openai_key_edit.clear()
            self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.openai_toggle_btn.setText("Show")
        if not ocr_stored:
            self.ocr_key_edit.clear()
            self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.ocr_toggle_btn.setText("Show")
        QtSettingsDialog._refresh_provider_controls(self)

    def _save_openai_key(self) -> None:
        key = self.openai_key_edit.text().strip()
        if not key:
            QMessageBox.critical(self, "Settings", "OpenAI API key cannot be empty.")
            return
        try:
            set_openai_key(key)
            if not get_openai_key():
                raise RuntimeError("Secure credential storage is unavailable on this system.")
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.openai_key_edit.clear()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_toggle_btn.setText("Show")
        self._refresh_key_status()
        QMessageBox.information(self, "Settings", "Saved")

    def _clear_openai_key(self) -> None:
        try:
            delete_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.openai_key_edit.clear()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_toggle_btn.setText("Show")
        self._refresh_key_status()

    def _save_ocr_key(self) -> None:
        key = self.ocr_key_edit.text().strip()
        if not key:
            QMessageBox.critical(self, "Settings", "OCR API key cannot be empty.")
            return
        try:
            set_ocr_key(key)
            if not get_ocr_key():
                raise RuntimeError("Secure credential storage is unavailable on this system.")
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.ocr_key_edit.clear()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_toggle_btn.setText("Show")
        self._refresh_key_status()
        QMessageBox.information(self, "Settings", "Saved")

    def _clear_ocr_key(self) -> None:
        try:
            delete_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.ocr_key_edit.clear()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_toggle_btn.setText("Show")
        self._refresh_key_status()

    def _test_openai_key(self) -> None:
        try:
            key = get_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        if not key:
            QMessageBox.warning(self, "Key Test", "OpenAI key is not stored.")
            return
        started = time.perf_counter()
        try:
            client = OpenAI(api_key=key)
            client.responses.create(
                model=OPENAI_MODEL,
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                max_output_tokens=8,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Key Test", f"OpenAI key test failed: {type(exc).__name__}")
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        QMessageBox.information(self, "Key Test", f"OpenAI test passed ({latency_ms} ms).")

    def _test_ocr_key(self) -> None:
        try:
            key = get_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        if not key:
            QMessageBox.warning(self, "Key Test", "OCR key is not stored.")
            return
        provider = self._current_ocr_provider()
        base_url = self.ocr_base_url_edit.text().strip() or default_ocr_api_base_url(provider)
        model = self.ocr_model_edit.text().strip() or default_ocr_api_model(provider)
        env_name = self.ocr_env_edit.text().strip() or default_ocr_api_env_name(provider)
        started = time.perf_counter()
        try:
            test_ocr_provider_connection(
                OcrEngineConfig(
                    api_provider=provider,
                    api_base_url=base_url or None,
                    api_model=model,
                    api_key_env_name=env_name,
                ),
                api_key=key,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Key Test", f"OCR key test failed: {type(exc).__name__}")
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        QMessageBox.information(self, "Key Test", f"OCR test passed for {provider.value} ({latency_ms} ms).")

    def _restore_defaults(self) -> None:
        self.default_lang_combo.setCurrentText("EN")
        self.default_effort_combo.setCurrentText("high")
        self.default_effort_policy_combo.setCurrentText("adaptive")
        self.lemma_effort_combo.setCurrentText("high")
        self.default_images_combo.setCurrentText("off")
        self.default_workers_combo.setCurrentText("3")
        self.default_resume_check.setChecked(True)
        self.default_keep_check.setChecked(True)
        self.default_breaks_check.setChecked(True)
        self.default_start_edit.setText("1")
        self.default_end_edit.setText("")
        self.default_outdir_edit.setText("")
        self.glossary_file_edit.setText("")
        self._glossaries_by_lang = normalize_glossaries({}, supported_target_langs())
        self._glossaries_by_lang["AR"] = default_ar_entries()
        self._glossary_seed_version = 2
        self._set_glossaries_from_settings(
            {
                "default_lang": "EN",
                "glossaries_by_lang": serialize_glossaries(self._glossaries_by_lang),
                "glossary_seed_version": self._glossary_seed_version,
            }
        )
        self._set_study_from_settings(
            {
                "study_glossary_entries": [],
                "study_glossary_include_snippets": False,
                "study_glossary_snippet_max_chars": 120,
                "study_glossary_last_run_dirs": [],
                "study_glossary_corpus_source": "run_folders",
                "study_glossary_pdf_paths": [],
                "study_glossary_default_coverage_percent": 80,
            }
        )
        self.ocr_provider_combo.setCurrentText("openai")
        self.ocr_provider_default_combo.setCurrentText("openai")
        self.ocr_mode_default_combo.setCurrentText("auto")
        self.ocr_engine_default_combo.setCurrentText("local_then_api")
        self.ocr_base_url_edit.clear()
        self.ocr_model_edit.clear()
        self.ocr_env_edit.setText(default_ocr_api_env_name(OcrApiProvider.OPENAI))
        self.gmail_gog_path_edit.clear()
        self.gmail_account_edit.clear()
        self.gmail_intake_enabled_check.setChecked(False)
        self.gmail_intake_token_edit.clear()
        self.gmail_intake_port_spin.setValue(8765)
        self.retries_edit.setText("4")
        self.backoff_cap_edit.setText("12.0")
        self.timeout_text_edit.setText(str(DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS))
        self.timeout_image_edit.setText(str(DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS))
        self.allow_xhigh_check.setChecked(False)
        self._refresh_provider_controls()

    def _collect_values(self) -> dict[str, object]:
        self._commit_glossary_cell_editor()
        base_url = self.ocr_base_url_edit.text().strip()
        if not _validate_url_or_blank(base_url):
            raise ValueError("OCR base URL must be a valid http/https URL.")

        default_end_text = self.default_end_edit.text().strip()
        if default_end_text == "":
            default_end = None
        else:
            default_end = _to_int(default_end_text, field="Default end page", min_value=1, max_value=100000)
        default_start = 1

        ui_scale = _to_float(self.ui_scale_combo.currentText(), field="UI scale", min_value=1.0, max_value=1.25)
        if ui_scale not in (1.0, 1.1, 1.25):
            raise ValueError("UI scale must be one of 1.00, 1.10, or 1.25.")

        self._save_current_glossary_language_rows()
        normalized_glossaries = normalize_glossaries(self._glossaries_by_lang, supported_target_langs())
        normalized_enabled_tiers = normalize_enabled_tiers_by_target_lang(
            self._enabled_glossary_tiers_by_lang,
            supported_target_langs(),
        )
        bridge_enabled = bool(self.gmail_intake_enabled_check.isChecked())
        bridge_token = self.gmail_intake_token_edit.text().strip()
        if bridge_enabled and bridge_token == "":
            bridge_token = secrets.token_urlsafe(24)
            self.gmail_intake_token_edit.setText(bridge_token)

        return {
            "ui_theme": self.ui_theme_combo.currentText().strip(),
            "ui_scale": ui_scale,
            "default_lang": self.default_lang_combo.currentText().strip().upper(),
            "default_effort": self.default_effort_combo.currentText().strip().lower(),
            "default_effort_policy": self.default_effort_policy_combo.currentText().strip().lower(),
            "openai_reasoning_effort_lemma": self.lemma_effort_combo.currentText().strip().lower(),
            "default_images_mode": self.default_images_combo.currentText().strip().lower(),
            "default_workers": _to_int(self.default_workers_combo.currentText(), field="Default workers", min_value=1, max_value=6),
            "default_resume": bool(self.default_resume_check.isChecked()),
            "default_keep_intermediates": bool(self.default_keep_check.isChecked()),
            "default_page_breaks": bool(self.default_breaks_check.isChecked()),
            "default_start_page": default_start,
            "default_end_page": default_end,
            "default_outdir": self.default_outdir_edit.text().strip(),
            "personal_glossaries_by_lang": serialize_glossaries(normalized_glossaries),
            "glossaries_by_lang": serialize_glossaries(normalized_glossaries),
            "enabled_glossary_tiers_by_target_lang": {
                lang: list(normalized_enabled_tiers.get(lang, [1, 2]))
                for lang in supported_target_langs()
            },
            "glossary_seed_version": max(2, int(self._glossary_seed_version)),
            "glossary_file_path": self.glossary_file_edit.text().strip(),
            **self._collect_study_settings_values(),
            "ocr_api_provider": self.ocr_provider_combo.currentText().strip().lower(),
            "ocr_api_provider_default": self.ocr_provider_default_combo.currentText().strip().lower(),
            "ocr_mode_default": self.ocr_mode_default_combo.currentText().strip().lower(),
            "ocr_engine_default": self.ocr_engine_default_combo.currentText().strip().lower(),
            "ocr_api_base_url": base_url,
            "ocr_api_model": self.ocr_model_edit.text().strip(),
            "ocr_api_key_env_name": self.ocr_env_edit.text().strip()
            or default_ocr_api_env_name(normalize_ocr_api_provider(self.ocr_provider_combo.currentText())),
            "gmail_gog_path": self.gmail_gog_path_edit.text().strip(),
            "gmail_account_email": self.gmail_account_edit.text().strip(),
            "gmail_intake_bridge_enabled": bridge_enabled,
            "gmail_intake_bridge_token": bridge_token,
            "gmail_intake_port": int(self.gmail_intake_port_spin.value()),
            "perf_max_transport_retries": _to_int(self.retries_edit.text(), field="Transport retries", min_value=0, max_value=12),
            "perf_backoff_cap_seconds": _to_float(self.backoff_cap_edit.text(), field="Backoff cap", min_value=1.0, max_value=120.0),
            "perf_timeout_text_seconds": _to_int(self.timeout_text_edit.text(), field="Text timeout", min_value=5, max_value=600),
            "perf_timeout_image_seconds": _to_int(self.timeout_image_edit.text(), field="Image timeout", min_value=5, max_value=1200),
            "allow_xhigh_escalation": bool(self.allow_xhigh_check.isChecked()),
            "adaptive_effort_enabled": self.default_effort_policy_combo.currentText().strip().lower() == "adaptive",
            "adaptive_effort_xhigh_only_when_image_or_validator_fail": bool(self.allow_xhigh_check.isChecked()),
            "diagnostics_show_cost_summary": bool(self.diag_cost_summary_check.isChecked()),
            "diagnostics_verbose_metadata_logs": bool(self.diag_verbose_meta_check.isChecked()),
            "diagnostics_admin_mode": bool(self.diag_admin_mode_check.isChecked()),
            "diagnostics_include_sanitized_snippets": bool(self.diag_snippets_check.isChecked()),
            "min_chars_to_accept_ocr": _to_int(self.min_chars_edit.text(), field="Min chars to accept OCR", min_value=20, max_value=10000),
        }

    def _apply(self) -> None:
        try:
            values = self._collect_values()
        except ValueError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self._apply_callback(values, False)

    def _save(self) -> None:
        try:
            values = self._collect_values()
        except ValueError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self._apply_callback(values, True)
        QMessageBox.information(self, "Settings", "Saved")

    def reject(self) -> None:
        """Commit any pending cell edit and auto-save glossary before closing."""
        self._commit_glossary_cell_editor()
        timer = getattr(self, "_glossary_auto_save_timer", None)
        if timer is not None:
            timer.stop()
        self._persist_glossary_to_disk()
        super().reject()

    def _create_debug_bundle(self) -> None:
        try:
            snapshot = self._collect_values()
        except ValueError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save debug bundle", "", "Zip archive (*.zip)")
        if not save_path:
            return
        output = Path(save_path).expanduser().resolve()
        metadata_paths = self._collect_debug_paths()
        try:
            with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
                for path in metadata_paths:
                    if not path.exists() or not path.is_file():
                        continue
                    archive.write(path, arcname=path.name)
                archive.writestr("settings_snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Settings", f"Failed to create debug bundle: {exc}")
            return
        QMessageBox.information(self, "Settings", f"Debug bundle created:\n{output}")
