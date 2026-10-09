"""Shared translation workflow services used by the browser parity app."""

from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import uuid
from zipfile import BadZipFile
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .checkpoint import (
    bool_from_text,
    build_run_paths,
    load_run_state,
    parse_effort,
    parse_effort_policy,
    parse_image_mode,
    parse_ocr_engine_policy,
    parse_ocr_mode,
)
from .joblog_db import insert_job_run, list_job_runs, open_job_log, update_job_run, update_job_run_output_paths
from .joblog_flow import (
    JobLogSavedResult,
    JobLogSeed,
    build_joblog_saved_result,
    build_joblog_settings_save_bundle,
    build_seed_from_joblog_row,
    build_seed_from_run,
    count_words_from_docx,
    hydrate_joblog_seed,
    merge_payload_into_joblog_settings,
    normalize_joblog_payload,
)
from .ocr_engine import (
    OcrEngineConfig,
    candidate_ocr_api_env_names,
    default_ocr_api_env_name,
    local_ocr_available,
    normalize_ocr_api_provider,
    resolve_ocr_api_key,
)
from .openai_client import OpenAIResponsesClient, resolve_openai_key_with_source
from .output_paths import require_writable_output_dir
from .pricing import translation_fee_eur
from .review_export import export_review_queue
from .run_report import build_run_report_markdown
from .run_workspace_lock import RunWorkspaceBusy
from .source_document import get_source_page_count, is_pdf_source, is_supported_source_file
from .types import AnalyzeSummary, OcrMode, RunConfig, RunSummary, TargetLang
from .user_settings import (
    load_gui_settings_from_path,
    load_joblog_settings_from_path,
    save_joblog_settings_to_path,
)

if TYPE_CHECKING:
    from .accounting_policy import OrdinaryAccountingPolicy
    from .workflow import TranslationWorkflow

_PAGE_LOG_RE = re.compile(
    r"page=(?P<page>\d+)\s+image_used=(?P<image>True|False)\s+retry_used=(?P<retry>True|False)\s+status=(?P<status>[a-z_]+)"
)
_PAGE_STATUS_RE = re.compile(r"Page\s+(?P<page>\d+)\s+(?P<status>finished|failed)", re.IGNORECASE)
_MAX_JOB_LOG_LINES = 240


def _formatting_json(value):
    def default(item):
        if isinstance(item, Path):
            return str(item)
        raise TypeError("Unsupported saved config value.")
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False, default=default)


def read_reviewed_formatting_file(path: Path, *, maximum=64 * 1024 * 1024) -> bytes:
    """Read exact direct owned artifact bytes; never follow a download path link."""
    try:
        path = Path(path)
        if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
            raise ValueError
        for item in (path, *path.parents):
            info = item.lstat()
            if (item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400
                    or item != path and not stat.S_ISDIR(info.st_mode)):
                raise ValueError
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_nlink", 1) != 1:
            raise ValueError
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not 0 < before.st_size <= maximum:
                raise ValueError
            raw = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        current = path.stat()
        if (len(raw) != before.st_size or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)
                or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)):
            raise ValueError
        for item in (path, *path.parents):
            current_info = item.lstat()
            if (item.is_symlink() or getattr(current_info, "st_file_attributes", 0) & 0x400
                    or item == path and (not stat.S_ISREG(current_info.st_mode) or getattr(current_info, "st_nlink", 1) != 1)
                    or item != path and not stat.S_ISDIR(current_info.st_mode)):
                raise ValueError
        return raw
    except Exception:
        raise ValueError("formatting_job_artifact_unavailable") from None


@dataclass(frozen=True, slots=True)
class TrustedFormattingJob:
    """Backend-only snapshot. Config/context must never be serialized to a route."""
    config: RunConfig
    source_context: Any
    settings_path: Path
    run_dir: Path
    owner_json: str


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _path_text(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.expanduser().resolve())


def _serialize_joblog_seed(seed: JobLogSeed) -> dict[str, Any]:
    return {
        "completed_at": seed.completed_at,
        "translation_date": seed.translation_date,
        "job_type": seed.job_type,
        "case_number": seed.case_number,
        "court_email": seed.court_email,
        "case_entity": seed.case_entity,
        "case_city": seed.case_city,
        "service_entity": seed.service_entity,
        "service_city": seed.service_city,
        "service_date": seed.service_date,
        "lang": seed.lang,
        "pages": seed.pages,
        "word_count": seed.word_count,
        "rate_per_word": seed.rate_per_word,
        "expected_total": seed.expected_total,
        "amount_paid": seed.amount_paid,
        "api_cost": seed.api_cost,
        "run_id": seed.run_id,
        "target_lang": seed.target_lang,
        "total_tokens": seed.total_tokens,
        "estimated_api_cost": seed.estimated_api_cost,
        "quality_risk_score": seed.quality_risk_score,
        "profit": seed.profit,
        "travel_km_outbound": seed.travel_km_outbound,
        "travel_km_return": seed.travel_km_return,
        "use_service_location_in_honorarios": seed.use_service_location_in_honorarios,
        "include_transport_sentence_in_honorarios": seed.include_transport_sentence_in_honorarios,
        "pdf_path": _path_text(seed.pdf_path),
        "output_docx": _path_text(seed.output_docx),
        "partial_docx": _path_text(seed.partial_docx),
    }


def _serialize_joblog_saved_result(result: JobLogSavedResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["translated_docx_path"] = _path_text(result.translated_docx_path)
    payload["payload"] = dict(result.payload or {})
    return payload


def _serialize_joblog_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(row, "keys"):
        return {str(key): row[key] for key in row.keys()}
    return {str(key): value for key, value in dict(row).items()}


def _coerce_int_or_none(value: object) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    cleaned = str(value or "").strip()
    if cleaned == "":
        return None
    try:
        return int(cleaned)
    except ValueError:
        try:
            return int(float(cleaned))
        except ValueError:
            return None


def _coerce_float_or_none(value: object) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value or "").strip().replace(",", ".")
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    cleaned = str(value or "").strip()
    if cleaned == "":
        return default
    try:
        return bool_from_text(cleaned)
    except ValueError:
        return default


def _normalize_optional_path(value: object) -> str:
    cleaned = str(value or "").strip()
    if cleaned == "":
        return ""
    return str(Path(cleaned).expanduser().resolve())


def _normalize_gmail_batch_context(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    source = str(value.get("source", "") or "").strip()
    session_id = str(value.get("session_id", "") or "").strip()
    message_id = str(value.get("message_id", "") or "").strip()
    thread_id = str(value.get("thread_id", "") or "").strip()
    attachment_id = str(value.get("attachment_id", "") or "").strip()
    selected_attachment_filename = str(value.get("selected_attachment_filename", "") or "").strip()
    selected_target_lang = str(value.get("selected_target_lang", "") or "").strip().upper()
    gmail_batch_session_report_path = _normalize_optional_path(value.get("gmail_batch_session_report_path"))
    selected_attachment_count = _coerce_int_or_none(value.get("selected_attachment_count"))
    selected_start_page = _coerce_int_or_none(value.get("selected_start_page"))
    normalized = {
        "source": source,
        "session_id": session_id,
        "message_id": message_id,
        "thread_id": thread_id,
        "attachment_id": attachment_id,
        "selected_attachment_filename": selected_attachment_filename,
        "selected_attachment_count": int(selected_attachment_count or 0),
        "selected_target_lang": selected_target_lang,
        "selected_start_page": int(selected_start_page or 0),
        "gmail_batch_session_report_path": gmail_batch_session_report_path,
    }
    if not any(normalized.values()):
        return None
    return normalized


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        return {}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_dir_key(path: Path) -> str:
    return str(path.expanduser().resolve()).replace("\\", "/").lower()


def _default_output_dir_text(gui_settings: Mapping[str, Any], outputs_dir: Path) -> str:
    last_outdir = str(gui_settings.get("last_outdir", "") or "").strip()
    if last_outdir:
        return str(Path(last_outdir).expanduser().resolve())
    default_outdir = str(gui_settings.get("default_outdir", "") or "").strip()
    if default_outdir:
        return str(Path(default_outdir).expanduser().resolve())
    return str(outputs_dir.expanduser().resolve())


def _translation_raw_values(form_values: Mapping[str, Any], *, seed: JobLogSeed) -> dict[str, str]:
    def numeric_value(name: str, fallback: object) -> str:
        value = form_values.get(name)
        if value is None or str(value).strip() == "":
            value = fallback
        return "" if value is None else str(value).strip()

    translation_date = str(
        form_values.get("translation_date", "") or seed.translation_date or seed.completed_at[:10]
    ).strip()
    return {
        "translation_date": translation_date,
        "job_type": "Translation",
        "case_number": str(form_values.get("case_number", "") or "").strip(),
        "court_email": str(form_values.get("court_email", "") or "").strip(),
        "case_entity": str(form_values.get("case_entity", "") or "").strip(),
        "case_city": str(form_values.get("case_city", "") or "").strip(),
        "service_entity": "",
        "service_city": "",
        "service_date": translation_date,
        "travel_km_outbound": "",
        "travel_km_return": "",
        "lang": str(form_values.get("lang", "") or seed.lang).strip().upper(),
        "target_lang": str(form_values.get("target_lang", "") or seed.target_lang).strip().upper(),
        "run_id": str(form_values.get("run_id", "") or seed.run_id).strip(),
        "pages": numeric_value("pages", seed.pages),
        "word_count": numeric_value("word_count", seed.word_count),
        "total_tokens": str(form_values.get("total_tokens", "") or (seed.total_tokens or "")).strip(),
        "rate_per_word": numeric_value("rate_per_word", seed.rate_per_word),
        "expected_total": numeric_value("expected_total", seed.expected_total),
        "amount_paid": numeric_value("amount_paid", seed.amount_paid),
        "api_cost": numeric_value("api_cost", seed.api_cost),
        "estimated_api_cost": numeric_value("estimated_api_cost", seed.estimated_api_cost),
        "quality_risk_score": str(
            form_values.get("quality_risk_score", "") or (seed.quality_risk_score or "")
        ).strip(),
        "profit": "" if seed.profit is None else str(seed.profit),
        "expected_total_mode": str(form_values.get("expected_total_mode", "") or "").strip(),
    }


def build_translation_capability_flags(*, settings_path: Path) -> dict[str, Any]:
    gui_settings = load_gui_settings_from_path(settings_path)
    provider = normalize_ocr_api_provider(
        gui_settings.get("ocr_api_provider", gui_settings.get("ocr_api_provider_default", "openai"))
    )
    ocr_env_name = str(
        gui_settings.get("ocr_api_key_env_name")
        or default_ocr_api_env_name(provider)
    ).strip() or default_ocr_api_env_name(provider)
    ocr_engine_config = OcrEngineConfig(
        policy=parse_ocr_engine_policy(
            str(
                gui_settings.get(
                    "ocr_engine",
                    gui_settings.get("ocr_engine_default", "local_then_api"),
                )
                or "local_then_api"
            )
        ),
        api_provider=provider,
        api_base_url=str(gui_settings.get("ocr_api_base_url", "") or "") or None,
        api_model=str(gui_settings.get("ocr_api_model", "") or "") or None,
        api_key_env_name=ocr_env_name,
        api_timeout_seconds=float(gui_settings.get("ocr_api_timeout_seconds", 60.0) or 60.0),
    )
    translation_key, translation_source = resolve_openai_key_with_source()
    translation_source_payload = (
        translation_source.to_payload() if translation_source is not None else {"kind": "missing", "name": ""}
    )
    return {
        "ocr": {
            "mode": str(gui_settings.get("ocr_mode", gui_settings.get("ocr_mode_default", "auto")) or "auto"),
            "engine_policy": ocr_engine_config.policy.value,
            "provider": ocr_engine_config.api_provider.value,
            "local_available": local_ocr_available(),
            "api_configured": resolve_ocr_api_key(ocr_engine_config) is not None,
            "api_env_names": list(candidate_ocr_api_env_names(ocr_engine_config)),
            "default_env_name": ocr_env_name,
        },
        "translation": {
            "status": "ready" if translation_key is not None else "needs_auth",
            "credentials_configured": translation_key is not None,
            "credential_source": translation_source_payload,
            "auth_test_supported": True,
            "supports_analyze": True,
            "supports_translate": True,
            "supports_cancel": True,
            "supports_resume": True,
            "supports_rebuild": True,
            "supports_review_queue": True,
            "supports_save_joblog": True,
        },
        "gmail": {
            "status": "planned_stage_3",
            "reason": "gmail_browser_parity_not_in_stage_2",
        },
        "browser_extension": {
            "status": "ready_for_diagnostics",
            "reason": "extension_lab_is_available",
        },
    }


def build_translation_defaults(*, settings_path: Path, outputs_dir: Path) -> dict[str, Any]:
    gui_settings = load_gui_settings_from_path(settings_path)
    provider = normalize_ocr_api_provider(
        gui_settings.get("ocr_api_provider", gui_settings.get("ocr_api_provider_default", "openai"))
    )
    return {
        "source_path": "",
        "uploaded_source_path": "",
        "output_dir": _default_output_dir_text(gui_settings, outputs_dir),
        "target_lang": str(gui_settings.get("last_lang", gui_settings.get("default_lang", "EN")) or "EN").strip().upper(),
        "effort": str(gui_settings.get("effort", "high") or "high").strip().lower(),
        "effort_policy": str(
            gui_settings.get("effort_policy", gui_settings.get("default_effort_policy", "adaptive")) or "adaptive"
        ).strip().lower(),
        "image_mode": str(gui_settings.get("image_mode", gui_settings.get("default_images_mode", "off")) or "off").strip().lower(),
        "ocr_mode": str(gui_settings.get("ocr_mode", gui_settings.get("ocr_mode_default", "auto")) or "auto").strip().lower(),
        "ocr_engine": str(
            gui_settings.get("ocr_engine", gui_settings.get("ocr_engine_default", "local_then_api")) or "local_then_api"
        ).strip().lower(),
        "ocr_api_provider": provider.value,
        "start_page": int(_coerce_int_or_none(gui_settings.get("start_page")) or 1),
        "end_page": _coerce_int_or_none(gui_settings.get("end_page")),
        "max_pages": _coerce_int_or_none(gui_settings.get("max_pages")),
        "workers": max(1, min(6, int(_coerce_int_or_none(gui_settings.get("workers")) or 3))),
        "resume": _coerce_bool(gui_settings.get("resume"), True),
        "page_breaks": _coerce_bool(gui_settings.get("page_breaks"), True),
        "keep_intermediates": _coerce_bool(gui_settings.get("keep_intermediates"), True),
        "context_file": "",
        "context_text": "",
        "glossary_file": _normalize_optional_path(gui_settings.get("glossary_file_path")),
        "allow_xhigh_escalation": _coerce_bool(gui_settings.get("allow_xhigh_escalation"), False),
        "diagnostics_admin_mode": _coerce_bool(gui_settings.get("diagnostics_admin_mode"), True),
        "diagnostics_include_sanitized_snippets": _coerce_bool(
            gui_settings.get("diagnostics_include_sanitized_snippets"),
            False,
        ),
    }


def _build_config_from_form(
    *,
    form_values: Mapping[str, Any],
    settings_path: Path,
) -> RunConfig:
    defaults = load_gui_settings_from_path(settings_path)
    source_path = str(form_values.get("source_path", "") or "").strip()
    if source_path == "":
        raise ValueError("Source file is required.")
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ValueError(f"Source file must exist: {source}")
    if not is_supported_source_file(source):
        raise ValueError("Source file must be a PDF or supported image.")

    output_dir_text = str(form_values.get("output_dir", "") or "").strip()
    if output_dir_text == "":
        raise ValueError("Output folder is required.")
    output_dir = require_writable_output_dir(Path(output_dir_text))

    gmail_batch_context = _normalize_gmail_batch_context(form_values.get("gmail_batch_context"))
    gmail_prepared_launch = (
        gmail_batch_context is not None
        and str(gmail_batch_context.get("source", "") or "").strip().lower() == "gmail_intake"
    )
    gmail_target_lang = (
        str(gmail_batch_context.get("selected_target_lang", "") or "").strip().upper()
        if gmail_prepared_launch and gmail_batch_context is not None
        else ""
    )
    target_lang_text = str(
        form_values.get("target_lang", gmail_target_lang or defaults.get("default_lang", "EN"))
        or gmail_target_lang
        or "EN"
    ).strip().upper()
    if target_lang_text not in {"EN", "FR", "AR"}:
        raise ValueError("Target language must be EN, FR, or AR.")

    start_page = _coerce_int_or_none(form_values.get("start_page"))
    if start_page is None and gmail_prepared_launch and gmail_batch_context is not None:
        start_page = _coerce_int_or_none(gmail_batch_context.get("selected_start_page"))
    if start_page is None:
        start_page = 1
    if start_page <= 0:
        raise ValueError("Start page must be >= 1.")
    end_page = _coerce_int_or_none(form_values.get("end_page"))
    if end_page is not None and end_page <= 0:
        raise ValueError("End page must be >= 1.")
    max_pages = _coerce_int_or_none(form_values.get("max_pages"))
    if max_pages is not None and max_pages <= 0:
        raise ValueError("Max pages must be >= 1.")

    context_file_text = str(form_values.get("context_file", "") or "").strip()
    glossary_file_text = str(form_values.get("glossary_file", defaults.get("glossary_file_path", "")) or "").strip()
    context_file = Path(context_file_text).expanduser().resolve() if context_file_text else None
    glossary_file = Path(glossary_file_text).expanduser().resolve() if glossary_file_text else None

    provider = normalize_ocr_api_provider(
        defaults.get("ocr_api_provider", defaults.get("ocr_api_provider_default", "openai"))
    )
    ocr_api_key_env_name = str(
        defaults.get("ocr_api_key_env_name")
        or default_ocr_api_env_name(provider)
    ).strip() or default_ocr_api_env_name(provider)
    if gmail_batch_context is not None:
        gmail_batch_context = {
            **gmail_batch_context,
            "selected_target_lang": target_lang_text,
            "selected_start_page": int(start_page),
        }
    image_mode_default = "auto" if gmail_prepared_launch else defaults.get("image_mode", defaults.get("default_images_mode", "off"))
    ocr_mode_default = "auto" if gmail_prepared_launch else defaults.get("ocr_mode", defaults.get("ocr_mode_default", "auto"))
    ocr_engine_default = (
        "local_then_api"
        if gmail_prepared_launch
        else defaults.get("ocr_engine", defaults.get("ocr_engine_default", "local_then_api"))
    )
    resume_default = False if gmail_prepared_launch else defaults.get("resume")
    keep_intermediates_default = True if gmail_prepared_launch else defaults.get("keep_intermediates")

    return RunConfig(
        pdf_path=source,
        output_dir=output_dir,
        target_lang=TargetLang(target_lang_text),
        effort=parse_effort(str(form_values.get("effort", defaults.get("effort", "high")) or "high")),
        effort_policy=parse_effort_policy(
            str(
                form_values.get(
                    "effort_policy",
                    defaults.get("effort_policy", defaults.get("default_effort_policy", "adaptive")),
                )
                or "adaptive"
            )
        ),
        allow_xhigh_escalation=_coerce_bool(
            form_values.get("allow_xhigh_escalation", defaults.get("allow_xhigh_escalation")),
            False,
        ),
        image_mode=parse_image_mode(
            str(form_values.get("image_mode", image_mode_default) or "off")
        ),
        start_page=int(start_page),
        end_page=end_page,
        max_pages=max_pages,
        workers=max(1, min(6, int(_coerce_int_or_none(form_values.get("workers")) or 3))),
        resume=_coerce_bool(form_values.get("resume", resume_default), True),
        page_breaks=_coerce_bool(form_values.get("page_breaks", defaults.get("page_breaks")), True),
        keep_intermediates=_coerce_bool(
            form_values.get("keep_intermediates", keep_intermediates_default),
            True,
        ),
        ocr_mode=parse_ocr_mode(
            str(form_values.get("ocr_mode", ocr_mode_default) or "auto")
        ),
        ocr_engine=parse_ocr_engine_policy(
            str(
                form_values.get(
                    "ocr_engine",
                    ocr_engine_default,
                )
                or "local_then_api"
            )
        ),
        ocr_api_provider=provider,
        ocr_api_base_url=str(defaults.get("ocr_api_base_url", "") or "") or None,
        ocr_api_model=str(defaults.get("ocr_api_model", "") or "") or None,
        ocr_api_key_env_name=ocr_api_key_env_name,
        context_file=context_file,
        context_text=str(form_values.get("context_text", "") or "").strip() or None,
        glossary_file=glossary_file,
        diagnostics_admin_mode=_coerce_bool(
            form_values.get("diagnostics_admin_mode", defaults.get("diagnostics_admin_mode")),
            True,
        ),
        diagnostics_include_sanitized_snippets=_coerce_bool(
            form_values.get(
                "diagnostics_include_sanitized_snippets",
                defaults.get("diagnostics_include_sanitized_snippets"),
            ),
            False,
        ),
        gmail_batch_context=gmail_batch_context,
    )


def build_translation_config(*, form_values: Mapping[str, Any], settings_path: Path) -> RunConfig:
    """Public backend form normalization; preserves all existing saved defaults."""
    return _build_config_from_form(form_values=form_values, settings_path=settings_path)


def _load_run_summary_metrics(summary_path: Path | None) -> dict[str, object]:
    payload = _load_json_object(summary_path)
    if not payload:
        return {
            "run_id": "",
            "target_lang": "",
            "total_tokens": None,
            "estimated_api_cost": None,
            "quality_risk_score": None,
        }
    totals_payload = payload.get("totals", {})
    totals = totals_payload if isinstance(totals_payload, dict) else {}
    return {
        "run_id": str(payload.get("run_id", "") or "").strip(),
        "target_lang": str(payload.get("lang", "") or "").strip(),
        "total_tokens": _coerce_int_or_none(totals.get("total_tokens")),
        "estimated_api_cost": _coerce_float_or_none(totals.get("total_cost_estimate_if_available")),
        "quality_risk_score": _coerce_float_or_none(payload.get("quality_risk_score")),
    }


def _normalize_review_queue_entries(review_queue: object) -> list[dict[str, object]]:
    if not isinstance(review_queue, list):
        return []
    items: list[dict[str, object]] = []
    for raw_item in review_queue:
        if not isinstance(raw_item, Mapping):
            continue
        page_number = _coerce_int_or_none(raw_item.get("page_number"))
        if page_number is None or page_number <= 0:
            continue
        reasons: list[str] = []
        if isinstance(raw_item.get("reasons"), list):
            for reason in raw_item.get("reasons", []):
                cleaned = str(reason or "").strip()
                if cleaned:
                    reasons.append(cleaned)
        items.append(
            {
                "page_number": int(page_number),
                "score": round(min(1.0, max(0.0, _coerce_float_or_none(raw_item.get("score")) or 0.0)), 4),
                "status": str(raw_item.get("status", "") or "").strip(),
                "reasons": reasons,
                "recommended_action": str(raw_item.get("recommended_action", "") or "").strip(),
                "retry_reason": str(raw_item.get("retry_reason", "") or "").strip(),
            }
        )
    items.sort(key=lambda item: (-float(item.get("score", 0.0) or 0.0), int(item.get("page_number", 0) or 0)))
    return items


def _load_review_queue_entries(summary_path: Path | None) -> list[dict[str, object]]:
    payload = _load_json_object(summary_path)
    return _normalize_review_queue_entries(payload.get("review_queue", []))


def _load_run_failure_context(summary_path: Path | None) -> dict[str, object]:
    payload = _load_json_object(summary_path)
    if not payload:
        return {
            "suspected_cause": "",
            "halt_reason": "",
            "scope": "",
            "page_number": None,
            "error": "",
            "status_code": None,
            "exception_class": "",
            "retry_reason": "",
            "validator_defect_reason": "",
            "ar_violation_kind": "",
            "ar_violation_samples": [],
            "ar_token_details": {},
            "request_type": "",
            "request_timeout_budget_seconds": 0.0,
            "request_elapsed_before_failure_seconds": 0.0,
            "cancel_requested_before_failure": False,
            "credential_source": {"kind": "missing", "name": ""},
            "message": "",
        }
    failure_obj = payload.get("failure_context")
    failure = failure_obj if isinstance(failure_obj, dict) else {}
    return {
        "suspected_cause": str(payload.get("suspected_cause", "") or ""),
        "halt_reason": str(payload.get("halt_reason", "") or ""),
        "scope": str(failure.get("scope", "") or ""),
        "page_number": _coerce_int_or_none(failure.get("page_number")),
        "error": str(failure.get("error", "") or ""),
        "status_code": _coerce_int_or_none(failure.get("status_code")),
        "exception_class": str(failure.get("exception_class", "") or ""),
        "retry_reason": str(failure.get("retry_reason", "") or ""),
        "validator_defect_reason": str(failure.get("validator_defect_reason", "") or ""),
        "ar_violation_kind": str(failure.get("ar_violation_kind", "") or ""),
        "ar_violation_samples": [
            str(item)
            for item in failure.get("ar_violation_samples", [])
            if str(item or "").strip() != ""
        ]
        if isinstance(failure.get("ar_violation_samples"), list)
        else [],
        "ar_token_details": (
            dict(failure.get("ar_token_details", {}))
            if isinstance(failure.get("ar_token_details"), Mapping)
            else {}
        ),
        "request_type": str(failure.get("request_type", "") or ""),
        "request_timeout_budget_seconds": _coerce_float_or_none(
            failure.get("request_timeout_budget_seconds")
        )
        or 0.0,
        "request_elapsed_before_failure_seconds": _coerce_float_or_none(
            failure.get("request_elapsed_before_failure_seconds")
        )
        or 0.0,
        "cancel_requested_before_failure": bool(failure.get("cancel_requested_before_failure", False)),
        "credential_source": (
            dict(failure.get("credential_source", {}))
            if isinstance(failure.get("credential_source"), Mapping)
            else {"kind": "missing", "name": ""}
        ),
        "message": str(failure.get("message", "") or ""),
    }


def _build_translation_seed_from_run_summary(
    *,
    settings_path: Path,
    config: RunConfig,
    summary: RunSummary,
) -> JobLogSeed:
    settings = load_joblog_settings_from_path(settings_path)
    default_rate = settings["default_rate_per_word"].get(config.target_lang.value, 0.0)
    seed = build_seed_from_run(
        pdf_path=config.pdf_path,
        lang=config.target_lang.value,
        output_docx=summary.output_docx,
        partial_docx=summary.partial_docx,
        pages_dir=summary.run_dir / "pages",
        completed_pages=summary.completed_pages,
        completed_at=datetime.now().replace(microsecond=0).isoformat(),
        default_rate_per_word=float(default_rate),
        api_cost=0.0,
    )
    summary_path = summary.run_summary_path or (summary.run_dir / "run_summary.json")
    metrics = _load_run_summary_metrics(summary_path)
    seed.run_id = str(metrics.get("run_id", "") or "").strip() or summary.run_dir.name
    seed.target_lang = str(metrics.get("target_lang", "") or "").strip() or config.target_lang.value
    seed.total_tokens = _coerce_int_or_none(metrics.get("total_tokens"))
    seed.estimated_api_cost = _coerce_float_or_none(metrics.get("estimated_api_cost"))
    seed.quality_risk_score = _coerce_float_or_none(metrics.get("quality_risk_score"))
    if seed.estimated_api_cost is not None:
        seed.api_cost = float(seed.estimated_api_cost)

    try:
        from .metadata_autofill import (
            choose_court_email_suggestion,
            extract_pdf_header_metadata_priority_pages,
            metadata_config_from_settings,
        )

        metadata_config = replace(
            metadata_config_from_settings(settings),
            ocr_mode=OcrMode.OFF,
            metadata_ai_enabled=False,
            metadata_allow_header_ocr_even_if_ocr_off=False,
        )
        suggestion = extract_pdf_header_metadata_priority_pages(
            seed.pdf_path,
            vocab_cities=list(settings["vocab_cities"]),
            config=metadata_config,
        )
    except Exception:
        suggestion = None
    if suggestion is not None:
        if suggestion.case_entity:
            seed.case_entity = suggestion.case_entity
            seed.service_entity = suggestion.service_entity or suggestion.case_entity
        if suggestion.case_city:
            seed.case_city = suggestion.case_city
            seed.service_city = suggestion.service_city or suggestion.case_city
        elif suggestion.service_city:
            seed.service_city = suggestion.service_city
        if suggestion.case_number:
            seed.case_number = suggestion.case_number
        seed.court_email = choose_court_email_suggestion(
            exact_email=suggestion.court_email,
            case_entity=seed.case_entity,
            case_city=seed.case_city,
            vocab_court_emails=list(settings.get("vocab_court_emails", [])),
        ) or ""
    return seed


def _serialize_run_config(config: RunConfig) -> dict[str, Any]:
    return {
        "source_path": str(config.pdf_path.expanduser().resolve()),
        "output_dir": str(config.output_dir.expanduser().resolve()),
        "target_lang": config.target_lang.value,
        "effort": config.effort.value,
        "effort_policy": config.effort_policy.value,
        "allow_xhigh_escalation": bool(config.allow_xhigh_escalation),
        "image_mode": config.image_mode.value,
        "ocr_mode": config.ocr_mode.value,
        "ocr_engine": config.ocr_engine.value,
        "start_page": int(config.start_page),
        "end_page": int(config.end_page) if config.end_page is not None else None,
        "max_pages": int(config.max_pages) if config.max_pages is not None else None,
        "workers": int(config.workers),
        "resume": bool(config.resume),
        "page_breaks": bool(config.page_breaks),
        "keep_intermediates": bool(config.keep_intermediates),
        "context_file": _path_text(config.context_file),
        "context_text": str(config.context_text or ""),
        "glossary_file": _path_text(config.glossary_file),
        "diagnostics_admin_mode": bool(config.diagnostics_admin_mode),
        "diagnostics_include_sanitized_snippets": bool(config.diagnostics_include_sanitized_snippets),
        "source_type": "pdf" if is_pdf_source(config.pdf_path) else "image",
        "gmail_batch_context": (
            dict(config.gmail_batch_context)
            if isinstance(config.gmail_batch_context, Mapping)
            else None
        ),
    }


def build_translation_bootstrap(
    *,
    settings_path: Path,
    job_log_db_path: Path,
    outputs_dir: Path,
    active_jobs: list[dict[str, Any]] | None = None,
    history_limit: int = 25,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "normalized_payload": {
            "defaults": build_translation_defaults(settings_path=settings_path, outputs_dir=outputs_dir),
            "history": list_translation_history(db_path=job_log_db_path, limit=history_limit),
            "active_jobs": list(active_jobs or []),
        },
        "diagnostics": {},
        "capability_flags": build_translation_capability_flags(settings_path=settings_path),
    }


def _hydrate_translation_seed_payload(seed_payload: Mapping[str, Any] | None) -> JobLogSeed:
    if seed_payload is None:
        return build_seed_from_joblog_row({})
    baseline_payload = _serialize_joblog_seed(build_seed_from_joblog_row({}))
    baseline_payload.update(dict(seed_payload))
    try:
        return hydrate_joblog_seed(baseline_payload)
    except TypeError as exc:
        raise ValueError("Translation save seed is invalid.") from exc


def list_translation_history(*, db_path: Path, limit: int = 100) -> list[dict[str, Any]]:
    with closing(open_job_log(db_path)) as conn:
        rows = list_job_runs(conn, limit=max(1, int(limit)))
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = _serialize_joblog_row(row)
        if str(payload.get("job_type", "") or "").strip().casefold() == "interpretation":
            continue
        items.append(
            {
                "row": payload,
                "seed": _serialize_joblog_seed(build_seed_from_joblog_row(payload)),
            }
        )
    return items


def reviewed_translation_word_count(docx_path: Path) -> int:
    """Read the durable review artifact, never fall back to pre-review page text."""
    try:
        word_count = count_words_from_docx(docx_path)
    except (OSError, BadZipFile, ValueError) as exc:
        raise ValueError("The reviewed translation DOCX could not be read. Save and close it, then try again.") from exc
    if word_count <= 0:
        raise ValueError("The reviewed translation DOCX is missing or has no readable words. Save and close it, then try again.")
    return word_count


def translation_job_docx_path(job: Mapping[str, Any]) -> Path:
    result = job.get("result", {})
    seed = result.get("save_seed") if isinstance(result, Mapping) else None
    automatic = result.get("automatic_layout") if isinstance(result, Mapping) else None
    eligible_kind = job.get("job_kind") == "translate" or (job.get("job_kind") == "rebuild"
        and isinstance(automatic, Mapping) and automatic.get("status") == "automatic_unreviewed")
    if job.get("status") != "completed" or not eligible_kind or not isinstance(seed, Mapping):
        raise ValueError("A completed translation with a Save-to-Job-Log seed is required.")
    path = seed.get("output_docx") or seed.get("partial_docx")
    if not path:
        raise ValueError("The reviewed translation DOCX is unavailable.")
    return Path(str(path)).expanduser().resolve()


def refresh_completed_translation_metrics(job: Mapping[str, Any]) -> dict[str, Any]:
    """Refresh a response snapshot without rewriting the original completion seed."""
    refreshed = deepcopy(dict(job))
    if job.get("status") != "completed" or job.get("job_kind") != "translate":
        return refreshed
    seed = refreshed.get("result", {}).get("save_seed")
    if not isinstance(seed, dict):
        return refreshed
    seed["word_count"] = reviewed_translation_word_count(translation_job_docx_path(job))
    seed["expected_total"] = translation_fee_eur(seed["word_count"], seed.get("rate_per_word", 0))
    seed["profit"] = None
    return refreshed


def _refresh_saved_word_count(payload: dict[str, Any], word_count: int, *, seed: JobLogSeed,
                              total_mode: str = "") -> None:
    previous_count = payload["word_count"]
    previous_total = payload["expected_total"]
    # Explicit mode is authoritative, including when the submitted count is current.
    # Older clients retain the previous derived-versus-manual amount heuristic.
    if total_mode == "auto" or (not total_mode and previous_count != word_count and previous_total in (
            translation_fee_eur(previous_count, payload["rate_per_word"]), seed.expected_total)):
        payload["expected_total"] = translation_fee_eur(word_count, payload["rate_per_word"])
    payload["word_count"] = word_count


def validate_translation_row(
    *, job_log_db_path: Path, form_values: Mapping[str, Any],
    seed_payload: Mapping[str, Any] | None = None, row_id: int | None = None,
    word_count_docx: Path | None = None, owned_run_id: str | None = None,
) -> tuple[JobLogSeed, dict[str, Any]]:
    """Validate prospective save values without changing a DB, settings or files."""
    seed = _hydrate_translation_seed_payload(seed_payload)
    raw_values = _translation_raw_values(form_values, seed=seed)
    payload = normalize_joblog_payload(
        seed=seed,
        raw_values=raw_values,
        service_same_checked=True,
        use_service_location_in_honorarios_checked=False,
        include_transport_sentence_in_honorarios_checked=True,
    )
    if word_count_docx is not None:
        _refresh_saved_word_count(payload, reviewed_translation_word_count(word_count_docx), seed=seed,
                                 total_mode=raw_values["expected_total_mode"])

    if row_id is not None and owned_run_id is not None:
        import sqlite3
        database = job_log_db_path.expanduser().resolve()
        if not database.is_file():
            raise ValueError("The saved translation record no longer exists.")
        try:
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                prior = conn.execute("SELECT run_id, target_lang FROM job_runs WHERE id = ?", (int(row_id),)).fetchone()
        except sqlite3.Error as exc:
            raise ValueError("The saved translation record could not be verified.") from exc
        if prior is None:
            raise ValueError("The saved translation record no longer exists.")
        if owned_run_id is not None and (prior["run_id"] != owned_run_id or prior["target_lang"] != seed.target_lang):
            raise ValueError("The saved record does not belong to this completed translation.")
    return seed, payload


def save_translation_row(
    *,
    settings_path: Path,
    job_log_db_path: Path,
    form_values: Mapping[str, Any],
    seed_payload: Mapping[str, Any] | None = None,
    row_id: int | None = None,
    word_count_docx: Path | None = None,
    owned_run_id: str | None = None,
) -> dict[str, Any]:
    seed, payload = validate_translation_row(job_log_db_path=job_log_db_path, form_values=form_values,
        seed_payload=seed_payload, row_id=row_id, word_count_docx=word_count_docx, owned_run_id=owned_run_id)

    with closing(open_job_log(job_log_db_path)) as conn:
        if row_id is not None:
            prior = conn.execute("SELECT profit, run_id, target_lang FROM job_runs WHERE id = ?", (int(row_id),)).fetchone()
            if prior is None:
                raise ValueError("The saved translation record no longer exists.")
            if owned_run_id is not None and (prior["run_id"] != owned_run_id or prior["target_lang"] != seed.target_lang):
                raise ValueError("The saved record does not belong to this completed translation.")
            payload["profit"] = prior["profit"]
            update_job_run(conn, row_id=int(row_id), values=payload)
            if seed.output_docx is not None or seed.partial_docx is not None:
                update_job_run_output_paths(
                    conn,
                    row_id=int(row_id),
                    output_docx_path=_path_text(seed.output_docx),
                    partial_docx_path=_path_text(seed.partial_docx),
                )
            saved_row_id = int(row_id)
        else:
            payload["profit"] = None
            insert_payload = {
                "completed_at": seed.completed_at or datetime.now().replace(microsecond=0).isoformat(),
                **payload,
                "output_docx_path": _path_text(seed.output_docx),
                "partial_docx_path": _path_text(seed.partial_docx),
            }
            saved_row_id = insert_job_run(conn, insert_payload)

    settings = load_joblog_settings_from_path(settings_path)
    merged_settings = merge_payload_into_joblog_settings(
        settings,
        payload,
        service_equals_case_by_default=False,
    )
    save_joblog_settings_to_path(
        settings_path,
        build_joblog_settings_save_bundle(merged_settings),
    )
    saved_result = build_joblog_saved_result(
        row_id=saved_row_id,
        payload=payload,
        translated_docx_path=seed.output_docx or seed.partial_docx,
    )
    return {
        "status": "ok",
        "normalized_payload": dict(payload),
        "diagnostics": {},
        "saved_result": _serialize_joblog_saved_result(saved_result),
        "capability_flags": build_translation_capability_flags(settings_path=settings_path),
    }


def upload_translation_source(
    *,
    source_path: Path,
    settings_path: Path,
) -> dict[str, Any]:
    resolved = source_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Uploaded source file was not saved correctly: {resolved}")
    if not is_supported_source_file(resolved):
        raise ValueError("Source file must be a PDF or supported image.")
    try:
        page_count = int(get_source_page_count(resolved))
    except Exception:  # noqa: BLE001
        page_count = None
    return {
        "status": "ok",
        "normalized_payload": {
            "source_path": str(resolved),
            "source_filename": resolved.name,
            "source_type": "pdf" if is_pdf_source(resolved) else "image",
            "page_count": page_count,
        },
        "diagnostics": {},
        "capability_flags": build_translation_capability_flags(settings_path=settings_path),
    }


def export_translation_review_queue_for_job(
    *,
    summary_path: Path,
) -> dict[str, Any]:
    resolved = summary_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Run summary path is unavailable: {resolved}")
    default_base = resolved.parent / "review_queue"
    csv_path, markdown_path, count = export_review_queue(resolved, default_base)
    return {
        "status": "ok",
        "normalized_payload": {
            "csv_path": str(csv_path),
            "markdown_path": str(markdown_path),
            "review_queue_count": int(count),
        },
        "diagnostics": {},
    }


def _generate_translation_run_report(
    *,
    run_dir: Path,
    settings_path: Path,
) -> dict[str, Any]:
    resolved_run_dir = run_dir.expanduser().resolve()
    if not resolved_run_dir.exists() or not resolved_run_dir.is_dir():
        raise ValueError(f"Run directory is unavailable for report generation: {resolved_run_dir}")
    gui = load_gui_settings_from_path(settings_path)
    admin_mode = bool(gui.get("diagnostics_admin_mode", True))
    include_snippets = admin_mode and bool(gui.get("diagnostics_include_sanitized_snippets", False))
    markdown = build_run_report_markdown(
        run_dir=resolved_run_dir,
        admin_mode=admin_mode,
        include_sanitized_snippets=include_snippets,
    )
    report_path = resolved_run_dir / "run_report.md"
    report_path.write_text(markdown, encoding="utf-8")
    return {
        "run_dir": str(resolved_run_dir),
        "report_path": str(report_path.expanduser().resolve()),
        "preview": markdown[:6000],
    }


def _artifacts_payload_from_summary(summary: RunSummary) -> dict[str, Any]:
    summary_path = summary.run_summary_path or (summary.run_dir / "run_summary.json")
    report_path = summary.run_dir / "run_report.md"
    return {
        "run_dir": str(summary.run_dir.expanduser().resolve()),
        "run_summary_path": _path_text(summary_path),
        "pages_dir": str((summary.run_dir / "pages").expanduser().resolve()),
        "run_report_path": _path_text(report_path if report_path.exists() else None),
        "output_docx": _path_text(summary.output_docx),
        "partial_docx": _path_text(summary.partial_docx),
    }


def _artifacts_payload_for_rebuild(*, run_dir: Path, output_docx: Path) -> dict[str, Any]:
    report_path = run_dir / "run_report.md"
    return {
        "run_dir": str(run_dir.expanduser().resolve()),
        "run_summary_path": _path_text(run_dir / "run_summary.json"),
        "pages_dir": str((run_dir / "pages").expanduser().resolve()),
        "run_report_path": _path_text(report_path if report_path.exists() else None),
        "output_docx": str(output_docx.expanduser().resolve()),
        "partial_docx": None,
    }


def _analysis_payload(summary: AnalyzeSummary) -> dict[str, Any]:
    report = _load_json_object(summary.analyze_report_path)
    advisor = {
        "recommended_ocr_mode": str(report.get("recommended_ocr_mode", "") or ""),
        "recommended_image_mode": str(report.get("recommended_image_mode", "") or ""),
        "recommendation_reasons": [
            str(item)
            for item in report.get("recommendation_reasons", [])
            if str(item or "").strip() != ""
        ]
        if isinstance(report.get("recommendation_reasons"), list)
        else [],
        "confidence": _coerce_float_or_none(report.get("confidence")) or 0.0,
        "advisor_track": str(report.get("advisor_track", "") or ""),
    }
    return {
        "run_dir": str(summary.run_dir.expanduser().resolve()),
        "analyze_report_path": str(summary.analyze_report_path.expanduser().resolve()),
        "selected_pages_count": int(summary.selected_pages_count),
        "pages_would_attach_images": int(summary.pages_would_attach_images),
        "advisor_recommendation": advisor,
        "report_excerpt": {
            "run_id": str(report.get("run_id", "") or ""),
            "lang": str(report.get("lang", "") or ""),
            "selected_pages_count": int(
                report.get("selected_pages_count", summary.selected_pages_count) or summary.selected_pages_count
            ),
            "pages_would_attach_images": int(
                report.get("pages_would_attach_images", summary.pages_would_attach_images)
                or summary.pages_would_attach_images
            ),
        },
    }


def _translation_result_payload(
    *,
    summary: RunSummary,
    config: RunConfig,
    settings_path: Path,
) -> dict[str, Any]:
    summary_path = summary.run_summary_path or (summary.run_dir / "run_summary.json")
    summary_payload = _load_json_object(summary_path)
    run_state = load_run_state(summary.run_dir / "run_state.json")
    metrics = _load_run_summary_metrics(summary_path)
    review_queue = _load_review_queue_entries(summary_path)
    payload: dict[str, Any] = {
        "success": bool(summary.success),
        "run_dir": str(summary.run_dir.expanduser().resolve()),
        "source_sha256": str(getattr(run_state, "pdf_fingerprint", "") or ""),
        "run_status": str(getattr(run_state, "run_status", "") or ""),
        "halt_reason": str(getattr(run_state, "halt_reason", "") or ""),
        "completed_pages": int(summary.completed_pages),
        "failed_page": int(summary.failed_page) if summary.failed_page is not None else None,
        "error": str(summary.error or ""),
        "artifacts": _artifacts_payload_from_summary(summary),
        "review_queue": review_queue,
        "review_queue_count": int(len(review_queue)),
        "metrics": {
            "run_id": str(metrics.get("run_id", "") or summary.run_dir.name),
            "target_lang": str(metrics.get("target_lang", "") or config.target_lang.value),
            "total_tokens": _coerce_int_or_none(metrics.get("total_tokens")),
            "estimated_api_cost": _coerce_float_or_none(metrics.get("estimated_api_cost")),
            "quality_risk_score": _coerce_float_or_none(metrics.get("quality_risk_score")),
        },
        "advisor_recommendation_applied": (
            bool(summary_payload.get("advisor_recommendation_applied"))
            if isinstance(summary_payload.get("advisor_recommendation_applied"), bool)
            else None
        ),
        "advisor_recommendation": (
            dict(summary_payload.get("advisor_recommendation", {}))
            if isinstance(summary_payload.get("advisor_recommendation"), Mapping)
            else {}
        ),
        "failure_context": _load_run_failure_context(summary_path),
        "save_seed": None,
    }
    if summary.success:
        payload["save_seed"] = _serialize_joblog_seed(
            _build_translation_seed_from_run_summary(
                settings_path=settings_path,
                config=config,
                summary=summary,
            )
        )
    return payload


@dataclass(slots=True)
class _ManagedTranslationJob:
    job_id: str
    job_kind: str
    runtime_mode: str
    workspace_id: str
    created_at: str
    updated_at: str
    status: str
    status_text: str
    config_payload: dict[str, Any]
    progress_payload: dict[str, Any]
    diagnostics_payload: dict[str, Any]
    log_tail: list[str] = field(default_factory=list)
    result_payload: dict[str, Any] = field(default_factory=dict)
    artifacts_payload: dict[str, Any] = field(default_factory=dict)
    _config: RunConfig | None = field(default=None, repr=False)
    _workflow: "TranslationWorkflow | None" = field(default=None, repr=False)
    _reservation_key: str = field(default="", repr=False)
    _page_flags: dict[int, tuple[bool, bool]] = field(default_factory=dict, repr=False)
    _reviewed_source_context: Any = field(default=None, repr=False)
    _reviewed_source_loader: Callable[[], Any] | None = field(default=None, repr=False)
    _reviewed_settings_path: Path | None = field(default=None, repr=False)
    _reviewed_formatting_records: dict[str, str] = field(default_factory=dict, repr=False)
    _ordinary_baseline: dict[str, Any] = field(default_factory=dict, repr=False)
    _completed_accountant: Any = field(default=None, repr=False)
    _ordinary_auto_layout_policy: str | None = field(default=None, repr=False)
    _rebuild_origin_job_id: str | None = field(default=None, repr=False)
    _automatic_layout_cancel_requested: bool = field(default=False, repr=False)
    _automatic_layout_publication_started: bool = field(default=False, repr=False)
    _automatic_layout_recovery_active: bool = field(default=False, repr=False)


class TranslationJobManager:
    """In-process durable job registry for browser translation workflows."""

    def __init__(
        self,
        *,
        accounting_factory: Callable[..., Any] | None = None,
        accounting_policy: OrdinaryAccountingPolicy | None = None,
        automatic_layout_runner: Callable[[str, str], Mapping[str, Any]] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, _ManagedTranslationJob] = {}
        self._reservations: dict[str, str] = {}
        # Caller-owned accounting can share a hard cap across real browser jobs.
        # Leave ordinary construction unchanged when no dependencies are supplied.
        self._workflow_accounting: dict[str, Any] = {}
        if accounting_factory is not None:
            self._workflow_accounting["accounting_factory"] = accounting_factory
        if accounting_policy is not None:
            self._workflow_accounting["accounting_policy"] = accounting_policy
        self._automatic_layout_runner = automatic_layout_runner
        self._automatic_layout_cancel = None
        self._automatic_layout_recovery_runner = None

    def set_automatic_layout_runner(self, runner: Callable[[str, str], Mapping[str, Any]]) -> None:
        """Attach the browser-owned runner before jobs start; tests may inject a bounded fake."""
        if not callable(runner) or self._automatic_layout_runner is not None:
            raise ValueError("ordinary_auto_layout_runner_unavailable")
        with self._lock:
            if self._jobs:
                raise ValueError("ordinary_auto_layout_runner_late")
            self._automatic_layout_runner = runner

    def set_automatic_layout_cancel(self, callback: Callable[[str], None]) -> None:
        if not callable(callback) or self._automatic_layout_cancel is not None:
            raise ValueError("ordinary_auto_layout_cancel_unavailable")
        self._automatic_layout_cancel = callback

    def set_automatic_layout_recovery_runner(self, runner: Callable[[str, str], Mapping[str, Any]]) -> None:
        if not callable(runner) or self._automatic_layout_recovery_runner is not None:
            raise ValueError("ordinary_auto_layout_recovery_runner_unavailable")
        self._automatic_layout_recovery_runner = runner

    def automatic_layout_recovery_active(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job._automatic_layout_recovery_active)

    def automatic_layout_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job._automatic_layout_cancel_requested)

    def begin_automatic_layout_publication(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if (job is None or job.status != "formatting"
                    or job._automatic_layout_cancel_requested):
                return False
            job._automatic_layout_publication_started = True
            return True

    def _job_actions(self, job: _ManagedTranslationJob) -> dict[str, bool]:
        status = job.status
        return {
            "cancel": (job.job_kind == "translate" and status in {"queued", "running", "cancel_requested"}
                or status == "formatting" and not job._automatic_layout_cancel_requested
                    and not job._automatic_layout_publication_started),
            "resume": job.job_kind == "translate" and status in {"failed", "cancelled"},
            "recover_layout": (job.job_kind == "translate" and status == "completed"
                and bool(job._config and job._ordinary_auto_layout_policy and job._ordinary_baseline)
                and isinstance(job.result_payload.get("automatic_layout"), dict)
                and job.result_payload["automatic_layout"].get("status") == "raw_fallback"
                and self._automatic_layout_recovery_runner is not None),
            "rebuild": job.job_kind == "translate" and status in {"completed", "failed", "cancelled"},
            "review_export": job.job_kind == "translate" and bool(job.result_payload.get("review_queue")),
            "save_row": job.job_kind == "translate" and isinstance(job.result_payload.get("save_seed"), dict),
            "download_run_report": job.job_kind == "translate" and bool(job.artifacts_payload.get("run_report_path")),
            "download_output_docx": bool(job.artifacts_payload.get("output_docx")),
            "download_partial_docx": bool(job.artifacts_payload.get("partial_docx")),
            "download_run_summary": bool(job.artifacts_payload.get("run_summary_path")),
            "download_analyze_report": bool(job.artifacts_payload.get("analyze_report_path")),
            "formatting_review": status == "completed" and job.job_kind in {"translate", "rebuild"}
                and job._reviewed_source_context is not None and job._reviewed_source_loader is not None,
        }

    def _snapshot(self, job: _ManagedTranslationJob) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "job_kind": job.job_kind,
            "runtime_mode": job.runtime_mode,
            "workspace_id": job.workspace_id,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "status": job.status,
            "status_text": job.status_text,
            "config": dict(job.config_payload),
            "progress": dict(job.progress_payload),
            "diagnostics": dict(job.diagnostics_payload),
            "logs": list(job.log_tail),
            "artifacts": deepcopy(job.artifacts_payload),
            "result": deepcopy(job.result_payload),
            "actions": self._job_actions(job),
        }

    def list_jobs(self, *, runtime_mode: str | None = None, workspace_id: str | None = None,
                  limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        if runtime_mode is not None:
            jobs = [job for job in jobs if job.runtime_mode == runtime_mode]
        if workspace_id is not None:
            jobs = [job for job in jobs if job.workspace_id == workspace_id]
        jobs.sort(key=lambda job: job.updated_at, reverse=True)
        return [self._snapshot(job) for job in jobs[: max(1, int(limit))]]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return self._snapshot(job)

    def _reserve(self, reservation_key: str) -> None:
        with self._lock:
            owner = self._reservations.get(reservation_key)
            if owner:
                existing = self._jobs.get(owner)
                if existing is not None and existing.status in {"queued", "running", "cancel_requested", "formatting"}:
                    raise ValueError(
                        "A browser translation workflow is already active for this run folder: "
                        + reservation_key
                    )

    def _claim_reservation(self, reservation_key: str, job_id: str) -> None:
        with self._lock:
            self._reservations[reservation_key] = job_id

    def _release_reservation(self, reservation_key: str, job_id: str) -> None:
        with self._lock:
            if self._reservations.get(reservation_key) == job_id:
                self._reservations.pop(reservation_key, None)

    def _append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            cleaned = str(message or "").rstrip()
            if cleaned:
                job.log_tail.append(cleaned)
                if len(job.log_tail) > _MAX_JOB_LOG_LINES:
                    job.log_tail = job.log_tail[-_MAX_JOB_LOG_LINES:]
            match = _PAGE_LOG_RE.search(cleaned)
            if match:
                job._page_flags[int(match.group("page"))] = (
                    match.group("image") == "True",
                    match.group("retry") == "True",
                )
            job.updated_at = _utc_now_iso()

    def _update_progress(self, job_id: str, selected_index: int, selected_total: int, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            real_page = 0
            image_used = False
            retry_used = False
            match = _PAGE_STATUS_RE.search(status)
            if match:
                real_page = int(match.group("page"))
                flags = job._page_flags.get(real_page)
                if flags is not None:
                    image_used, retry_used = flags
            job.progress_payload = {
                "selected_index": int(selected_index),
                "selected_total": int(selected_total),
                "real_page": int(real_page),
                "status_text": str(status),
                "image_used": bool(image_used),
                "retry_used": bool(retry_used),
            }
            job.status_text = str(status)
            job.updated_at = _utc_now_iso()

    def _mark_running(self, job_id: str, workflow: "TranslationWorkflow | None", status_text: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job._workflow = workflow
            job.status = "running"
            job.status_text = status_text
            job.updated_at = _utc_now_iso()

    def _mark_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status == "formatting":
                if job._automatic_layout_cancel_requested or job._automatic_layout_publication_started:
                    return False
                job._automatic_layout_cancel_requested = True
                job.status_text = "Stopping source layout after the current page..."
                job.updated_at = _utc_now_iso()
                callback = self._automatic_layout_cancel
                workflow = None
            else:
                callback = None
                workflow = job._workflow
                if workflow is None or job.job_kind != "translate" or job.status not in {"queued", "running"}:
                    return False
                job.status = "cancel_requested"
                job.status_text = "Cancellation requested"
                job.updated_at = _utc_now_iso()
        if callback is not None:
            try:
                callback(job_id)
            except Exception:
                pass  # The job-level intent still stops pre-dispatch/publication.
        if workflow is not None:
            workflow.cancel()
        return True

    def _mark_finished(
        self,
        *,
        job_id: str,
        status: str,
        status_text: str,
        diagnostics: Mapping[str, Any] | None = None,
        result: Mapping[str, Any] | None = None,
        artifacts: Mapping[str, Any] | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            job.status_text = status_text
            if diagnostics is not None:
                job.diagnostics_payload = dict(diagnostics)
            if result is not None:
                job.result_payload = dict(result)
            if artifacts is not None:
                job.artifacts_payload = dict(artifacts)
            job._completed_accountant = getattr(job._workflow, "_dispatch_accounting", None)
            if status in {"completed", "formatting"} and job.job_kind in {"translate", "rebuild"}:
                try:
                    self._capture_ordinary_baseline(job)
                except Exception:
                    # A local review setup failure cannot erase completed paid work.
                    job.diagnostics_payload["ordinary_layout_warning"] = "ordinary_layout_original_snapshot_unavailable"
            job._workflow = None
            job.updated_at = _utc_now_iso()
            reservation_key = job._reservation_key
        if reservation_key and status != "formatting":
            self._release_reservation(reservation_key, job_id)

    def _finish_automatic_layout(self, job_id: str, result: Mapping[str, Any] | None,
                                 error_code: str | None = None) -> None:
        """Complete the ordinary job without losing the immutable raw baseline."""
        with self._lock:
            job = self._jobs[job_id]
            if job.status != "formatting":
                raise ValueError("ordinary_auto_layout_state_changed")
            state = dict(result or {})
            output = state.get("output_path")
            if output:
                path = Path(output).expanduser().resolve()
                from .saved_docx_layout_service import _read as bounded_read
                raw = bounded_read(path, 32 * 1024 * 1024)
                if hashlib.sha256(raw).hexdigest() != state.get("sha256"):
                    raise ValueError("ordinary_auto_layout_candidate_changed")
                job.artifacts_payload["output_docx"] = str(path)
                job.result_payload.setdefault("artifacts", {})["output_docx"] = str(path)
                seed = job.result_payload.get("save_seed")
                if isinstance(seed, dict):
                    seed["output_docx"] = str(path)
                    if type(state.get("word_count")) is int:
                        seed["word_count"] = state["word_count"]
                job.status_text = "Translation and automatic layout complete; review the unreviewed DOCX"
                state["status"] = "automatic_unreviewed"
            else:
                job.status_text = ("Translation complete; source layout stopped after cancellation"
                    if job._automatic_layout_cancel_requested else
                    "Translation complete; automatic layout needs attention")
                state = {"status": "raw_fallback", "reason": error_code or state.get("reason") or "automatic_layout_unavailable"}
            if job._ordinary_auto_layout_policy and job.config_payload.get("image_mode") == "off":
                notice = ("Page images were off; coverage is limited to extractable text. "
                          "Visible text in drawings or images can be missing.")
                job.diagnostics_payload["source_coverage_notice"] = notice
                job.status_text = f"{job.status_text}. {notice}"
            job.result_payload["automatic_layout"] = state
            job.diagnostics_payload["automatic_layout"] = {"status": state["status"],
                **({"reason": state["reason"]} if state.get("reason") else {})}
            job.status = "completed"
            job._automatic_layout_recovery_active = False
            job.updated_at = _utc_now_iso()
            reservation_key = job._reservation_key
        if reservation_key:
            self._release_reservation(reservation_key, job_id)

    def _reuse_proven_ordinary_baseline(self, job: _ManagedTranslationJob, output: Path, source: Path) -> bool:
        """Reuse exact pinned raw/map bytes after a byte-equivalent local repack.

        ZIP container metadata may change on rebuild/resume. Every member byte,
        writer ownership entry, source and frozen policy must still agree.
        """
        from io import BytesIO
        from zipfile import ZipFile
        from .ordinary_layout_contracts import identifier
        from .saved_docx_layout_service import _read as bounded_read
        run_dir = Path(job.result_payload["run_dir"]).expanduser().resolve()
        intent_path = run_dir / "ordinary_auto_layout" / "intent.json"
        pointer_path = run_dir / "ordinary_auto_layout" / "operation.json"
        if not intent_path.exists() or not pointer_path.exists():
            return False
        intent = json.loads(bounded_read(intent_path, 8 * 1024 * 1024))
        pointer = json.loads(bounded_read(pointer_path, 8 * 1024 * 1024))
        origin = identifier(pointer["origin_job_id"])
        retained = run_dir / "ordinary_layout_originals" / origin
        original_path = retained / "provider.docx"
        mapping_path = retained / "provider.source_map.json"
        old_raw = bounded_read(original_path, 32 * 1024 * 1024)
        old_map_bytes = bounded_read(mapping_path, 8 * 1024 * 1024)
        new_raw = bounded_read(output, 32 * 1024 * 1024)
        new_map = json.loads(bounded_read(output.with_suffix(".source_map.json"), 8 * 1024 * 1024))
        old_map = json.loads(old_map_bytes)
        def members(raw):
            with ZipFile(BytesIO(raw)) as package:
                names = package.namelist()
                if len(names) > 1024 or len(names) != len(set(names)):
                    raise ValueError("ordinary_auto_layout_rebuild_package_changed")
                return {name: hashlib.sha256(package.read(name)).hexdigest() for name in names}
        policy = job._ordinary_auto_layout_policy or ""
        source_hash = hashlib.sha256(bounded_read(source, 64 * 1024 * 1024)).hexdigest()
        seed = job.result_payload.get("save_seed") or {}
        if (not isinstance(intent, dict) or not isinstance(pointer, dict)
                or not isinstance(old_map, dict) or not isinstance(new_map, dict)
                or intent.get("run_id") != seed.get("run_id")
                or intent.get("runtime_mode") != job.runtime_mode
                or intent.get("workspace_id") != job.workspace_id
                or intent.get("target_lang") != job.config_payload["target_lang"]
                or intent.get("policy_fingerprint") != policy.split(":", 1)[-1]
                or intent.get("source_pdf_sha256") != source_hash
                or intent.get("raw_docx_sha256") != hashlib.sha256(old_raw).hexdigest()
                or intent.get("raw_source_map_bytes_sha256") != hashlib.sha256(old_map_bytes).hexdigest()
                or old_map.get("docx_sha256") != hashlib.sha256(old_raw).hexdigest()
                or new_map.get("docx_sha256") != hashlib.sha256(new_raw).hexdigest()
                or members(old_raw) != members(new_raw)):
            raise ValueError("ordinary_auto_layout_rebuild_identity_changed")
        old_map["docx_sha256"] = new_map["docx_sha256"] = "verified-equivalent"
        if old_map != new_map:
            raise ValueError("ordinary_auto_layout_rebuild_ownership_changed")
        pages = tuple(page["source_page_number"] for page in old_map["pages"])
        if list(pages) != intent.get("selected_pages"):
            raise ValueError("ordinary_auto_layout_rebuild_page_selection_changed")
        job._ordinary_baseline = {"original_path": str(original_path),
            "original_sha256": hashlib.sha256(old_raw).hexdigest(),
            "source_sha256": source_hash, "source_path": str(source),
            "output_path": str(original_path), "selected_pages": pages,
            "mapping": json.loads(old_map_bytes),
            "mapping_sha256": hashlib.sha256(old_map_bytes).hexdigest(),
            "mapping_path": str(mapping_path)}
        return True

    def _capture_ordinary_baseline(self, job: _ManagedTranslationJob) -> None:
        """Preserve provider output before the browser exposes interactive editing."""
        from .saved_docx_layout_service import _read as bounded_read
        if job._ordinary_baseline or job._config is None:
            return
        # Formatting is a post-translation state: the public completed-job
        # accessor deliberately rejects it, while the raw seed is already
        # durable and must be captured before automatic layout can replace it.
        seed = job.result_payload.get("save_seed")
        if not isinstance(seed, dict) or not seed.get("output_docx"):
            raise ValueError("ordinary_layout_completed_output_unavailable")
        output = Path(str(seed["output_docx"])).expanduser().resolve()
        source = job._config.pdf_path.expanduser().resolve()
        if not is_pdf_source(source):
            return
        if job._ordinary_auto_layout_policy and self._reuse_proven_ordinary_baseline(job, output, source):
            return
        raw = bounded_read(output, 32 * 1024 * 1024)
        source_raw = bounded_read(source, 64 * 1024 * 1024)
        if not 0 < len(raw) <= 32 * 1024 * 1024 or not 0 < len(source_raw) <= 64 * 1024 * 1024:
            raise ValueError("ordinary_layout_snapshot_size")
        source_hash = hashlib.sha256(source_raw).hexdigest()
        expected_source = job.result_payload.get("source_sha256")
        if expected_source and expected_source != source_hash:
            raise ValueError("ordinary_layout_completed_source_changed")
        folder = Path(job.result_payload["run_dir"]) / "ordinary_layout_originals" / job.job_id
        folder.mkdir(parents=True, exist_ok=False)
        original = folder / "provider.docx"
        with original.open("xb") as handle:
            handle.write(raw)
        mapping_raw = b""
        try:
            mapping_raw = bounded_read(output.with_suffix(".source_map.json"), 8 * 1024 * 1024)
            mapping = json.loads(mapping_raw)
            if not isinstance(mapping, dict):
                mapping = {}
        except (ValueError, OSError):
            mapping = {}
        map_copy = folder / "provider.source_map.json"
        with map_copy.open("xb") as handle:
            handle.write(mapping_raw)
        pages = tuple(int(page["source_page_number"]) for page in mapping.get("pages", []))
        if not pages:
            config = job._config
            end = config.end_page or get_source_page_count(source)
            if config.max_pages is not None:
                end = min(end, config.start_page + config.max_pages - 1)
            pages = tuple(range(config.start_page, end + 1))
        job._ordinary_baseline = {"original_path": str(original), "original_sha256": hashlib.sha256(raw).hexdigest(),
            "source_sha256": source_hash, "source_path": str(source),
            "output_path": str(output), "selected_pages": pages, "mapping": mapping,
            "mapping_sha256": hashlib.sha256(mapping_raw).hexdigest() if mapping_raw else "",
            "mapping_path": str(map_copy)}

    def trusted_ordinary_layout_job(self, job_id: str, *, runtime_mode: str, workspace_id: str):
        """Resolve bytes and source associations exclusively from the owned completed job."""
        from .ordinary_layout_contracts import OrdinaryLayoutJob, fail
        from .saved_docx_layout import inspect_docx
        from .saved_docx_layout_service import _read as bounded_read
        with self._lock:
            job = self._jobs.get(job_id)
            if (job is None or job.runtime_mode != runtime_mode or job.workspace_id != workspace_id
                    or job.status not in {"completed", "formatting"} or job.job_kind not in {"translate", "rebuild"}
                    or not job._ordinary_baseline):
                fail("job_unavailable", 404)
            baseline = deepcopy(job._ordinary_baseline)
            seed = deepcopy(job.result_payload.get("save_seed", {}))
            run_id = str(seed.get("run_id") or Path(job.result_payload["run_dir"]).name)
            language = str(seed.get("target_lang") or job.config_payload["target_lang"])
        source = bounded_read(Path(baseline["source_path"]), 64 * 1024 * 1024)
        original = bounded_read(Path(baseline["original_path"]), 32 * 1024 * 1024)
        reviewed = bounded_read(Path(baseline["output_path"]), 32 * 1024 * 1024)
        if (hashlib.sha256(source).hexdigest() != baseline["source_sha256"]
                or hashlib.sha256(original).hexdigest() != baseline["original_sha256"]):
            fail("original_changed", 409)
        groups = {}
        mapping = baseline["mapping"]
        # Exact writer OOXML locations, rather than target wording or paragraph
        # counts, own physical source-page associations. Unmapped controls stay
        # unassigned; nonempty ambiguous text fails closed in the pure binder.
        current = inspect_docx(reviewed, language)
        prior = inspect_docx(original, language)
        if (mapping.get("docx_sha256") == baseline["original_sha256"]
                and len(current["paragraphs"]) == len(prior["paragraphs"]) and all(
                    (a["text"], a["has_page_break"]) == (b["text"], b["has_page_break"])
                    for a, b in zip(current["paragraphs"], prior["paragraphs"]))):
            from .ordinary_auto_layout_artifacts import bind_raw_page_map, OrdinaryAutoArtifactError
            raw_map = bounded_read(Path(baseline["mapping_path"]), 8 * 1024 * 1024)
            if hashlib.sha256(raw_map).hexdigest() != baseline["mapping_sha256"]:
                fail("page_mapping_stale", 409)
            try:
                snapshot = bind_raw_page_map(original, mapping,
                    source_pdf_sha256=baseline["source_sha256"],
                    selected_pages=tuple(baseline["selected_pages"]), target_lang=language)
                groups = snapshot.page_ids
            except OrdinaryAutoArtifactError:
                # Historical/manual layouts may lack a complete writer map.
                # They remain editable but cannot claim source-page seeding.
                groups = {}
        return OrdinaryLayoutJob(job_id=job_id, mode=runtime_mode, workspace_id=workspace_id, run_id=run_id,
            source_pdf=source, reviewed_docx=reviewed, original_docx=original, target_lang=language,
            selected_pages=tuple(baseline["selected_pages"]), binding={"job_id": job_id, "run_id": run_id,
                "source_sha256": baseline["source_sha256"], "original_sha256": baseline["original_sha256"],
                "raw_source_map_sha256": hashlib.sha256(json.dumps(mapping, sort_keys=True,
                    ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()},
            page_groups={p: tuple(ids) for p, ids in groups.items()},
            mapping_docx_sha256=hashlib.sha256(reviewed).hexdigest() if groups else "")

    def trusted_ordinary_raw_map(self, job_id: str, *, runtime_mode: str, workspace_id: str) -> dict[str, Any]:
        """Return the exact retained writer map after checking its immutable bytes."""
        with self._lock:
            job = self._jobs.get(job_id)
            if (job is None or job.runtime_mode != runtime_mode or job.workspace_id != workspace_id
                    or job.status not in {"formatting", "completed"} or not job._ordinary_baseline):
                raise ValueError("ordinary_auto_layout_job_unavailable")
            baseline = deepcopy(job._ordinary_baseline)
        from .saved_docx_layout_service import _read as bounded_read
        raw = bounded_read(Path(baseline["mapping_path"]), 8 * 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != baseline["mapping_sha256"]:
            raise ValueError("ordinary_auto_layout_map_changed")
        return json.loads(raw)

    def trusted_ordinary_baseline_identity(self, job_id: str, *, runtime_mode: str,
                                            workspace_id: str) -> dict[str, Any]:
        """Expose only content-free bytes and run identities for durable re-entry."""
        with self._lock:
            job = self._jobs.get(job_id)
            if (job is None or job.runtime_mode != runtime_mode or job.workspace_id != workspace_id
                    or job.status not in {"formatting", "completed"} or not job._ordinary_baseline):
                raise ValueError("ordinary_auto_layout_job_unavailable")
            base = job._ordinary_baseline
            return {"job_id": job_id, "run_dir": str(job.result_payload["run_dir"]),
                "run_id": str(job.result_payload.get("save_seed", {}).get("run_id") or Path(job.result_payload["run_dir"]).name),
                "source_pdf_sha256": base["source_sha256"], "raw_docx_sha256": base["original_sha256"],
                "raw_source_map_bytes_sha256": base["mapping_sha256"],
                "selected_pages": list(base["selected_pages"]),
                "target_lang": job.config_payload["target_lang"],
                "runtime_mode": runtime_mode, "workspace_id": workspace_id}

    def _start_job(
        self,
        *,
        job_kind: str,
        runtime_mode: str,
        workspace_id: str,
        config: RunConfig,
        settings_path: Path,
        reviewed_source_context: Any = None,
        reviewed_source_loader: Callable[[], Any] | None = None,
        rebuild_origin_job_id: str | None = None,
    ) -> dict[str, Any]:
        if reviewed_source_context is not None:
            from .ordinary_reviewed_source import OrdinaryReviewedSourceContext
            if (job_kind not in {"translate", "rebuild"} or type(reviewed_source_context) is not OrdinaryReviewedSourceContext
                    or not callable(reviewed_source_loader)):
                raise ValueError("ordinary_source_review_job_context_invalid")
        reservation_key = _run_dir_key(
            build_run_paths(
                config.output_dir,
                config.pdf_path,
                config.target_lang,
                gmail_batch_context=config.gmail_batch_context,
            ).run_dir
        )
        self._reserve(reservation_key)
        job_id = f"tx-{uuid.uuid4().hex[:12]}"
        created_at = _utc_now_iso()
        record = _ManagedTranslationJob(
            job_id=job_id,
            job_kind=job_kind,
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            created_at=created_at,
            updated_at=created_at,
            status="queued",
            status_text="Queued",
            config_payload=_serialize_run_config(config),
            progress_payload={
                "selected_index": 0,
                "selected_total": 0,
                "real_page": 0,
                "status_text": "Queued",
                "image_used": False,
                "retry_used": False,
            },
            diagnostics_payload={},
            _config=config,
            _reservation_key=reservation_key,
            _reviewed_source_context=reviewed_source_context,
            _reviewed_source_loader=reviewed_source_loader,
            _reviewed_settings_path=settings_path.expanduser().resolve() if reviewed_source_context is not None else None,
            _rebuild_origin_job_id=rebuild_origin_job_id,
        )
        with self._lock:
            self._jobs[job_id] = record
        self._claim_reservation(reservation_key, job_id)

        def _run_job() -> None:
            try:
                selected_context = None
                if reviewed_source_context is not None:
                    from .ordinary_reviewed_source import OrdinaryReviewedSourceContext
                    selected_context = reviewed_source_loader()
                    if (type(selected_context) is not OrdinaryReviewedSourceContext
                            or selected_context.identity != reviewed_source_context.identity):
                        raise ValueError("ordinary_source_review_job_context_changed")
                gui_settings = load_gui_settings_from_path(settings_path)
                if job_kind == "translate":
                    retries_setting = gui_settings.get("perf_max_transport_retries", 4)
                    max_retries = 4 if retries_setting is None else int(retries_setting)
                    backoff_cap = float(gui_settings.get("perf_backoff_cap_seconds", 12.0) or 12.0)
                    client = None if selected_context is not None else OpenAIResponsesClient(
                        max_transport_retries=max_retries,
                        backoff_cap_seconds=backoff_cap,
                        logger=lambda message: self._append_log(job_id, message),
                    )
                    from .workflow import TranslationWorkflow

                    from .translation_policy import resolve_ordinary_auto_layout_policy, resolve_translation_protocol
                    auto_policy = resolve_ordinary_auto_layout_policy(
                        protocol=resolve_translation_protocol(),
                        fresh_browser_job=not config.resume and self._automatic_layout_runner is not None,
                        reviewed_source=selected_context is not None)
                    if auto_policy and self._automatic_layout_runner is None:
                        raise ValueError("ordinary_auto_layout_runner_unavailable")
                    if auto_policy:
                        from .ordinary_layout_accounting import verified_page_ceiling
                        per_page = None
                        try:
                            per_page = verified_page_ceiling()
                            progress_text = ("Translating; automatic source layout follows "
                                f"(up to USD{per_page} per selected page)")
                        except Exception:
                            progress_text = "Translating; automatic source layout reference needs renewal"
                        with self._lock:
                            self._jobs[job_id]._ordinary_auto_layout_policy = auto_policy
                            self._jobs[job_id].diagnostics_payload["automatic_layout"] = {
                                "status": "planned", "policy": auto_policy.split(":", 1)[0],
                                "max_page_cost_usd": str(per_page) if per_page is not None else None}
                    else:
                        progress_text = "Translating..."
                    workflow = TranslationWorkflow(
                        client=client,
                        log_callback=lambda message: self._append_log(job_id, message),
                        progress_callback=lambda idx, total, status: self._update_progress(job_id, idx, total, status),
                        gui_settings=gui_settings,
                        **self._workflow_accounting,
                        ordinary_auto_layout_policy=auto_policy,
                        **({"reviewed_source_context": selected_context} if selected_context is not None else {}),
                    )
                    self._mark_running(job_id, workflow, progress_text)
                    summary = workflow.run(config)
                    payload = _translation_result_payload(summary=summary, config=config, settings_path=settings_path)
                    status = "completed"
                    status_text = "Translation complete"
                    if not summary.success:
                        if str(summary.error or "") == "cancelled":
                            status = "cancelled"
                            status_text = "Translation cancelled"
                        elif str(summary.error or "") == "authentication_failure":
                            status = "failed"
                            status_text = "OpenAI authentication failed"
                        elif str(summary.error or "") == "source_unavailable":
                            status = "failed"
                            status_text = "Source text is unavailable. Enable page images or OCR, then retry."
                        elif str(summary.error or "") == "source_image_unavailable":
                            status = "failed"
                            status_text = "The required full-page image is unavailable. Retry the source upload before translating."
                        else:
                            status = "failed"
                            status_text = f"Translation failed ({summary.error or 'runtime_failure'})"
                    auto_policy = workflow._ordinary_auto_layout_policy if summary.success else None
                    if auto_policy:
                        with self._lock:
                            self._jobs[job_id]._ordinary_auto_layout_policy = auto_policy
                    self._mark_finished(
                        job_id=job_id,
                        status="formatting" if auto_policy else status,
                        status_text="Formatting source layout..." if auto_policy else status_text,
                        diagnostics={"kind": "translate"},
                        result=payload,
                        artifacts=payload.get("artifacts", {}),
                    )
                    if auto_policy:
                        try:
                            auto_result = self._automatic_layout_runner(job_id, auto_policy)
                            self._finish_automatic_layout(job_id, auto_result)
                        except Exception as exc:
                            code = getattr(exc, "code", "automatic_layout_unavailable")
                            if type(code) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,120}", code) is None:
                                code = "automatic_layout_unavailable"
                            self._finish_automatic_layout(job_id, None, code)
                    return

                if job_kind == "analyze":
                    from .workflow import TranslationWorkflow

                    workflow = TranslationWorkflow(
                        log_callback=lambda message: self._append_log(job_id, message),
                        gui_settings=gui_settings,
                        **self._workflow_accounting,
                    )
                    self._mark_running(job_id, workflow, "Analyzing...")
                    summary = workflow.analyze(config)
                    analysis = _analysis_payload(summary)
                    self._mark_finished(
                        job_id=job_id,
                        status="completed",
                        status_text="Analyze complete",
                        diagnostics={"kind": "analyze"},
                        result={"analysis": analysis},
                        artifacts={
                            "run_dir": analysis["run_dir"],
                            "analyze_report_path": analysis["analyze_report_path"],
                            "output_docx": None,
                            "partial_docx": None,
                            "run_summary_path": None,
                        },
                    )
                    return

                from .workflow import TranslationWorkflow

                workflow = TranslationWorkflow(
                    log_callback=lambda message: self._append_log(job_id, message),
                    gui_settings=gui_settings,
                    **self._workflow_accounting,
                    **({"reviewed_source_context": selected_context} if selected_context is not None else {}),
                )
                self._mark_running(job_id, workflow, "Rebuilding DOCX...")
                output_docx = workflow.rebuild_docx(config)
                run_dir = build_run_paths(
                    config.output_dir,
                    config.pdf_path,
                    config.target_lang,
                    gmail_batch_context=config.gmail_batch_context,
                ).run_dir
                rebuilt_artifacts = _artifacts_payload_for_rebuild(run_dir=run_dir, output_docx=output_docx)
                with self._lock:
                    parent = self._jobs.get(record._rebuild_origin_job_id or "")
                    prior = deepcopy(parent.result_payload) if parent is not None else {}
                prior_auto = prior.get("automatic_layout") if isinstance(prior, dict) else None
                prior_policy = parent._ordinary_auto_layout_policy if parent is not None else None
                if (self._automatic_layout_runner is not None and isinstance(prior_auto, dict)
                        and prior_auto.get("status") == "automatic_unreviewed" and prior_policy):
                    seed = prior.get("save_seed")
                    if not isinstance(seed, dict) or str(prior.get("run_dir")) != str(run_dir):
                        raise ValueError("ordinary_auto_layout_rebuild_identity_changed")
                    with self._lock:
                        self._jobs[job_id]._ordinary_auto_layout_policy = prior_policy
                    seed = deepcopy(seed)
                    seed["output_docx"] = str(output_docx.expanduser().resolve())
                    prior.pop("automatic_layout", None)
                    prior["save_seed"] = seed
                    prior["artifacts"] = deepcopy(rebuilt_artifacts)
                    prior["rebuild"] = {"docx_path": str(output_docx.expanduser().resolve()),
                        "run_dir": str(run_dir.expanduser().resolve()), "reuse_verified": True}
                    self._mark_finished(job_id=job_id, status="formatting",
                        status_text="Reusing source layout...", diagnostics={"kind": "rebuild"},
                        result=prior, artifacts=rebuilt_artifacts)
                    try:
                        self._finish_automatic_layout(job_id,
                            self._automatic_layout_runner(job_id, prior_policy))
                    except Exception as exc:
                        code = getattr(exc, "code", "automatic_layout_unavailable")
                        if type(code) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,120}", code) is None:
                            code = "automatic_layout_unavailable"
                        self._finish_automatic_layout(job_id, None, code)
                    return
                self._mark_finished(
                    job_id=job_id,
                    status="completed",
                    status_text="Rebuild complete",
                    diagnostics={"kind": "rebuild"},
                    result={
                        "rebuild": {
                            "docx_path": str(output_docx.expanduser().resolve()),
                            "run_dir": str(run_dir.expanduser().resolve()),
                        }
                    },
                    artifacts=rebuilt_artifacts,
                )
            except Exception as exc:  # noqa: BLE001
                self._mark_finished(
                    job_id=job_id,
                    status="failed",
                    status_text=f"{job_kind.title()} failed",
                    diagnostics={"error": ("ordinary_source_review_job_failed" if reviewed_source_context is not None
                                           else str(exc)), "kind": job_kind},
                    result={},
                    artifacts={},
                )

        thread = threading.Thread(target=_run_job, name=f"translation-browser-{job_kind}-{job_id}", daemon=True)
        thread.start()
        return self.get_job(job_id) or {}

    def start_translate(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        form_values: Mapping[str, Any],
        settings_path: Path,
    ) -> dict[str, Any]:
        config = _build_config_from_form(form_values=form_values, settings_path=settings_path)
        return self._start_job(
            job_kind="translate",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            config=config,
            settings_path=settings_path,
        )

    def start_analyze(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        form_values: Mapping[str, Any],
        settings_path: Path,
    ) -> dict[str, Any]:
        config = _build_config_from_form(form_values=form_values, settings_path=settings_path)
        return self._start_job(
            job_kind="analyze",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            config=config,
            settings_path=settings_path,
        )

    def start_reviewed_translate(self, *, runtime_mode: str, workspace_id: str, config: RunConfig,
            settings_path: Path, reviewed_source_context: Any,
            reviewed_source_loader: Callable[[], Any]) -> dict[str, Any]:
        """Explicit backend-only selection; existing form payloads stay unchanged.

        The browser bridge owns scope/config and an exact revision loader. The
        loader is called again in the background before any client construction.
        Workflow revalidates source/resume under its run lock before auth/send.
        """
        if runtime_mode not in {"live", "shadow"} or not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("ordinary_source_review_job_owner_invalid")
        if (type(config) is not RunConfig or not isinstance(settings_path, Path)
                or reviewed_source_context is None or not callable(reviewed_source_loader)):
            raise ValueError("ordinary_source_review_job_context_invalid")
        return self._start_job(job_kind="translate", runtime_mode=runtime_mode, workspace_id=workspace_id,
            config=deepcopy(config), settings_path=settings_path,
            reviewed_source_context=reviewed_source_context, reviewed_source_loader=reviewed_source_loader)

    def resume_job(self, *, job_id: str, settings_path: Path) -> dict[str, Any]:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None or existing._config is None:
                raise ValueError("Translation job is unavailable for resume.")
            if existing.job_kind != "translate" or existing.status not in {"failed", "cancelled"}:
                raise ValueError("Only failed or cancelled translation jobs can be resumed.")
            config = replace(existing._config, resume=True)
            runtime_mode = existing.runtime_mode
            workspace_id = existing.workspace_id
            reviewed_options = {}
            if existing._reviewed_source_context is not None:
                if settings_path.expanduser().resolve() != existing._reviewed_settings_path:
                    raise ValueError("ordinary_source_review_job_owner_changed")
                reviewed_options = {"reviewed_source_context": existing._reviewed_source_context,
                                    "reviewed_source_loader": existing._reviewed_source_loader}
        return self._start_job(
            job_kind="translate",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            config=config,
            settings_path=settings_path,
            **reviewed_options,
        )

    def recover_layout_job(self, *, job_id: str) -> dict[str, Any]:
        """Explicit layout-only successor of a completed checkpoint Resume."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.job_kind != "translate":
                raise ValueError("Translation job is unavailable for layout recovery.")
            if job.status == "formatting" and job._automatic_layout_recovery_active:
                return self._snapshot(job)
            automatic = job.result_payload.get("automatic_layout")
            if (job.status == "completed" and isinstance(automatic, dict)
                    and automatic.get("status") == "automatic_unreviewed"
                    and automatic.get("recovery_predecessor")):
                return self._snapshot(job)
            if (not self._job_actions(job)["recover_layout"] or not job._ordinary_auto_layout_policy
                    or self._automatic_layout_recovery_runner is None):
                raise ValueError("A completed raw translation with unresolved layout is required for recovery.")
            reservation_key = job._reservation_key
            self._reserve(reservation_key)
            self._claim_reservation(reservation_key, job_id)
            old_policy = job._ordinary_auto_layout_policy
            job._automatic_layout_cancel_requested = False
            job._automatic_layout_publication_started = False
            job._automatic_layout_recovery_active = True
            job.status = "formatting"
            job.status_text = "Recovering source layout from the completed translation..."
            job.updated_at = _utc_now_iso()
            snapshot = self._snapshot(job)

        def _run_recovery() -> None:
            try:
                result = self._automatic_layout_recovery_runner(job_id, old_policy)
                self._finish_automatic_layout(job_id, result)
            except Exception as exc:
                code = getattr(exc, "code", "automatic_layout_recovery_unavailable")
                if type(code) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,120}", code) is None:
                    code = "automatic_layout_recovery_unavailable"
                self._finish_automatic_layout(job_id, None, code)

        thread = threading.Thread(target=_run_recovery, name=f"translation-layout-recovery-{job_id}", daemon=True)
        thread.start()
        return snapshot

    def rebuild_job(self, *, job_id: str, settings_path: Path) -> dict[str, Any]:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None or existing._config is None:
                raise ValueError("Translation job is unavailable for rebuild.")
            config = existing._config
            runtime_mode = existing.runtime_mode
            workspace_id = existing.workspace_id
            reviewed_options = {}
            if existing._reviewed_source_context is not None:
                if settings_path.expanduser().resolve() != existing._reviewed_settings_path:
                    raise ValueError("ordinary_source_review_job_owner_changed")
                reviewed_options = {"reviewed_source_context": existing._reviewed_source_context,
                                    "reviewed_source_loader": existing._reviewed_source_loader}
        return self._start_job(
            job_kind="rebuild",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            config=config,
            settings_path=settings_path,
            rebuild_origin_job_id=job_id,
            **reviewed_options,
        )

    def generate_run_report(self, *, job_id: str, settings_path: Path) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError("Translation job not found.")
            if job.job_kind != "translate":
                raise ValueError("Run reports are only available for translation jobs.")
            run_dir_text = str(job.artifacts_payload.get("run_dir") or "").strip()
        if run_dir_text == "":
            raise ValueError("Translation run directory is unavailable for report generation.")
        report = _generate_translation_run_report(run_dir=Path(run_dir_text), settings_path=settings_path)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError("Translation job not found.")
            report_path = str(report["report_path"])
            job.artifacts_payload["run_report_path"] = report_path
            result_artifacts = job.result_payload.get("artifacts")
            if not isinstance(result_artifacts, dict):
                result_artifacts = {}
                job.result_payload["artifacts"] = result_artifacts
            result_artifacts["run_report_path"] = report_path
            job.updated_at = _utc_now_iso()
            snapshot = self._snapshot(job)
        return {
            "status": "ok",
            "normalized_payload": {
                "job": snapshot,
                "report_kind": "run_report",
                "run_dir": report["run_dir"],
                "report_path": report["report_path"],
                "preview": report["preview"],
            },
            "diagnostics": {},
        }

    def cancel_job(self, *, job_id: str) -> bool:
        return self._mark_cancel_requested(job_id)

    def job_artifact_path(self, *, job_id: str, artifact_kind: str) -> Path:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError("Translation job not found.")
            if artifact_kind == "output_docx":
                candidate = job.artifacts_payload.get("output_docx")
            elif artifact_kind == "original_output_docx":
                candidate = job._ordinary_baseline.get("original_path")
                if candidate and hashlib.sha256(Path(candidate).read_bytes()).hexdigest() != job._ordinary_baseline["original_sha256"]:
                    raise ValueError("The preserved original artifact changed.")
            elif artifact_kind == "partial_docx":
                candidate = job.artifacts_payload.get("partial_docx")
            elif artifact_kind == "run_summary":
                candidate = job.artifacts_payload.get("run_summary_path")
            elif artifact_kind == "run_report":
                candidate = job.artifacts_payload.get("run_report_path")
            elif artifact_kind == "analyze_report":
                candidate = job.artifacts_payload.get("analyze_report_path")
            else:
                raise ValueError(f"Unsupported artifact kind: {artifact_kind}")
        cleaned = str(candidate or "").strip()
        if cleaned == "":
            raise ValueError(f"Artifact is unavailable for {artifact_kind}.")
        resolved = Path(cleaned).expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Artifact path is unavailable: {resolved}")
        return resolved

    def trusted_formatting_job(self, *, job_id, runtime_mode, workspace_id, settings_path):
        """Resolve a completed job and reload its exact retained source review."""
        from .ordinary_reviewed_source import OrdinaryReviewedSourceContext
        try:
            if (type(job_id) is not str or re.fullmatch(r"tx-[a-f0-9]{12}", job_id) is None
                    or runtime_mode not in {"live", "shadow"}
                    or type(workspace_id) is not str or not workspace_id
                    or not isinstance(settings_path, Path)):
                raise ValueError
            candidate = settings_path.expanduser()
            path = candidate.resolve()
            if os.path.lexists(candidate) and not path.is_file():
                raise ValueError
            with self._lock:
                job = self._jobs.get(job_id)
                if (job is None or job.job_id != job_id or job.runtime_mode != runtime_mode
                        or job.workspace_id != workspace_id or job.status != "completed"
                        or job.job_kind not in {"translate", "rebuild"}
                        or type(job._config) is not RunConfig
                        or type(job._reviewed_source_context) is not OrdinaryReviewedSourceContext
                        or not callable(job._reviewed_source_loader)
                        or job._reviewed_settings_path != path):
                    raise ValueError
                config = deepcopy(job._config)
                config_json = _formatting_json(asdict(config))
                identity = job._reviewed_source_context.identity
                loader = job._reviewed_source_loader
                run_dir = build_run_paths(config.output_dir, config.pdf_path, config.target_lang,
                    gmail_batch_context=config.gmail_batch_context).run_dir.resolve(strict=True)
                if Path(job.artifacts_payload.get("run_dir", "")).resolve() != run_dir:
                    raise ValueError
            # Storage checks may be expensive; never run them while holding the job mutex.
            fresh = loader()
            if type(fresh) is not OrdinaryReviewedSourceContext or fresh.identity != identity:
                raise ValueError
            fresh.source_guard()
            with self._lock:
                if (self._jobs.get(job_id) is not job or job.job_id != job_id or job.status != "completed"
                        or job.job_kind not in {"translate", "rebuild"}
                        or job.runtime_mode != runtime_mode or job.workspace_id != workspace_id
                        or job._reviewed_settings_path != path or job._reviewed_source_loader is not loader
                        or _formatting_json(asdict(job._config)) != config_json
                        or job._reviewed_source_context.identity != identity
                        or Path(job.artifacts_payload.get("run_dir", "")).resolve() != run_dir):
                    raise ValueError
            owner = {"job_id": job_id, "runtime_mode": runtime_mode, "workspace_id": workspace_id,
                "settings_path": str(path), "run_dir": str(run_dir), "source_context": identity,
                "config_sha256": hashlib.sha256(config_json.encode("utf-8")).hexdigest()}
            return TrustedFormattingJob(config, fresh, path, run_dir, _formatting_json(owner))
        except RunWorkspaceBusy:
            raise
        except Exception:
            raise ValueError("formatting_job_unavailable") from None

    def register_reviewed_formatting_artifact(self, *, trusted, record):
        """Register a separate exact reviewed derivative without selecting it."""
        try:
            if type(trusted) is not TrustedFormattingJob:
                raise ValueError
            owner = json.loads(trusted.owner_json)
            fresh = self.trusted_formatting_job(job_id=owner["job_id"], runtime_mode=owner["runtime_mode"],
                workspace_id=owner["workspace_id"], settings_path=trusted.settings_path)
            if fresh.owner_json != trusted.owner_json:
                raise ValueError
            if (type(record) is not dict or set(record) != {"artifact_id", "review_id", "revision_id", "files"}
                    or any(type(record[k]) is not str or re.fullmatch(r"[a-f0-9]{32}", record[k]) is None
                           for k in ("artifact_id", "review_id", "revision_id"))
                    or set(record["files"]) != {"output_docx", "source_map", "assembly_receipt"}):
                raise ValueError
            docx = Path(record["files"]["output_docx"]["path"])
            expected = {"output_docx": docx, "source_map": docx.with_suffix(".source_map.json"),
                        "assembly_receipt": docx.with_suffix(".formatting_assembly.json")}
            if docx.suffix != ".docx" or docx.parent != fresh.config.output_dir.resolve(strict=True):
                raise ValueError
            for kind, row in record["files"].items():
                if set(row) != {"path", "sha256", "size"} or Path(row["path"]) != expected[kind]:
                    raise ValueError
                maximum = {"output_docx": 32, "source_map": 128, "assembly_receipt": 8}[kind] * 1024 * 1024
                raw = read_reviewed_formatting_file(expected[kind], maximum=maximum)
                if (type(row["size"]) is not int or row["size"] != len(raw)
                        or row["sha256"] != hashlib.sha256(raw).hexdigest()):
                    raise ValueError
            public = {k: record[k] for k in ("artifact_id", "review_id", "revision_id")}
            public["kinds"] = ["output_docx", "source_map", "assembly_receipt"]
            with self._lock:
                job = self._jobs[owner["job_id"]]
                if (job.job_id != owner["job_id"] or job.status != "completed" or job.runtime_mode != owner["runtime_mode"]
                        or job.workspace_id != owner["workspace_id"]
                        or job._reviewed_settings_path != trusted.settings_path
                        or hashlib.sha256(_formatting_json(asdict(job._config)).encode("utf-8")).hexdigest()
                            != owner["config_sha256"]
                        or job._reviewed_source_context.identity != owner["source_context"]):
                    raise ValueError
                rows = job.artifacts_payload.setdefault("reviewed_formatting", [])
                record_json = _formatting_json(record)
                retained = job._reviewed_formatting_records.get(record["artifact_id"])
                if retained is not None and retained != record_json:
                    raise ValueError
                matching = [r for r in rows if r.get("artifact_id") == record["artifact_id"]]
                if matching and (len(matching) != 1 or _formatting_json(matching[0]) != _formatting_json(public)):
                    raise ValueError
                if not matching:
                    if len(rows) >= 256:
                        raise ValueError
                    rows.append(deepcopy(public))
                job._reviewed_formatting_records[record["artifact_id"]] = record_json
                return deepcopy(public)
        except Exception:
            raise ValueError("formatting_job_artifact_unavailable") from None


__all__ = [
    "TranslationJobManager",
    "build_translation_bootstrap",
    "build_translation_capability_flags",
    "build_translation_defaults",
    "export_translation_review_queue_for_job",
    "list_translation_history",
    "save_translation_row",
    "upload_translation_source",
]
