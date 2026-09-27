"""Scoped, local-only saved Word layout import/review routes.

The multipart reader bounds the actual request stream before handing any bytes
to the parser. It never accepts paths, authoritative hashes or replacement text.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, Response
try:
    from python_multipart.multipart import MultipartParser, parse_options_header
except ImportError:  # Supported python-multipart versions before its namespace move.
    from multipart.multipart import MultipartParser, parse_options_header
from starlette.concurrency import run_in_threadpool

from .source_review_api import explicit_scope

PREFIX = "/api/saved-docx-layout"
MAX_REQUEST_BYTES = 97 * 1024 * 1024
MAX_DOCX_BYTES = 32 * 1024 * 1024
MAX_PDF_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_HEADER_BYTES = 8 * 1024
MAX_FIELD_BYTES = 1024
_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
_KINDS = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "source_map": "application/json", "receipt": "application/json"}


class SavedDocxLayoutAPIError(ValueError):
    def __init__(self, code: str, status: int = 422):
        self.code, self.status = code, status
        super().__init__(code)


def _fail(code, status=422):
    raise SavedDocxLayoutAPIError(code, status)


def default_saved_docx_layout_root(*, mode, repo, identity):
    """Resolve storage without reading settings or deriving configured outputs."""
    if mode == "live":
        from legalpdf_translate.user_settings import app_data_dir_from_settings_path, settings_path
        return app_data_dir_from_settings_path(settings_path())
    from legalpdf_translate.shadow_runtime import shadow_app_data_dir
    return shadow_app_data_dir(repo=repo, identity=identity)


def _response(value=None, *, error=None, status=200):
    capability = "available"
    if error == "saved_docx_layout_disabled":
        capability = "disabled"
    elif error == "saved_docx_layout_renderer_unavailable" or isinstance(value, dict) and value.get("available") is False:
        capability = "unavailable"
    return JSONResponse({
        "status": "failed" if error else "ok",
        "normalized_payload": {} if error else {"saved_docx_layout": value},
        "diagnostics": {"error": error} if error else {},
        "capability_flags": {"saved_docx_layout": {"status": capability}},
    }, status_code=status, headers=_HEADERS)


def _error(exc):
    code = getattr(exc, "code", None)
    if code is None and type(exc).__name__ == "SourceReviewAPIError":
        code = str(exc).removeprefix("source_review_")
    if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,100}", code):
        code = "operation_failed"
    if not code.startswith("saved_docx_layout_"):
        code = "saved_docx_layout_" + code
    status = getattr(exc, "status", getattr(exc, "status_code", 422))
    if type(status) is not int or status not in {400, 404, 409, 413, 415, 422, 503}:
        status = 422
    return _response(error=code, status=status)


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        _fail("invalid_id")
    return value


def _generation(value):
    if type(value) is not int or not 1 <= value <= 1_000_000:
        _fail("invalid_generation")
    return value


async def _json_payload(request, fields):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_JSON_BYTES:
            _fail("request_too_large", 413)
        raw.extend(chunk)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("invalid_json")
            result[key] = value
        return result

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: _fail("invalid_json"))
    except SavedDocxLayoutAPIError:
        raise
    except Exception:
        _fail("invalid_json")
    if type(data) is not dict or set(data) != fields:
        _fail("invalid_request")
    return data


class _ImportParts:
    """Small streaming parser sink; bounded buffers only, no filename writes."""
    def __init__(self):
        self.parts = {}
        self.count = self.header_bytes = 0
        self.ended = False

    def on_part_begin(self):
        self.count += 1
        if self.count > 4:
            _fail("invalid_multipart")
        self.headers, self.field, self.value, self.buffer = {}, bytearray(), bytearray(), bytearray()
        self.name, self.limit = None, 0

    def _header(self, target, data, start, end):
        self.header_bytes += end - start
        if self.header_bytes > MAX_HEADER_BYTES:
            _fail("multipart_headers_too_large", 413)
        target.extend(data[start:end])

    def on_header_field(self, data, start, end):
        self._header(self.field, data, start, end)

    def on_header_value(self, data, start, end):
        self._header(self.value, data, start, end)

    def on_header_end(self):
        key = bytes(self.field).lower()
        if key not in {b"content-disposition", b"content-type"} or key in self.headers:
            _fail("invalid_multipart")
        self.headers[key] = bytes(self.value)
        self.field.clear()
        self.value.clear()

    def on_headers_finished(self):
        disposition, options = parse_options_header(self.headers.get(b"content-disposition"))
        if disposition != b"form-data" or b"name" not in options:
            _fail("invalid_multipart")
        try:
            self.name = options[b"name"].decode("ascii")
        except (ValueError, UnicodeError):
            _fail("invalid_multipart")
        if self.name in self.parts or self.name not in {"source_pdf", "saved_docx", "target_lang", "import_nonce"}:
            _fail("invalid_multipart")
        is_file = self.name in {"source_pdf", "saved_docx"}
        if is_file != (b"filename" in options):
            _fail("invalid_multipart")
        if set(options) - {b"name", b"filename"}:
            _fail("invalid_multipart")
        self.limit = (MAX_PDF_BYTES if self.name == "source_pdf" else MAX_DOCX_BYTES) if is_file else MAX_FIELD_BYTES

    def on_part_data(self, data, start, end):
        if self.name is None:
            _fail("invalid_multipart")
        if len(self.buffer) + end - start > self.limit:
            _fail("upload_too_large", 413)
        self.buffer.extend(data[start:end])

    def on_part_end(self):
        if not self.buffer:
            _fail("empty_upload")
        self.parts[self.name] = bytes(self.buffer)

    def on_end(self):
        self.ended = True


async def _import_payload(request):
    content_type, options = parse_options_header(request.headers.get("content-type"))
    boundary = options.get(b"boundary", b"")
    if content_type != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
        _fail("invalid_multipart", 415)
    sink = _ImportParts()
    names = ("part_begin", "header_field", "header_value", "header_end", "headers_finished", "part_data", "part_end", "end")
    parser = MultipartParser(boundary, {"on_" + name: getattr(sink, "on_" + name) for name in names})
    total = 0
    try:
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                _fail("request_too_large", 413)
            parser.write(chunk)
        parser.finalize()
    except SavedDocxLayoutAPIError:
        raise
    except Exception:
        _fail("invalid_multipart")
    if not sink.ended or set(sink.parts) != {"source_pdf", "saved_docx", "target_lang", "import_nonce"}:
        _fail("invalid_multipart")
    try:
        lang = sink.parts["target_lang"].decode("ascii")
        nonce = sink.parts["import_nonce"].decode("ascii")
    except UnicodeError:
        _fail("invalid_multipart")
    if lang not in {"EN", "FR", "AR"}:
        _fail("unsupported_language")
    return sink.parts["source_pdf"], sink.parts["saved_docx"], lang, _identifier(nonce)


class SavedDocxLayoutRoutes:
    def __init__(self, app, *, context_for):
        self._context_for = context_for
        self._slots = asyncio.Semaphore(2)
        for suffix, method, endpoint in (
            ("/capabilities", "GET", self.capabilities),
            ("/imports", "POST", self.import_document),
            ("/reviews", "GET", self.list_reviews),
            ("/reviews/{review_id}", "GET", self.read),
            ("/reviews/{review_id}/pages/{page_number}/image", "GET", self.image),
            ("/reviews/{review_id}/decisions", "POST", self.save),
            ("/reviews/{review_id}/builds", "POST", self.build),
            ("/reviews/{review_id}/artifacts/{artifact_id}/{kind}", "GET", self.artifact),
        ):
            app.add_api_route(PREFIX + suffix, endpoint, methods=[method])

    def _service(self, request):
        mode, workspace = explicit_scope(request, {})
        context = self._context_for(request)
        factory = context.services.saved_docx_layout_factory
        root_for = context.services.saved_docx_layout_root
        if factory is None or root_for is None:
            _fail("disabled", 409)
        root = root_for(mode=mode, repo=context.repo_root, identity=context.build_identity)
        return factory(Path(root), mode=mode, workspace_id=workspace)

    async def _call(self, request, operation):
        try:
            service = self._service(request)
            async with self._slots:
                return _response(await run_in_threadpool(operation, service))
        except Exception as exc:
            return _error(exc)

    async def capabilities(self, request: Request):
        return await self._call(request, lambda service: service.capabilities())

    async def list_reviews(self, request: Request):
        return await self._call(request, lambda service: service.list_reviews())

    async def read(self, request: Request, review_id: str):
        return await self._call(request, lambda service: service.read(_identifier(review_id)))

    async def import_document(self, request: Request):
        try:
            service = self._service(request)  # Scope checked before body consumption.
            async with self._slots:
                args = await _import_payload(request)
                return _response(await run_in_threadpool(service.import_document, *args))
        except Exception as exc:
            return _error(exc)

    async def save(self, request: Request, review_id: str):
        try:
            service = self._service(request)
            async with self._slots:
                data = await _json_payload(request, {"expected_generation", "save_nonce", "decisions"})
                value = await run_in_threadpool(service.save_decisions, _identifier(review_id),
                    _generation(data["expected_generation"]), _identifier(data["save_nonce"]), data["decisions"])
                return _response(value)
        except Exception as exc:
            return _error(exc)

    async def build(self, request: Request, review_id: str):
        try:
            service = self._service(request)
            async with self._slots:
                data = await _json_payload(request, {"expected_generation", "operation_nonce", "review_confirmed"})
                if type(data["review_confirmed"]) is not bool:
                    _fail("invalid_review_confirmation")
                value = await run_in_threadpool(service.build, _identifier(review_id),
                    _generation(data["expected_generation"]), _identifier(data["operation_nonce"]), data["review_confirmed"])
                return _response(value)
        except Exception as exc:
            return _error(exc)

    async def image(self, request: Request, review_id: str, page_number: int):
        try:
            service = self._service(request)
            if not 1 <= page_number <= 100:
                _fail("invalid_page")
            async with self._slots:
                data = await run_in_threadpool(service.image, _identifier(review_id), page_number)
            return Response(data, media_type="image/png", headers=_HEADERS)
        except Exception as exc:
            return _error(exc)

    async def artifact(self, request: Request, review_id: str, artifact_id: str, kind: str):
        try:
            service = self._service(request)
            if kind not in _KINDS:
                _fail("artifact_not_found", 404)
            async with self._slots:
                data = await run_in_threadpool(service.artifact, _identifier(review_id), _identifier(artifact_id), kind)
            suffix = "docx" if kind == "docx" else "json"
            return Response(data, media_type=_KINDS[kind], headers={**_HEADERS,
                "Content-Disposition": f'attachment; filename="formatted-copy-{artifact_id}-{kind}.{suffix}"'})
        except Exception as exc:
            return _error(exc)
