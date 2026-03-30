"""FastAPI app for the local LegalPDF Translate browser app."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from legalpdf_translate.browser_gmail_bridge import BrowserLiveGmailBridgeManager
from legalpdf_translate.browser_pdf_bundle import (
    browser_pdf_bundle_manifest_path,
    write_browser_pdf_bundle,
)
from legalpdf_translate.browser_app_service import (
    build_blank_browser_profile,
    build_browser_capability_snapshot,
    build_browser_bootstrap,
    build_browser_parity_audit,
    build_browser_profile_summary,
    build_browser_settings_summary,
    delete_browser_joblog_rows,
    delete_browser_profile,
    build_extension_lab_summary,
    list_browser_recent_jobs,
    save_browser_profile,
    set_browser_primary_profile,
    simulate_extension_handoff,
)
from legalpdf_translate.build_identity import RuntimeBuildIdentity, detect_runtime_build_identity
from legalpdf_translate.gmail_browser_service import (
    GmailBrowserSessionManager,
    extension_prepare_reason_catalog,
)
from legalpdf_translate.gmail_focus_host import inspect_edge_native_host, prepare_gmail_intake
from legalpdf_translate.interpretation_service import (
    InterpretationValidationError,
    add_interpretation_city,
    autofill_interpretation_from_notification_pdf,
    autofill_interpretation_from_photo,
    build_interpretation_capability_flags,
    export_interpretation_honorarios,
    import_live_profile_settings,
    list_interpretation_history,
    save_interpretation_row,
)
from legalpdf_translate.power_tools_service import (
    apply_builder_suggestions,
    build_browser_provider_state,
    build_power_tools_bootstrap,
    clear_browser_ocr_key,
    clear_browser_translation_key,
    create_browser_debug_bundle,
    document_runtime_state_payload,
    export_glossary_markdown,
    generate_browser_run_report,
    repair_browser_native_host,
    run_browser_calibration_audit,
    run_gmail_draft_preflight,
    run_glossary_builder,
    run_native_host_test,
    run_ocr_provider_test,
    run_word_pdf_export_test,
    run_translation_provider_test,
    run_settings_preflight,
    save_browser_settings,
    save_browser_ocr_key,
    save_browser_translation_key,
    save_glossary_workspace,
)
from legalpdf_translate.translation_service import (
    TranslationJobManager,
    build_translation_bootstrap,
    build_translation_capability_flags,
    export_translation_review_queue_for_job,
    list_translation_history,
    save_translation_row,
    upload_translation_source,
)
from legalpdf_translate.shadow_runtime import (
    BrowserDataPaths,
    RUNTIME_MODE_LIVE,
    RUNTIME_MODE_SHADOW,
    SHADOW_DEFAULT_PORT,
    SHADOW_HOST,
    ShadowRuntimePaths,
    build_shadow_runtime_metadata,
    classify_shadow_listener,
    clear_shadow_runtime_metadata,
    detect_browser_data_paths,
    detect_shadow_runtime_paths,
    load_shadow_runtime_metadata,
    normalize_workspace_id,
    run_browser_automation_preflight,
    write_shadow_runtime_metadata,
)
from legalpdf_translate.user_settings import load_settings_from_path
_SAFE_UPLOAD_TOKEN_RE = re.compile(r"[^A-Za-z0-9._-]+")
_PREPARE_REASON_MESSAGES = {item["reason"]: item["message"] for item in extension_prepare_reason_catalog()}


@dataclass(frozen=True, slots=True)
class ShadowWebContext:
    repo_root: Path
    port: int
    static_dir: Path
    asset_version: str
    server_runtime_paths: ShadowRuntimePaths
    build_identity: RuntimeBuildIdentity
    automation_preflight: dict[str, object]
    translation_jobs: TranslationJobManager
    gmail_sessions: GmailBrowserSessionManager
    live_gmail_bridge: BrowserLiveGmailBridgeManager
    enable_live_gmail_bridge: bool


@dataclass(frozen=True, slots=True)
class ActiveBrowserTarget:
    mode: str
    workspace_id: str
    data_paths: BrowserDataPaths


def _safe_upload_name(filename: str, *, fallback_suffix: str) -> str:
    cleaned = _SAFE_UPLOAD_TOKEN_RE.sub("_", str(filename or "").strip()).strip("._")
    if cleaned:
        return cleaned
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"upload_{timestamp}{fallback_suffix}"


async def _save_upload(upload: UploadFile, target_dir: Path, *, fallback_suffix: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    original_name = getattr(upload, "filename", "") or ""
    safe_name = _safe_upload_name(str(original_name), fallback_suffix=fallback_suffix)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target_path = (target_dir / f"{timestamp}_{safe_name}").expanduser().resolve()
    contents = await upload.read()
    target_path.write_bytes(contents)
    return target_path


def _parse_browser_pdf_bundle_manifest(raw_manifest: str) -> dict[str, Any]:
    try:
        payload = json.loads(str(raw_manifest or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("Browser PDF bundle manifest must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Browser PDF bundle manifest must be an object.")
    return payload


def compute_browser_asset_version(static_dir: Path) -> str:
    tracked_suffixes = {".js", ".mjs", ".css"}
    hasher = hashlib.sha256()
    static_root = static_dir.expanduser().resolve()
    tracked_count = 0
    for path in sorted(static_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in tracked_suffixes:
            continue
        stat = path.stat()
        relative = path.relative_to(static_root).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(int(stat.st_size)).encode("ascii"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\n")
        tracked_count += 1
    if tracked_count == 0:
        return "static-empty"
    return hasher.hexdigest()[:12]


def _versioned_static_base_url(request: Request, context: ShadowWebContext) -> str:
    base_url = str(request.base_url).rstrip("/")
    encoded_version = quote(context.asset_version, safe="")
    return f"{base_url}/static-build/{encoded_version}/"


def _versioned_static_url(request: Request, context: ShadowWebContext, asset_path: str) -> str:
    relative_path = quote(str(asset_path or "").lstrip("/"), safe="/")
    return f"{_versioned_static_base_url(request, context)}{relative_path}"


def _resolve_static_asset(static_dir: Path, asset_path: str) -> Path | None:
    candidate = (static_dir / str(asset_path or "")).expanduser().resolve()
    root = static_dir.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


async def _json_payload_or_empty(request: Request) -> dict[str, Any]:
    content_length = str(request.headers.get("content-length", "") or "").strip()
    if content_length in {"", "0"}:
        return {}
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _context(request: Request) -> ShadowWebContext:
    return request.app.state.shadow_context


def _active_target(
    request: Request,
    *,
    mode_override: object | None = None,
    workspace_override: object | None = None,
) -> ActiveBrowserTarget:
    context = _context(request)
    raw_mode = (
        mode_override
        if mode_override is not None
        else request.query_params.get("mode")
        or request.headers.get("X-LegalPDF-Runtime-Mode")
    )
    mode = _default_browser_mode(raw_mode)
    workspace_id = normalize_workspace_id(
        workspace_override
        if workspace_override is not None
        else request.query_params.get("workspace")
        or request.headers.get("X-LegalPDF-Workspace-Id")
    )
    data_paths = detect_browser_data_paths(
        mode=mode,
        repo=context.repo_root,
        identity=context.build_identity,
    )
    return ActiveBrowserTarget(
        mode=mode,
        workspace_id=workspace_id,
        data_paths=data_paths,
    )


def _default_browser_mode(raw_value: object | None) -> str:
    candidate = str(raw_value or "").strip().lower()
    if candidate == RUNTIME_MODE_SHADOW:
        return RUNTIME_MODE_SHADOW
    return RUNTIME_MODE_LIVE


def _supported_browser_modes() -> list[dict[str, str]]:
    return [
        {"id": RUNTIME_MODE_LIVE, "label": "Live App Data (recommended)"},
        {"id": RUNTIME_MODE_SHADOW, "label": "Isolated Test Data"},
    ]


def _normalize_ui_variant(raw_value: object | None) -> str:
    candidate = str(raw_value or "").strip().lower()
    if candidate == "legacy":
        return "legacy"
    return "qt"


def _runtime_payload(context: ShadowWebContext, target: ActiveBrowserTarget) -> dict[str, Any]:
    return {
        "host": SHADOW_HOST,
        "port": context.port,
        "build_branch": context.build_identity.branch,
        "build_sha": context.build_identity.head_sha,
        "asset_version": context.asset_version,
        "runtime_mode": target.mode,
        "runtime_mode_label": target.data_paths.label,
        "workspace_id": target.workspace_id,
        "live_data": target.data_paths.live_data,
        "banner_text": target.data_paths.banner_text,
        "settings_path": str(target.data_paths.settings_path),
        "job_log_db_path": str(target.data_paths.job_log_db_path),
        "outputs_dir": str(target.data_paths.outputs_dir),
        "app_data_dir": str(target.data_paths.app_data_dir),
    }


def _runtime_diagnostics(context: ShadowWebContext, target: ActiveBrowserTarget) -> dict[str, object]:
    listener = classify_shadow_listener(port=context.port, expected_pid=os.getpid())
    runtime_metadata = build_shadow_runtime_metadata(
        repo=context.repo_root,
        identity=context.build_identity,
        port=context.port,
        listener=listener,
        automation_preflight=context.automation_preflight,
        capabilities={"runtime_mode": target.mode},
    )
    existing_runtime_metadata = load_shadow_runtime_metadata(context.server_runtime_paths.runtime_metadata_path)
    normalized_existing = dict(existing_runtime_metadata or {})
    normalized_existing.pop("updated_at", None)
    normalized_runtime_metadata = dict(runtime_metadata)
    normalized_runtime_metadata.pop("updated_at", None)
    if normalized_existing != normalized_runtime_metadata:
        write_shadow_runtime_metadata(context.server_runtime_paths.runtime_metadata_path, runtime_metadata)
    return {
        "listener_ownership": asdict(listener),
        "runtime_metadata": runtime_metadata,
        "runtime_metadata_path": str(context.server_runtime_paths.runtime_metadata_path),
        "shadow_paths": {
            "app_data_dir": str(context.server_runtime_paths.app_data_dir),
            "settings_path": str(context.server_runtime_paths.settings_path),
            "job_log_db_path": str(context.server_runtime_paths.job_log_db_path),
            "outputs_dir": str(context.server_runtime_paths.outputs_dir),
            "uploads_dir": str(context.server_runtime_paths.uploads_dir),
        },
        "active_data_target": {
            "mode": target.mode,
            "label": target.data_paths.label,
            "app_data_dir": str(target.data_paths.app_data_dir),
            "settings_path": str(target.data_paths.settings_path),
            "job_log_db_path": str(target.data_paths.job_log_db_path),
            "outputs_dir": str(target.data_paths.outputs_dir),
            "live_data": target.data_paths.live_data,
            "banner_text": target.data_paths.banner_text,
            "workspace_id": target.workspace_id,
        },
        "failure_semantics": {
            "unavailable": "host/toolchain cannot execute automation preflight or flow",
            "failed": "automation executed but flow assertions failed",
        },
    }
def _shell_bridge_mode_state(*, target: ActiveBrowserTarget) -> dict[str, Any]:
    settings_payload = load_settings_from_path(target.data_paths.settings_path)
    prepare_response = prepare_gmail_intake(
        base_dir=target.data_paths.app_data_dir,
        request_focus=False,
        include_token=False,
        settings_loader=lambda: load_settings_from_path(target.data_paths.settings_path),
    )
    bridge_port = prepare_response.get("bridgePort")
    if not isinstance(bridge_port, int):
        try:
            bridge_port = int(settings_payload.get("gmail_intake_port", 0))
        except (TypeError, ValueError):
            bridge_port = None
    reason = str(prepare_response.get("reason", "") or "").strip()
    return {
        "mode": target.data_paths.mode,
        "label": target.data_paths.label,
        "live_data": target.data_paths.live_data,
        "bridge_enabled": bool(settings_payload.get("gmail_intake_bridge_enabled", False)),
        "bridge_port": bridge_port if isinstance(bridge_port, int) and 1 <= int(bridge_port) <= 65535 else None,
        "account_email": str(settings_payload.get("gmail_account_email", "") or "").strip(),
        "ready": bool(prepare_response.get("ok")),
        "reason": reason,
        "reason_message": _PREPARE_REASON_MESSAGES.get(reason, reason.replace("_", " ").strip() or "Unknown state."),
        "owner_kind": str(prepare_response.get("ui_owner", "") or "none").strip() or "none",
        "browser_url": str(prepare_response.get("browser_url", "") or "").strip(),
        "workspace_id": str(prepare_response.get("workspace_id", "") or target.workspace_id).strip() or target.workspace_id,
        "runtime_mode": str(prepare_response.get("runtime_mode", "") or target.mode).strip() or target.mode,
        "prepare_response": prepare_response,
    }


def _shell_bridge_capability_flags(
    context: ShadowWebContext,
    target: ActiveBrowserTarget,
    *,
    current_mode_bridge: Mapping[str, Any],
    native_host_state: Mapping[str, Any],
    document_runtime_state: Mapping[str, Any],
) -> dict[str, Any]:
    bridge_sync = asdict(context.live_gmail_bridge.last_result)
    reason = str(current_mode_bridge.get("reason", "") or "").strip() or str(bridge_sync.get("reason", "") or "").strip()
    ready = bool(current_mode_bridge.get("ready"))
    status = "ok" if ready else "bad" if reason in {"bridge_browser_mismatch", "split_brain_browser_owner"} else "warn"
    label = "Ready" if ready else "Host issue" if status == "bad" else "Needs attention"
    message = (
        "The browser workspace is ready for Gmail handoff."
        if ready
        else str(current_mode_bridge.get("reason_message", "") or "The browser workspace is not ready for Gmail handoff.")
    )
    return {
        "native_host": {
            "status": "ok" if native_host_state.get("ready") else "warn" if native_host_state.get("repairable") else "bad",
            "label": "Ready" if native_host_state.get("ready") else "Repairable" if native_host_state.get("repairable") else "Blocked",
            "message": str(native_host_state.get("message", "") or "Edge native host status is unavailable."),
            "reason": str(native_host_state.get("reason", "") or ""),
            "repairable": bool(native_host_state.get("repairable")),
            "self_test_status": str(native_host_state.get("self_test_status", "") or ""),
            "current_runtime_python": str(native_host_state.get("current_runtime_python", "") or ""),
        },
        "gmail_bridge": {
            "status": status,
            "label": label,
            "message": message,
            "reason": reason,
            "owner_kind": str(current_mode_bridge.get("owner_kind", "") or bridge_sync.get("owner_kind", "") or "none"),
            "current_mode": dict(current_mode_bridge),
            "live_desktop": None,
            "shadow_isolation_active": bool(target.mode == RUNTIME_MODE_SHADOW and not current_mode_bridge.get("bridge_enabled")),
            "live_desktop_ready_while_shadow_disabled": False,
            "user_action_needed": not ready,
        },
        "document_runtime": {
            "status": "ok" if document_runtime_state.get("native_pdf_available") else "warn",
            "label": "Ready" if document_runtime_state.get("native_pdf_available") else "Browser-managed",
            "message": str(document_runtime_state.get("message", "") or "Document runtime status is unavailable."),
            "reason": str(document_runtime_state.get("reason", "") or ""),
            "native_pdf_available": bool(document_runtime_state.get("native_pdf_available")),
            "browser_pdf_bundle_supported": bool(document_runtime_state.get("browser_pdf_bundle_supported", False)),
        },
    }


def _browser_capability_flags(
    context: ShadowWebContext,
    target: ActiveBrowserTarget,
    *,
    extension_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provider_state = build_browser_provider_state(settings_path=target.data_paths.settings_path)
    flags = build_browser_capability_snapshot(
        data_paths=target.data_paths,
        automation_preflight=context.automation_preflight,
        word_pdf_preflight=provider_state.get("word_pdf_export", {}) if isinstance(provider_state, Mapping) else {},
        extension_summary=extension_summary,
    )
    native_host_state = provider_state.get("native_host", {}) if isinstance(provider_state, Mapping) else {}
    flags["native_host"] = {
        "status": "ok" if native_host_state.get("ready") else "warn" if native_host_state.get("repairable") else "bad",
        "label": "Ready" if native_host_state.get("ready") else "Repairable" if native_host_state.get("repairable") else "Blocked",
        "message": str(native_host_state.get("message", "") or "Edge native host status is unavailable."),
        "reason": str(native_host_state.get("reason", "") or ""),
        "repairable": bool(native_host_state.get("repairable")),
        "self_test_status": str(native_host_state.get("self_test_status", "") or ""),
        "wrapper_target_python": str(native_host_state.get("wrapper_target_python", "") or ""),
    }
    document_runtime_state = provider_state.get("document_runtime", {}) if isinstance(provider_state, Mapping) else {}
    flags["document_runtime"] = {
        "status": "ok" if document_runtime_state.get("native_pdf_available") else "warn",
        "label": "Ready" if document_runtime_state.get("native_pdf_available") else "Browser-managed",
        "message": str(document_runtime_state.get("message", "") or "Document runtime status is unavailable."),
        "reason": str(document_runtime_state.get("reason", "") or ""),
        "native_pdf_available": bool(document_runtime_state.get("native_pdf_available")),
        "browser_pdf_bundle_supported": bool(document_runtime_state.get("browser_pdf_bundle_supported", False)),
    }
    return flags


def _merge_response(
    context: ShadowWebContext,
    target: ActiveBrowserTarget,
    response: dict[str, object],
) -> dict[str, object]:
    diagnostics = dict(response.get("diagnostics", {}) if isinstance(response.get("diagnostics"), dict) else {})
    diagnostics.setdefault("runtime", _runtime_diagnostics(context, target))
    normalized_payload = dict(
        response.get("normalized_payload", {}) if isinstance(response.get("normalized_payload"), dict) else {}
    )
    runtime_payload = dict(normalized_payload.get("runtime", {}) if isinstance(normalized_payload.get("runtime"), dict) else {})
    runtime_payload.update(_runtime_payload(context, target))
    normalized_payload["runtime"] = runtime_payload
    normalized_payload.setdefault(
        "workspace",
        {
            "id": target.workspace_id,
            "runtime_mode": target.mode,
            "runtime_mode_label": target.data_paths.label,
        },
    )
    capability_flags = response.get("capability_flags")
    if capability_flags is None:
        capability_flags = _browser_capability_flags(context, target)
    merged = {
        "status": str(response.get("status", "ok") or "ok"),
        "normalized_payload": normalized_payload,
        "diagnostics": diagnostics,
        "capability_flags": capability_flags,
    }
    for key, value in response.items():
        if key in merged or key in {"diagnostics", "capability_flags", "normalized_payload"}:
            continue
        merged[key] = value
    return merged


def _validation_error_response(
    context: ShadowWebContext,
    target: ActiveBrowserTarget,
    *,
    message: str,
    validation_error: Mapping[str, Any] | None = None,
    status_code: int = 422,
) -> JSONResponse:
    normalized_payload: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {"error": message}
    if validation_error:
        normalized_payload["validation_error"] = dict(validation_error)
        diagnostics["validation_error"] = dict(validation_error)
    return JSONResponse(
        _merge_response(
            context,
            target,
            {
                "status": "failed",
                "normalized_payload": normalized_payload,
                "diagnostics": diagnostics,
            },
        ),
        status_code=status_code,
    )


def create_shadow_app(
    *,
    repo_root: Path | None = None,
    port: int = SHADOW_DEFAULT_PORT,
    enable_live_gmail_bridge: bool = True,
) -> FastAPI:
    root = (repo_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
    build_identity = detect_runtime_build_identity(repo=root, labels=("shadow-web",))
    server_runtime_paths = detect_shadow_runtime_paths(repo=root, identity=build_identity)
    automation_preflight = run_browser_automation_preflight(repo=root)
    templates_dir = Path(__file__).resolve().parent / "templates"
    static_dir = Path(__file__).resolve().parent / "static"
    asset_version = compute_browser_asset_version(static_dir)
    templates = Jinja2Templates(directory=str(templates_dir))
    gmail_sessions = GmailBrowserSessionManager()

    shadow_context = ShadowWebContext(
        repo_root=root,
        port=int(port),
        static_dir=static_dir,
        asset_version=asset_version,
        server_runtime_paths=server_runtime_paths,
        build_identity=build_identity,
        automation_preflight=automation_preflight,
        translation_jobs=TranslationJobManager(),
        gmail_sessions=gmail_sessions,
        live_gmail_bridge=BrowserLiveGmailBridgeManager(
            repo_root=root,
            build_identity=build_identity,
            server_port=int(port),
            gmail_sessions=gmail_sessions,
        ),
        enable_live_gmail_bridge=bool(enable_live_gmail_bridge),
    )

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        context = app.state.shadow_context
        payload = build_shadow_runtime_metadata(
            repo=context.repo_root,
            identity=context.build_identity,
            port=context.port,
            listener=classify_shadow_listener(port=context.port, expected_pid=os.getpid()),
            automation_preflight=context.automation_preflight,
        )
        write_shadow_runtime_metadata(context.server_runtime_paths.runtime_metadata_path, payload)
        if context.enable_live_gmail_bridge:
            context.live_gmail_bridge.sync()
        try:
            yield
        finally:
            if context.enable_live_gmail_bridge:
                context.live_gmail_bridge.stop()
            clear_shadow_runtime_metadata(app.state.shadow_context.server_runtime_paths.runtime_metadata_path)

    app = FastAPI(title="LegalPDF Translate Browser Parity", version="0.2.0", lifespan=_lifespan)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.state.shadow_context = shadow_context

    @app.get("/static-build/{asset_version}/{asset_path:path}", name="static_build")
    async def versioned_static_asset(asset_version: str, asset_path: str) -> Response:
        context = app.state.shadow_context
        if str(asset_version or "").strip() != context.asset_version:
            return Response(status_code=404)
        asset = _resolve_static_asset(context.static_dir, asset_path)
        if asset is None:
            return Response(status_code=404)
        return FileResponse(
            asset,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    def _structured_validation_payload(exc: Exception) -> dict[str, Any] | None:
        if isinstance(exc, InterpretationValidationError):
            return exc.to_payload()
        return None

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        context = _context(request)
        response = templates.TemplateResponse(
            request,
            "index.html",
            {
                "shadow_host": SHADOW_HOST,
                "shadow_port": context.port,
                "build_branch": context.build_identity.branch,
                "build_sha": context.build_identity.head_sha,
                "asset_version": context.asset_version,
                "static_base_url": _versioned_static_base_url(request, context),
                "style_css_url": _versioned_static_url(request, context, "style.css"),
                "app_js_url": _versioned_static_url(request, context, "app.js"),
                "default_runtime_mode": _default_browser_mode(request.query_params.get("mode")),
                "default_workspace_id": normalize_workspace_id(request.query_params.get("workspace")),
                "ui_variant": _normalize_ui_variant(request.query_params.get("ui")),
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/bootstrap")
    async def api_bootstrap(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = build_browser_bootstrap(
            data_paths=target.data_paths,
            history_limit=25,
        )
        response["normalized_payload"].update(
            build_power_tools_bootstrap(
                data_paths=target.data_paths,
                runtime_metadata_path=context.server_runtime_paths.runtime_metadata_path,
            )
        )
        translation_bootstrap = build_translation_bootstrap(
            settings_path=target.data_paths.settings_path,
            job_log_db_path=target.data_paths.job_log_db_path,
            outputs_dir=target.data_paths.outputs_dir,
            active_jobs=context.translation_jobs.list_jobs(runtime_mode=target.mode, limit=12),
            history_limit=25,
        )
        response["normalized_payload"]["translation"] = translation_bootstrap["normalized_payload"]
        gmail_bootstrap = context.gmail_sessions.build_bootstrap(
            runtime_mode=target.mode,
            workspace_id=target.workspace_id,
            settings_path=target.data_paths.settings_path,
            outputs_dir=target.data_paths.outputs_dir,
        )
        response["normalized_payload"]["gmail"] = gmail_bootstrap["normalized_payload"]
        extension_payload = response["normalized_payload"].get("extension_lab", {})
        if isinstance(extension_payload, dict):
            extension_payload["prepare_reason_catalog"] = extension_prepare_reason_catalog()
            response["normalized_payload"]["extension_lab"] = extension_payload
        response["capability_flags"] = _browser_capability_flags(
            context,
            target,
            extension_summary=extension_payload if isinstance(extension_payload, dict) else None,
        )
        response["normalized_payload"]["automation_preflight"] = context.automation_preflight
        payload = JSONResponse(_merge_response(context, target, response))
        payload.headers["Cache-Control"] = "no-store"
        return payload

    @app.get("/api/bootstrap/shell")
    async def api_bootstrap_shell(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        gmail_bootstrap = context.gmail_sessions.build_bootstrap(
            runtime_mode=target.mode,
            workspace_id=target.workspace_id,
            settings_path=target.data_paths.settings_path,
            outputs_dir=target.data_paths.outputs_dir,
        )
        current_mode_bridge = _shell_bridge_mode_state(target=target)
        document_runtime_state = document_runtime_state_payload()
        native_host_state = inspect_edge_native_host(
            base_dir=target.data_paths.app_data_dir,
            preferred_python_executable=Path(sys.executable),
            runtime_path=Path(sys.executable),
            run_self_test=False,
        )
        response = {
            "status": "ok",
            "normalized_payload": {
                "shell": {
                    "ready": bool(current_mode_bridge.get("ready")),
                    "native_host_ready": bool(native_host_state.get("ready")),
                    "asset_version": context.asset_version,
                    "runtime_mode": target.mode,
                    "workspace_id": target.workspace_id,
                    "owner_kind": current_mode_bridge.get("owner_kind", "none"),
                },
                "gmail": gmail_bootstrap["normalized_payload"],
                "document_runtime": document_runtime_state,
                "native_host": native_host_state,
                "extension_lab": {
                    "prepare_response": current_mode_bridge["prepare_response"],
                },
            },
            "diagnostics": {
                "gmail_bridge_sync": asdict(context.live_gmail_bridge.last_result),
                "document_runtime": document_runtime_state,
                "native_host": native_host_state,
            },
            "capability_flags": _shell_bridge_capability_flags(
                context,
                target,
                current_mode_bridge=current_mode_bridge,
                native_host_state=native_host_state,
                document_runtime_state=document_runtime_state,
            ),
        }
        payload = JSONResponse(_merge_response(context, target, response))
        payload.headers["Cache-Control"] = "no-store"
        return payload

    @app.get("/api/capabilities")
    async def api_capabilities(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        extension_payload = build_extension_lab_summary(data_paths=target.data_paths)
        extension_payload["prepare_reason_catalog"] = extension_prepare_reason_catalog()
        capability_flags = _browser_capability_flags(
            context,
            target,
            extension_summary=extension_payload,
        )
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {
                        "capability_snapshot": capability_flags,
                        "extension_lab": extension_payload,
                    },
                    "diagnostics": {
                        "word_pdf_export": capability_flags["word_pdf_export"]["preflight"],
                    },
                    "capability_flags": capability_flags,
                },
            )
        )

    @app.get("/api/runtime-mode")
    async def api_runtime_mode(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": {
                "current_mode": target.mode,
                "workspace_id": target.workspace_id,
                "supported_modes": _supported_browser_modes(),
            },
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/runtime-mode")
    async def api_runtime_mode_post(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        response = {
            "status": "ok",
            "normalized_payload": {
                "current_mode": target.mode,
                "workspace_id": target.workspace_id,
                "supported_modes": _supported_browser_modes(),
            },
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/workspaces/current")
    async def api_workspace_current(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": {
                "workspace": {
                    "id": target.workspace_id,
                    "runtime_mode": target.mode,
                    "runtime_label": target.data_paths.label,
                    "live_data": target.data_paths.live_data,
                    "available_sections": [
                        "dashboard",
                        "new-job",
                        "recent-jobs",
                        "settings",
                        "profile",
                        "extension-lab",
                        "power-tools",
                    ],
                }
            },
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/joblog/recent")
    async def api_recent_jobs(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        limit_raw = request.query_params.get("limit", "12")
        try:
            limit = max(1, min(100, int(limit_raw)))
        except ValueError:
            limit = 12
        recent = list_browser_recent_jobs(db_path=target.data_paths.job_log_db_path, limit=limit)
        response = {
            "status": "ok",
            "normalized_payload": recent,
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/joblog/delete")
    async def api_joblog_delete(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        raw_row_ids = payload.get("row_ids")
        if not isinstance(raw_row_ids, list):
            raw_single = payload.get("row_id")
            raw_row_ids = [] if raw_single in (None, "") else [raw_single]
        try:
            response = delete_browser_joblog_rows(
                db_path=target.data_paths.job_log_db_path,
                row_ids=[int(row_id) for row_id in raw_row_ids],
            )
        except (TypeError, ValueError) as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/settings/summary")
    async def api_settings_summary(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": build_browser_settings_summary(
                settings_path=target.data_paths.settings_path,
                data_paths=target.data_paths,
            ),
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/settings/admin")
    async def api_settings_admin(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": build_power_tools_bootstrap(
                data_paths=target.data_paths,
                runtime_metadata_path=context.server_runtime_paths.runtime_metadata_path,
            )["settings_admin"],
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/save")
    async def api_settings_save(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = save_browser_settings(
                settings_path=target.data_paths.settings_path,
                values=dict(payload.get("form_values", {})),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        if target.mode == RUNTIME_MODE_LIVE and context.enable_live_gmail_bridge:
            context.live_gmail_bridge.sync()
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/preflight")
    async def api_settings_preflight(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        response = run_settings_preflight(settings_path=target.data_paths.settings_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/ocr-test")
    async def api_settings_ocr_test(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = run_ocr_provider_test(settings_path=target.data_paths.settings_path)
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/translation-test")
    async def api_settings_translation_test(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = run_translation_provider_test(settings_path=target.data_paths.settings_path)
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/native-host-test")
    async def api_settings_native_host_test(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        response = run_native_host_test(settings_path=target.data_paths.settings_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/word-pdf-test")
    async def api_settings_word_pdf_test(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        response = run_word_pdf_export_test(settings_path=target.data_paths.settings_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/native-host-repair")
    async def api_settings_native_host_repair(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        response = repair_browser_native_host(settings_path=target.data_paths.settings_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/translation-key/save")
    async def api_settings_translation_key_save(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = save_browser_translation_key(
                settings_path=target.data_paths.settings_path,
                key=payload.get("key") if isinstance(payload, dict) else "",
            )
        except (ValueError, RuntimeError) as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/translation-key/clear")
    async def api_settings_translation_key_clear(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = clear_browser_translation_key(settings_path=target.data_paths.settings_path)
        except RuntimeError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/ocr-key/save")
    async def api_settings_ocr_key_save(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = save_browser_ocr_key(
                settings_path=target.data_paths.settings_path,
                key=payload.get("key") if isinstance(payload, dict) else "",
            )
        except (ValueError, RuntimeError) as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/ocr-key/clear")
    async def api_settings_ocr_key_clear(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = clear_browser_ocr_key(settings_path=target.data_paths.settings_path)
        except RuntimeError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/settings/gmail-prereqs")
    async def api_settings_gmail_prereqs(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        response = run_gmail_draft_preflight(settings_path=target.data_paths.settings_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/profile/summary")
    async def api_profile_summary(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": build_browser_profile_summary(settings_path=target.data_paths.settings_path),
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/profile/new")
    async def api_profile_new(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": {
                "profile": build_blank_browser_profile(),
            },
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/profile/save")
    async def api_profile_save(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = save_browser_profile(
                settings_path=target.data_paths.settings_path,
                profile_payload=dict(payload.get("profile", {})),
                make_primary=bool(payload.get("make_primary", False)),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/profile/delete")
    async def api_profile_delete(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = delete_browser_profile(
                settings_path=target.data_paths.settings_path,
                profile_id=str(payload.get("profile_id", "") or "").strip(),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/profile/set-primary")
    async def api_profile_set_primary(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = set_browser_primary_profile(
                settings_path=target.data_paths.settings_path,
                profile_id=str(payload.get("profile_id", "") or "").strip(),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/parity-audit")
    async def api_parity_audit(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": build_browser_parity_audit(data_paths=target.data_paths),
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/extension/diagnostics")
    async def api_extension_diagnostics(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        extension_payload = build_extension_lab_summary(data_paths=target.data_paths)
        extension_payload["prepare_reason_catalog"] = extension_prepare_reason_catalog()
        response = {
            "status": "ok",
            "normalized_payload": extension_payload,
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/power-tools/bootstrap")
    async def api_power_tools_bootstrap(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = {
            "status": "ok",
            "normalized_payload": build_power_tools_bootstrap(
                data_paths=target.data_paths,
                runtime_metadata_path=context.server_runtime_paths.runtime_metadata_path,
            )["power_tools"],
            "diagnostics": {},
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/glossary/save")
    async def api_power_tools_glossary_save(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = save_glossary_workspace(
                settings_path=target.data_paths.settings_path,
                personal_glossaries_payload=payload.get("personal_glossaries_by_lang"),
                project_glossaries_payload=payload.get("project_glossaries_by_lang"),
                enabled_tiers_payload=payload.get("enabled_tiers_by_target_lang"),
                prompt_addendum_payload=payload.get("prompt_addendum_by_lang"),
                project_glossary_path_text=payload.get("project_glossary_path"),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/glossary/export-markdown")
    async def api_power_tools_glossary_export_markdown(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = export_glossary_markdown(
                outputs_dir=target.data_paths.outputs_dir,
                personal_glossaries_payload=payload.get("personal_glossaries_by_lang"),
                project_glossaries_payload=payload.get("project_glossaries_by_lang"),
                enabled_tiers_payload=payload.get("enabled_tiers_by_target_lang"),
                title=str(payload.get("title", "") or "").strip(),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/glossary-builder/run")
    async def api_power_tools_glossary_builder_run(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = run_glossary_builder(
                settings_path=target.data_paths.settings_path,
                outputs_dir=target.data_paths.outputs_dir,
                source_mode=str(payload.get("source_mode", "run_folders") or "run_folders"),
                run_dirs=list(payload.get("run_dirs", []) or []),
                pdf_paths=list(payload.get("pdf_paths", []) or []),
                target_lang=str(payload.get("target_lang", "EN") or "EN"),
                mode=str(payload.get("builder_mode", "full_text") or "full_text"),
                lemma_enabled=bool(payload.get("lemma_enabled", False)),
                lemma_effort=str(payload.get("lemma_effort", "high") or "high"),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/glossary-builder/apply")
    async def api_power_tools_glossary_builder_apply(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = apply_builder_suggestions(
                settings_path=target.data_paths.settings_path,
                suggestions_payload=payload.get("suggestions"),
                project_glossary_path_text=payload.get("project_glossary_path"),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/calibration/run")
    async def api_power_tools_calibration_run(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = run_browser_calibration_audit(
                settings_path=target.data_paths.settings_path,
                pdf_path_text=payload.get("pdf_path"),
                output_dir_text=payload.get("output_dir"),
                target_lang=payload.get("target_lang"),
                sample_pages=payload.get("sample_pages"),
                user_seed=payload.get("user_seed"),
                include_excerpts=payload.get("include_excerpts"),
                excerpt_max_chars=payload.get("excerpt_max_chars"),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/diagnostics/debug-bundle")
    async def api_power_tools_debug_bundle(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        response = create_browser_debug_bundle(
            settings_path=target.data_paths.settings_path,
            outputs_dir=target.data_paths.outputs_dir,
            runtime_metadata_path=context.server_runtime_paths.runtime_metadata_path,
            selected_run_dir_text=payload.get("run_dir") if isinstance(payload, dict) else None,
        )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/power-tools/diagnostics/run-report")
    async def api_power_tools_run_report(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = generate_browser_run_report(
                settings_path=target.data_paths.settings_path,
                outputs_dir=target.data_paths.outputs_dir,
                run_dir_text=payload.get("run_dir") if isinstance(payload, dict) else None,
                browser_failure_context=payload.get("browser_failure_context") if isinstance(payload, dict) else None,
                gmail_finalization_context=payload.get("gmail_finalization_context") if isinstance(payload, dict) else None,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/extension/simulate-handoff")
    async def api_extension_simulate_handoff(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = simulate_extension_handoff(
                data_paths=target.data_paths,
                context_payload=dict(payload.get("message_context", {})),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/gmail/bootstrap")
    async def api_gmail_bootstrap(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = context.gmail_sessions.build_bootstrap(
            runtime_mode=target.mode,
            workspace_id=target.workspace_id,
            settings_path=target.data_paths.settings_path,
            outputs_dir=target.data_paths.outputs_dir,
        )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/load-message")
    async def api_gmail_load_message(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = context.gmail_sessions.load_message(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                context_payload=dict(payload.get("message_context", {})),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/preview-attachment")
    async def api_gmail_preview_attachment(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = context.gmail_sessions.preview_attachment(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                attachment_id=str(payload.get("attachment_id", "") or "").strip(),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        normalized = dict(response.get("normalized_payload", {}))
        attachment_id = str(normalized.get("attachment", {}).get("attachment_id", "") or "").strip()
        if attachment_id:
            normalized["preview_href"] = (
                f"/api/gmail/attachment/{attachment_id}"
                f"?mode={target.mode}&workspace={target.workspace_id}"
            )
        response["normalized_payload"] = normalized
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/gmail/attachment/{attachment_id}")
    async def api_gmail_attachment_file(request: Request, attachment_id: str):
        context = _context(request)
        target = _active_target(request)
        path = context.gmail_sessions.current_attachment_file(
            runtime_mode=target.mode,
            workspace_id=target.workspace_id,
            attachment_id=str(attachment_id or "").strip(),
        )
        if path is None or not path.exists():
            return JSONResponse(
                {"status": "failed", "diagnostics": {"error": "Gmail attachment file was not found."}},
                status_code=404,
            )
        media_type = "application/octet-stream"
        content_disposition_type = "attachment"
        if path.suffix.lower() == ".pdf":
            media_type = "application/pdf"
            content_disposition_type = "inline"
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            media_type = f"image/{path.suffix.lower().lstrip('.')}"
            content_disposition_type = "inline"
        # Gmail review preview embeds this route in an iframe/new tab, so previewable
        # attachment types must not inherit the generic download disposition.
        return FileResponse(
            path,
            media_type=media_type,
            filename=path.name,
            content_disposition_type=content_disposition_type,
        )

    @app.post("/api/browser-pdf/bundle")
    async def api_browser_pdf_bundle(
        request: Request,
        manifest: str = Form(...),
        page_images: list[UploadFile] = File(...),
    ) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        try:
            manifest_payload = _parse_browser_pdf_bundle_manifest(manifest)
            source_path_text = str(manifest_payload.get("source_path", "") or "").strip()
            if source_path_text == "":
                raise ValueError("Browser PDF bundle source_path is required.")
            source_path = Path(source_path_text).expanduser().resolve()
            if source_path.suffix.lower() != ".pdf":
                raise ValueError("Browser PDF bundles are only supported for PDF sources.")
            page_count = int(manifest_payload.get("page_count", 0) or 0)
            if page_count <= 0:
                raise ValueError("Browser PDF bundle page_count must be >= 1.")
            raw_pages = manifest_payload.get("pages")
            if not isinstance(raw_pages, list) or not raw_pages:
                raise ValueError("Browser PDF bundle pages are required.")
            uploads_by_name = {
                str(upload.filename or "").strip(): upload
                for upload in page_images
                if str(upload.filename or "").strip()
            }
            if not uploads_by_name:
                raise ValueError("Browser PDF bundle page images are required.")
            pages: list[dict[str, Any]] = []
            for item in raw_pages:
                if not isinstance(item, dict):
                    raise ValueError("Browser PDF bundle pages must be objects.")
                upload_name = str(item.get("file_name", "") or "").strip()
                if upload_name == "":
                    raise ValueError("Browser PDF bundle page file_name is required.")
                upload = uploads_by_name.get(upload_name)
                if upload is None:
                    raise ValueError(f"Browser PDF bundle upload is missing: {upload_name}")
                image_bytes = await upload.read()
                pages.append(
                    {
                        "page_number": item.get("page_number"),
                        "mime_type": item.get("mime_type"),
                        "width_px": item.get("width_px"),
                        "height_px": item.get("height_px"),
                        "image_bytes": image_bytes,
                    }
                )
            written_manifest = write_browser_pdf_bundle(
                source_path=source_path,
                page_count=page_count,
                pages=pages,
            )
            attachment_id = str(manifest_payload.get("attachment_id", "") or "").strip()
            if attachment_id:
                context.gmail_sessions.record_browser_pdf_bundle(
                    runtime_mode=target.mode,
                    workspace_id=target.workspace_id,
                    attachment_id=attachment_id,
                    source_path=source_path,
                    page_count=page_count,
                )
            response = {
                "status": "ok",
                "normalized_payload": {
                    "source_path": str(source_path),
                    "source_name": source_path.name,
                    "page_count": int(written_manifest.get("page_count", page_count) or page_count),
                    "manifest_path": str(browser_pdf_bundle_manifest_path(source_path)),
                    "attachment_id": attachment_id,
                },
                "diagnostics": {
                    "page_upload_count": len(page_images),
                    "workspace_cached": bool(attachment_id),
                    "render_engine": "browser_pdf",
                },
            }
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/prepare-session")
    async def api_gmail_prepare_session(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = context.gmail_sessions.prepare_session(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                outputs_dir=target.data_paths.outputs_dir,
                workflow_kind=payload.get("workflow_kind"),
                target_lang=str(payload.get("target_lang", "") or "").strip(),
                output_dir_text=str(payload.get("output_dir", "") or "").strip(),
                selections_payload=list(payload.get("selections", [])),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/gmail/session/current")
    async def api_gmail_session_current(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = context.gmail_sessions.build_bootstrap(
            runtime_mode=target.mode,
            workspace_id=target.workspace_id,
            settings_path=target.data_paths.settings_path,
            outputs_dir=target.data_paths.outputs_dir,
        )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/batch/confirm-current")
    async def api_gmail_batch_confirm_current(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = context.gmail_sessions.confirm_current_batch_translation(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                job_log_db_path=target.data_paths.job_log_db_path,
                translation_jobs=context.translation_jobs,
                job_id=str(payload.get("job_id", "") or "").strip(),
                form_values=dict(payload.get("form_values", {})),
                row_id=payload.get("row_id"),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/batch/finalize")
    async def api_gmail_batch_finalize(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = context.gmail_sessions.finalize_batch(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                output_filename=str(payload.get("output_filename", "") or "").strip() or None,
                profile_id=str(payload.get("profile_id", "") or "").strip() or None,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/batch/finalize-preflight")
    async def api_gmail_batch_finalize_preflight(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        try:
            response = context.gmail_sessions.preflight_batch_finalization(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                force_refresh=bool(payload.get("force_refresh")) if isinstance(payload, dict) else False,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/interpretation/finalize")
    async def api_gmail_interpretation_finalize(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = context.gmail_sessions.finalize_interpretation(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                settings_path=target.data_paths.settings_path,
                form_values=dict(payload.get("form_values", {})),
                profile_id=str(payload.get("profile_id", "") or "").strip() or None,
                service_same_checked=bool(payload.get("service_same_checked", True)),
                output_filename=str(payload.get("output_filename", "") or "").strip() or None,
            )
        except ValueError as exc:
            return _validation_error_response(
                context,
                target,
                message=str(exc),
                validation_error=_structured_validation_payload(exc),
            )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/gmail/reset")
    async def api_gmail_reset(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await _json_payload_or_empty(request)
        target = _active_target(
            request,
            mode_override=payload.get("mode") if isinstance(payload, dict) else None,
            workspace_override=payload.get("workspace_id") if isinstance(payload, dict) else None,
        )
        context.gmail_sessions.clear_workspace(runtime_mode=target.mode, workspace_id=target.workspace_id)
        response = context.gmail_sessions.build_bootstrap(
            runtime_mode=target.mode,
            workspace_id=target.workspace_id,
            settings_path=target.data_paths.settings_path,
            outputs_dir=target.data_paths.outputs_dir,
        )
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/translation/bootstrap")
    async def api_translation_bootstrap(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        response = build_translation_bootstrap(
            settings_path=target.data_paths.settings_path,
            job_log_db_path=target.data_paths.job_log_db_path,
            outputs_dir=target.data_paths.outputs_dir,
            active_jobs=context.translation_jobs.list_jobs(runtime_mode=target.mode, limit=12),
            history_limit=50,
        )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/translation/upload-source")
    async def api_translation_upload_source(request: Request, file: UploadFile = File(...)) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        suffix = Path(str(file.filename or "")).suffix or ".pdf"
        upload_root = context.server_runtime_paths.uploads_dir / "translation" / target.mode / target.workspace_id
        saved_path = await _save_upload(file, upload_root, fallback_suffix=suffix)
        try:
            response = upload_translation_source(
                source_path=saved_path,
                settings_path=target.data_paths.settings_path,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        response.setdefault("diagnostics", {})
        response["diagnostics"]["uploaded_file"] = str(saved_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/translation/jobs/analyze")
    async def api_translation_start_analyze(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            job = context.translation_jobs.start_analyze(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                form_values=dict(payload.get("form_values", {})),
                settings_path=target.data_paths.settings_path,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {"job": job},
                    "diagnostics": {},
                    "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
                },
            )
        )

    @app.post("/api/translation/jobs/translate")
    async def api_translation_start_translate(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            job = context.translation_jobs.start_translate(
                runtime_mode=target.mode,
                workspace_id=target.workspace_id,
                form_values=dict(payload.get("form_values", {})),
                settings_path=target.data_paths.settings_path,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {"job": job},
                    "diagnostics": {},
                    "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
                },
            )
        )

    @app.get("/api/translation/jobs/{job_id}")
    async def api_translation_job_status(request: Request, job_id: str) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        job = context.translation_jobs.get_job(job_id)
        if job is None:
            return _validation_error_response(context, target, message="Translation job was not found.", status_code=404)
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {"job": job},
                    "diagnostics": {},
                    "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
                },
            )
        )

    @app.post("/api/translation/jobs/{job_id}/cancel")
    async def api_translation_job_cancel(request: Request, job_id: str) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        cancelled = context.translation_jobs.cancel_job(job_id=job_id)
        if not cancelled:
            return _validation_error_response(
                context,
                target,
                message="Translation job cannot be cancelled in its current state.",
            )
        job = context.translation_jobs.get_job(job_id)
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {"job": job},
                    "diagnostics": {},
                    "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
                },
            )
        )

    @app.post("/api/translation/jobs/{job_id}/resume")
    async def api_translation_job_resume(request: Request, job_id: str) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        try:
            job = context.translation_jobs.resume_job(
                job_id=job_id,
                settings_path=target.data_paths.settings_path,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {"job": job},
                    "diagnostics": {},
                    "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
                },
            )
        )

    @app.post("/api/translation/jobs/{job_id}/rebuild")
    async def api_translation_job_rebuild(request: Request, job_id: str) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        try:
            job = context.translation_jobs.rebuild_job(
                job_id=job_id,
                settings_path=target.data_paths.settings_path,
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(
            _merge_response(
                context,
                target,
                {
                    "status": "ok",
                    "normalized_payload": {"job": job},
                    "diagnostics": {},
                    "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
                },
            )
        )

    @app.post("/api/translation/jobs/{job_id}/review-export")
    async def api_translation_job_review_export(request: Request, job_id: str) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        job = context.translation_jobs.get_job(job_id)
        if job is None:
            return _validation_error_response(context, target, message="Translation job was not found.", status_code=404)
        summary_path = str(job.get("artifacts", {}).get("run_summary_path", "") or "").strip()
        if summary_path == "":
            return _validation_error_response(context, target, message="Run summary is unavailable for review export.")
        try:
            response = export_translation_review_queue_for_job(summary_path=Path(summary_path))
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        response["capability_flags"] = build_translation_capability_flags(settings_path=target.data_paths.settings_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/translation/jobs/{job_id}/artifact/{artifact_kind}")
    async def api_translation_job_artifact(request: Request, job_id: str, artifact_kind: str):
        context = _context(request)
        _target = _active_target(request)
        try:
            path = context.translation_jobs.job_artifact_path(job_id=job_id, artifact_kind=artifact_kind)
        except ValueError as exc:
            return JSONResponse(
                {"status": "failed", "diagnostics": {"error": str(exc)}},
                status_code=404,
            )
        media_type = "application/octet-stream"
        if path.suffix.lower() == ".docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif path.suffix.lower() == ".json":
            media_type = "application/json"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.post("/api/translation/save-row")
    async def api_translation_save_row(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = save_translation_row(
                settings_path=target.data_paths.settings_path,
                job_log_db_path=target.data_paths.job_log_db_path,
                form_values=dict(payload.get("form_values", {})),
                seed_payload=payload.get("seed_payload"),
                row_id=payload.get("row_id"),
            )
        except ValueError as exc:
            return _validation_error_response(context, target, message=str(exc))
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/translation/history")
    async def api_translation_history(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        limit_raw = request.query_params.get("limit", "100")
        try:
            limit = max(1, min(500, int(limit_raw)))
        except ValueError:
            limit = 100
        response = {
            "status": "ok",
            "normalized_payload": {
                "history": list_translation_history(
                    db_path=target.data_paths.job_log_db_path,
                    limit=limit,
                ),
                "active_jobs": context.translation_jobs.list_jobs(runtime_mode=target.mode, limit=12),
            },
            "diagnostics": {},
            "capability_flags": build_translation_capability_flags(settings_path=target.data_paths.settings_path),
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/interpretation/autofill-notification")
    async def api_autofill_notification(request: Request, file: UploadFile = File(...)) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        if not str(file.filename or "").lower().endswith(".pdf"):
            return JSONResponse(
                _merge_response(
                    context,
                    target,
                    {
                        "status": "failed",
                        "normalized_payload": {},
                        "diagnostics": {"error": "Notification upload must be a PDF."},
                    },
                ),
                status_code=400,
            )
        saved_path = await _save_upload(file, context.server_runtime_paths.uploads_dir, fallback_suffix=".pdf")
        response = autofill_interpretation_from_notification_pdf(
            pdf_path=saved_path,
            settings_path=target.data_paths.settings_path,
        )
        response.setdefault("diagnostics", {})
        response["diagnostics"]["uploaded_file"] = str(saved_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/interpretation/autofill-photo")
    async def api_autofill_photo(request: Request, file: UploadFile = File(...)) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        suffix = Path(str(file.filename or "")).suffix or ".png"
        saved_path = await _save_upload(file, context.server_runtime_paths.uploads_dir, fallback_suffix=suffix)
        response = autofill_interpretation_from_photo(
            image_path=saved_path,
            settings_path=target.data_paths.settings_path,
        )
        response.setdefault("diagnostics", {})
        response["diagnostics"]["uploaded_file"] = str(saved_path)
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/interpretation/save-row")
    async def api_save_row(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = save_interpretation_row(
                settings_path=target.data_paths.settings_path,
                job_log_db_path=target.data_paths.job_log_db_path,
                form_values=dict(payload.get("form_values", {})),
                seed_payload=payload.get("seed_payload"),
                row_id=payload.get("row_id"),
                service_same_checked=bool(payload.get("service_same_checked", True)),
                use_service_location_in_honorarios_checked=bool(
                    payload.get("use_service_location_in_honorarios_checked", False)
                ),
                include_transport_sentence_in_honorarios_checked=bool(
                    payload.get("include_transport_sentence_in_honorarios_checked", True)
                ),
                profile_id=str(payload.get("profile_id", "") or "").strip() or None,
            )
        except ValueError as exc:
            return _validation_error_response(
                context,
                target,
                message=str(exc),
                validation_error=_structured_validation_payload(exc),
            )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/interpretation/export-honorarios")
    async def api_export_honorarios(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        form_values = dict(payload.get("form_values", {}))
        form_values["include_transport_sentence_in_honorarios"] = bool(
            payload.get(
                "include_transport_sentence_in_honorarios_checked",
                form_values.get("include_transport_sentence_in_honorarios", True),
            )
        )
        form_values["use_service_location_in_honorarios"] = bool(
            payload.get(
                "use_service_location_in_honorarios_checked",
                form_values.get("use_service_location_in_honorarios", False),
            )
        )
        try:
            response = export_interpretation_honorarios(
                settings_path=target.data_paths.settings_path,
                outputs_dir=target.data_paths.outputs_dir,
                form_values=form_values,
                profile_id=str(payload.get("profile_id", "") or "").strip() or None,
                output_filename=str(payload.get("output_filename", "") or "").strip() or None,
                service_same_checked=bool(payload.get("service_same_checked", True)),
            )
        except ValueError as exc:
            return _validation_error_response(
                context,
                target,
                message=str(exc),
                validation_error=_structured_validation_payload(exc),
            )
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/interpretation/cities/add")
    async def api_add_interpretation_city(request: Request) -> JSONResponse:
        context = _context(request)
        payload = await request.json()
        target = _active_target(
            request,
            mode_override=payload.get("mode"),
            workspace_override=payload.get("workspace_id"),
        )
        try:
            response = add_interpretation_city(
                settings_path=target.data_paths.settings_path,
                city=str(payload.get("city", "") or "").strip(),
                profile_id=str(payload.get("profile_id", "") or "").strip() or None,
                include_transport_sentence=bool(payload.get("include_transport_sentence_in_honorarios", False)),
                travel_km_outbound=payload.get("travel_km_outbound", ""),
                field_name=str(payload.get("field_name", "") or "service_city").strip() or "service_city",
            )
        except ValueError as exc:
            return _validation_error_response(
                context,
                target,
                message=str(exc),
                validation_error=_structured_validation_payload(exc),
            )
        return JSONResponse(_merge_response(context, target, response))

    @app.get("/api/interpretation/history")
    async def api_history(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        limit_raw = request.query_params.get("limit", "100")
        try:
            limit = max(1, min(500, int(limit_raw)))
        except ValueError:
            limit = 100
        response = {
            "status": "ok",
            "normalized_payload": {
                "history": list_interpretation_history(
                    db_path=target.data_paths.job_log_db_path,
                    limit=limit,
                )
            },
            "diagnostics": {},
            "capability_flags": build_interpretation_capability_flags(settings_path=target.data_paths.settings_path),
        }
        return JSONResponse(_merge_response(context, target, response))

    @app.post("/api/profiles/import-live")
    async def api_import_live_profiles(request: Request) -> JSONResponse:
        context = _context(request)
        target = _active_target(request)
        if target.mode == RUNTIME_MODE_LIVE:
            response = {
                "status": "ok",
                "normalized_payload": {
                    "imported_profile_count": 0,
                    "message": "Live mode already uses the live desktop profiles directly.",
                },
                "diagnostics": {},
            }
            return JSONResponse(_merge_response(context, target, response))
        response = import_live_profile_settings(
            shadow_settings_path=target.data_paths.settings_path,
            live_settings_path=detect_browser_data_paths(mode=RUNTIME_MODE_LIVE).settings_path,
        )
        response.setdefault("normalized_payload", {})
        profiles = response["normalized_payload"].get("profiles", [])
        response["normalized_payload"]["imported_profile_count"] = len(profiles)
        return JSONResponse(_merge_response(context, target, response))

    return app
