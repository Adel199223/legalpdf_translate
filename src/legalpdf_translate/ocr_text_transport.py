"""Saved OpenAI OCR transport, with immutable answered acquisition replay.

This stores exact provider output strings and flags, not HTTP response bytes.
The existing native dispatch journal remains the sole usage/cost authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

POLICY = "openai_ocr_text_envelope_v1"
KEY = "ocr_text_transport_policy"
MAX_TEXT = 300_000
MAX_RAW = 2_000_000
_SCOPE = ContextVar("ocr_text_acquisition_scope", default=None)
INSTRUCTIONS = ("Extract all visible source text, preserving its exact characters and line breaks. "
    "Return only the strict JSON object with one field text. The value is the source transcription, "
    "not commentary. Do not add Markdown or code fences as transport formatting. If literal "
    "backticks, fences, quotes or JSON appear on the source, preserve them inside text exactly.")


class OcrTextTransportError(ValueError):
    def __init__(self, code):
        self.code = "ocr_text_transport_" + code
        super().__init__(self.code)


def _fail(code):
    raise OcrTextTransportError(code)


def _json(value):
    try:
        # Private artifact encoding must retain even a malformed provider string
        # containing a lone surrogate before decoded source validation rejects it.
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (ValueError, TypeError, UnicodeError):
        _fail("evidence_shape")


def _sha(value):
    try:
        return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()
    except UnicodeError:
        _fail("invalid_unicode")


def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _bytes(path):
    try:
        return path.read_bytes()
    except OSError:
        _fail("evidence_missing")


def _object(rows):
    result = {}
    for key,value in rows:
        if key in result:
            _fail("duplicate_key")
        result[key] = value
    return result


def _parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=lambda _: _fail("invalid_json"))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        _fail("invalid_json")


def decode(raw):
    if type(raw) is not str or len(raw) > MAX_RAW:
        _fail("response_bound")
    data = _parse(raw)
    if type(data) is not dict or set(data) != {"text"} or type(data["text"]) is not str:
        _fail("response_shape")
    text = data["text"]
    if not text.strip() or len(text) > MAX_TEXT:
        _fail("text_bound")
    _sha(text)  # Reject lone surrogates; preserve every valid decoded character.
    return text


def response_format():
    return {"type": "json_schema", "name": POLICY, "strict": True, "schema": {
        "type": "object", "properties": {"text": {"type": "string"}},
        "required": ["text"], "additionalProperties": False}}


def descriptor():
    return {"policy": POLICY, "schema_sha256": _sha(_json(response_format())),
        "instructions_sha256": _sha(INSTRUCTIONS), "max_text_chars": MAX_TEXT,
        "max_raw_output_chars": MAX_RAW, "text_semantics": "exact_decoded_string_v1",
        "retention": "exact_provider_output_string_and_flags_not_http_bytes_v1"}


@dataclass(frozen=True)
class AcquisitionScope:
    run_dir: Path
    page: int
    pdf_sha256: str


@contextmanager
def scope(run_dir, page, pdf_sha256):
    token = _SCOPE.set(AcquisitionScope(Path(run_dir), page, pdf_sha256))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def _owned(run_dir, relative):
    path = Path(run_dir)/relative
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != Path(run_dir).parent):
        _fail("evidence_path")
    try:
        path.resolve().relative_to(Path(run_dir).resolve())
    except ValueError:
        _fail("evidence_path")
    return path


def _read(path):
    try:
        raw = _bytes(path)
        data = _parse(raw)
        if _json(data).encode("utf-8") != raw:
            _fail("evidence_changed")
        return data
    except OSError:
        _fail("evidence_missing")


def _persist(path, value):
    raw = _json(value).encode("utf-8")
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            _fail("evidence_changed")
        return
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        _fail("evidence_persistence")


def _journal(path):
    try:
        data = _parse(path.read_bytes())
    except OSError:
        _fail("native_evidence_missing")
    if (type(data) is not dict or type(data.get("events")) is not list
            or any(type(row) is not dict for row in data["events"])):
        _fail("native_evidence_changed")
    return data


def _begins(journal, identity):
    return [row for row in journal["events"] if row.get("event") == "begin"
        and row.get("provider") == "openai" and row.get("purpose") == "ocr"
        and row.get("page_number") == identity["page"]
        and row.get("request_hash") == identity["wire_request_sha256"]]


def _native(journal, identity, response_id=None, *, call_id=None):
    begins = _begins(journal, identity)
    if len(begins) != 1:
        _fail("native_call_ownership")
    begin = begins[0]
    if type(begin.get("call_id")) is not str or not begin["call_id"]:
        _fail("native_call_ownership")
    finishes = [r for r in journal["events"] if r.get("event") == "finish" and r.get("call_id") == begin["call_id"]]
    if (len(finishes) != 1 or begin.get("requested_model") != identity["model"]
            or begin.get("route") != "responses.create" or begin.get("attempt") != 1
            or (call_id is not None and begin["call_id"] != call_id)):
        _fail("native_call_ownership")
    finish = finishes[0]
    if response_id is not None and finish.get("response_id") != response_id:
        _fail("native_response_ownership")
    return {"call_id": begin["call_id"], "begin_sha256": _sha(_json(begin)),
        "finish_sha256": _sha(_json(finish))}, finish


def _settled(finish):
    if (finish.get("cost_status") != "available" or type(finish.get("usage")) is not dict
            or finish["usage"].get("usage_status") != "available"
            or finish.get("outcome") not in {"succeeded", "refused"}):
        _fail("native_unsettled")


def _response(response):
    from .openai_client import _field
    parts = []
    unsupported = False
    refused, incomplete = bool(_field(response, "refusal")), False
    output = _field(response, "output", [])
    if not isinstance(output, list):
        output, unsupported = [], True
    for item in output:
        item_type = _field(item, "type")
        refused |= item_type == "refusal"
        if item_type == "reasoning":
            reasoning = _field(item, "content")
            if reasoning is not None and (type(reasoning) is not list or any(
                    _field(part, "type") != "reasoning_text" or type(_field(part, "text")) is not str for part in reasoning)):
                unsupported = True
            continue
        if (item_type != "message" or _field(item, "role") != "assistant"
                or _field(item, "status") != "completed"):
            unsupported = True
        incomplete |= item_type == "message" and _field(item, "status") not in (None, "completed")
        content = _field(item, "content", [])
        if not isinstance(content, list):
            unsupported = True
            continue
        for part in content:
            kind = _field(part, "type")
            refused |= kind == "refusal"
            if kind == "output_text" and type(_field(part, "text")) is str:
                parts.append(_field(part, "text"))
            elif kind != "refusal":
                unsupported = True
    return {"raw_output": parts[0] if len(parts) == 1 else "", "output_text_parts": parts,
        "unsupported_output_shape": unsupported, "response_id": _field(response, "id"),
        "response_model": _field(response, "model"), "response_status": _field(response, "status"),
        "refused": refused, "incomplete": incomplete,
        "incomplete_details": _field(response, "incomplete_details") is not None}


def _decoded(answer):
    response = answer["response"]
    keys = {"raw_output", "output_text_parts", "unsupported_output_shape", "response_id", "response_model",
        "response_status", "refused", "incomplete", "incomplete_details"}
    if (type(response) is not dict or set(response) != keys or type(response["raw_output"]) is not str
            or type(response["output_text_parts"]) is not list
            or any(type(v) is not str for v in response["output_text_parts"])
            or any(type(response[k]) is not bool for k in ("unsupported_output_shape","refused","incomplete","incomplete_details"))):
        _fail("evidence_shape")
    if (response["response_status"] != "completed" or response["refused"] is not False
            or response["incomplete"] is not False or response["incomplete_details"] is not False):
        _fail("response_not_completed")
    if (response["unsupported_output_shape"] is not False or len(response["output_text_parts"]) != 1
            or response["raw_output"] != response["output_text_parts"][0]
            or type(response["response_id"]) is not str or not response["response_id"]):
        _fail("response_shape")
    return decode(response["raw_output"])


def acquire(*, client, fallback_accountant, image_bytes, request):
    """One immutable request slot; a paid/answered slot is never dispatched twice."""
    from .openai_client import (_active_accountant, _dispatch_limits, _apply_openai_dispatch_limits,
        _request_accounting_details, _accounted_openai_create)
    from .usage_accounting import DispatchAccounting, current_accounting_binding
    context = _SCOPE.get()
    active = _active_accountant(fallback_accountant)
    binding = current_accounting_binding()
    if (context is None or not isinstance(active, DispatchAccounting) or binding is None
            or binding.page_number != context.page):
        _fail("acquisition_context_required")
    _, limits = _dispatch_limits(active, provider="openai", purpose="ocr", model=request["model"])
    wire = _apply_openai_dispatch_limits(request, active, limits)
    request_sha, _ = _request_accounting_details(wire)
    try:
        journal_relative = Path(active.journal_path).resolve().relative_to(context.run_dir.resolve()).as_posix()
    except ValueError:
        _fail("native_context")
    journal_path = _owned(context.run_dir, journal_relative)
    journal = _journal(journal_path)
    identity = {"version": "ocr_text_acquisition_intent_v1", "policy": descriptor(),
        "pdf_sha256": context.pdf_sha256, "page": context.page, "image_sha256": _sha(image_bytes),
        "model": request["model"], "wire_request_sha256": request_sha,
        "journal_path": journal_relative, "native_run_identity_sha256": _sha(_json(journal.get("run_identity")))}
    relative = f"ocr_transport/page_{context.page:04d}"
    directory = _owned(context.run_dir, relative)
    directory.mkdir(parents=True, exist_ok=True)
    intent_path, answered_path = directory/"intent.json", directory/"answered.json"
    if any(p.name not in {"intent.json", "answered.json"} for p in directory.iterdir()):
        _fail("evidence_changed")
    if intent_path.exists():
        if _read(intent_path) != identity:
            _fail("request_binding_changed")
        if not answered_path.is_file():
            _fail("acquisition_unsettled")
    else:
        prior_page_call = any(row.get("event") == "begin" and row.get("provider") == "openai"
            and row.get("purpose") == "ocr" and row.get("page_number") == context.page for row in journal["events"])
        if answered_path.exists() or prior_page_call:
            _fail("native_evidence_missing")
        _persist(intent_path, identity)
        # Native accounting completes its settlement before returning a response.
        # An exception leaves the intent conservative; it cannot authorize retry.
        try:
            response = _accounted_openai_create(client=client, accountant=fallback_accountant, purpose="ocr", **request)
        except Exception as exc:
            raise OcrTextTransportError("acquisition_failed") from exc
        retained = _response(response)
        proof, _ = _native(_journal(journal_path), identity, retained["response_id"])
        _persist(answered_path, {"version": "ocr_text_acquisition_answer_v1",
            "intent_sha256": _sha(intent_path.read_bytes()), "native": proof, "response": retained})
    answer = _read(answered_path)
    text = _validate_answer(context.run_dir, intent_path, answered_path, identity, answer)
    return text, {"version": "ocr_text_acquisition_ref_v1", "path": (answered_path.relative_to(context.run_dir)).as_posix(),
        "sha256": _sha(answered_path.read_bytes()), "decoded_text_sha256": _sha(text)}


def _validate_answer(run_dir, intent_path, answered_path, identity, answer):
    if (type(answer) is not dict or set(answer) != {"version", "intent_sha256", "native", "response"}
            or answer["version"] != "ocr_text_acquisition_answer_v1"
            or answer["intent_sha256"] != _sha(_bytes(intent_path))
            or type(answer["native"]) is not dict or type(answer["response"]) is not dict):
        _fail("evidence_changed")
    journal = _journal(_owned(run_dir, identity["journal_path"]))
    if _sha(_json(journal.get("run_identity"))) != identity["native_run_identity_sha256"]:
        _fail("native_context")
    proof, finish = _native(journal, identity, answer["response"].get("response_id"), call_id=answer["native"].get("call_id"))
    if proof != answer["native"]:
        _fail("native_evidence_changed")
    if answer["response"].get("response_model") != finish.get("actual_model"):
        _fail("native_response_ownership")
    _settled(finish)
    return _decoded(answer)


def validate_ref(*, run_dir, pdf_sha256, page, reference, original_source_text=None):
    if (type(reference) is not dict or set(reference) != {"version", "path", "sha256", "decoded_text_sha256"}
            or reference["version"] != "ocr_text_acquisition_ref_v1" or type(reference["path"]) is not str
            or not _digest(reference["sha256"]) or not _digest(reference["decoded_text_sha256"])):
        _fail("source_binding")
    path = _owned(run_dir, reference["path"])
    if reference["path"] != f"ocr_transport/page_{page:04d}/answered.json":
        _fail("source_binding")
    identity = _read(path.parent/"intent.json")
    keys = {"version", "policy", "pdf_sha256", "page", "image_sha256", "model", "wire_request_sha256",
        "journal_path", "native_run_identity_sha256"}
    if (type(identity) is not dict or set(identity) != keys or identity.get("policy") != descriptor()
            or type(identity["page"]) is not int or identity["page"] != page or identity["pdf_sha256"] != pdf_sha256
            or identity["version"] != "ocr_text_acquisition_intent_v1"
            or any(not _digest(identity[k]) for k in ("pdf_sha256", "image_sha256", "wire_request_sha256", "native_run_identity_sha256"))
            or type(identity["model"]) is not str or not identity["model"]
            or type(identity["journal_path"]) is not str or not identity["journal_path"]):
        _fail("source_binding")
    if _sha(_bytes(path)) != reference["sha256"]:
        _fail("evidence_changed")
    text = _validate_answer(run_dir, path.parent/"intent.json", path, identity, _read(path))
    if _sha(text) != reference["decoded_text_sha256"] or (original_source_text is not None and text != original_source_text):
        _fail("decoded_source_changed")
    return text
