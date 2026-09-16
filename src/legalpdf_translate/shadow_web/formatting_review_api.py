"""Additive job-owned formatting routes with explicit operator decisions."""
from __future__ import annotations

import asyncio
import math
import re

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from legalpdf_translate.browser_formatting_review import BrowserFormattingReviewError
from legalpdf_translate.ordinary_formatting_review_service import (
    FormattingFragment, FormattingParagraph, FormattingTable, FormattingPageDecision,
    FormattingDocumentDecision, FormattingDocumentGroup,
)
from .source_review_api import SourceReviewAPIError, explicit_scope, _payload

PREFIX = "/api/translation/jobs/{job_id}/formatting-reviews"
_SCOPE_KEYS = {"mode", "workspace_id"}


class FormattingReviewAPIError(ValueError):
    def __init__(self, code, status_code=422):
        super().__init__("formatting_review_" + code)
        self.status_code = status_code


def _fail(code):
    raise FormattingReviewAPIError(code) from None


class DisabledFormattingReviews:
    enabled = False

    def __init__(self, _jobs=None):
        pass


def _keys(value, keys):
    if type(value) is not dict or set(value) != keys:
        _fail("invalid_request")


def _integer(value, *, minimum=1, maximum=1_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail("invalid_integer")
    return value


def _boolean(value):
    if type(value) is not bool:
        _fail("invalid_decision")
    return value


def _text(value):
    if type(value) is not str or not value.strip() or len(value) > 1000:
        _fail("invalid_text")
    value.encode("utf-8")
    return value


def _list(value, maximum=5000):
    if type(value) is not list or len(value) > maximum:
        _fail("invalid_decision")
    return value


def _numbers(value):
    return tuple(_integer(n, maximum=5000) for n in _list(value))


def _range(value):
    if type(value) is not list or len(value) != 2:
        _fail("invalid_decision")
    result = tuple(_integer(n, minimum=0, maximum=10_000_000) for n in value)
    if result[0] >= result[1]:
        _fail("invalid_decision")
    return result


def _number(value):
    if type(value) not in (int, float) or not 0 <= value <= 10_000_000 or not math.isfinite(value):
        _fail("invalid_decision")
    return value


def _choice(value, options):
    if type(value) is not str or value not in options:
        _fail("invalid_decision")
    return value


def formatting_page_decision(value):
    _keys(value, {"fragments", "header", "body", "footer", "folio_fragment_number",
        "full_page_review_completed", "source_target_mapping_reviewed", "reviewer", "review_note"})
    fragments = []
    for row in _list(value["fragments"]):
        _keys(row, {"parent_number", "source_range", "target_range", "bbox_px", "role", "alignment", "bold", "italic", "review_note"})
        box = tuple(_number(n) for n in _list(row["bbox_px"], 4))
        if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
            _fail("invalid_decision")
        fragments.append(FormattingFragment(_integer(row["parent_number"], maximum=5000),
            _range(row["source_range"]), _range(row["target_range"]), box,
            _choice(row["role"], {"header", "body", "signature", "footer", "folio"}),
            _choice(row["alignment"], {"left", "right", "center", "justify"}),
            _boolean(row["bold"]), _boolean(row["italic"]), _text(row["review_note"])))
    body = []
    for row in _list(value["body"]):
        if type(row) is dict and set(row) == {"fragment_number"}:
            body.append(FormattingParagraph(_integer(row["fragment_number"], maximum=5000)))
        else:
            if type(row) is not dict or set(row) not in ({"column_widths", "rows"}, {"column_widths", "rows", "column_gaps_px"}):
                _fail("invalid_decision")
            widths = tuple(_integer(n, maximum=100) for n in _list(row["column_widths"], 4))
            rows = tuple(tuple(_numbers(cell) for cell in _list(cells, 4)) for cells in _list(row["rows"], 100))
            gaps = tuple(_number(n) for n in _list(row["column_gaps_px"], 3)) if "column_gaps_px" in row else None
            body.append(FormattingTable(widths, rows, gaps))
    folio = value["folio_fragment_number"]
    return FormattingPageDecision(tuple(fragments), _numbers(value["header"]), tuple(body), _numbers(value["footer"]),
        None if folio is None else _integer(folio, maximum=5000),
        _boolean(value["full_page_review_completed"]), _boolean(value["source_target_mapping_reviewed"]),
        _text(value["reviewer"]), _text(value["review_note"]))


def formatting_document_decision(value):
    _keys(value, {"groups", "all_pages_reviewed", "allow_pipe_cell_boundaries", "preserve_source_gaps", "reviewer", "review_note"})
    groups = []
    for row in _list(value["groups"], 1000):
        _keys(row, {"start_page", "end_page"})
        groups.append(FormattingDocumentGroup(_integer(row["start_page"], maximum=1000),
            _integer(row["end_page"], maximum=1000)))
    return FormattingDocumentDecision(tuple(groups), _boolean(value["all_pages_reviewed"]),
        _boolean(value["allow_pipe_cell_boundaries"]), _boolean(value["preserve_source_gaps"]),
        _text(value["reviewer"]), _text(value["review_note"]))


def _response(value=None, *, error=None, status_code=200):
    return JSONResponse({"status": "failed" if error else "ok",
        "normalized_payload": {} if value is None else {"formatting_review": value},
        "diagnostics": {} if error is None else {"error": error},
        "capability_flags": {"formatting_review": {"status": "disabled" if error == "formatting_review_disabled" else "available"}}},
        status_code=status_code, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class FormattingReviewRoutes:
    def __init__(self, app, *, context_for, target_for):
        self._context_for, self._target_for = context_for, target_for
        self._slots = asyncio.Semaphore(4)
        for suffix, method, endpoint in (("/prepare", "POST", self.prepare),
                ("/{review_id}", "GET", self.read),
                ("/{review_id}/pages/{page_number}/image", "GET", self.image),
                ("/{review_id}/pages/{page_number}", "POST", self.save_page),
                ("/{review_id}/document", "POST", self.save_document),
                ("/{review_id}/submit", "POST", self.submit),
                ("/{review_id}/revisions/{revision_id}", "GET", self.inspect),
                ("/{review_id}/rebuild", "POST", self.rebuild),
                ("/{review_id}/artifacts/{artifact_id}/{artifact_kind}", "GET", self.artifact)):
            app.add_api_route(PREFIX + suffix, endpoint, methods=[method])

    async def _operation(self, request, job_id, fields, callback, *, body=False):
        try:
            payload = await _payload(request) if body else {}
            if set(payload) - _SCOPE_KEYS != fields:
                _fail("invalid_request")
            mode, workspace = explicit_scope(request, payload)
            context = self._context_for(request)
            manager = getattr(context, "formatting_reviews", None)
            if manager is None or getattr(manager, "enabled", True) is False:
                raise FormattingReviewAPIError("disabled", 409)
            target = self._target_for(request, mode_override=mode, workspace_override=workspace)
            if target.mode != mode or target.workspace_id != workspace:
                _fail("scope_conflict")
            scope = {"runtime_mode": mode, "workspace_id": workspace, "job_id": job_id,
                     "settings_path": target.data_paths.settings_path}
            async with self._slots:
                return await run_in_threadpool(callback, manager, scope, payload)
        except FormattingReviewAPIError as exc:
            return _response(error=str(exc), status_code=exc.status_code)
        except SourceReviewAPIError as exc:
            return _response(error=str(exc).replace("source_review_", "formatting_review_", 1), status_code=exc.status_code)
        except BrowserFormattingReviewError as exc:
            code = str(exc)
            return _response(error=code if re.fullmatch(r"browser_formatting_review_[a-z_]+", code) else "formatting_review_operation_failed", status_code=422)
        except Exception:
            return _response(error="formatting_review_operation_failed", status_code=422)

    async def prepare(self, request: Request, job_id: str):
        return await self._operation(request, job_id, {"page_matched_derivative"},
            lambda m, s, p: _response(m.prepare(**s, page_matched_derivative=_boolean(p["page_matched_derivative"]))), body=True)

    async def read(self, request: Request, job_id: str, review_id: str):
        return await self._operation(request, job_id, set(), lambda m, s, p: _response(m.read(**s, review_id=review_id)))

    async def image(self, request: Request, job_id: str, review_id: str, page_number: int):
        return await self._operation(request, job_id, set(), lambda m, s, p: Response(
            m.image(**s, review_id=review_id, page_number=_integer(page_number, maximum=1000)), media_type="image/png",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}))

    async def save_page(self, request: Request, job_id: str, review_id: str, page_number: int):
        return await self._operation(request, job_id, {"expected_generation", "decision"}, lambda m, s, p: _response(
            m.save_page(**s, review_id=review_id, page_number=_integer(page_number, maximum=1000),
                expected_generation=_integer(p["expected_generation"]), decision=formatting_page_decision(p["decision"]))), body=True)

    async def save_document(self, request: Request, job_id: str, review_id: str):
        return await self._operation(request, job_id, {"expected_generation", "decision"}, lambda m, s, p: _response(
            m.save_document(**s, review_id=review_id, expected_generation=_integer(p["expected_generation"]),
                decision=formatting_document_decision(p["decision"]))), body=True)

    async def submit(self, request: Request, job_id: str, review_id: str):
        return await self._operation(request, job_id, {"expected_generation", "reviewer", "accept_formatting"}, lambda m, s, p: _response(
            m.submit(**s, review_id=review_id, expected_generation=_integer(p["expected_generation"]),
                reviewer=_text(p["reviewer"]), accept_formatting=_boolean(p["accept_formatting"]))), body=True)

    async def inspect(self, request: Request, job_id: str, review_id: str, revision_id: str):
        return await self._operation(request, job_id, set(), lambda m, s, p: _response(m.inspect(**s, review_id=review_id, revision_id=revision_id)))

    async def rebuild(self, request: Request, job_id: str, review_id: str):
        return await self._operation(request, job_id, {"revision_id", "operation_nonce"}, lambda m, s, p: _response(
            m.rebuild(**s, review_id=review_id, revision_id=p["revision_id"], operation_nonce=p["operation_nonce"])), body=True)

    async def artifact(self, request: Request, job_id: str, review_id: str, artifact_id: str, artifact_kind: str):
        def download(manager, scope, _payload):
            raw = manager.artifact(**scope, review_id=review_id, artifact_id=artifact_id, artifact_kind=artifact_kind)
            docx = artifact_kind == "output_docx"
            return Response(raw, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if docx else "application/json",
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                    "Content-Disposition": 'attachment; filename="reviewed-' + artifact_kind + ('.docx"' if docx else '.json"')})
        return await self._operation(request, job_id, set(), download)
