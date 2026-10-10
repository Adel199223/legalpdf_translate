"""Bounded additive ordinary-layout routes; all reads are local-only."""
from __future__ import annotations

import asyncio
import re

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ..ordinary_layout_contracts import decode, fail
from .source_review_api import explicit_scope

MAX_JSON_BYTES = 64 * 1024
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
PREFIX = "/api/translation/jobs/{job_id}"


def response(value=None, *, error=None, status=200):
    return JSONResponse({"status": "failed" if error else "ok",
        "normalized_payload": {} if error else {"ordinary_layout": value},
        "diagnostics": {"error": error} if error else {}, "capability_flags": {}}, status_code=status, headers=HEADERS)


def error_response(exc):
    code = getattr(exc, "code", "ordinary_layout_operation_failed")
    if type(code) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,150}", code) is None:
        code = "ordinary_layout_operation_failed"
    if not code.startswith("ordinary_layout_"):
        code = "ordinary_layout_" + code
    status = getattr(exc, "status", getattr(exc, "status_code", 422))
    if type(status) is not int or status not in {400, 404, 409, 413, 415, 422, 503}:
        status = 422
    return response(error=code, status=status)


async def payload(request, fields):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        fail("json_required", 415)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_JSON_BYTES:
            fail("request_too_large", 413)
        raw.extend(chunk)
    value = decode(bytes(raw))
    if type(value) is not dict or set(value) != fields:
        fail("invalid_request")
    return value


class OrdinaryLayoutRoutes:
    """manager_for(request, mode, workspace_id) returns the trusted scoped manager."""
    def __init__(self, app, *, manager_for):
        self.manager_for = manager_for
        self.slots = asyncio.Semaphore(2)
        for suffix, method, endpoint in (
            ("/layout", "GET", self.state), ("/layout/prepare", "POST", self.prepare),
            ("/layout/suggestions", "POST", self.suggest),
            ("/layout/suggestions/{operation_nonce}", "GET", self.suggestion),
            ("/layout/suggestions/{operation_nonce}/cancel", "POST", self.cancel_suggestion),
            ("/layout/output-review", "POST", self.accept_output),
            ("/delivery", "GET", self.delivery), ("/delivery", "POST", self.select_delivery),
            ("/text-corrections", "GET", self.text_state),
            ("/text-corrections", "POST", self.text_draft),
            ("/text-corrections/{draft_id}/approve", "POST", self.text_approve),
            ("/text-corrections/{draft_id}/cancel", "POST", self.text_cancel),
            ("/text-corrections/output-review", "POST", self.text_output_review),
            ("/text-corrections/source/{page_number}", "GET", self.text_source),
            ("/text-corrections/findings/{finding_id}", "POST", self.text_finding),
        ):
            app.add_api_route(PREFIX + suffix, endpoint, methods=[method])

    def manager(self, request):
        mode, workspace_id = explicit_scope(request, {})
        manager = self.manager_for(request, mode, workspace_id)
        if manager is None:
            fail("disabled", 503)
        if manager.mode != mode or manager.workspace_id != workspace_id:
            fail("owner_mismatch", 409)
        return manager

    async def _call(self, request, job_id, operation, fields=None, *, control=False):
        try:
            manager = self.manager(request)
            data = await payload(request, fields) if fields is not None else None
            if control:
                # Cancellation must not queue behind both occupied paid slots.
                return response(await run_in_threadpool(operation, manager, data))
            async with self.slots:
                return response(await run_in_threadpool(operation, manager, data))
        except Exception as exc:
            return error_response(exc)

    async def state(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, _: m.state(job_id))

    async def prepare(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, d: m.prepare(job_id, d["prepare_nonce"]), {"prepare_nonce"})

    async def suggest(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, d: m.suggest(job_id, d["expected_generation"],
            d["operation_nonce"], d["page_numbers"], expected_baseline_id=d["baseline_id"]),
            {"expected_generation", "operation_nonce", "page_numbers", "baseline_id"})

    async def suggestion(self, request: Request, job_id: str, operation_nonce: str):
        return await self._call(request, job_id, lambda m, _: m.suggestion(job_id, operation_nonce))

    async def cancel_suggestion(self, request: Request, job_id: str, operation_nonce: str):
        return await self._call(request, job_id, lambda m, d: m.cancel_suggestion(job_id, operation_nonce,
            d["expected_generation"], expected_baseline_id=d["baseline_id"]),
            {"baseline_id", "expected_generation"}, control=True)

    async def accept_output(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, d: m.accept_output(job_id, d["artifact_id"],
            d["expected_generation"], d["acceptance_nonce"], d["all_pages_reviewed"], expected_baseline_id=d["baseline_id"]),
            {"artifact_id", "expected_generation", "acceptance_nonce", "all_pages_reviewed", "baseline_id"})

    async def delivery(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, _: m.delivery(job_id))

    async def select_delivery(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, d: m.select_delivery(job_id, d["expected_delivery_generation"],
            d["selection_nonce"], d["kind"], d["review_id"], d["artifact_id"], d["expected_review_generation"],
            d["keep_ordinary_confirmed"], expected_baseline_id=d["baseline_id"]),
            {"expected_delivery_generation", "selection_nonce", "kind", "review_id", "artifact_id",
             "expected_review_generation", "keep_ordinary_confirmed", "baseline_id"})

    def correction_job(self, manager, job_id):
        job = manager._job(job_id)
        if manager.service.state(job_id)["status"] == "unprepared":
            from uuid import uuid4
            manager.service.prepare(job, uuid4().hex)
        manager.service.assert_current(job)
        return job

    async def text_state(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, _: m.service.text_correction_state(self.correction_job(m, job_id)))

    async def text_draft(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, d: m.service.draft_text_correction(
            self.correction_job(m, job_id), d["draft_nonce"], d["parent"], d["actions"], import_word=d["import_word"]),
            {"draft_nonce", "parent", "actions", "import_word"})

    async def text_approve(self, request: Request, job_id: str, draft_id: str):
        return await self._call(request, job_id, lambda m, d: m.service.approve_text_correction(
            self.correction_job(m, job_id), draft_id, d["approval_nonce"], d["source_compared"],
            d["changes_reviewed"], d["rationale"]), {"approval_nonce", "source_compared", "changes_reviewed", "rationale"})

    async def text_cancel(self, request: Request, job_id: str, draft_id: str):
        return await self._call(request, job_id, lambda m, _: m.service.cancel_text_correction(
            self.correction_job(m, job_id), draft_id), set())

    async def text_source(self, request: Request, job_id: str, page_number: int):
        try:
            manager = self.manager(request)
            self.correction_job(manager, job_id)
            view = manager.service.state(job_id)
            if page_number not in view["selected_pages"]:
                fail("correction_source_page_required")
            raw = await run_in_threadpool(manager.service.saved.image, view["review"]["review_id"], page_number)
            return Response(raw, media_type="image/png", headers=HEADERS)
        except Exception as exc:
            return error_response(exc)

    async def text_output_review(self, request: Request, job_id: str):
        return await self._call(request, job_id, lambda m, d: m.service.review_text_output(
            self.correction_job(m, job_id), d["selection_id"], d["expected_generation"], d["all_pages_reviewed"]),
            {"selection_id", "expected_generation", "all_pages_reviewed"})

    async def text_finding(self, request: Request, job_id: str, finding_id: str):
        return await self._call(request, job_id, lambda m, d: m.service.review_source_finding(
            self.correction_job(m, job_id), finding_id, d["parent"], d["disposition"], d["source_compared"]),
            {"parent", "disposition", "source_compared"})
