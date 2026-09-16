"""Additive owned source-review routes; no browser-authored evidence or paths.

The only source path accepted at preparation is an existing owned manual upload.
Review text belongs in private UI views, never diagnostics. This module adds no
restart restore shortcut and does not change ordinary translation contracts.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import stat
import threading

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from legalpdf_translate.browser_source_review import BrowserSourceReviewError
from legalpdf_translate.checkpoint import build_run_paths
from legalpdf_translate.ordinary_source_review_service import SourcePageDecision, SourceReviewAction, SourceReviewFinding
from legalpdf_translate.run_workspace_lock import run_workspace_slot
from legalpdf_translate.shadow_runtime import normalize_workspace_id
from legalpdf_translate.translation_service import build_translation_config

_MAX_BODY = 2 * 1024 * 1024
_SCOPE_KEYS = {"mode", "workspace_id"}
_PREFIX = "/api/translation/source-reviews"


class SourceReviewAPIError(ValueError):
    def __init__(self, code, status_code=422):
        super().__init__(code)
        self.status_code = status_code


def _fail(code, status_code=422):
    raise SourceReviewAPIError("source_review_" + code, status_code) from None


class DisabledSourceReviews:
    enabled = False

    def __init__(self, _translation_jobs=None):
        pass


def direct_file(value):
    """Reject redirections before resolving a browser-provided candidate path."""
    if type(value) not in (str, Path) and not isinstance(value, Path):
        _fail("source_unavailable")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
        _fail("source_unavailable")
    for item in (path, *path.parents):
        info = item.lstat()
        if (item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400
                or item != path and not stat.S_ISDIR(info.st_mode)):
            _fail("source_unavailable")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_nlink", 1) != 1:
        _fail("source_unavailable")
    return path.resolve(strict=True)


def owned_browser_source(context, target, source_path, *, attachment_id=""):
    """Shared pre-write check for manual upload or backend-selected attachment."""
    try:
        actual = direct_file(source_path)
        if attachment_id:
            expected = context.gmail_sessions.current_attachment_file(runtime_mode=target.mode,
                workspace_id=target.workspace_id, attachment_id=attachment_id)
            if expected is None or direct_file(expected) != actual:
                _fail("source_unavailable")
        else:
            root = context.server_runtime_paths.uploads_dir / "translation" / target.mode / target.workspace_id
            # Uploads are server-generated direct children, never an arbitrary
            # file found somewhere below a user-supplied directory.
            if actual.parent != root.absolute() or actual.parent.resolve(strict=True) != actual.parent:
                _fail("source_unavailable")
        return actual
    except SourceReviewAPIError:
        raise
    except Exception:
        _fail("source_unavailable")


def direct_output_directory(value):
    """Validate the raw directory before the normal parser resolves/probes it."""
    try:
        if type(value) is not str:
            _fail("output_unavailable")
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
            _fail("output_unavailable")
        for item in (path, *path.parents):
            info = item.lstat()
            if (not stat.S_ISDIR(info.st_mode) or item.is_symlink()
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                _fail("output_unavailable")
        # The unchanged normal parser uses a fixed writable-folder probe. Do
        # not enter it when that name already belongs to any existing object.
        if os.path.lexists(path / ".write_test.tmp"):
            _fail("output_probe_conflict")
        return path.resolve(strict=True)
    except SourceReviewAPIError:
        raise
    except Exception:
        _fail("output_unavailable")


def _keys(value, expected):
    if type(value) is not dict or set(value) != expected:
        _fail("invalid_request")
    return value


def _id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        _fail("invalid_id")
    return value


def _positive(value, maximum=1_000_000):
    if type(value) is not int or not 1 <= value <= maximum:
        _fail("invalid_integer")
    return value


def _text(value, *, maximum=1000, empty=False):
    if type(value) is not str or len(value) > maximum or (not empty and not value.strip()):
        _fail("invalid_text")
    value.encode("utf-8")
    return value


def _ids(value):
    if type(value) is not list or len(value) > 5000 or any(type(n) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", n) is None for n in value):
        _fail("invalid_decision")
    return tuple(value)


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        _fail("invalid_decision")
    return value


def source_page_decision(value, *, image_size):
    _keys(value, {"actions", "reading_order", "full_page_review_completed", "reading_order_reviewed",
        "boundary_decision", "boundary_rationale", "findings", "reviewer"})
    if any(type(value[key]) is not bool for key in ("full_page_review_completed", "reading_order_reviewed")):
        _fail("invalid_decision")
    if (type(value["actions"]) is not list or len(value["actions"]) > 5000
            or type(value["findings"]) is not list or len(value["findings"]) > 5000):
        _fail("invalid_decision")
    width, height = image_size
    actions, findings = [], []
    for row in value["actions"]:
        _keys(row, {"id", "kind", "baseline_block_ids", "after_text", "region_px", "rationale"})
        region = row["region_px"]
        if (type(region) is not list or len(region) != 4 or any(type(n) not in (int, float) for n in region)
                or not 0 <= region[0] < region[2] <= width or not 0 <= region[1] < region[3] <= height
                or not all(math.isfinite(n) for n in region)):
            _fail("invalid_region")
        identifier = _ids([row["id"]])[0]
        actions.append(SourceReviewAction(identifier, _enum(row["kind"], {"retain", "replace", "omit_nontext", "transcribe"}),
            _ids(row["baseline_block_ids"]), _text(row["after_text"], maximum=100_000, empty=True), tuple(region), _text(row["rationale"])))
    for row in value["findings"]:
        _keys(row, {"id", "category", "status", "action_ids", "rationale"})
        findings.append(SourceReviewFinding(_ids([row["id"]])[0],
            _enum(row["category"], {"identifier", "citation", "omission", "invention", "reading_order", "boundary", "other"}),
            _enum(row["status"], {"resolved", "unresolved"}), _ids(row["action_ids"]), _text(row["rationale"])))
    return SourcePageDecision(tuple(actions), _ids(value["reading_order"]), value["full_page_review_completed"],
        value["reading_order_reviewed"], _enum(value["boundary_decision"], {"start", "continuation", "unresolved"}),
        _text(value["boundary_rationale"]), tuple(findings), _text(value["reviewer"]))


async def _payload(request):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > _MAX_BODY:
            _fail("request_too_large", 413)
        raw.extend(chunk)
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                _fail("invalid_json")
            output[key] = value
        return output
    def constant(_value):
        _fail("invalid_json")
    try:
        value = json.loads(bytes(raw).decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        if type(value) is not dict:
            _fail("invalid_request")
        return value
    except SourceReviewAPIError:
        raise
    except Exception:
        _fail("invalid_json")


def explicit_scope(request, payload):
    modes = request.headers.getlist("X-LegalPDF-Runtime-Mode") + request.query_params.getlist("mode")
    workspaces = (request.headers.getlist("X-LegalPDF-Workspace-Id") + request.query_params.getlist("workspace")
                  + request.query_params.getlist("workspace_id"))
    if "mode" in payload:
        modes.append(payload["mode"])
    if "workspace_id" in payload:
        workspaces.append(payload["workspace_id"])
    if (not modes or not workspaces or any(type(v) is not str or v not in {"live", "shadow"} for v in modes)
            or any(type(v) is not str or not 0 < len(v) <= 128 or normalize_workspace_id(v) != v
                   or v.strip("._-") != v for v in workspaces)):
        _fail("explicit_scope_required")
    if len(set(modes)) != 1 or len(set(workspaces)) != 1:
        _fail("scope_conflict")
    return modes[0], workspaces[0]


def _response(*, value=None, job=None, error=None, status_code=200):
    normalized = {}
    if value is not None:
        normalized["source_review"] = value
    if job is not None:
        normalized["job"] = job
    return JSONResponse({"status": "failed" if error else "ok", "normalized_payload": normalized,
        "diagnostics": {} if error is None else {"error": error},
        "capability_flags": {"source_review": {"status": "disabled" if error == "source_review_disabled" else "available"}}},
        status_code=status_code, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class SourceReviewRoutes:
    def __init__(self, app, *, context_for, target_for):
        self._context_for, self._target_for = context_for, target_for
        self._slots = asyncio.Semaphore(4)
        self._guard = threading.RLock()
        self._run_owners = {}
        app.add_api_route(_PREFIX + "/prepare", self.prepare, methods=["POST"])
        app.add_api_route(_PREFIX + "/{review_id}", self.read, methods=["GET"])
        app.add_api_route(_PREFIX + "/{review_id}/pages/{page_number}/image", self.image, methods=["GET"])
        app.add_api_route(_PREFIX + "/{review_id}/pages/{page_number}", self.save_page, methods=["POST"])
        app.add_api_route(_PREFIX + "/{review_id}/submit", self.submit, methods=["POST"])
        app.add_api_route(_PREFIX + "/{review_id}/translate", self.translate, methods=["POST"])

    async def _operation(self, request, fields, operation, *, body=False):
        try:
            payload = await _payload(request) if body else {}
            if set(payload) - _SCOPE_KEYS != fields:
                _fail("invalid_request")
            mode, workspace = explicit_scope(request, payload)
            context = self._context_for(request)
            if getattr(context.source_reviews, "enabled", True) is False:
                _fail("disabled", 409)
            target = self._target_for(request, mode_override=mode, workspace_override=workspace)
            if target.mode != mode or target.workspace_id != workspace:
                _fail("scope_conflict")
            async with self._slots:
                return await run_in_threadpool(operation, context, target, payload)
        except SourceReviewAPIError as exc:
            return _response(error=str(exc), status_code=exc.status_code)
        except BrowserSourceReviewError as exc:
            code = str(exc)
            return _response(error=code if re.fullmatch(r"browser_source_review_[a-z_]+", code) else "source_review_operation_failed", status_code=422)
        except Exception:
            return _response(error="source_review_operation_failed", status_code=422)

    def _release_pristine_claim(self, root, key, claim):
        # _prepare keeps its outer run slot until this check and release end.
        # Reenter it to verify the actual retained OS-lock identity, including
        # on context exit, before deleting only our exact in-memory claim.
        with self._guard:
            if self._run_owners.get(key) is not claim:
                return False
            try:
                with run_workspace_slot(root) as locked_root:
                    with os.scandir(locked_root) as entries:
                        only = next(entries, None)
                        second = next(entries, None)
                    if (only is None or second is not None or only.name != ".run_workspace.lock"
                            or direct_file(locked_root / only.name) != locked_root / ".run_workspace.lock"):
                        return False
                del self._run_owners[key]
                return True
            except Exception:
                # An incomplete check is not proof that acquisition did nothing.
                return False

    def _prepare(self, context, target, payload):
        form = payload["form_values"]
        if type(form) is not dict:
            _fail("invalid_request")
        if form.get("gmail_batch_context"):
            _fail("manual_upload_required")
        source = owned_browser_source(context, target, form.get("source_path"))
        output = direct_output_directory(form.get("output_dir"))
        try:
            config = build_translation_config(form_values={**form, "source_path": str(source), "output_dir": str(output)},
                                               settings_path=target.data_paths.settings_path)
        except Exception:
            _fail("invalid_saved_setup")
        root = build_run_paths(config.output_dir, config.pdf_path, config.target_lang,
                               gmail_batch_context=config.gmail_batch_context).run_dir
        owner = (target.mode, target.workspace_id, deepcopy(config))
        with run_workspace_slot(root, create=True):
            key = os.path.normcase(str(root.resolve()))
            installed_here = False
            with self._guard:
                retained = self._run_owners.get(key)
                if retained is None:
                    if len(self._run_owners) >= 256:
                        _fail("registry_full")
                    if any(p.name != ".run_workspace.lock" for p in root.iterdir()):
                        _fail("saved_run_owner_unavailable")
                    self._run_owners[key] = owner
                    installed_here = True
                elif retained != owner:
                    _fail("run_owner_conflict")
            value = context.source_reviews.prepare(runtime_mode=target.mode, workspace_id=target.workspace_id,
                config=config, settings_path=target.data_paths.settings_path)
            explicit_decline = (type(value) is dict and set(value) == {"status", "notice_codes"}
                and value["status"] == "declined" and type(value["notice_codes"]) is list
                and 0 < len(value["notice_codes"]) <= 32 and all(type(code) is str
                    and re.fullmatch(r"source_review_[a-z_]{1,100}", code) is not None
                    for code in value["notice_codes"]))
            if installed_here and explicit_decline:
                self._release_pristine_claim(root, key, owner)
        return _response(value=value)

    async def prepare(self, request: Request):
        return await self._operation(request, {"form_values"}, self._prepare, body=True)

    async def read(self, request: Request, review_id: str):
        def operation(context, target, _payload):
            return _response(value=context.source_reviews.read(runtime_mode=target.mode,
                workspace_id=target.workspace_id, review_id=_id(review_id)))
        return await self._operation(request, set(), operation)

    async def image(self, request: Request, review_id: str, page_number: str):
        def operation(context, target, _payload):
            if re.fullmatch(r"[1-9][0-9]{0,3}", page_number) is None:
                _fail("invalid_integer")
            image = context.source_reviews.image(runtime_mode=target.mode, workspace_id=target.workspace_id,
                                                  review_id=_id(review_id), page_number=_positive(int(page_number), 5000))
            return Response(image, media_type="image/png", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        return await self._operation(request, set(), operation)

    async def save_page(self, request: Request, review_id: str, page_number: str):
        def operation(context, target, payload):
            if re.fullmatch(r"[1-9][0-9]{0,3}", page_number) is None:
                _fail("invalid_integer")
            number = _positive(int(page_number), 5000)
            generation = _positive(payload["expected_generation"])
            kwargs = {"runtime_mode": target.mode, "workspace_id": target.workspace_id, "review_id": _id(review_id)}
            view = context.source_reviews.read(**kwargs)
            page = next((p for p in view.get("pages", ()) if p["page_number"] == number), None)
            if page is None:
                _fail("page_unavailable")
            decision = source_page_decision(payload["decision"], image_size=page["image_size_px"])
            return _response(value=context.source_reviews.save_page(**kwargs, expected_generation=generation,
                page_number=number, decision=decision))
        return await self._operation(request, {"expected_generation", "decision"}, operation, body=True)

    async def submit(self, request: Request, review_id: str):
        def operation(context, target, payload):
            if payload["accept_source"] is not True:
                _fail("explicit_acceptance_required")
            return _response(value=context.source_reviews.submit(runtime_mode=target.mode, workspace_id=target.workspace_id,
                review_id=_id(review_id), expected_generation=_positive(payload["expected_generation"]),
                reviewer=_text(payload["reviewer"]), accept_source=True))
        return await self._operation(request, {"expected_generation", "reviewer", "accept_source"}, operation, body=True)

    async def translate(self, request: Request, review_id: str):
        def operation(context, target, payload):
            return _response(job=context.source_reviews.start_translate(runtime_mode=target.mode, workspace_id=target.workspace_id,
                review_id=_id(review_id), revision_id=_id(payload["revision_id"]), operation_nonce=_id(payload["operation_nonce"])))
        return await self._operation(request, {"revision_id", "operation_nonce"}, operation, body=True)
