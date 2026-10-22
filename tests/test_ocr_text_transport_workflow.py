"""Saved ordinary OCR acquisition through the pinned SDK and real workflow."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ocr_engine as engines, ocr_text_transport as transport
from legalpdf_translate import workflow as module
from legalpdf_translate.types import OcrMode, OcrEnginePolicy, OcrApiProvider
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_semantic_review_model_integration import setup
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_new_run_preflight import SOURCE


def configured(tmp_path, monkeypatch, *, text=SOURCE, mutate=None, literal_primary=None):
    def response(body, data):
        if body["model"] == "gpt-4o-mini":
            data["output"][0]["content"][0]["text"] = json.dumps({"text": text}, ensure_ascii=False)
            if mutate: return mutate(data)
        elif literal_primary is not None:
            from tests.semantic_review_fakes import review_response, UNIT_REF_VERSIONS
            name = body.get("text", {}).get("format", {}).get("name")
            if name:
                payload = json.loads(body["input"][0]["content"][0]["text"])
                data["output"][0]["content"][0]["text"] = json.dumps(review_response(payload,
                    unit_references=name in UNIT_REF_VERSIONS.values()), ensure_ascii=False)
            else:
                data["output"][0]["content"][0]["text"] = "```text\n" + literal_primary + "\n```"
        return data
    config, http, flow = setup(tmp_path, mutate=response)
    monkeypatch.setattr(engines, "OpenAI", lambda **kwargs: http.sdk)
    monkeypatch.setattr(engines, "_resolve_api_key", lambda *args: "fictional")
    config = replace(config, ocr_mode=OcrMode.ALWAYS, ocr_engine=OcrEnginePolicy.API, ocr_api_model="gpt-4o-mini")
    return config, http, flow


def immutable(run):
    return {p.relative_to(run).as_posix(): p.read_bytes() for folder in ("ocr_transport", "semantic_source", "semantic_audit", "accounting")
        for p in (run / folder).rglob("*") if p.is_file() and p.suffix != ".lock"}


def test_fresh_full_page_source_bound_saved_replay_and_offline_no_calls(tmp_path, monkeypatch):
    config, http, flow = configured(tmp_path, monkeypatch, text=" \n" + SOURCE + "\r\n ")
    result = flow.run(config)
    assert result.success, result.error
    assert flow._last_state.settings["ordinary_semantic_audit_recipe"][transport.KEY] == transport.POLICY
    source = json.loads((result.run_dir / "semantic_source/page_0001.json").read_bytes())
    assert source["original_source_text"] == " \n" + SOURCE + "\r\n "
    assert source["ocr_text_acquisition"]["composition"] == "api_ocr"
    assert [r["model"] for r in http.requests] == ["gpt-4o-mini", "gpt-5.2"] + ["gpt-6-astra"] * 3
    before = immutable(result.run_dir)
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == 5 and immutable(result.run_dir) == before


@pytest.mark.parametrize("failure", ["malformed", "incomplete", "refused", "empty", "unknown_cost"])
def test_failed_answer_before_primary_retained_resume_never_purchases(tmp_path, monkeypatch, failure):
    def mutate(data):
        if failure == "malformed": data["output"][0]["content"][0]["text"] = "```not-json```"
        elif failure == "incomplete": data.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        elif failure == "refused": data["output"][0]["content"] = [{"type": "refusal", "refusal": "fictional"}]
        elif failure == "empty": data["output"][0]["content"][0]["text"] = '{"text":""}'
        else: data["usage"] = None
        return data
    config, http, flow = configured(tmp_path, monkeypatch, mutate=mutate)
    result = flow.run(config)
    assert not result.success and len(http.requests) == 1
    assert (result.run_dir / "ocr_transport/page_0001/answered.json").is_file()
    assert not (result.run_dir / "semantic_source/page_0001.json").exists()
    before = immutable(result.run_dir)
    resumed = flow.run(replace(config, resume=True))
    assert not resumed.success and len(http.requests) == 1 and immutable(result.run_dir) == before


@pytest.mark.parametrize("damage", ["answer", "intent", "missing", "native"])
def test_completed_page_resume_and_offline_reject_ocr_artifact_tamper(tmp_path, monkeypatch, damage):
    config, http, flow = configured(tmp_path, monkeypatch)
    result = flow.run(config)
    assert result.success, result.error
    directory = result.run_dir / "ocr_transport/page_0001"
    if damage == "missing": (directory / "answered.json").unlink()
    elif damage == "native":
        path = flow._dispatch_accounting.journal_path
        data = json.loads(path.read_bytes()); data["events"][1]["response_id"] = "wrong"
        from legalpdf_translate.usage_accounting import _state_fingerprint
        data["fingerprint"] = _state_fingerprint(data); path.write_text(json.dumps(data))
    else:
        path = directory / ("answered.json" if damage == "answer" else "intent.json")
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises((ValueError, RuntimeError)): TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    try: resumed = flow.run(replace(config, resume=True))
    except (ValueError, RuntimeError): pass
    else: assert not resumed.success
    assert len(http.requests) == 5


def test_crop_merge_uses_exact_crop_acquisition_and_preserves_composed_source(tmp_path, monkeypatch):
    from tests.test_workflow_ocr_routing import _integrity_ordered_text_result
    crop = "10. A última remuneração registada ascende a 498,03 € (quatrocentos e noventa e oito euros e três cêntimos)."
    from legalpdf_translate.arabic_pre_tokenize import pretokenize_arabic_source
    config, http, flow = configured(tmp_path, monkeypatch, text=crop,
        literal_primary="نص تجريبي. " + pretokenize_arabic_source("498,03"))
    config = replace(config, ocr_mode=OcrMode.AUTO)
    monkeypatch.setattr(module, "extract_ordered_page_text", lambda *args, **kwargs: _integrity_ordered_text_result())
    monkeypatch.setattr(module, "_count_vector_gap_drawings", lambda *args, **kwargs: 38)
    # Production currently selects inline recovery only for EN/FR. Exercise the
    # same existing crop route under a saved strict policy without expanding it.
    assess = module._assess_extraction_integrity
    from legalpdf_translate.types import TargetLang
    monkeypatch.setattr(module, "_assess_extraction_integrity", lambda **kwargs: assess(**{**kwargs, "target_lang": TargetLang.FR}))
    result = flow.run(config)
    assert result.success, result.error
    source = json.loads((result.run_dir / "semantic_source/page_0001.json").read_bytes())
    assert source["ocr_text_acquisition"]["composition"] == "merged_pdf_ocr"
    assert "498,03" in source["original_source_text"]
    assert flow._last_state.pages["1"]["source_route_reason"] == "visual_recovery_crop_merged"
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == 5


def test_pending_page_after_answer_before_source_capture_reuses_native_ocr(tmp_path, monkeypatch):
    from legalpdf_translate import workflow_semantic_audit as glue
    config, http, flow = configured(tmp_path, monkeypatch)
    original = glue.capture_source
    stopped = []
    def capture(**kwargs):
        if not stopped:
            stopped.append(True)
            raise RuntimeError("fictional interruption after settled OCR")
        return original(**kwargs)
    monkeypatch.setattr(glue, "capture_source", capture)
    result = flow.run(config)
    assert not result.success and len(http.requests) == 1
    answer = result.run_dir / "ocr_transport/page_0001/answered.json"
    before = answer.read_bytes()
    assert flow.run(replace(config, resume=True)).success
    assert len(http.requests) == 5 and answer.read_bytes() == before
    assert sum(r["model"] == "gpt-4o-mini" for r in http.requests) == 1


def test_genuine_printed_fences_remain_source_units_in_native_inventory(tmp_path, monkeypatch):
    config, http, flow = configured(tmp_path, monkeypatch, text="```\n" + SOURCE + "\n```")
    result = flow.run(config)
    assert result.success, result.error
    request = next(r for r in http.requests if r.get("text", {}).get("format", {}).get("name") == "ordinary_source_inventory_unit_refs_v1")
    payload = json.loads(request["input"][0]["content"][0]["text"])
    assert sum(row["text"] == "```" for row in payload["source_units"]) == 2
    assert json.loads((result.run_dir / "semantic_source/page_0001.json").read_bytes())["original_source_text"].startswith("```\n")


@pytest.mark.parametrize("index", [0, 1])
def test_genuine_prechange_ocr_success_and_fence_failure_native_history_exact_replay(tmp_path, monkeypatch, index):
    from legalpdf_translate import ordinary_semantic_review as review, ordinary_semantic_repair as repair
    fixture = json.loads((Path(__file__).parent / "fixtures/ocr_text_transport_prechange_native.json").read_bytes())
    assert fixture["fictional_only"] and fixture["baseline_runtime_sha256"] == "c5a5594df0838c592cb45a816abf8e14f15d7e032588af7239e8f4814a5f10e7"
    case = fixture["cases"][index]
    assert transport.KEY not in case["saved_recipe"] and "text" not in case["ocr_request"]
    assert "ocr_text_acquisition" not in case["source_pack"]
    assert case["source_pack"]["original_source_text"] == case["source"]
    directory = tmp_path / "audit"; directory.mkdir()
    for name, value in case["evidence"].items():
        file = directory / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(value.encode())
    before = {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    requests = []; original = review._stage
    def stage(*args, **kwargs): requests.append(args[1]); return original(*args, **kwargs)
    monkeypatch.setattr(review, "_stage", stage)
    def guard(**stage):
        if stage["action"] == "final": return {"native_calls": len(case["proofs"])}
        proof = case["proofs"][stage["stage_id"]]
        assert proof["request_sha256"] == review.audit._sha(review.audit._json(stage["request"]))
        return proof
    arguments = dict(pages=[review.SemanticAuditPage(**p) for p in case["pages"]],
        recipe=review.SemanticAuditRecipe(**case["recipe"]), pdf_sha256=case["pdf_sha256"], evidence_dir=directory,
        source_origins=case["source_origins"], stage_guard=guard, **case["options"])
    if case["failed"]:
        with pytest.raises(review.SemanticAuditError, match=case["expected_error"]): repair.load_semantic_repair(**arguments)
    else: assert repair.load_semantic_repair(**arguments).reused
    assert review.audit._json(requests) == review.audit._json(case["requests"])
    assert {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()} == before
