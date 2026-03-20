"""Shared backend aggregation helpers for the browser app shell."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

from .gmail_browser_service import extension_prepare_reason_catalog
from .gmail_focus_host import build_edge_extension_report, prepare_gmail_intake
from .gmail_browser_service import build_gmail_browser_capability_flags
from .interpretation_service import (
    build_interpretation_capability_flags,
    build_shadow_bootstrap,
    serialize_joblog_row,
)
from .joblog_db import delete_job_runs, list_job_runs, open_job_log
from .shadow_runtime import (
    BrowserDataPaths,
    RUNTIME_MODE_LIVE,
    RUNTIME_MODE_SHADOW,
    detect_browser_data_paths,
)
from .translation_service import build_translation_capability_flags
from .user_profile import (
    PROFILE_FIELD_LABELS,
    UserProfile,
    blank_profile,
    find_profile,
    missing_required_profile_fields,
)
from .user_settings import (
    load_gui_settings_from_path,
    load_profile_settings_from_path,
    load_settings_from_path,
    save_profile_settings_to_path,
)

_GMAIL_CONTEXT_REQUIRED_FIELDS = ("message_id", "thread_id")
_PREPARE_REASON_MESSAGES = {item["reason"]: item["message"] for item in extension_prepare_reason_catalog()}
_GMAIL_BRIDGE_BAD_REASONS = {
    "bridge_port_owner_mismatch",
    "bridge_port_owner_unknown",
    "bridge_port_mismatch",
    "invalid_bridge_port",
    "runtime_metadata_invalid",
    "launch_target_missing",
    "launch_helper_missing",
    "launch_python_missing",
    "launch_command_failed",
    "launch_timeout",
    "unsupported_platform",
}


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _serialize_profile(profile: UserProfile, *, primary_profile_id: str) -> dict[str, Any]:
    return {
        "id": profile.id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "document_name_override": profile.document_name_override,
        "document_name": profile.document_name,
        "email": profile.email,
        "phone_number": profile.phone_number,
        "postal_address": profile.postal_address,
        "iban": profile.iban,
        "iva_text": profile.iva_text,
        "irs_text": profile.irs_text,
        "travel_origin_label": profile.travel_origin_label,
        "travel_distances_by_city": dict(profile.travel_distances_by_city),
        "distance_city_count": len(profile.travel_distances_by_city),
        "is_primary": profile.id == primary_profile_id,
    }


def browser_navigation_sections() -> list[dict[str, str]]:
    return [
        {
            "id": "dashboard",
            "label": "Dashboard",
            "status": "ready",
            "description": "Capability snapshot, mode provenance, and quick links into browser-ready workflows.",
        },
        {
            "id": "new-job",
            "label": "New Job",
            "status": "ready",
            "description": "Translation and interpretation both run directly in the browser app.",
        },
        {
            "id": "gmail-intake",
            "label": "Gmail",
            "status": "ready",
            "description": "Dedicated Gmail handoff, attachment review, and finalization workspace.",
        },
        {
            "id": "recent-jobs",
            "label": "Recent Jobs",
            "status": "ready",
            "description": "Job-log history and quick reopen details for the selected runtime mode.",
        },
        {
            "id": "settings",
            "label": "Settings",
            "status": "ready",
            "description": "Editable runtime defaults, provider diagnostics, OCR preflight, Gmail draft checks, and admin settings.",
        },
        {
            "id": "profile",
            "label": "Profile",
            "status": "ready",
            "description": "Primary profile and imported profile management for the selected runtime mode.",
        },
        {
            "id": "power-tools",
            "label": "Power Tools",
            "status": "ready",
            "description": "Glossary workspace, glossary builder, calibration audit, debug bundles, and run-report generation.",
        },
        {
            "id": "extension-lab",
            "label": "Extension Lab",
            "status": "ready",
            "description": "Real extension diagnostics plus a browser-hosted handoff simulator.",
        },
    ]


def browser_dashboard_cards() -> list[dict[str, str]]:
    return [
        {
            "id": "interpretation",
            "title": "Interpretation + Honorários",
            "status": "ready",
            "description": "Notification/photo autofill, editable form, save to job log, and DOCX/PDF export.",
        },
        {
            "id": "translation",
            "title": "Translation Workflow",
            "status": "ready",
            "description": "Analyze, translate, cancel/resume, rebuild, review queue, artifacts, and Save to Job Log are ready in the browser app.",
        },
        {
            "id": "gmail",
            "title": "Gmail Batch + Drafts",
            "status": "ready",
            "description": "Exact-message load, attachment review, Gmail batch progression, interpretation notice intake, and draft finalization are ready here.",
        },
        {
            "id": "extension",
            "title": "Extension Diagnostics",
            "status": "ready",
            "description": "The real Gmail extension stays canonical; Extension Lab adds repeatable diagnostics and simulation.",
        },
        {
            "id": "power-tools",
            "title": "Power Tools",
            "status": "ready",
            "description": "Glossary editing/building, calibration audit, diagnostics bundles, and run-report tools are browser-ready.",
        },
    ]


def list_browser_recent_jobs(*, db_path: Path, limit: int = 12) -> dict[str, Any]:
    with closing(open_job_log(db_path)) as conn:
        rows = list_job_runs(conn, limit=limit)
    items: list[dict[str, Any]] = []
    counts = {
        "total": 0,
        "translation": 0,
        "interpretation": 0,
    }
    for row in rows:
        payload = serialize_joblog_row(row)
        job_type = _clean_text(payload.get("job_type")).lower()
        if job_type == "interpretation":
            counts["interpretation"] += 1
        else:
            counts["translation"] += 1
        counts["total"] += 1
        items.append(
            {
                "id": int(payload.get("id", 0) or 0),
                "job_type": _clean_text(payload.get("job_type")) or "Translation",
                "case_number": _clean_text(payload.get("case_number")) or "No case number",
                "case_entity": _clean_text(payload.get("case_entity")) or "No case entity",
                "case_city": _clean_text(payload.get("case_city")) or "No case city",
                "service_date": _clean_text(payload.get("service_date")) or _clean_text(payload.get("translation_date")),
                "target_lang": _clean_text(payload.get("target_lang")) or _clean_text(payload.get("lang")),
                "completed_at": _clean_text(payload.get("completed_at")),
                "row": payload,
            }
        )
    return {
        "items": items,
        "counts": counts,
    }


def build_browser_settings_summary(*, settings_path: Path, data_paths: BrowserDataPaths) -> dict[str, Any]:
    gui_settings = load_gui_settings_from_path(settings_path)
    return {
        "ui_theme": gui_settings.get("ui_theme"),
        "default_lang": gui_settings.get("default_lang"),
        "default_outdir": str(gui_settings.get("default_outdir", "") or "").strip(),
        "ocr_mode_default": gui_settings.get("ocr_mode_default"),
        "ocr_engine_default": gui_settings.get("ocr_engine_default"),
        "ocr_api_provider_default": gui_settings.get("ocr_api_provider_default"),
        "gmail_intake_bridge_enabled": bool(gui_settings.get("gmail_intake_bridge_enabled", False)),
        "gmail_intake_port": int(gui_settings.get("gmail_intake_port", 8765) or 8765),
        "gmail_account_email": str(gui_settings.get("gmail_account_email", "") or "").strip(),
        "diagnostics_admin_mode": bool(gui_settings.get("diagnostics_admin_mode", False)),
        "runtime_mode": data_paths.mode,
        "runtime_label": data_paths.label,
        "settings_path": str(data_paths.settings_path),
        "job_log_db_path": str(data_paths.job_log_db_path),
        "outputs_dir": str(data_paths.outputs_dir),
    }


def build_browser_profile_summary(*, settings_path: Path) -> dict[str, Any]:
    profiles, primary_profile_id = load_profile_settings_from_path(settings_path)
    serialized_profiles = [
        _serialize_profile(profile, primary_profile_id=primary_profile_id) for profile in profiles
    ]
    primary = next((item for item in serialized_profiles if item["is_primary"]), None)
    return {
        "count": len(serialized_profiles),
        "primary_profile_id": primary_profile_id,
        "primary_profile": primary,
        "profiles": serialized_profiles,
    }


def build_blank_browser_profile() -> dict[str, Any]:
    profile = blank_profile()
    return _serialize_profile(profile, primary_profile_id="")


def _missing_profile_field_labels(profile: UserProfile) -> list[str]:
    return [PROFILE_FIELD_LABELS.get(name, name) for name in missing_required_profile_fields(profile)]


def save_browser_profile(
    *,
    settings_path: Path,
    profile_payload: Mapping[str, Any],
    make_primary: bool = False,
) -> dict[str, Any]:
    profiles, primary_profile_id = load_profile_settings_from_path(settings_path)
    requested_id = _clean_text(profile_payload.get("id"))
    existing = find_profile(profiles, requested_id) if requested_id else None
    fallback = blank_profile(profile_id=requested_id or None)
    updated = UserProfile(
        id=existing.id if existing is not None else fallback.id,
        first_name=_clean_text(profile_payload.get("first_name")),
        last_name=_clean_text(profile_payload.get("last_name")),
        document_name_override=_clean_text(profile_payload.get("document_name_override")),
        email=_clean_text(profile_payload.get("email")),
        phone_number=_clean_text(profile_payload.get("phone_number")),
        postal_address=_clean_text(profile_payload.get("postal_address")),
        iban=_clean_text(profile_payload.get("iban")),
        iva_text=_clean_text(profile_payload.get("iva_text")),
        irs_text=_clean_text(profile_payload.get("irs_text")),
        travel_origin_label=_clean_text(profile_payload.get("travel_origin_label")),
        travel_distances_by_city=profile_payload.get("travel_distances_by_city"),
    )
    missing_labels = _missing_profile_field_labels(updated)
    if missing_labels:
        raise ValueError(
            f"Profile '{updated.document_name or '(Unnamed profile)'}' is missing required fields: "
            + ", ".join(missing_labels)
            + "."
        )
    if existing is None:
        profiles.append(updated)
    else:
        profiles = [updated if profile.id == existing.id else profile for profile in profiles]
    resolved_primary_id = updated.id if make_primary else primary_profile_id
    save_profile_settings_to_path(
        settings_path,
        profiles=profiles,
        primary_profile_id=resolved_primary_id,
    )
    summary = build_browser_profile_summary(settings_path=settings_path)
    return {
        "status": "ok",
        "normalized_payload": {
            "saved_profile": next(
                (
                    profile
                    for profile in summary.get("profiles", [])
                    if _clean_text(profile.get("id")) == updated.id
                ),
                _serialize_profile(updated, primary_profile_id=summary.get("primary_profile_id", "")),
            ),
            "profile_summary": summary,
            "message": "Profile saved.",
        },
        "diagnostics": {
            "profile_id": updated.id,
            "make_primary": bool(make_primary),
            "created": existing is None,
        },
    }


def set_browser_primary_profile(*, settings_path: Path, profile_id: str) -> dict[str, Any]:
    profiles, primary_profile_id = load_profile_settings_from_path(settings_path)
    selected = find_profile(profiles, _clean_text(profile_id))
    if selected is None:
        raise ValueError("Profile not found.")
    if selected.id == primary_profile_id:
        summary = build_browser_profile_summary(settings_path=settings_path)
        return {
            "status": "ok",
            "normalized_payload": {
                "profile_summary": summary,
                "message": "Selected profile is already primary.",
            },
            "diagnostics": {"profile_id": selected.id},
        }
    save_profile_settings_to_path(
        settings_path,
        profiles=profiles,
        primary_profile_id=selected.id,
    )
    return {
        "status": "ok",
        "normalized_payload": {
            "profile_summary": build_browser_profile_summary(settings_path=settings_path),
            "message": f"Primary profile set to {selected.document_name or selected.id}.",
        },
        "diagnostics": {"profile_id": selected.id},
    }


def delete_browser_profile(*, settings_path: Path, profile_id: str) -> dict[str, Any]:
    profiles, primary_profile_id = load_profile_settings_from_path(settings_path)
    selected = find_profile(profiles, _clean_text(profile_id))
    if selected is None:
        raise ValueError("Profile not found.")
    if len(profiles) <= 1:
        raise ValueError("At least one profile must remain.")
    remaining = [profile for profile in profiles if profile.id != selected.id]
    resolved_primary_id = primary_profile_id
    if resolved_primary_id == selected.id:
        resolved_primary_id = remaining[0].id
    save_profile_settings_to_path(
        settings_path,
        profiles=remaining,
        primary_profile_id=resolved_primary_id,
    )
    return {
        "status": "ok",
        "normalized_payload": {
            "deleted_profile_id": selected.id,
            "deleted_profile_name": selected.document_name or selected.id,
            "profile_summary": build_browser_profile_summary(settings_path=settings_path),
            "message": "Profile deleted.",
        },
        "diagnostics": {"profile_id": selected.id},
    }


def delete_browser_joblog_rows(*, db_path: Path, row_ids: list[int] | tuple[int, ...]) -> dict[str, Any]:
    normalized_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in row_ids:
        row_id = int(raw_id)
        if row_id <= 0 or row_id in seen:
            continue
        seen.add(row_id)
        normalized_ids.append(row_id)
    if not normalized_ids:
        raise ValueError("At least one valid row id is required.")
    with closing(open_job_log(db_path)) as conn:
        deleted_count = delete_job_runs(conn, row_ids=normalized_ids)
    recent = list_browser_recent_jobs(db_path=db_path, limit=12)
    return {
        "status": "ok",
        "normalized_payload": {
            "deleted_row_ids": normalized_ids,
            "deleted_count": deleted_count,
            "recent_jobs": recent["items"],
            "recent_job_counts": recent["counts"],
            "message": f"Deleted {deleted_count} job-log row(s).",
        },
        "diagnostics": {
            "requested_row_ids": normalized_ids,
        },
    }


def build_browser_parity_audit(*, data_paths: BrowserDataPaths) -> dict[str, Any]:
    checklist = [
        {
            "id": "browser-shell",
            "title": "Browser shell and runtime modes",
            "status": "ready",
            "description": "Dashboard, New Job, Recent Jobs, Settings, Profile, Power Tools, and Extension Lab are available with clear live-mode and isolated-test-mode provenance.",
        },
        {
            "id": "translation",
            "title": "Translation workflow",
            "status": "ready",
            "description": "Analyze, translate, cancel/resume, rebuild, review export, artifact downloads, and Save to Job Log are browser-ready.",
        },
        {
            "id": "interpretation",
            "title": "Interpretation and honorários",
            "status": "ready",
            "description": "Notification/photo autofill, editable interpretation save flow, job-log history, and DOCX/PDF export are browser-ready.",
        },
        {
            "id": "gmail",
            "title": "Gmail batch and finalization",
            "status": "ready",
            "description": "Exact-message Gmail intake, attachment review, batch progression, interpretation intake, and Gmail draft finalization are available in the browser app.",
        },
        {
            "id": "joblog",
            "title": "Recent Jobs and Job Log actions",
            "status": "ready",
            "description": "Recent Jobs, translation history, and interpretation history now support load and confirmation-gated delete actions in the browser app.",
        },
        {
            "id": "profiles-settings-admin",
            "title": "Profile, settings, and admin tools",
            "status": "ready",
            "description": "Editable settings, profile management, glossary, calibration, diagnostics bundles, and provider preflight are available in the browser app.",
        },
        {
            "id": "extension-lab",
            "title": "Extension diagnostics and simulator",
            "status": "ready",
            "description": "The real Gmail extension remains canonical, while Extension Lab provides repeatable localhost diagnostics and handoff simulation.",
        },
    ]
    remaining_limitations = [
        "The browser app is intentionally local-only on 127.0.0.1 and is not a public web deployment.",
        "Isolated test mode remains available when you want to try changes without touching live data.",
        "The real Gmail extension remains the canonical live Gmail entrypoint; Extension Lab is a diagnostics companion.",
    ]
    return {
        "summary": (
            "The browser app now covers the latest daily workflows, while keeping live-data use, Gmail bridge ownership, "
            "and isolated testing explicit."
        ),
        "checklist": checklist,
        "ready_count": len(checklist),
        "total_count": len(checklist),
        "remaining_limitations": remaining_limitations,
        "promotion_recommendation": {
            "status": "ready_for_daily_use",
            "headline": "Ready for daily browser use, with isolated test mode still available when needed.",
            "recommended_workflows": [
                "Translation setup, run monitoring, resume/rebuild, and Save to Job Log",
                "Interpretation notice/photo intake and honorários DOCX/PDF export",
                "Recent Jobs and Job Log history load/delete actions",
                "Settings, profile management, glossary, calibration, diagnostics, and Gmail tools",
            ],
            "keep_qt_canonical_for_now": True,
            "current_runtime_mode": data_paths.mode,
            "current_runtime_label": data_paths.label,
        },
    }


def _extension_settings_loader(settings_path: Path):
    def _loader() -> Mapping[str, Any]:
        return load_settings_from_path(settings_path)

    return _loader


def _serialize_bridge_mode_state(*, data_paths: BrowserDataPaths) -> dict[str, Any]:
    settings_summary = build_browser_settings_summary(
        settings_path=data_paths.settings_path,
        data_paths=data_paths,
    )
    prepare_response = prepare_gmail_intake(
        base_dir=data_paths.app_data_dir,
        request_focus=False,
        include_token=False,
        settings_loader=_extension_settings_loader(data_paths.settings_path),
    )
    reason = _clean_text(prepare_response.get("reason"))
    bridge_port = prepare_response.get("bridgePort")
    if not isinstance(bridge_port, int):
        configured_port = settings_summary.get("gmail_intake_port")
        bridge_port = int(configured_port) if isinstance(configured_port, int) else None
    return {
        "mode": data_paths.mode,
        "label": data_paths.label,
        "live_data": data_paths.live_data,
        "bridge_enabled": bool(settings_summary.get("gmail_intake_bridge_enabled", False)),
        "bridge_port": bridge_port,
        "account_email": _clean_text(settings_summary.get("gmail_account_email")),
        "ready": bool(prepare_response.get("ok")),
        "reason": reason,
        "reason_message": _PREPARE_REASON_MESSAGES.get(reason, reason.replace("_", " ").strip() or "Unknown state."),
        "owner_kind": _clean_text(prepare_response.get("ui_owner")) or "none",
        "browser_url": _clean_text(prepare_response.get("browser_url")),
        "workspace_id": _clean_text(prepare_response.get("workspace_id")),
        "runtime_mode": _clean_text(prepare_response.get("runtime_mode")),
        "prepare_response": prepare_response,
    }


def _build_gmail_bridge_summary(
    *,
    data_paths: BrowserDataPaths,
    current_mode_bridge: Mapping[str, Any],
    live_desktop_bridge: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current_ready = bool(current_mode_bridge.get("ready"))
    current_port = current_mode_bridge.get("bridge_port")
    current_reason_message = _clean_text(current_mode_bridge.get("reason_message"))
    current_detail = (
        f"Current mode: ready on port {current_port}."
        if current_ready and current_port
        else f"Current mode: {current_reason_message or 'unknown'}"
    )
    detail_lines = [current_detail]
    live_ready = bool(live_desktop_bridge and live_desktop_bridge.get("ready"))
    if live_desktop_bridge:
        live_port = live_desktop_bridge.get("bridge_port")
        live_reason_message = _clean_text(live_desktop_bridge.get("reason_message"))
        live_detail = (
            f"Live app: ready on port {live_port}."
            if live_ready and live_port
            else f"Live app: {live_reason_message or 'unknown'}"
        )
        detail_lines.append(live_detail)

    if current_ready:
        owner_kind = _clean_text(current_mode_bridge.get("owner_kind")) or "qt_app"
        return {
            "status": "ok",
            "label": "Ready",
            "message": (
                "The browser app owns the live Gmail bridge for this runtime mode."
                if owner_kind == "browser_app"
                else "The Gmail bridge is ready for the active browser runtime mode."
            ),
            "detail_lines": detail_lines,
            "current_mode": dict(current_mode_bridge),
            "live_desktop": dict(live_desktop_bridge) if live_desktop_bridge else None,
            "shadow_isolation_active": False,
            "live_desktop_ready_while_shadow_disabled": False,
            "user_action_needed": False,
            "owner_kind": owner_kind,
        }

    shadow_isolation_active = (
        data_paths.mode == RUNTIME_MODE_SHADOW and not bool(current_mode_bridge.get("bridge_enabled"))
    )
    if shadow_isolation_active and live_ready:
        return {
            "status": "info",
            "label": "Isolated",
            "message": "Disabled in isolated test mode; the live app Gmail bridge is ready.",
            "detail_lines": detail_lines,
            "current_mode": dict(current_mode_bridge),
            "live_desktop": dict(live_desktop_bridge) if live_desktop_bridge else None,
            "shadow_isolation_active": True,
            "live_desktop_ready_while_shadow_disabled": True,
            "user_action_needed": False,
            "owner_kind": _clean_text(live_desktop_bridge.get("owner_kind") if live_desktop_bridge else "") or "none",
        }

    if shadow_isolation_active:
        return {
            "status": "info",
            "label": "Isolated",
            "message": "Disabled in isolated test mode. Enable the Gmail bridge here only if you want isolated-mode Gmail handoff.",
            "detail_lines": detail_lines,
            "current_mode": dict(current_mode_bridge),
            "live_desktop": dict(live_desktop_bridge) if live_desktop_bridge else None,
            "shadow_isolation_active": True,
            "live_desktop_ready_while_shadow_disabled": False,
            "user_action_needed": False,
            "owner_kind": "none",
        }

    reason = _clean_text(current_mode_bridge.get("reason"))
    status = "bad" if reason in _GMAIL_BRIDGE_BAD_REASONS else "warn"
    label = "Host issue" if status == "bad" else "Needs attention"
    return {
        "status": status,
        "label": label,
        "message": current_reason_message or "The Gmail bridge is not ready for the active browser runtime mode.",
        "detail_lines": detail_lines,
        "current_mode": dict(current_mode_bridge),
        "live_desktop": dict(live_desktop_bridge) if live_desktop_bridge else None,
        "shadow_isolation_active": shadow_isolation_active,
        "live_desktop_ready_while_shadow_disabled": False,
        "user_action_needed": True,
        "owner_kind": _clean_text(current_mode_bridge.get("owner_kind")) or "external",
    }


def build_extension_lab_summary(*, data_paths: BrowserDataPaths) -> dict[str, Any]:
    current_mode_bridge = _serialize_bridge_mode_state(data_paths=data_paths)
    live_desktop_bridge = None
    if data_paths.mode == RUNTIME_MODE_SHADOW:
        live_desktop_bridge = _serialize_bridge_mode_state(
            data_paths=detect_browser_data_paths(mode=RUNTIME_MODE_LIVE),
        )
    bridge_summary = _build_gmail_bridge_summary(
        data_paths=data_paths,
        current_mode_bridge=current_mode_bridge,
        live_desktop_bridge=live_desktop_bridge,
    )
    extension_report = build_edge_extension_report()
    notes = [
        "The real Gmail extension remains canonical.",
        "This lab simulates extension handoff behavior without replacing the extension.",
    ]
    if data_paths.mode == RUNTIME_MODE_SHADOW:
        notes.append("Isolated test mode uses separate browser-app settings by default, so live Gmail bridge readiness may differ.")
        if bridge_summary.get("status") == "info":
            notes.append(str(bridge_summary.get("message") or ""))
    else:
        notes.append("Live mode is reading your real app settings and job-log state directly.")
    return {
        "prepare_response": current_mode_bridge["prepare_response"],
        "extension_report": extension_report,
        "bridge_context": {
            "current_mode": current_mode_bridge,
            "live_desktop": live_desktop_bridge,
            "shadow_isolation_active": bool(bridge_summary.get("shadow_isolation_active")),
            "live_desktop_ready_while_shadow_disabled": bool(
                bridge_summary.get("live_desktop_ready_while_shadow_disabled")
            ),
            "owner_provenance": bridge_summary.get("owner_kind") or "none",
        },
        "bridge_summary": bridge_summary,
        "simulator_defaults": {
            "message_id": "190f8dbbd-example",
            "thread_id": "190f8dba9-example",
            "subject": "Notificacao de diligencia",
            "account_email": "",
        },
        "notes": notes,
    }


def build_browser_capability_snapshot(
    *,
    data_paths: BrowserDataPaths,
    automation_preflight: Mapping[str, Any],
    word_pdf_preflight: Mapping[str, Any],
    extension_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    flags = build_interpretation_capability_flags(settings_path=data_paths.settings_path)
    flags.update(build_translation_capability_flags(settings_path=data_paths.settings_path))
    flags.update(build_gmail_browser_capability_flags(settings_path=data_paths.settings_path))
    flags.setdefault("word_pdf_export", {})
    flags["word_pdf_export"]["preflight"] = dict(word_pdf_preflight)
    flags["browser_automation"] = dict(automation_preflight)
    resolved_extension_summary = (
        extension_summary
        if isinstance(extension_summary, Mapping)
        else build_extension_lab_summary(data_paths=data_paths)
    )
    flags["gmail_bridge"] = dict(resolved_extension_summary.get("bridge_summary", {}))
    return flags


def simulate_extension_handoff(
    *,
    data_paths: BrowserDataPaths,
    context_payload: Mapping[str, Any],
) -> dict[str, Any]:
    message_context = {
        "message_id": _clean_text(context_payload.get("message_id")),
        "thread_id": _clean_text(context_payload.get("thread_id")),
        "subject": _clean_text(context_payload.get("subject")),
        "account_email": _clean_text(context_payload.get("account_email")),
    }
    missing_fields = [field for field in _GMAIL_CONTEXT_REQUIRED_FIELDS if not message_context[field]]
    if missing_fields:
        raise ValueError("Missing required Gmail context fields: " + ", ".join(missing_fields) + ".")
    prepare_response = prepare_gmail_intake(
        base_dir=data_paths.app_data_dir,
        request_focus=False,
        include_token=False,
        settings_loader=_extension_settings_loader(data_paths.settings_path),
    )
    bridge_port = prepare_response.get("bridgePort")
    bridge_endpoint = (
        f"http://127.0.0.1:{int(bridge_port)}/gmail-intake"
        if isinstance(bridge_port, int) and 1 <= int(bridge_port) <= 65535
        else None
    )
    status = "ok" if bool(prepare_response.get("ok")) else "unavailable"
    handoff_payload = {
        "message_id": message_context["message_id"],
        "thread_id": message_context["thread_id"],
        "subject": message_context["subject"],
    }
    if message_context["account_email"]:
        handoff_payload["account_email"] = message_context["account_email"]
    return {
        "status": status,
        "normalized_payload": {
            "message_context": message_context,
            "handoff_request": handoff_payload,
            "bridge_endpoint": bridge_endpoint,
            "would_post": bool(prepare_response.get("ok")) and bridge_endpoint is not None,
            "ui_owner": _clean_text(prepare_response.get("ui_owner")) or "none",
            "browser_url": _clean_text(prepare_response.get("browser_url")),
        },
        "diagnostics": {
            "prepare_response": prepare_response,
            "extension_report": build_edge_extension_report(),
            "mode_label": data_paths.label,
        },
        "capability_flags": build_interpretation_capability_flags(settings_path=data_paths.settings_path),
    }


def build_browser_bootstrap(
    *,
    data_paths: BrowserDataPaths,
    history_limit: int = 25,
) -> dict[str, Any]:
    response = build_shadow_bootstrap(
        settings_path=data_paths.settings_path,
        job_log_db_path=data_paths.job_log_db_path,
        history_limit=history_limit,
    )
    normalized_payload = dict(response.get("normalized_payload", {}))
    recent_jobs = list_browser_recent_jobs(db_path=data_paths.job_log_db_path, limit=12)
    normalized_payload.update(
        {
            "navigation": browser_navigation_sections(),
            "dashboard_cards": browser_dashboard_cards(),
            "recent_jobs": recent_jobs["items"],
            "recent_job_counts": recent_jobs["counts"],
            "settings_summary": build_browser_settings_summary(
                settings_path=data_paths.settings_path,
                data_paths=data_paths,
            ),
            "profile_summary": build_browser_profile_summary(settings_path=data_paths.settings_path),
            "parity_audit": build_browser_parity_audit(data_paths=data_paths),
            "extension_lab": build_extension_lab_summary(data_paths=data_paths),
            "runtime_mode": {
                "current_mode": data_paths.mode,
                "label": data_paths.label,
                "live_data": data_paths.live_data,
                "banner_text": data_paths.banner_text,
                "supported_modes": [
                    {
                        "id": RUNTIME_MODE_LIVE,
                        "label": "Live App Data (recommended)",
                    },
                    {
                        "id": RUNTIME_MODE_SHADOW,
                        "label": "Isolated Test Data",
                    },
                ],
            },
        }
    )
    response["normalized_payload"] = normalized_payload
    return response
