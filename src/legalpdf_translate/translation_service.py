"""Shared translation workflow services used by the browser parity app."""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import threading
import uuid
from typing import TYPE_CHECKING, Any, Mapping

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
from .review_export import export_review_queue
from .source_document import get_source_page_count, is_pdf_source, is_supported_source_file
from .types import AnalyzeSummary, RunConfig, RunSummary, TargetLang
from .user_settings import (
    load_gui_settings_from_path,
    load_joblog_settings_from_path,
    save_joblog_settings_to_path,
)

if TYPE_CHECKING:
    from .workflow import TranslationWorkflow

_PAGE_LOG_RE = re.compile(
    r"page=(?P<page>\d+)\s+image_used=(?P<image>True|False)\s+retry_used=(?P<retry>True|False)\s+status=(?P<status>[a-z_]+)"
)
_PAGE_STATUS_RE = re.compile(r"Page\s+(?P<page>\d+)\s+(?P<status>finished|failed)", re.IGNORECASE)
_MAX_JOB_LOG_LINES = 240


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
        "pages": str(form_values.get("pages", "") or seed.pages).strip(),
        "word_count": str(form_values.get("word_count", "") or seed.word_count).strip(),
        "total_tokens": str(form_values.get("total_tokens", "") or (seed.total_tokens or "")).strip(),
        "rate_per_word": str(form_values.get("rate_per_word", "") or seed.rate_per_word).strip(),
        "expected_total": str(form_values.get("expected_total", "") or seed.expected_total).strip(),
        "amount_paid": str(form_values.get("amount_paid", "") or seed.amount_paid).strip(),
        "api_cost": str(form_values.get("api_cost", "") or seed.api_cost).strip(),
        "estimated_api_cost": str(
            form_values.get("estimated_api_cost", "") or (seed.estimated_api_cost or "")
        ).strip(),
        "quality_risk_score": str(
            form_values.get("quality_risk_score", "") or (seed.quality_risk_score or "")
        ).strip(),
        "profit": str(form_values.get("profit", "") or seed.profit).strip(),
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

    target_lang_text = str(form_values.get("target_lang", defaults.get("default_lang", "EN")) or "EN").strip().upper()
    if target_lang_text not in {"EN", "FR", "AR"}:
        raise ValueError("Target language must be EN, FR, or AR.")

    start_page = _coerce_int_or_none(form_values.get("start_page"))
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
            str(form_values.get("image_mode", defaults.get("image_mode", defaults.get("default_images_mode", "off"))) or "off")
        ),
        start_page=int(start_page),
        end_page=end_page,
        max_pages=max_pages,
        workers=max(1, min(6, int(_coerce_int_or_none(form_values.get("workers")) or 3))),
        resume=_coerce_bool(form_values.get("resume", defaults.get("resume")), True),
        page_breaks=_coerce_bool(form_values.get("page_breaks", defaults.get("page_breaks")), True),
        keep_intermediates=_coerce_bool(
            form_values.get("keep_intermediates", defaults.get("keep_intermediates")),
            True,
        ),
        ocr_mode=parse_ocr_mode(
            str(form_values.get("ocr_mode", defaults.get("ocr_mode", defaults.get("ocr_mode_default", "auto"))) or "auto")
        ),
        ocr_engine=parse_ocr_engine_policy(
            str(
                form_values.get(
                    "ocr_engine",
                    defaults.get("ocr_engine", defaults.get("ocr_engine_default", "local_then_api")),
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
    )


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
        seed.profit = round(seed.expected_total - seed.api_cost, 2)

    try:
        from .metadata_autofill import (
            choose_court_email_suggestion,
            extract_pdf_header_metadata_priority_pages,
            metadata_config_from_settings,
        )

        suggestion = extract_pdf_header_metadata_priority_pages(
            seed.pdf_path,
            vocab_cities=list(settings["vocab_cities"]),
            config=metadata_config_from_settings(settings),
        )
    except Exception:
        suggestion = None
    if suggestion is not None:
        if suggestion.case_entity:
            seed.case_entity = suggestion.case_entity
            seed.service_entity = suggestion.case_entity
        if suggestion.case_city:
            seed.case_city = suggestion.case_city
            seed.service_city = suggestion.case_city
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


def save_translation_row(
    *,
    settings_path: Path,
    job_log_db_path: Path,
    form_values: Mapping[str, Any],
    seed_payload: Mapping[str, Any] | None = None,
    row_id: int | None = None,
) -> dict[str, Any]:
    seed = _hydrate_translation_seed_payload(seed_payload)
    raw_values = _translation_raw_values(form_values, seed=seed)
    payload = normalize_joblog_payload(
        seed=seed,
        raw_values=raw_values,
        service_same_checked=True,
        use_service_location_in_honorarios_checked=False,
        include_transport_sentence_in_honorarios_checked=True,
    )

    with closing(open_job_log(job_log_db_path)) as conn:
        if row_id is not None:
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


def _artifacts_payload_from_summary(summary: RunSummary) -> dict[str, Any]:
    summary_path = summary.run_summary_path or (summary.run_dir / "run_summary.json")
    return {
        "run_dir": str(summary.run_dir.expanduser().resolve()),
        "run_summary_path": _path_text(summary_path),
        "pages_dir": str((summary.run_dir / "pages").expanduser().resolve()),
        "output_docx": _path_text(summary.output_docx),
        "partial_docx": _path_text(summary.partial_docx),
    }


def _artifacts_payload_for_rebuild(*, run_dir: Path, output_docx: Path) -> dict[str, Any]:
    return {
        "run_dir": str(run_dir.expanduser().resolve()),
        "run_summary_path": _path_text(run_dir / "run_summary.json"),
        "pages_dir": str((run_dir / "pages").expanduser().resolve()),
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


class TranslationJobManager:
    """In-process durable job registry for browser translation workflows."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, _ManagedTranslationJob] = {}
        self._reservations: dict[str, str] = {}

    def _job_actions(self, job: _ManagedTranslationJob) -> dict[str, bool]:
        status = job.status
        return {
            "cancel": job.job_kind == "translate" and status in {"queued", "running", "cancel_requested"},
            "resume": job.job_kind == "translate" and status in {"failed", "cancelled"},
            "rebuild": job.job_kind == "translate" and status in {"completed", "failed", "cancelled"},
            "review_export": job.job_kind == "translate" and bool(job.result_payload.get("review_queue")),
            "save_row": job.job_kind == "translate" and isinstance(job.result_payload.get("save_seed"), dict),
            "download_output_docx": bool(job.artifacts_payload.get("output_docx")),
            "download_partial_docx": bool(job.artifacts_payload.get("partial_docx")),
            "download_run_summary": bool(job.artifacts_payload.get("run_summary_path")),
            "download_analyze_report": bool(job.artifacts_payload.get("analyze_report_path")),
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
            "artifacts": dict(job.artifacts_payload),
            "result": dict(job.result_payload),
            "actions": self._job_actions(job),
        }

    def list_jobs(self, *, runtime_mode: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        if runtime_mode is not None:
            jobs = [job for job in jobs if job.runtime_mode == runtime_mode]
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
                if existing is not None and existing.status in {"queued", "running", "cancel_requested"}:
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
            workflow = job._workflow
            if workflow is None or job.job_kind != "translate" or job.status not in {"queued", "running"}:
                return False
            job.status = "cancel_requested"
            job.status_text = "Cancellation requested"
            job.updated_at = _utc_now_iso()
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
            job._workflow = None
            job.updated_at = _utc_now_iso()
            reservation_key = job._reservation_key
        if reservation_key:
            self._release_reservation(reservation_key, job_id)

    def _start_job(
        self,
        *,
        job_kind: str,
        runtime_mode: str,
        workspace_id: str,
        config: RunConfig,
        settings_path: Path,
    ) -> dict[str, Any]:
        reservation_key = _run_dir_key(build_run_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir)
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
        )
        with self._lock:
            self._jobs[job_id] = record
        self._claim_reservation(reservation_key, job_id)

        def _run_job() -> None:
            try:
                if job_kind == "translate":
                    gui_settings = load_gui_settings_from_path(settings_path)
                    max_retries = int(gui_settings.get("perf_max_transport_retries", 4) or 4)
                    backoff_cap = float(gui_settings.get("perf_backoff_cap_seconds", 12.0) or 12.0)
                    client = OpenAIResponsesClient(
                        max_transport_retries=max_retries,
                        backoff_cap_seconds=backoff_cap,
                        logger=lambda message: self._append_log(job_id, message),
                    )
                    from .workflow import TranslationWorkflow

                    workflow = TranslationWorkflow(
                        client=client,
                        log_callback=lambda message: self._append_log(job_id, message),
                        progress_callback=lambda idx, total, status: self._update_progress(job_id, idx, total, status),
                    )
                    self._mark_running(job_id, workflow, "Translating...")
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
                        else:
                            status = "failed"
                            status_text = f"Translation failed ({summary.error or 'runtime_failure'})"
                    self._mark_finished(
                        job_id=job_id,
                        status=status,
                        status_text=status_text,
                        diagnostics={"kind": "translate"},
                        result=payload,
                        artifacts=payload.get("artifacts", {}),
                    )
                    return

                if job_kind == "analyze":
                    from .workflow import TranslationWorkflow

                    workflow = TranslationWorkflow(log_callback=lambda message: self._append_log(job_id, message))
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

                workflow = TranslationWorkflow(log_callback=lambda message: self._append_log(job_id, message))
                self._mark_running(job_id, workflow, "Rebuilding DOCX...")
                output_docx = workflow.rebuild_docx(config)
                run_dir = build_run_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir
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
                    artifacts=_artifacts_payload_for_rebuild(run_dir=run_dir, output_docx=output_docx),
                )
            except Exception as exc:  # noqa: BLE001
                self._mark_finished(
                    job_id=job_id,
                    status="failed",
                    status_text=f"{job_kind.title()} failed",
                    diagnostics={"error": str(exc), "kind": job_kind},
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

    def resume_job(self, *, job_id: str, settings_path: Path) -> dict[str, Any]:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None or existing._config is None:
                raise ValueError("Translation job is unavailable for resume.")
            if existing.job_kind != "translate" or existing.status not in {"failed", "cancelled"}:
                raise ValueError("Only failed or cancelled translation jobs can be resumed.")
            config = existing._config
            runtime_mode = existing.runtime_mode
            workspace_id = existing.workspace_id
        return self._start_job(
            job_kind="translate",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            config=config,
            settings_path=settings_path,
        )

    def rebuild_job(self, *, job_id: str, settings_path: Path) -> dict[str, Any]:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None or existing._config is None:
                raise ValueError("Translation job is unavailable for rebuild.")
            config = existing._config
            runtime_mode = existing.runtime_mode
            workspace_id = existing.workspace_id
        return self._start_job(
            job_kind="rebuild",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            config=config,
            settings_path=settings_path,
        )

    def cancel_job(self, *, job_id: str) -> bool:
        return self._mark_cancel_requested(job_id)

    def job_artifact_path(self, *, job_id: str, artifact_kind: str) -> Path:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError("Translation job not found.")
            if artifact_kind == "output_docx":
                candidate = job.artifacts_payload.get("output_docx")
            elif artifact_kind == "partial_docx":
                candidate = job.artifacts_payload.get("partial_docx")
            elif artifact_kind == "run_summary":
                candidate = job.artifacts_payload.get("run_summary_path")
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
