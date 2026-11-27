"""Fictional resolved context and bounded terminology through the actual workflow."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil

import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy

from legalpdf_translate import workflow_semantic_audit as audit
from legalpdf_translate import ordinary_semantic_audit as engine
from legalpdf_translate.checkpoint import (SemanticAuditRecipeError, load_run_state,
    ordinary_semantic_audit_recipe, save_run_state_atomic, sha256_of_text)
from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.pt_legal_glossary_aliases import source_matches_glossary_entry
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_workflow_semantic_audit_integration import offline, saved_v2_protocol, setup, text, CORRECTED


CONTEXT = "Fictional preference: use source-compatible preferred legal terminology.\r\nKeep all original facts."
PREFERRED = "الشخص المتابع"
UNRELATED = "irrelevant glossary phrase"


def payload(sdk):
    return json.loads(sdk.requests[-1]["input"][0]["content"][0]["text"])


def glossary_settings():
    return {"personal_glossaries_by_lang": {"AR": [
        {"source_text": "arguido", "preferred_translation": PREFERRED,
         "match_mode": "exact", "source_lang": "PT", "tier": 1},
        {"source_text": UNRELATED, "preferred_translation": "لفظ غير متعلق",
         "match_mode": "contains", "source_lang": "PT", "tier": 1}]}}


def prepared(tmp_path, *, file_context=False):
    config, sdk, flow = setup(tmp_path, image=False)
    flow._gui_settings = glossary_settings()
    if file_context:
        path = tmp_path / "fictional_context.txt"
        path.write_bytes(CONTEXT.encode("utf-8"))
        config = replace(config, context_file=path, context_text="unused lower-priority text")
    else:
        config = replace(config, context_text=CONTEXT)
    return config, sdk, flow


def test_resolved_file_context_and_only_source_matched_primary_terms_reach_audit(tmp_path):
    config, sdk, flow = prepared(tmp_path, file_context=True)
    result = flow.run(config)
    assert result.success, result.error
    state = flow._last_state
    recipe = ordinary_semantic_audit_recipe(state.settings)
    assert recipe["version"] == "ordinary_semantic_audit_v2"
    assert recipe["context_sha256"] == state.context_hash == sha256_of_text(CONTEXT)
    assert CONTEXT not in json.dumps(state.settings)
    primary_prompt = sdk.requests[0]["input"][0]["content"][0]["text"]
    assert CONTEXT in primary_prompt and "unused lower-priority text" not in primary_prompt
    # The historical primary prompt still contains its capped generic glossary rows.
    assert UNRELATED in primary_prompt and PREFERRED in primary_prompt
    pack = json.loads((result.run_dir / "semantic_context.json").read_bytes())
    assert pack["context_text"] == CONTEXT
    source = json.loads((result.run_dir / "semantic_source/page_0001.json").read_bytes())
    assert source["version"] == "ordinary_semantic_source_v2"
    entries = source["applicable_terminology"]
    assert any(e["source_text"] == "arguido" and e["preferred_translation"] == PREFERRED for e in entries)
    assert all(e["source_text"] != UNRELATED for e in entries)
    assert all(source_matches_glossary_entry(source["original_source_text"], GlossaryEntry(**e)) for e in entries)
    guidance = json.loads(payload(sdk)["context_text"])
    assert guidance["resolved_user_context"] == CONTEXT
    assert guidance["page_terminology"] == [{"page_number": 1, "entries": entries}]
    assert guidance["source_fidelity_priority"] == "originals_over_context_and_terminology"
    assert "cannot override originals" in guidance["terminology_policy"]
    assert "Preserve source-compatible preferred wording" in sdk.requests[-1]["instructions"]
    assert len(sdk.requests) == 2


def test_saved_context_and_terms_freeze_resume_and_offline_rebuild(tmp_path):
    config, sdk, flow = prepared(tmp_path, file_context=True)
    result = flow.run(config)
    assert result.success
    journal = flow._dispatch_accounting.journal_path.read_bytes()
    context = (result.run_dir / "semantic_context.json").read_bytes()
    source = (result.run_dir / "semantic_source/page_0001.json").read_bytes()
    manifest = (result.run_dir / "semantic_audit/manifest.json").read_bytes()
    flow._gui_settings = {"personal_glossaries_by_lang": {"AR": []}}
    assert flow.run(replace(config, resume=True)).success
    # No source-file or current-settings dependency in a local audited rebuild.
    config.context_file.unlink()
    offline_config = replace(config, context_text="different current preference",
        glossary_file=tmp_path / "missing_current_glossary.json")
    output = TranslationWorkflow(gui_settings={}).rebuild_docx(offline_config)
    assert CORRECTED in text(output)
    assert len(sdk.requests) == 2
    assert (result.run_dir / "semantic_context.json").read_bytes() == context
    assert (result.run_dir / "semantic_source/page_0001.json").read_bytes() == source
    assert (result.run_dir / "semantic_audit/manifest.json").read_bytes() == manifest
    assert flow._dispatch_accounting is not None
    journal_path = result.run_dir / "accounting" / flow._last_state.dispatch_accounting["id"] / "dispatch_accounting.json"
    assert journal_path.read_bytes() == journal


def test_source_compatible_preferred_wording_can_remain_unchanged_in_selected_output(tmp_path):
    config, sdk, flow = prepared(tmp_path)
    preferred_primary = f"يجب على {PREFERRED} الحضور إلى المحكمة."
    sdk.correction = False
    original_create = sdk.responses.create
    def response(**request):
        result = original_create(**request)
        if "text" not in request:
            result.output_text = f"```text\n{preferred_primary}\n```"
        else:
            guidance = json.loads(json.loads(request["input"][0]["content"][0]["text"])["context_text"])
            assert any(e["preferred_translation"] == PREFERRED
                       for e in guidance["page_terminology"][0]["entries"])
        return result
    sdk.responses.create = response
    result = flow.run(config)
    assert result.success, result.error
    assert preferred_primary in text(result.output_docx)
    assert (result.run_dir / "semantic_audit/page_0001.txt").read_text(encoding="utf-8").strip() == preferred_primary
    assert payload(sdk)["pages"][0]["primary_text"].strip() == preferred_primary


def test_v2_guidance_handoff_leaves_exact_primary_request_unchanged(tmp_path, monkeypatch):
    one = tmp_path / "v1"
    two = tmp_path / "v2"
    one.mkdir()
    two.mkdir()
    config1, sdk1, flow1 = prepared(one)
    config2, sdk2, flow2 = prepared(two)
    fresh = audit.fresh_recipe
    def historical(*args, **kwargs):
        recipe = fresh(*args, **kwargs)
        recipe["version"] = "ordinary_semantic_audit_v1"
        for key in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(key)
        return recipe
    with monkeypatch.context() as old:
        old.setattr(audit, "fresh_recipe", historical)
        assert flow1.run(config1).success
    assert flow2.run(config2).success
    # The transport's remaining wall-clock timeout naturally differs between runs.
    assert {k: v for k, v in sdk1.requests[0].items() if k != "timeout"} == {
        k: v for k, v in sdk2.requests[0].items() if k != "timeout"}
    assert 0 < sdk1.requests[0]["timeout"] <= 480
    assert 0 < sdk2.requests[0]["timeout"] <= 480
    assert payload(sdk1)["context_text"] == ""
    assert json.loads(payload(sdk2)["context_text"])["resolved_user_context"] == CONTEXT


@pytest.mark.parametrize("replacement", ["changed private preference", "", None])
def test_changed_or_missing_supplied_context_refuses_resume_before_send(tmp_path, replacement):
    config, sdk, flow = prepared(tmp_path)
    assert flow.run(config).success
    journal = flow._dispatch_accounting.journal_path.read_bytes()
    with pytest.raises(ValueError, match="context mismatch") as caught:
        flow.run(replace(config, resume=True, context_text=replacement))
    assert CONTEXT not in str(caught.value)
    if replacement:
        assert replacement not in str(caught.value)
    assert len(sdk.requests) == 2
    journal_path = flow._last_paths.run_dir / "accounting" / load_run_state(flow._last_paths.run_state_path).dispatch_accounting["id"] / "dispatch_accounting.json"
    assert journal_path.read_bytes() == journal


@pytest.mark.parametrize("damage", ["missing", "invalid_json", "whitespace", "text", "recipe_hash", "context_hash"])
def test_changed_or_missing_private_context_pack_blocks_resume_and_rebuild(tmp_path, damage):
    config, sdk, flow = prepared(tmp_path)
    result = flow.run(config)
    assert result.success
    journal_path = flow._dispatch_accounting.journal_path
    journal = journal_path.read_bytes()
    path = result.run_dir / "semantic_context.json"
    if damage == "missing":
        path.unlink()
    elif damage == "invalid_json":
        path.write_bytes(b"{")
    elif damage == "whitespace":
        path.write_bytes(path.read_bytes() + b" ")
    else:
        data = json.loads(path.read_bytes())
        key = {"text": "context_text", "recipe_hash": "recipe_sha256", "context_hash": "context_sha256"}[damage]
        data[key] = "modified private evidence"
        path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(audit.SemanticIntegrationError, match="context_evidence") as caught:
        flow.run(replace(config, resume=True))
    assert "modified private evidence" not in str(caught.value)
    with pytest.raises(audit.SemanticIntegrationError, match="context_evidence"):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == 2 and journal_path.read_bytes() == journal


@pytest.mark.parametrize("damage", ["missing", "unmatched", "changed_preference"])
def test_terminology_source_binding_prevents_changed_replay(tmp_path, damage):
    config, sdk, flow = prepared(tmp_path)
    result = flow.run(config)
    assert result.success
    path = result.run_dir / "semantic_source/page_0001.json"
    data = json.loads(path.read_bytes())
    if damage == "missing":
        data.pop("applicable_terminology")
    elif damage == "unmatched":
        data["applicable_terminology"][0]["source_text"] = UNRELATED
    else:
        data["applicable_terminology"][0]["preferred_translation"] = "تفضيل آخر"
    path.write_bytes(audit._encode(data))
    # Even a re-pinned page hash cannot reinterpret an already bound engine audit.
    state = load_run_state(flow._last_paths.run_state_path)
    state.pages["1"]["semantic_source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    save_run_state_atomic(flow._last_paths.run_state_path, state)
    with pytest.raises(audit.SemanticIntegrationError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == 2


def test_historical_v1_audit_replays_exact_empty_context_without_new_pack(tmp_path, monkeypatch):
    config, sdk, flow = prepared(tmp_path)
    fresh = audit.fresh_recipe
    def historical(*args, **kwargs):
        recipe = fresh(*args, **kwargs)
        recipe["version"] = "ordinary_semantic_audit_v1"
        for key in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(key)
        return recipe
    with monkeypatch.context() as old:
        old.setattr(audit, "fresh_recipe", historical)
        result = flow.run(config)
    assert result.success and payload(sdk)["context_text"] == ""
    assert not (result.run_dir / "semantic_context.json").exists()
    source = json.loads((result.run_dir / "semantic_source/page_0001.json").read_bytes())
    assert source["version"] == "ordinary_semantic_source_v1" and "applicable_terminology" not in source
    manifest = (result.run_dir / "semantic_audit/manifest.json").read_bytes()
    assert flow.run(replace(config, resume=True)).success
    assert CORRECTED in text(TranslationWorkflow(gui_settings={}).rebuild_docx(config))
    assert len(sdk.requests) == 2
    assert (result.run_dir / "semantic_audit/manifest.json").read_bytes() == manifest
    assert ordinary_semantic_audit_recipe(flow._last_state.settings)["version"] == "ordinary_semantic_audit_v1"


@pytest.mark.parametrize("key,value", [("context_sha256", "bad"),
    ("context_binding_version", "unknown"), ("terminology_policy", "unknown"), ("context_sha256", None),
    ("source_field_policy", "unknown"), ("source_field_policy", None)])
def test_malformed_v2_context_recipe_is_not_treated_as_historical(tmp_path, key, value):
    config, sdk, flow = prepared(tmp_path)
    assert flow.run(config).success
    state = flow._last_state
    state.settings["ordinary_semantic_audit_recipe"][key] = value
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(state.settings)


def test_glossary_capture_preserves_exact_primary_prompt_and_uses_existing_cap_and_matcher():
    flow = TranslationWorkflow(client=object(), gui_settings={})
    flow._prompt_glossaries_by_lang = {"AR": [
        GlossaryEntry("p. e p. pelos artigos", "المعاقب عليه", "contains", "PT", 1),
        GlossaryEntry(UNRELATED, "لفظ غير متعلق", "contains", "PT", 1),
        *[GlossaryEntry(f"Term{i}", f"تفضيل {i}", "contains", "PT", 2) for i in range(70)]]}
    flow._enabled_glossary_tiers_by_lang = {"AR": [1, 2]}
    source = "O processo: p. e p. pelos arts. Term1 Term2 Term69"
    before = flow._append_glossary_prompt("BASE", TargetLang.AR, source_text=source)
    captured = []
    after = flow._append_glossary_prompt("BASE", TargetLang.AR, source_text=source, audit_terminology=captured)
    assert after == before
    assert captured and len(captured) <= 50
    assert all(e["source_text"] != UNRELATED for e in captured)
    assert any(e["source_text"] == "p. e p. pelos artigos" for e in captured)
    assert all(e["source_text"] in before for e in captured)


def test_genuine_pre_change_v1_request_receipt_and_manifest_replay_exactly(tmp_path):
    fixture = Path(__file__).parent / "fixtures/semantic_audit_pre_source_policy_v1"
    inputs = json.loads((fixture / "inputs.json").read_bytes())
    generation = json.loads((fixture / "generation_receipt.json").read_bytes())
    assert generation["generator_engine_sha256"] == "63fb69b524c538cf9a60d45e7cfa6dcda68761d205fe590502334a43aaf2abdd"
    for name, digest in generation["fixture_files"].items():
        assert hashlib.sha256((fixture / name).read_bytes()).hexdigest() == digest
    pages = [engine.SemanticAuditPage(**page) for page in inputs["pages"]]
    recipe = engine.SemanticAuditRecipe(**inputs["recipe"])
    current_request = engine.build_semantic_audit_request(pages, recipe, inputs["pdf_sha256"])
    assert json.loads(json.dumps(current_request)) == inputs["request"]
    assert "source_field_policy" not in json.loads(current_request["prompt_text"])
    directory = tmp_path / "old_evidence"
    shutil.copytree(fixture / "evidence", directory)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    loaded = engine.load_semantic_audit(pages=pages, recipe=recipe,
        pdf_sha256=inputs["pdf_sha256"], evidence_dir=directory)
    assert loaded.reused and loaded.binding_sha256 == generation["binding_sha256"]
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
    # A settled old response also reconstructs exactly after interrupted publication.
    (directory / "manifest.json").unlink()
    (directory / "page_0001.txt").unlink()
    recovered = engine.load_semantic_audit(pages=pages, recipe=recipe,
        pdf_sha256=inputs["pdf_sha256"], evidence_dir=directory)
    assert recovered.reused and recovered.binding_sha256 == generation["binding_sha256"]
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(engine.SemanticAuditError, match="source_binding_mismatch"):
        engine.load_semantic_audit(pages=pages,
            recipe=replace(recipe, source_field_policy="baseline_label_value_v1"),
            pdf_sha256=inputs["pdf_sha256"], evidence_dir=directory)
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}


def test_saved_source_field_policy_flows_only_to_fresh_v2_source_and_evaluators(tmp_path, monkeypatch):
    from legalpdf_translate import workflow as workflow_module
    config, sdk, flow = prepared(tmp_path)
    extraction = []
    pretokenization = []
    evaluation = []
    audit_evaluation = []
    extract = workflow_module.extract_ordered_page_text
    pretokenize = workflow_module.pretokenize_arabic_source
    evaluate = workflow_module.evaluate_workflow_output
    audit_evaluate = engine.evaluate_output
    def record_extract(*args, **kwargs):
        extraction.append(kwargs.copy())
        return extract(*args, **kwargs)
    def record_pretokenize(*args, **kwargs):
        pretokenization.append(kwargs.copy())
        return pretokenize(*args, **kwargs)
    def record_evaluate(*args, **kwargs):
        evaluation.append(kwargs.copy())
        return evaluate(*args, **kwargs)
    def record_audit_evaluate(*args, **kwargs):
        audit_evaluation.append(kwargs.copy())
        return audit_evaluate(*args, **kwargs)
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", record_extract)
    monkeypatch.setattr(workflow_module, "pretokenize_arabic_source", record_pretokenize)
    monkeypatch.setattr(workflow_module, "evaluate_workflow_output", record_evaluate)
    monkeypatch.setattr(engine, "evaluate_output", record_audit_evaluate)
    result = flow.run(config)
    assert result.success, result.error
    policy = "baseline_label_value_v1"
    assert flow._last_state.settings["ordinary_semantic_audit_recipe"]["source_field_policy"] == policy
    assert any(k.get("source_field_policy") == policy for k in extraction)
    assert pretokenization and all(k.get("source_field_policy") == policy for k in pretokenization)
    assert evaluation and all(k.get("source_field_policy") == policy for k in evaluation)
    assert audit_evaluation and all(k.get("source_field_policy") == policy for k in audit_evaluation)
    assert payload(sdk)["source_field_policy"] == policy
    source = json.loads((result.run_dir / "semantic_source/page_0001.json").read_bytes())
    assert source["source_field_policy"] == policy
    source_reads = sum(k.get("source_field_policy") == policy for k in extraction)
    counts = tuple(map(len, (pretokenization, evaluation, audit_evaluation)))
    assert flow.run(replace(config, resume=True)).success
    assert sum(k.get("source_field_policy") == policy for k in extraction) == source_reads
    assert tuple(map(len, (pretokenization, evaluation))) == counts[:2]
    # Only audit response revalidation runs; original source is pretokenized and unchanged.
    assert len(audit_evaluation) == counts[2] + 1
