"""Shared browser power-tools services for glossary, calibration, and diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .checkpoint import (
    parse_effort,
    parse_effort_policy,
    parse_image_mode,
    parse_ocr_engine_policy,
    parse_ocr_mode,
)
from .calibration_audit import run_calibration_audit
from .glossary import (
    GlossaryEntry,
    build_consistency_glossary_markdown,
    load_project_glossaries,
    merge_glossary_scopes,
    normalize_enabled_tiers_by_target_lang,
    normalize_glossaries,
    save_project_glossaries,
    serialize_glossaries,
    supported_target_langs,
)
from .glossary_builder import (
    GlossaryBuilderSuggestion,
    build_glossary_builder_markdown,
    build_lemma_grouped_stats,
    compute_selection_delta,
    compute_selection_metadata,
    create_builder_stats,
    finalize_builder_suggestions,
    serialize_glossary_builder_suggestions,
    suggestions_to_glossary_entries,
    update_builder_stats_from_page,
)
from .gmail_draft import assess_gmail_draft_prereqs
from .lemma_normalizer import LemmaCache, batch_normalize_lemmas
from .ocr_engine import (
    OcrEngineConfig,
    candidate_ocr_api_env_names,
    default_ocr_api_base_url,
    default_ocr_api_env_name,
    default_ocr_api_model,
    local_ocr_available,
    normalize_ocr_api_provider,
    resolve_ocr_api_key_source,
    test_ocr_provider_connection,
)
from .openai_client import OpenAIResponsesClient
from .output_paths import require_writable_output_dir
from .pdf_text_order import extract_ordered_page_text, get_page_count
from .run_report import build_run_report_markdown
from .shadow_runtime import BrowserDataPaths
from .types import OcrEnginePolicy, RunConfig, TargetLang
from .user_settings import (
    app_data_dir_from_settings_path,
    load_gui_settings_from_path,
    load_joblog_settings_from_path,
    save_gui_settings_to_path,
    save_joblog_settings_to_path,
)
from .word_automation import probe_word_pdf_export_support

_GLOSSARY_TITLE_DEFAULT = "AI Glossary"
_DEBUG_BUNDLE_PREFIX = "browser_debug_bundle"
_RUN_REPORT_PREFIX = "browser_run_report"
_GLOSSARY_BUILDER_PREFIX = "glossary_builder"
_POWER_TOOLS_SUBDIR = "power_tools"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_path_text(path: Path | None) -> str:
    if path is None:
        return ""
    return str(path.expanduser().resolve())


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    output: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(resolved)
    return output


def _power_tools_output_dir(outputs_dir: Path) -> Path:
    target = outputs_dir.expanduser().resolve() / _POWER_TOOLS_SUBDIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _default_project_glossary_path(settings_path: Path) -> Path:
    return app_data_dir_from_settings_path(settings_path) / "browser_project_glossary.json"


def _load_project_glossaries_safe(project_glossary_path: Path | None) -> tuple[dict[str, list[GlossaryEntry]], dict[str, object]]:
    if project_glossary_path is None:
        return normalize_glossaries({}, supported_target_langs()), {
            "configured_path": "",
            "resolved_path": "",
            "loaded": False,
            "error": "",
        }
    try:
        loaded = load_project_glossaries(project_glossary_path)
        return loaded, {
            "configured_path": str(project_glossary_path),
            "resolved_path": _safe_path_text(project_glossary_path),
            "loaded": project_glossary_path.exists(),
            "error": "",
        }
    except ValueError as exc:
        return normalize_glossaries({}, supported_target_langs()), {
            "configured_path": str(project_glossary_path),
            "resolved_path": _safe_path_text(project_glossary_path),
            "loaded": False,
            "error": str(exc),
        }


def _configured_project_glossary_path(
    *,
    settings_path: Path,
    settings_payload: dict[str, object],
) -> Path | None:
    configured = str(settings_payload.get("glossary_file_path", "") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return None


def _serialize_suggestions(rows: list[GlossaryBuilderSuggestion]) -> list[dict[str, object]]:
    payload = serialize_glossary_builder_suggestions(rows)
    for row, source in zip(payload, rows, strict=False):
        row["header_hits"] = int(source.header_hits)
    return payload


def _normalize_json_mapping(value: object, *, field: str) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return {}
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field} must be valid JSON.") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{field} must be a JSON object.")


def _dedupe_text_values(values: list[object]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = str(raw or "").strip()
        if cleaned == "":
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return _dedupe_text_values(value)
    if isinstance(value, str):
        return _dedupe_text_values(value.splitlines())
    return []


def _settings_form_payload(settings_path: Path) -> dict[str, object]:
    gui = load_gui_settings_from_path(settings_path)
    joblog = load_joblog_settings_from_path(settings_path)
    return {
        "ui_theme": str(gui.get("ui_theme", "dark_futuristic") or "dark_futuristic"),
        "default_lang": str(gui.get("default_lang", "EN") or "EN"),
        "default_effort": str(gui.get("default_effort", "high") or "high"),
        "default_effort_policy": str(gui.get("default_effort_policy", "adaptive") or "adaptive"),
        "default_images_mode": str(gui.get("default_images_mode", "off") or "off"),
        "default_outdir": str(gui.get("default_outdir", "") or ""),
        "default_workers": int(gui.get("default_workers", 3) or 3),
        "default_resume": bool(gui.get("default_resume", True)),
        "default_keep_intermediates": bool(gui.get("default_keep_intermediates", True)),
        "default_page_breaks": bool(gui.get("default_page_breaks", True)),
        "ocr_mode_default": str(gui.get("ocr_mode_default", "auto") or "auto"),
        "ocr_engine_default": str(gui.get("ocr_engine_default", "local_then_api") or "local_then_api"),
        "ocr_api_provider": str(gui.get("ocr_api_provider", gui.get("ocr_api_provider_default", "openai")) or "openai"),
        "ocr_api_provider_default": str(gui.get("ocr_api_provider_default", "openai") or "openai"),
        "ocr_api_base_url": str(gui.get("ocr_api_base_url", "") or ""),
        "ocr_api_model": str(gui.get("ocr_api_model", "") or ""),
        "ocr_api_key_env_name": str(gui.get("ocr_api_key_env_name", "") or ""),
        "gmail_gog_path": str(gui.get("gmail_gog_path", "") or ""),
        "gmail_account_email": str(gui.get("gmail_account_email", "") or ""),
        "gmail_intake_bridge_enabled": bool(gui.get("gmail_intake_bridge_enabled", False)),
        "gmail_intake_port": int(gui.get("gmail_intake_port", 8765) or 8765),
        "allow_xhigh_escalation": bool(gui.get("allow_xhigh_escalation", False)),
        "diagnostics_admin_mode": bool(gui.get("diagnostics_admin_mode", True)),
        "diagnostics_include_sanitized_snippets": bool(gui.get("diagnostics_include_sanitized_snippets", False)),
        "diagnostics_verbose_metadata_logs": bool(gui.get("diagnostics_verbose_metadata_logs", False)),
        "diagnostics_show_cost_summary": bool(gui.get("diagnostics_show_cost_summary", True)),
        "perf_max_transport_retries": int(gui.get("perf_max_transport_retries", 4) or 4),
        "perf_backoff_cap_seconds": float(gui.get("perf_backoff_cap_seconds", 12.0) or 12.0),
        "perf_timeout_text_seconds": int(gui.get("perf_timeout_text_seconds", 180) or 180),
        "perf_timeout_image_seconds": int(gui.get("perf_timeout_image_seconds", 300) or 300),
        "metadata_ai_enabled": bool(joblog.get("metadata_ai_enabled", True)),
        "metadata_photo_enabled": bool(joblog.get("metadata_photo_enabled", True)),
        "service_equals_case_by_default": bool(joblog.get("service_equals_case_by_default", True)),
        "default_rate_per_word": dict(joblog.get("default_rate_per_word", {})),
    }


def _provider_state_payload(settings_path: Path) -> dict[str, object]:
    gui = load_gui_settings_from_path(settings_path)
    provider = normalize_ocr_api_provider(gui.get("ocr_api_provider", gui.get("ocr_api_provider_default", "openai")))
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_provider=provider,
        api_base_url=str(gui.get("ocr_api_base_url", "") or "") or None,
        api_model=str(gui.get("ocr_api_model", "") or "") or None,
        api_key_env_name=str(gui.get("ocr_api_key_env_name", "") or "") or default_ocr_api_env_name(provider),
    )
    source = resolve_ocr_api_key_source(config)
    if source is None:
        source_payload: dict[str, object] = {"kind": "missing", "name": ""}
    else:
        source_payload = {"kind": source[0], "name": source[1]}
    prereqs = assess_gmail_draft_prereqs(
        configured_gog_path=str(gui.get("gmail_gog_path", "") or ""),
        configured_account_email=str(gui.get("gmail_account_email", "") or ""),
    )
    word = probe_word_pdf_export_support(timeout_seconds=8.0)
    return {
        "ocr": {
            "provider": provider.value,
            "default_model": default_ocr_api_model(provider),
            "configured_model": str(gui.get("ocr_api_model", "") or "") or default_ocr_api_model(provider),
            "configured_env_name": config.api_key_env_name,
            "env_candidates": list(candidate_ocr_api_env_names(config)),
            "effective_credential_source": source_payload,
            "local_available": local_ocr_available(),
            "api_configured": source is not None,
            "base_url": str(gui.get("ocr_api_base_url", "") or "") or default_ocr_api_base_url(provider),
        },
        "gmail_draft": {
            "ready": bool(prereqs.ready),
            "message": prereqs.message,
            "gog_path": _safe_path_text(prereqs.gog_path),
            "account_email": str(prereqs.account_email or ""),
            "accounts": list(prereqs.accounts),
        },
        "word_pdf_export": {
            "ok": bool(word.ok),
            "failure_code": str(word.failure_code or ""),
            "message": str(word.message or ""),
            "details": str(word.details or ""),
            "elapsed_ms": int(word.elapsed_ms),
        },
    }


def _latest_run_dirs(outputs_dir: Path, *, limit: int = 20) -> list[dict[str, object]]:
    root = outputs_dir.expanduser().resolve()
    if not root.exists():
        return []
    candidates: list[Path] = []
    for marker in ("run_summary.json", "run_state.json", "calibration_report.json"):
        for path in root.rglob(marker):
            candidates.append(path.parent)
    unique_dirs = _dedupe_paths(candidates)
    unique_dirs.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    items: list[dict[str, object]] = []
    for path in unique_dirs[: max(1, int(limit))]:
        items.append(
            {
                "run_dir": _safe_path_text(path),
                "name": path.name,
                "has_run_summary": (path / "run_summary.json").exists(),
                "has_run_state": (path / "run_state.json").exists(),
                "has_run_events": (path / "run_events.jsonl").exists(),
                "has_calibration_report": (path / "calibration_report.json").exists(),
                "modified_at_iso": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(microsecond=0).isoformat(),
            }
        )
    return items


def build_power_tools_bootstrap(
    *,
    data_paths: BrowserDataPaths,
    runtime_metadata_path: Path | None = None,
) -> dict[str, object]:
    settings_path = data_paths.settings_path
    gui = load_gui_settings_from_path(settings_path)
    project_path = _configured_project_glossary_path(settings_path=settings_path, settings_payload=gui)
    project_glossaries, project_meta = _load_project_glossaries_safe(project_path)
    personal_glossaries = normalize_glossaries(
        gui.get("personal_glossaries_by_lang", gui.get("glossaries_by_lang")),
        supported_target_langs(),
    )
    enabled_tiers = normalize_enabled_tiers_by_target_lang(
        gui.get("enabled_glossary_tiers_by_target_lang"),
        supported_target_langs(),
    )
    prompt_addendum = gui.get("prompt_addendum_by_lang") if isinstance(gui.get("prompt_addendum_by_lang"), dict) else {}
    return {
        "settings_admin": {
            "form_values": _settings_form_payload(settings_path),
            "provider_state": _provider_state_payload(settings_path),
        },
        "power_tools": {
            "glossary": {
                "personal_glossaries_by_lang": serialize_glossaries(personal_glossaries),
                "project_glossaries_by_lang": serialize_glossaries(project_glossaries),
                "project_glossary_path": project_meta["resolved_path"] or _safe_path_text(_default_project_glossary_path(settings_path)),
                "project_glossary_status": project_meta,
                "enabled_tiers_by_target_lang": {
                    lang: list(enabled_tiers.get(lang, [1, 2]))
                    for lang in supported_target_langs()
                },
                "prompt_addendum_by_lang": {
                    lang: str(prompt_addendum.get(lang, "") or "")
                    for lang in supported_target_langs()
                },
            },
            "glossary_builder": {
                "defaults": {
                    "source_mode": str(gui.get("study_glossary_corpus_source", "run_folders") or "run_folders"),
                    "target_lang": str(gui.get("default_lang", "EN") or "EN"),
                    "mode": "full_text",
                    "lemma_enabled": False,
                    "lemma_effort": str(gui.get("openai_reasoning_effort_lemma", "high") or "high"),
                    "run_dirs": list(gui.get("study_glossary_last_run_dirs", []) or []),
                    "pdf_paths": list(gui.get("study_glossary_pdf_paths", []) or []),
                },
                "latest_run_dirs": _latest_run_dirs(data_paths.outputs_dir, limit=25),
                "last_result": None,
            },
            "calibration": {
                "defaults": {
                    "pdf_path": "",
                    "output_dir": _safe_path_text(data_paths.outputs_dir),
                    "target_lang": str(gui.get("default_lang", "EN") or "EN"),
                    "sample_pages": int(gui.get("calibration_sample_pages_default", 5) or 5),
                    "user_seed": str(gui.get("calibration_user_seed", "") or ""),
                    "include_excerpts": bool(gui.get("calibration_enable_excerpt_storage", False)),
                    "excerpt_max_chars": int(gui.get("calibration_excerpt_max_chars", 200) or 200),
                },
                "last_result": None,
            },
            "diagnostics": {
                "runtime_metadata_path": _safe_path_text(runtime_metadata_path),
                "latest_run_dirs": _latest_run_dirs(data_paths.outputs_dir, limit=25),
                "outputs_root": _safe_path_text(data_paths.outputs_dir),
                "default_bundle_path": _safe_path_text(
                    _power_tools_output_dir(data_paths.outputs_dir) / f"{_DEBUG_BUNDLE_PREFIX}_{_timestamp_slug()}.zip"
                ),
                "default_report_path": _safe_path_text(
                    _power_tools_output_dir(data_paths.outputs_dir) / f"{_RUN_REPORT_PREFIX}_{_timestamp_slug()}.md"
                ),
            },
        },
    }


def save_browser_settings(*, settings_path: Path, values: dict[str, object]) -> dict[str, object]:
    provider_text = str(values.get("ocr_api_provider", "openai") or "openai")
    provider = normalize_ocr_api_provider(provider_text)
    ocr_env = str(values.get("ocr_api_key_env_name", "") or "").strip() or default_ocr_api_env_name(provider)
    gui_values = {
        "ui_theme": str(values.get("ui_theme", "dark_futuristic") or "dark_futuristic"),
        "default_lang": str(values.get("default_lang", "EN") or "EN").strip().upper(),
        "default_effort": str(values.get("default_effort", "high") or "high").strip().lower(),
        "default_effort_policy": str(values.get("default_effort_policy", "adaptive") or "adaptive").strip().lower(),
        "default_images_mode": str(values.get("default_images_mode", "off") or "off").strip().lower(),
        "default_outdir": str(values.get("default_outdir", "") or "").strip(),
        "default_workers": int(values.get("default_workers", 3) or 3),
        "default_resume": bool(values.get("default_resume", True)),
        "default_keep_intermediates": bool(values.get("default_keep_intermediates", True)),
        "default_page_breaks": bool(values.get("default_page_breaks", True)),
        "ocr_mode_default": str(values.get("ocr_mode_default", "auto") or "auto").strip().lower(),
        "ocr_engine_default": str(values.get("ocr_engine_default", "local_then_api") or "local_then_api").strip().lower(),
        "ocr_api_provider": provider.value,
        "ocr_api_provider_default": str(values.get("ocr_api_provider_default", provider.value) or provider.value).strip().lower(),
        "ocr_api_base_url": str(values.get("ocr_api_base_url", "") or "").strip(),
        "ocr_api_model": str(values.get("ocr_api_model", "") or "").strip(),
        "ocr_api_key_env_name": ocr_env,
        "gmail_gog_path": str(values.get("gmail_gog_path", "") or "").strip(),
        "gmail_account_email": str(values.get("gmail_account_email", "") or "").strip(),
        "gmail_intake_bridge_enabled": bool(values.get("gmail_intake_bridge_enabled", False)),
        "gmail_intake_port": int(values.get("gmail_intake_port", 8765) or 8765),
        "allow_xhigh_escalation": bool(values.get("allow_xhigh_escalation", False)),
        "diagnostics_admin_mode": bool(values.get("diagnostics_admin_mode", True)),
        "diagnostics_include_sanitized_snippets": bool(values.get("diagnostics_include_sanitized_snippets", False)),
        "diagnostics_verbose_metadata_logs": bool(values.get("diagnostics_verbose_metadata_logs", False)),
        "diagnostics_show_cost_summary": bool(values.get("diagnostics_show_cost_summary", True)),
        "perf_max_transport_retries": int(values.get("perf_max_transport_retries", 4) or 4),
        "perf_backoff_cap_seconds": float(values.get("perf_backoff_cap_seconds", 12.0) or 12.0),
        "perf_timeout_text_seconds": int(values.get("perf_timeout_text_seconds", 180) or 180),
        "perf_timeout_image_seconds": int(values.get("perf_timeout_image_seconds", 300) or 300),
    }
    save_gui_settings_to_path(settings_path, gui_values)
    joblog_values = {
        "metadata_ai_enabled": bool(values.get("metadata_ai_enabled", True)),
        "metadata_photo_enabled": bool(values.get("metadata_photo_enabled", True)),
        "service_equals_case_by_default": bool(values.get("service_equals_case_by_default", True)),
        "default_rate_per_word": dict(values.get("default_rate_per_word", {}) or {}),
        "ocr_mode": gui_values["ocr_mode_default"],
        "ocr_engine": gui_values["ocr_engine_default"],
        "ocr_api_provider": gui_values["ocr_api_provider"],
        "ocr_api_base_url": gui_values["ocr_api_base_url"],
        "ocr_api_model": gui_values["ocr_api_model"],
        "ocr_api_key_env_name": gui_values["ocr_api_key_env_name"],
    }
    save_joblog_settings_to_path(settings_path, joblog_values)
    return {
        "status": "ok",
        "normalized_payload": {
            "saved": True,
            "form_values": _settings_form_payload(settings_path),
        },
        "diagnostics": {
            "provider_state": _provider_state_payload(settings_path),
        },
    }


def run_settings_preflight(*, settings_path: Path) -> dict[str, object]:
    return {
        "status": "ok",
        "normalized_payload": _provider_state_payload(settings_path),
        "diagnostics": {},
    }


def run_ocr_provider_test(*, settings_path: Path) -> dict[str, object]:
    gui = load_gui_settings_from_path(settings_path)
    provider = normalize_ocr_api_provider(gui.get("ocr_api_provider", gui.get("ocr_api_provider_default", "openai")))
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_provider=provider,
        api_base_url=str(gui.get("ocr_api_base_url", "") or "") or None,
        api_model=str(gui.get("ocr_api_model", "") or "") or None,
        api_key_env_name=str(gui.get("ocr_api_key_env_name", "") or "") or default_ocr_api_env_name(provider),
    )
    source = resolve_ocr_api_key_source(config)
    if source is None:
        return {
            "status": "unavailable",
            "normalized_payload": {
                "provider": provider.value,
                "message": "OCR credentials are not configured.",
                "source": None,
            },
            "diagnostics": {
                "env_candidates": list(candidate_ocr_api_env_names(config)),
            },
        }
    source_name = "stored OCR key" if source[0] == "stored" else f"env {source[1]}"
    test_ocr_provider_connection(config)
    return {
        "status": "ok",
        "normalized_payload": {
            "provider": provider.value,
            "message": f"OCR provider test passed for {provider.value} via {source_name}.",
            "source": {"kind": source[0], "name": source[1]},
        },
        "diagnostics": {
            "env_candidates": list(candidate_ocr_api_env_names(config)),
        },
    }


def run_gmail_draft_preflight(*, settings_path: Path) -> dict[str, object]:
    gui = load_gui_settings_from_path(settings_path)
    prereqs = assess_gmail_draft_prereqs(
        configured_gog_path=str(gui.get("gmail_gog_path", "") or ""),
        configured_account_email=str(gui.get("gmail_account_email", "") or ""),
    )
    return {
        "status": "ok" if prereqs.ready else "unavailable",
        "normalized_payload": {
            "ready": bool(prereqs.ready),
            "message": prereqs.message,
            "gog_path": _safe_path_text(prereqs.gog_path),
            "account_email": str(prereqs.account_email or ""),
            "accounts": list(prereqs.accounts),
        },
        "diagnostics": {},
    }


def save_glossary_workspace(
    *,
    settings_path: Path,
    personal_glossaries_payload: object,
    project_glossaries_payload: object,
    enabled_tiers_payload: object,
    prompt_addendum_payload: object,
    project_glossary_path_text: object,
) -> dict[str, object]:
    langs = supported_target_langs()
    personal = normalize_glossaries(personal_glossaries_payload, langs)
    project = normalize_glossaries(project_glossaries_payload, langs)
    enabled = normalize_enabled_tiers_by_target_lang(enabled_tiers_payload, langs)
    prompt_addendum = _normalize_json_mapping(prompt_addendum_payload, field="Prompt addendum")
    project_text = str(project_glossary_path_text or "").strip()
    project_path = Path(project_text).expanduser().resolve() if project_text else _default_project_glossary_path(settings_path)
    save_project_glossaries(project_path, project)
    save_gui_settings_to_path(
        settings_path,
        {
            "personal_glossaries_by_lang": serialize_glossaries(personal),
            "glossaries_by_lang": serialize_glossaries(personal),
            "enabled_glossary_tiers_by_target_lang": {
                lang: list(enabled.get(lang, [1, 2]))
                for lang in langs
            },
            "prompt_addendum_by_lang": {
                lang: str(prompt_addendum.get(lang, "") or "")
                for lang in langs
            },
            "glossary_file_path": str(project_path),
        },
    )
    return {
        "status": "ok",
        "normalized_payload": {
            "saved": True,
            "project_glossary_path": _safe_path_text(project_path),
            "personal_counts": {lang: len(personal.get(lang, [])) for lang in langs},
            "project_counts": {lang: len(project.get(lang, [])) for lang in langs},
        },
        "diagnostics": {},
    }


def export_glossary_markdown(
    *,
    outputs_dir: Path,
    personal_glossaries_payload: object,
    project_glossaries_payload: object,
    enabled_tiers_payload: object,
    title: str = _GLOSSARY_TITLE_DEFAULT,
) -> dict[str, object]:
    langs = supported_target_langs()
    personal = normalize_glossaries(personal_glossaries_payload, langs)
    project = normalize_glossaries(project_glossaries_payload, langs)
    enabled = normalize_enabled_tiers_by_target_lang(enabled_tiers_payload, langs)
    merged = merge_glossary_scopes(project, personal, supported_langs=langs)
    markdown = build_consistency_glossary_markdown(
        merged,
        enabled_tiers_by_lang=enabled,
        generated_at_iso=_utc_now_iso(),
        title=title.strip() or _GLOSSARY_TITLE_DEFAULT,
    )
    target = _power_tools_output_dir(outputs_dir) / f"consistency_glossary_{_timestamp_slug()}.md"
    target.write_text(markdown, encoding="utf-8")
    return {
        "status": "ok",
        "normalized_payload": {
            "markdown_path": _safe_path_text(target),
            "title": title.strip() or _GLOSSARY_TITLE_DEFAULT,
            "preview": markdown[:4000],
        },
        "diagnostics": {},
    }


def _builder_pages_from_run_dir(run_dir: Path) -> list[tuple[str, int, str]]:
    run_state_path = run_dir / "run_state.json"
    if not run_state_path.exists():
        return []
    try:
        payload = json.loads(run_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    page_numbers: list[int] = []
    pages_payload = payload.get("pages")
    if isinstance(pages_payload, dict):
        for raw in pages_payload.keys():
            try:
                page_number = int(str(raw))
            except ValueError:
                continue
            if page_number > 0:
                page_numbers.append(page_number)
    if not page_numbers:
        start = int(payload.get("selection_start_page", 1) or 1)
        end = int(payload.get("selection_end_page", start) or start)
        page_numbers = list(range(start, end + 1))
    pdf_path_text = str(payload.get("pdf_path", "") or "").strip()
    pdf_path = Path(pdf_path_text).expanduser().resolve() if pdf_path_text else None
    rows: list[tuple[str, int, str]] = []
    for page_number in sorted(set(page_numbers)):
        page_text = ""
        page_path = run_dir / "pages" / f"page_{page_number:04d}.txt"
        if page_path.exists():
            try:
                page_text = page_path.read_text(encoding="utf-8")
            except OSError:
                page_text = ""
        if page_text.strip() == "" and pdf_path is not None and pdf_path.exists():
            try:
                ordered = extract_ordered_page_text(pdf_path, page_number - 1)
                if not ordered.extraction_failed:
                    page_text = str(ordered.text or "")
            except Exception:
                page_text = ""
        if page_text.strip():
            rows.append((run_dir.name, page_number, page_text))
    return rows


def _builder_pages_from_pdf(pdf_path: Path) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    try:
        page_total = int(get_page_count(pdf_path))
    except Exception:
        return rows
    for page_number in range(1, page_total + 1):
        try:
            ordered = extract_ordered_page_text(pdf_path, page_number - 1)
        except Exception:
            continue
        if ordered.extraction_failed:
            continue
        text = str(ordered.text or "")
        if text.strip():
            rows.append((pdf_path.stem, page_number, text))
    return rows


def run_glossary_builder(
    *,
    settings_path: Path,
    outputs_dir: Path,
    source_mode: str,
    run_dirs: list[str],
    pdf_paths: list[str],
    target_lang: str,
    mode: str,
    lemma_enabled: bool,
    lemma_effort: str,
) -> dict[str, object]:
    selected_mode = str(mode or "full_text").strip().lower()
    if selected_mode not in {"full_text", "headers_only"}:
        raise ValueError("Glossary builder mode must be full_text or headers_only.")
    stats = create_builder_stats()
    pages_scanned = 0
    sources_processed = 0
    source_rows: list[tuple[str, int, str]] = []
    if str(source_mode or "run_folders").strip().lower() == "run_folders":
        for raw in run_dirs:
            rows = _builder_pages_from_run_dir(Path(raw).expanduser().resolve())
            if rows:
                source_rows.extend(rows)
                sources_processed += 1
    else:
        for raw in pdf_paths:
            rows = _builder_pages_from_pdf(Path(raw).expanduser().resolve())
            if rows:
                source_rows.extend(rows)
                sources_processed += 1
    for doc_id, page_number, text in source_rows:
        update_builder_stats_from_page(
            doc_id=doc_id,
            page_number=page_number,
            text=text,
            stats=stats,
            mode=selected_mode,  # type: ignore[arg-type]
        )
        pages_scanned += 1
    surface = finalize_builder_suggestions(stats, target_lang=target_lang.strip().upper() or "EN")
    suggestions = surface
    selection_metadata = compute_selection_metadata(stats, final_count=len(surface))
    lemma_summary: dict[str, object] | None = None
    if lemma_enabled and surface:
        terms = [row.source_term for row in surface if row.occurrences_corpus >= 2]
        if terms:
            cache = LemmaCache(cache_path=app_data_dir_from_settings_path(settings_path) / "lemma_cache.json")
            lemma_result = batch_normalize_lemmas(
                terms,
                client=OpenAIResponsesClient(),
                effort=str(lemma_effort or "high").strip().lower() or "high",
                cache=cache,
            )
            if lemma_result.mapping and not lemma_result.fallback_to_surface:
                grouped = build_lemma_grouped_stats(stats, lemma_result.mapping)
                lemma_rows = finalize_builder_suggestions(grouped, target_lang=target_lang.strip().upper() or "EN")
                delta = compute_selection_delta(surface, lemma_rows)
                selection_metadata = compute_selection_metadata(
                    stats,
                    final_count=len(lemma_rows),
                    selection_delta=delta,
                )
                suggestions = lemma_rows
            lemma_summary = {
                "api_calls": int(lemma_result.api_calls),
                "cache_hits": int(lemma_result.cache_hits),
                "cache_misses": int(lemma_result.cache_misses),
                "failures": int(lemma_result.failures),
                "fallback_to_surface": bool(lemma_result.fallback_to_surface),
                "wall_seconds": round(float(lemma_result.wall_seconds), 3),
            }
    artifact_dir = _power_tools_output_dir(outputs_dir) / f"{_GLOSSARY_BUILDER_PREFIX}_{_timestamp_slug()}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    serialized = _serialize_suggestions(suggestions)
    (artifact_dir / "glossary_builder_suggestions.json").write_text(
        json.dumps(
            {
                "generated_at_iso": generated_at,
                "target_lang": target_lang.strip().upper() or "EN",
                "source_mode": source_mode,
                "sources_processed": sources_processed,
                "pages_scanned": pages_scanned,
                "selection_metadata": selection_metadata,
                "lemma_summary": lemma_summary,
                "suggestions": serialized,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "glossary_builder_suggestions.md").write_text(
        build_glossary_builder_markdown(
            suggestions,
            generated_at_iso=generated_at,
            corpus_label=str(source_mode or "run_folders"),
            total_sources=sources_processed,
            total_pages_scanned=pages_scanned,
        ),
        encoding="utf-8",
    )
    return {
        "status": "ok",
        "normalized_payload": {
            "artifact_dir": _safe_path_text(artifact_dir),
            "sources_processed": sources_processed,
            "pages_scanned": pages_scanned,
            "selection_metadata": selection_metadata,
            "lemma_summary": lemma_summary,
            "suggestions": serialized,
        },
        "diagnostics": {},
    }


def apply_builder_suggestions(
    *,
    settings_path: Path,
    suggestions_payload: object,
    project_glossary_path_text: object,
) -> dict[str, object]:
    if not isinstance(suggestions_payload, list):
        raise ValueError("Builder suggestions must be a JSON array.")
    rows: list[GlossaryBuilderSuggestion] = []
    for raw in suggestions_payload:
        if not isinstance(raw, dict):
            continue
        source_term = str(raw.get("source_term", "") or "").strip()
        suggested_translation = str(raw.get("suggested_translation", "") or "").strip()
        if source_term == "" or suggested_translation == "":
            continue
        rows.append(
            GlossaryBuilderSuggestion(
                source_term=source_term,
                target_lang=str(raw.get("target_lang", "EN") or "EN").strip().upper(),
                occurrences_doc=int(raw.get("occurrences_doc", 0) or 0),
                occurrences_corpus=int(raw.get("occurrences_corpus", 0) or 0),
                df_pages=int(raw.get("df_pages", 0) or 0),
                df_docs=int(raw.get("df_docs", 0) or 0),
                suggested_translation=suggested_translation,
                confidence=float(raw.get("confidence", 0.0) or 0.0),
                recommended_scope="project"
                if str(raw.get("recommended_scope", "personal") or "personal").strip().lower() == "project"
                else "personal",
                header_hits=int(raw.get("header_hits", 0) or 0),
            )
        )
    if not rows:
        raise ValueError("No approved glossary builder suggestions were provided.")
    gui = load_gui_settings_from_path(settings_path)
    langs = supported_target_langs()
    personal = normalize_glossaries(gui.get("personal_glossaries_by_lang", gui.get("glossaries_by_lang")), langs)
    project_path_text = str(project_glossary_path_text or gui.get("glossary_file_path", "") or "").strip()
    project_path = Path(project_path_text).expanduser().resolve() if project_path_text else _default_project_glossary_path(settings_path)
    project, _project_meta = _load_project_glossaries_safe(project_path)
    by_scope: dict[str, list[GlossaryBuilderSuggestion]] = {"personal": [], "project": []}
    for row in rows:
        by_scope[row.recommended_scope].append(row)
    added_personal = suggestions_to_glossary_entries(by_scope["personal"], target_lang=rows[0].target_lang)
    added_project = suggestions_to_glossary_entries(by_scope["project"], target_lang=rows[0].target_lang)
    target_lang = rows[0].target_lang if rows else "EN"
    personal[target_lang] = personal.get(target_lang, []) + added_personal
    project[target_lang] = project.get(target_lang, []) + added_project
    personal = normalize_glossaries(serialize_glossaries(personal), langs)
    project = normalize_glossaries(serialize_glossaries(project), langs)
    save_gui_settings_to_path(
        settings_path,
        {
            "personal_glossaries_by_lang": serialize_glossaries(personal),
            "glossaries_by_lang": serialize_glossaries(personal),
            "glossary_file_path": str(project_path),
        },
    )
    save_project_glossaries(project_path, project)
    return {
        "status": "ok",
        "normalized_payload": {
            "applied_count": len(rows),
            "personal_applied": len(added_personal),
            "project_applied": len(added_project),
            "project_glossary_path": _safe_path_text(project_path),
        },
        "diagnostics": {},
    }


def run_browser_calibration_audit(
    *,
    settings_path: Path,
    pdf_path_text: object,
    output_dir_text: object,
    target_lang: object,
    sample_pages: object,
    user_seed: object,
    include_excerpts: object,
    excerpt_max_chars: object,
) -> dict[str, object]:
    pdf_path = Path(str(pdf_path_text or "").strip()).expanduser().resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        raise ValueError("Calibration audit PDF path must point to an existing file.")
    gui = load_gui_settings_from_path(settings_path)
    output_dir = require_writable_output_dir(Path(str(output_dir_text or "").strip() or str(pdf_path.parent)))
    lang_code = str(target_lang or gui.get("default_lang", "EN") or "EN").strip().upper()
    if lang_code not in {"EN", "FR", "AR"}:
        raise ValueError("Calibration target language must be EN, FR, or AR.")
    provider = normalize_ocr_api_provider(gui.get("ocr_api_provider", gui.get("ocr_api_provider_default", "openai")))
    config = RunConfig(
        pdf_path=pdf_path,
        output_dir=output_dir,
        target_lang=TargetLang(lang_code),
        effort=parse_effort(str(gui.get("default_effort", "high") or "high")),
        effort_policy=parse_effort_policy(str(gui.get("default_effort_policy", "adaptive") or "adaptive")),
        allow_xhigh_escalation=bool(gui.get("allow_xhigh_escalation", False)),
        image_mode=parse_image_mode(str(gui.get("default_images_mode", "off") or "off")),
        start_page=1,
        end_page=None,
        max_pages=None,
        workers=max(1, int(gui.get("default_workers", 3) or 3)),
        resume=True,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=parse_ocr_mode(str(gui.get("ocr_mode_default", "auto") or "auto")),
        ocr_engine=parse_ocr_engine_policy(str(gui.get("ocr_engine_default", "local_then_api") or "local_then_api")),
        ocr_api_provider=provider,
        ocr_api_base_url=str(gui.get("ocr_api_base_url", "") or "") or None,
        ocr_api_model=str(gui.get("ocr_api_model", "") or "") or None,
        ocr_api_key_env_name=str(gui.get("ocr_api_key_env_name", "") or "") or default_ocr_api_env_name(provider),
        context_file=None,
        context_text=None,
        glossary_file=None,
        diagnostics_admin_mode=bool(gui.get("diagnostics_admin_mode", True)),
        diagnostics_include_sanitized_snippets=bool(gui.get("diagnostics_include_sanitized_snippets", False)),
    )
    langs = supported_target_langs()
    personal = normalize_glossaries(gui.get("personal_glossaries_by_lang", gui.get("glossaries_by_lang")), langs)
    project_path = _configured_project_glossary_path(settings_path=settings_path, settings_payload=gui)
    project, _meta = _load_project_glossaries_safe(project_path)
    enabled = normalize_enabled_tiers_by_target_lang(gui.get("enabled_glossary_tiers_by_target_lang"), langs)
    prompt_addendum = gui.get("prompt_addendum_by_lang") if isinstance(gui.get("prompt_addendum_by_lang"), dict) else {}
    result = run_calibration_audit(
        config=config,
        personal_glossaries_by_lang=personal,
        project_glossaries_by_lang=project,
        enabled_tiers_by_lang=enabled,
        prompt_addendum_by_lang={lang: str(prompt_addendum.get(lang, "") or "") for lang in langs},
        sample_pages=int(sample_pages or gui.get("calibration_sample_pages_default", 5) or 5),
        user_seed=str(user_seed or gui.get("calibration_user_seed", "") or ""),
        include_excerpts=bool(include_excerpts if include_excerpts is not None else gui.get("calibration_enable_excerpt_storage", False)),
        excerpt_max_chars=int(excerpt_max_chars or gui.get("calibration_excerpt_max_chars", 200) or 200),
    )
    return {
        "status": "ok",
        "normalized_payload": {
            "report": result["report"],
            "suggestions": result["suggestions"],
            "report_json_path": _safe_path_text(result["report_json_path"]),
            "report_md_path": _safe_path_text(result["report_md_path"]),
            "suggestions_json_path": _safe_path_text(result["suggestions_json_path"]),
        },
        "diagnostics": {},
    }


def _sanitized_settings_snapshot(settings_path: Path) -> dict[str, object]:
    snapshot = load_gui_settings_from_path(settings_path)
    snapshot["gmail_intake_bridge_token"] = ""
    return snapshot


def _collect_debug_paths(
    *,
    settings_path: Path,
    outputs_dir: Path,
    runtime_metadata_path: Path | None,
    selected_run_dir: Path | None,
) -> list[Path]:
    paths: list[Path] = []
    if settings_path.exists():
        paths.append(settings_path)
    if runtime_metadata_path is not None and runtime_metadata_path.exists():
        paths.append(runtime_metadata_path)
    run_dirs: list[Path] = []
    if selected_run_dir is not None:
        run_dirs.append(selected_run_dir.expanduser().resolve())
    else:
        for item in _latest_run_dirs(outputs_dir, limit=3):
            run_dir_text = str(item.get("run_dir", "") or "").strip()
            if run_dir_text:
                run_dirs.append(Path(run_dir_text).expanduser().resolve())
    for run_dir in run_dirs:
        for name in (
            "run_state.json",
            "run_summary.json",
            "run_events.jsonl",
            "calibration_report.json",
            "calibration_report.md",
            "calibration_suggestions.json",
            "glossary_builder_suggestions.json",
            "glossary_builder_suggestions.md",
            "gmail_batch_session_report.json",
            "gmail_interpretation_session_report.json",
        ):
            candidate = run_dir / name
            if candidate.exists() and candidate.is_file():
                paths.append(candidate)
    return _dedupe_paths(paths)


def create_browser_debug_bundle(
    *,
    settings_path: Path,
    outputs_dir: Path,
    runtime_metadata_path: Path | None,
    selected_run_dir_text: object,
) -> dict[str, object]:
    selected_run_dir = (
        Path(str(selected_run_dir_text or "").strip()).expanduser().resolve()
        if str(selected_run_dir_text or "").strip()
        else None
    )
    bundle_path = _power_tools_output_dir(outputs_dir) / f"{_DEBUG_BUNDLE_PREFIX}_{_timestamp_slug()}.zip"
    included = _collect_debug_paths(
        settings_path=settings_path,
        outputs_dir=outputs_dir,
        runtime_metadata_path=runtime_metadata_path,
        selected_run_dir=selected_run_dir,
    )
    with ZipFile(bundle_path, mode="w", compression=ZIP_DEFLATED) as archive:
        for path in included:
            archive.write(path, arcname=path.name)
        archive.writestr("settings_snapshot.json", json.dumps(_sanitized_settings_snapshot(settings_path), ensure_ascii=False, indent=2))
    return {
        "status": "ok",
        "normalized_payload": {
            "bundle_path": _safe_path_text(bundle_path),
            "included_files": [path.name for path in included] + ["settings_snapshot.json"],
        },
        "diagnostics": {},
    }


def generate_browser_run_report(
    *,
    settings_path: Path,
    outputs_dir: Path,
    run_dir_text: object,
) -> dict[str, object]:
    run_dir = Path(str(run_dir_text or "").strip()).expanduser().resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError("Run report path must point to an existing run directory.")
    gui = load_gui_settings_from_path(settings_path)
    admin_mode = bool(gui.get("diagnostics_admin_mode", True))
    include_snippets = bool(gui.get("diagnostics_include_sanitized_snippets", False))
    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=admin_mode,
        include_sanitized_snippets=include_snippets,
    )
    report_path = _power_tools_output_dir(outputs_dir) / f"{_RUN_REPORT_PREFIX}_{_timestamp_slug()}.md"
    report_path.write_text(markdown, encoding="utf-8")
    return {
        "status": "ok",
        "normalized_payload": {
            "run_dir": _safe_path_text(run_dir),
            "report_path": _safe_path_text(report_path),
            "preview": markdown[:6000],
        },
        "diagnostics": {},
    }


__all__ = [
    "apply_builder_suggestions",
    "build_power_tools_bootstrap",
    "create_browser_debug_bundle",
    "export_glossary_markdown",
    "generate_browser_run_report",
    "run_browser_calibration_audit",
    "run_glossary_builder",
    "run_gmail_draft_preflight",
    "run_ocr_provider_test",
    "run_settings_preflight",
    "save_browser_settings",
    "save_glossary_workspace",
]
