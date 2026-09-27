"""Bounded additive ordinary-layout routes; all reads are local-only."""
from __future__ import annotations

import asyncio
import re

from fastapi import Request
from fastapi.responses import JSONResponse
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
