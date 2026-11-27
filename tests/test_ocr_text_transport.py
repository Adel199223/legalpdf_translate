"""Exact OCR JSON text and native once-only acquisition, fictional HTTP only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legalpdf_translate import ocr_engine as engines
from legalpdf_translate import ocr_text_transport as transport
from legalpdf_translate.accounting_policy import ordinary_accounting_policy
from legalpdf_translate.usage_accounting import DispatchAccounting, accounting_context
from tests.semantic_model_fakes import ModelHTTP

TEXT = " \n```\nTexto visível العربية \u2066ABC\u2069 \"text\" \\ \n```\r\n "
PDF = "a" * 64


def native(tmp_path, monkeypatch, *, raw=None, mutate=None):
    def response(body, data):
        data["output"][0]["content"][0]["text"] = json.dumps({"text": TEXT}, ensure_ascii=False) if raw is None else raw
        return mutate(data) if mutate else data
    http = ModelHTTP(response)
    monkeypatch.setattr(engines, "OpenAI", lambda **kwargs: http.sdk)
    engine = engines.ApiOcrEngine(api_key="fictional", model="gpt-4o-mini", text_transport_policy=transport.POLICY)
    accountant = DispatchAccounting(tmp_path / "accounting", run_identity={"fictional": "ocr"},
        **ordinary_accounting_policy().accounting_arguments())
    def call(image=b"fictional-image", model=None):
        if model is not None: engine._model = model
        with accounting_context(accountant, page_number=1), transport.scope(tmp_path, 1, PDF):
            return engine.ocr_image(image, "PT")
    return engine, accountant, http, call


def retained(tmp_path):
    return {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"}


@pytest.mark.parametrize("text", [TEXT, "```", "{\"text\":\"printed source\"}", "\ufeffA\u2028B\r\nC "])
def test_decode_preserves_genuine_fences_unicode_whitespace_exactly(text):
    assert transport.decode(json.dumps({"text": text}, ensure_ascii=False)) == text


@pytest.mark.parametrize("raw", ["```\n{}\n```", "{}", "[]", "null", '{"text":1}', '{"text":null}',
    '{"text":""}', '{"text":"  \\n"}', '{"text":"A","extra":1}', '{"text":"A","text":"B"}',
    '{"text":NaN}', '{"text":"\\ud800"}', '{"text":"A"} prose'])
def test_malformed_envelopes_fail_closed(raw):
    with pytest.raises(transport.OcrTextTransportError): transport.decode(raw)


@pytest.mark.parametrize("which", ["raw", "text"])
def test_parser_bounds_are_local_and_exact(monkeypatch, which):
    monkeypatch.setattr(transport, "MAX_RAW" if which == "raw" else "MAX_TEXT", 10)
    with pytest.raises(transport.OcrTextTransportError): transport.decode('{"text":"' + "x"*11 + '"}')


def test_answered_actual_surrogate_retained_losslessly_then_typed_rejected(tmp_path, monkeypatch):
    raw = '{"text":"' + chr(0xD800) + '"}'
    def mutate(data):
        # A valid JSON wire escape becomes an actual surrogate in the SDK's
        # output string. It must survive private artifact retention before fail.
        return json.dumps(data, ensure_ascii=True).encode()
    _, _, http, call = native(tmp_path, monkeypatch, raw=raw, mutate=mutate)
    with pytest.raises(transport.OcrTextTransportError, match="invalid_unicode"): call()
    answer = tmp_path / "ocr_transport/page_0001/answered.json"
    assert json.loads(answer.read_bytes())["response"]["raw_output"] == raw
    before = retained(tmp_path)
    with pytest.raises(transport.OcrTextTransportError, match="invalid_unicode"): call()
    assert len(http.requests) == 1 and retained(tmp_path) == before
    assert transport._read(answer)["response"]["raw_output"] == raw


def test_sdk_schema_native_cost_exact_answer_and_no_call_replay(tmp_path, monkeypatch):
    engine, accountant, http, call = native(tmp_path, monkeypatch)
    result = call()
    assert result.text == TEXT and result.text_transport_evidence
    request = http.requests[0]
    assert request["text"]["format"] == transport.response_format()
    assert request["model"] == "gpt-4o-mini" and request["store"] is False
    assert request["input"][0]["content"][1]["detail"] == "high"
    answer = json.loads((tmp_path / result.text_transport_evidence["path"]).read_bytes())
    assert answer["response"]["raw_output"] == json.dumps({"text": TEXT}, ensure_ascii=False)
    assert answer["response"]["response_model"] == request["model"]
    journal = json.loads(accountant.journal_path.read_bytes())
    assert [e["event"] for e in journal["events"]] == ["begin", "finish"]
    assert journal["events"][-1]["cost_status"] == "available"
    before = retained(tmp_path)
    assert call().text == TEXT and len(http.requests) == 1 and retained(tmp_path) == before
    assert transport.validate_ref(run_dir=tmp_path, pdf_sha256=PDF, page=1,
        reference=result.text_transport_evidence, original_source_text=TEXT) == TEXT


@pytest.mark.parametrize("drift", ["image", "model", "prompt", "limit"])
def test_page_slot_request_drift_never_purchases_again(tmp_path, monkeypatch, drift):
    engine, accountant, http, call = native(tmp_path, monkeypatch)
    call()
    if drift == "prompt": monkeypatch.setattr(transport, "INSTRUCTIONS", transport.INSTRUCTIONS + " Changed.")
    if drift == "limit":
        monkeypatch.setattr(transport, "response_format", lambda: {"type": "json_object"})
    with pytest.raises(transport.OcrTextTransportError, match="request_binding_changed"):
        call(image=b"different" if drift == "image" else b"fictional-image", model="gpt-4o" if drift == "model" else None)
    assert len(http.requests) == 1


@pytest.mark.parametrize("defect", ["malformed", "refusal", "incomplete", "content_none", "content_scalar", "parts", "unknown_cost"])
def test_answered_failure_is_retained_before_parse_and_reused_without_send(tmp_path, monkeypatch, defect):
    def mutate(data):
        if defect == "refusal": data["output"][0]["content"] = [{"type": "refusal", "refusal": "fictional"}]
        elif defect == "incomplete": data.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        elif defect == "content_none": data["output"][0]["content"] = None
        elif defect == "content_scalar": data["output"][0]["content"] = 5
        elif defect == "parts": data["output"][0]["content"] *= 2
        elif defect == "unknown_cost": data["usage"] = None
        return data
    _, _, http, call = native(tmp_path, monkeypatch, raw="not JSON" if defect == "malformed" else None, mutate=mutate)
    with pytest.raises(transport.OcrTextTransportError): call()
    # A malformed object that native accounting itself cannot settle remains an
    # intent-only unknown slot. All normally settled answers retain exact flags.
    if defect != "content_scalar": assert (tmp_path / "ocr_transport/page_0001/answered.json").is_file()
    before = retained(tmp_path)
    with pytest.raises(transport.OcrTextTransportError): call()
    assert len(http.requests) == 1 and retained(tmp_path) == before


@pytest.mark.parametrize("boundary", ["intent", "returned", "answered", "parsed"])
def test_crash_boundary_never_repurchases(tmp_path, monkeypatch, boundary):
    _, _, http, call = native(tmp_path, monkeypatch)
    original_persist, original_decoded = transport._persist, transport._decoded
    class Crash(BaseException): pass
    def persist(path, value):
        if path.name == "answered.json" and boundary == "returned": raise Crash()
        original_persist(path, value)
        if path.name == "intent.json" and boundary == "intent": raise Crash()
        if path.name == "answered.json" and boundary == "answered": raise Crash()
    def decoded(answer):
        value = original_decoded(answer)
        if boundary == "parsed": raise Crash()
        return value
    monkeypatch.setattr(transport, "_persist", persist)
    monkeypatch.setattr(transport, "_decoded", decoded)
    with pytest.raises(Crash): call()
    monkeypatch.setattr(transport, "_persist", original_persist)
    monkeypatch.setattr(transport, "_decoded", original_decoded)
    calls = len(http.requests)
    if boundary in {"answered", "parsed"}: assert call().text == TEXT
    else:
        with pytest.raises(transport.OcrTextTransportError, match="unsettled"): call()
    assert len(http.requests) == calls


@pytest.mark.parametrize("boundary", ["before_intent", "before_begin", "after_begin", "before_finish", "after_finish"])
def test_native_reservation_settlement_crash_cuts_keep_single_paid_slot(tmp_path, monkeypatch, boundary):
    _, accountant, http, call = native(tmp_path, monkeypatch)
    class Crash(BaseException): pass
    persist, begin, finish = transport._persist, accountant.begin, accountant.finish
    def save(path, value):
        if boundary == "before_intent" and path.name == "intent.json": raise Crash()
        return persist(path, value)
    def reserve(**kwargs):
        if boundary == "before_begin": raise Crash()
        value = begin(**kwargs)
        if boundary == "after_begin": raise Crash()
        return value
    def settle(*args, **kwargs):
        if boundary == "before_finish": raise Crash()
        value = finish(*args, **kwargs)
        if boundary == "after_finish": raise Crash()
        return value
    monkeypatch.setattr(transport, "_persist", save)
    monkeypatch.setattr(accountant, "begin", reserve)
    monkeypatch.setattr(accountant, "finish", settle)
    with pytest.raises(Crash): call()
    count = len(http.requests)
    monkeypatch.setattr(transport, "_persist", persist)
    monkeypatch.setattr(accountant, "begin", begin)
    monkeypatch.setattr(accountant, "finish", finish)
    if boundary == "before_intent":
        assert count == 0 and call().text == TEXT and len(http.requests) == 1
    else:
        with pytest.raises(transport.OcrTextTransportError, match="unsettled"): call()
        assert len(http.requests) == count


@pytest.mark.parametrize("damage", ["intent_removed", "answer_removed", "intent_scalar", "answer_scalar", "response_scalar", "native_scalar", "model", "raw", "native_event"])
def test_missing_tampered_and_malformed_evidence_typed_stop_no_send(tmp_path, monkeypatch, damage):
    _, accountant, http, call = native(tmp_path, monkeypatch)
    result = call()
    intent, answer = tmp_path / "ocr_transport/page_0001/intent.json", tmp_path / result.text_transport_evidence["path"]
    if damage.endswith("removed"):
        (intent if damage == "intent_removed" else answer).unlink()
    elif damage == "native_event":
        value = json.loads(accountant.journal_path.read_bytes()); value["events"][-1]["actual_model"] = "wrong"
        accountant.journal_path.write_text(json.dumps(value))
    else:
        path = intent if damage.startswith("intent") else answer
        value = json.loads(path.read_bytes())
        if damage in {"intent_scalar", "answer_scalar"}: value = []
        elif damage == "response_scalar": value["response"] = 5
        elif damage == "native_scalar": value["native"] = []
        elif damage == "model": value["response"]["response_model"] = "wrong"
        else: value["response"]["raw_output"] = '{"text":"wrong"}'
        path.write_text(transport._json(value), encoding="utf-8")
    with pytest.raises(transport.OcrTextTransportError): call()
    with pytest.raises(transport.OcrTextTransportError):
        transport.validate_ref(run_dir=tmp_path, pdf_sha256=PDF, page=1, reference=result.text_transport_evidence)
    assert len(http.requests) == 1


def test_selected_policy_requires_native_owned_context_legacy_request_unchanged(tmp_path, monkeypatch):
    engine, _, http, _ = native(tmp_path, monkeypatch)
    with pytest.raises(transport.OcrTextTransportError, match="context_required"): engine.ocr_image(b"image")
    assert not http.requests
    legacy = engines.ApiOcrEngine(api_key="fictional", model="gpt-4o-mini")
    assert legacy.ocr_image(b"image").text == json.dumps({"text": TEXT}, ensure_ascii=False)
    assert "text" not in http.requests[0]
    assert http.requests[0]["input"][0]["content"][0]["text"] == "Extract all visible text. Preserve line breaks. No commentary. Return plain text only."


@pytest.mark.parametrize("shape", ["scalar", "unknown", "missing", "reasoning", "reasoning_text", "bad_reasoning", "missing_role", "user_role", "missing_status"])
def test_only_message_text_and_optional_reasoning_output_are_accepted(tmp_path, monkeypatch, shape):
    def mutate(data):
        if shape == "scalar": data["output"].insert(0, 7)
        elif shape == "unknown": data["output"][0]["type"] = "arbitrary_unknown"
        elif shape == "missing": data["output"][0].pop("type")
        elif shape == "missing_role": data["output"][0].pop("role")
        elif shape == "user_role": data["output"][0]["role"] = "user"
        elif shape == "missing_status": data["output"][0].pop("status")
        else:
            item = {"type": "reasoning", "id": "fictional-reasoning", "summary": []}
            if shape != "reasoning": item["content"] = [{"type": "reasoning_text" if shape == "reasoning_text" else "output_text", "text": "not source text"}]
            data["output"].insert(0, item)
        return data
    _, _, http, call = native(tmp_path, monkeypatch, mutate=mutate)
    if shape in {"reasoning", "reasoning_text"}: assert call().text == TEXT and call().text == TEXT
    else:
        with pytest.raises(transport.OcrTextTransportError): call()
        with pytest.raises(transport.OcrTextTransportError): call()
    assert len(http.requests) == 1
