"""A rejected permutation can use one replacement; final identity stays strict."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate import ordinary_semantic_enclosure_sequence_repair as admission
from legalpdf_translate import ordinary_semantic_enclosure_authority as enclosure
from legalpdf_translate import ordinary_semantic_enclosure_identity as identity
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from tests.test_ordinary_semantic_audit import token
from tests.test_source_enclosure_authority import prepared, sample
from tests.test_source_literal_authority import INVENTORY, RECIPE, correction


def case():
    primary = replace(sample(), primary_text=sample().primary_text + " " + token("AX17") + " " + token("BY29"))
    pages, registry, raw, _, _, cert, _ = prepared(primary)
    context = enclosure.project(pages, registry, cert, identity_policy=identity.POLICY)
    text = json.loads(raw)["pages"][0]["corrected_text"]
    text = text.replace(token("AX17") + " " + token("BY29"), token("BY29") + " " + token("AX17"))
    return pages, registry, cert, context, text


def admit(args, text=None):
    pages, registry, cert, context, proposed = args
    return admission.check_eligibility(correction(pages, [proposed if text is None else text]),
        pages, INVENTORY, RECIPE, registry, cert, context, identity_policy=identity.POLICY)


def test_permission_admits_only_dispatch_and_never_accepts_reordered_candidate():
    args = case()
    pages, registry, cert, context, text = args
    before = deepcopy(args)
    assert admit(args) is None
    assert admit(args, text + " " + token("NEWLABEL")) is None
    with pytest.raises(review.SemanticAuditError, match="final_sequence_mismatch"):
        enclosure.validate(correction(pages, [text]), pages, INVENTORY, RECIPE, context,
            identity_policy=identity.POLICY)
    with pytest.raises(review.SemanticAuditError, match="initial_sequence_replacement_ineligible"):
        enclosure.check_initial_sequence_replacement_eligibility(correction(pages, [text]),
            pages, INVENTORY, registry, cert, context, identity_policy=identity.POLICY)
    assert enclosure.validate(correction(pages, [context.projected_pages[0].primary_text]),
        pages, INVENTORY, RECIPE, context, identity_policy=identity.POLICY)[0]
    assert args == before


def test_absent_descriptor_and_optional_python_none_remain_historical():
    assert repair.descriptor(repair.POLICY_V4) == repair.descriptor(repair.POLICY_V4,
        semantic_enclosure_sequence_repair_policy=None)
    descriptor = repair.descriptor(repair.POLICY_V4, source_enclosure_identity_policy=identity.POLICY,
        semantic_enclosure_sequence_repair_policy=admission.POLICY)
    assert descriptor[admission.KEY] == admission.descriptor()
    assert admission.KEY not in repair.descriptor(repair.POLICY_V4)


def test_fresh_saved_permission_roundtrips_and_rejects_explicit_null(tmp_path):
    from legalpdf_translate import workflow_semantic_audit as glue, ordinary_auto_layout as auto
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError, sha256_of_text
    from tests.test_semantic_review_model_integration import setup
    config, _, _ = setup(tmp_path)
    saved = glue.fresh_recipe(config, "gpt-5.2", auto.frozen_automatic_layout_policy(),
        context_text=config.context_text, context_hash=sha256_of_text(config.context_text))
    settings = {"ordinary_semantic_audit_recipe": saved, "image_mode": config.image_mode.value,
        "ocr_engine": config.ocr_engine.value, "ocr_api_provider": config.ocr_api_provider.value,
        "ordinary_auto_layout_policy": saved["ordinary_auto_layout_policy"],
        "strip_bidi_controls": config.strip_bidi_controls,
        "primary_assembly_recipe": {"version": "terminal_source_bound_folio_v4",
            "ordinary_auto_layout_policy": saved["ordinary_auto_layout_policy"]}}
    assert saved[admission.KEY] == admission.POLICY
    assert ordinary_semantic_audit_recipe(settings) == saved
    saved[admission.KEY] = None
    with pytest.raises(SemanticAuditRecipeError, match="enclosure_sequence_repair"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("damage", ["drop", "duplicate", "substitute", "ordered", "control",
    "malformed", "page_limit", "value_limit", "addition_control", "new_only"])
def test_only_complete_old_multiset_permutation_can_admit(damage):
    args = case()
    text = args[-1]
    if damage == "drop": text = text.replace(token("AX17"), "")
    elif damage == "duplicate": text += " " + token("AX17")
    elif damage == "substitute": text = text.replace(token("AX17"), token("CHANGED"))
    elif damage == "ordered": text = args[3].projected_pages[0].primary_text
    elif damage == "control": text += "\u202e"
    elif damage == "malformed": text += " [[broken[[x]]]]"
    elif damage == "page_limit": text += " " + " ".join(token("N" + str(i)) for i in range(9))
    elif damage == "value_limit": text += " " + token("N" * 513)
    elif damage == "addition_control": text += " " + token("NEW\u200eLABEL")
    else: text = "النص " + token("NEWLABEL")
    with pytest.raises(review.SemanticAuditError):
        admit(args, text)


@pytest.mark.parametrize("damage", ["context_page_float", "context_bool", "context_primary", "certificate_page_float",
    "certificate_empty", "certificate_literal", "registry", "identity"])
def test_canonical_context_certificate_and_dependencies_are_not_equivalent_python_values(damage):
    args = list(deepcopy(case()))
    if damage == "context_page_float": args[3].evidence["pages"][0]["page"] = 1.0
    elif damage == "context_bool": args[3].evidence["pages"][0]["page"] = True
    elif damage == "context_primary": args[3] = replace(args[3], projected_pages=(replace(args[0][0], primary_text="changed"),))
    elif damage == "certificate_page_float": args[2]["enclosure_lookups"][0]["page"] = 1.0
    elif damage == "certificate_empty": args[2]["enclosure_observations"] = []
    elif damage == "certificate_literal": args[2]["literal_certificate"] = {}
    elif damage == "registry": args[1]["pages"][0]["primary_sha256"] = "0" * 64
    else:
        with pytest.raises(review.SemanticAuditError, match="dependency"):
            admission.check_eligibility(correction(args[0], [args[-1]]), args[0], INVENTORY,
                RECIPE, args[1], args[2], args[3])
        return
    with pytest.raises((review.SemanticAuditError, ValueError)):
        admit(args)


def test_work_and_token_bounds_refuse_before_new_classification(monkeypatch):
    args = case()
    def forbidden(*a, **k): pytest.fail("classification ran before bound refusal")
    monkeypatch.setattr(enclosure, "classify", forbidden)
    with pytest.raises(review.SemanticAuditError, match="page_bound"):
        admit(args, args[-1] + " " + " ".join(token("N" + str(i)) for i in range(9)))
    monkeypatch.setattr(identity, "MAX_WORK", 1)
    with pytest.raises(review.SemanticAuditError, match="work_bound"):
        admit(args)


@pytest.mark.parametrize("value", [False, True, "", "unknown", [], {}])
def test_unknown_policy_fails_before_any_engine_work(tmp_path, value):
    with pytest.raises(review.SemanticAuditError, match="enclosure_sequence_repair_policy"):
        repair.run_semantic_repair(pages=[], recipe=RECIPE, pdf_sha256="a" * 64,
            evidence_dir=tmp_path / "audit", semantic_enclosure_sequence_repair_policy=value)
    assert not (tmp_path / "audit").exists()


@pytest.mark.parametrize("missing", ["semantic_repair_policy", "semantic_enclosure_authority_policy", "source_enclosure_identity_policy"])
def test_new_saved_permission_requires_each_existing_dependency(tmp_path, missing):
    from legalpdf_translate import workflow_semantic_audit as glue, ordinary_auto_layout as auto
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError, sha256_of_text
    from tests.test_semantic_review_model_integration import setup
    config, http, _ = setup(tmp_path)
    saved = glue.fresh_recipe(config, "gpt-5.2", auto.frozen_automatic_layout_policy(),
        context_text=config.context_text, context_hash=sha256_of_text(config.context_text))
    settings = {"ordinary_semantic_audit_recipe": saved, "image_mode": config.image_mode.value,
        "ocr_engine": config.ocr_engine.value, "ocr_api_provider": config.ocr_api_provider.value,
        "ordinary_auto_layout_policy": saved["ordinary_auto_layout_policy"],
        "strip_bidi_controls": config.strip_bidi_controls,
        "primary_assembly_recipe": {"version": "terminal_source_bound_folio_v4",
            "ordinary_auto_layout_policy": saved["ordinary_auto_layout_policy"]}}
    assert ordinary_semantic_audit_recipe(settings) == saved
    saved.pop(missing)
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)
    assert http.requests == []


@pytest.mark.parametrize("missing", ["semantic_repair_policy", "semantic_enclosure_authority_policy", "source_enclosure_identity_policy"])
def test_direct_engine_dependency_refusal_precedes_prepare_or_client(tmp_path, missing):
    options = {"semantic_repair_policy": repair.POLICY_V4,
        "semantic_literal_authority_policy": "source_literal_authority_v1",
        "semantic_enclosure_authority_policy": "source_enclosure_authority_v1",
        "source_enclosure_identity_policy": identity.POLICY,
        admission.KEY: admission.POLICY}
    options[missing] = None
    with pytest.raises(review.SemanticAuditError, match="repair_policy_or_accounting"):
        repair.run_semantic_repair(pages=[], recipe=RECIPE, pdf_sha256="a" * 64,
            evidence_dir=tmp_path / "audit", **options)
    assert not (tmp_path / "audit").exists()


def test_page_ownership_cannot_be_satisfied_by_document_wide_counts():
    primary = replace(sample(), primary_text=sample().primary_text + " " + token("AX17") + " " + token("BY29"))
    second = replace(sample(1), page_number=2)
    pages, registry, raw, _, _, cert, _ = prepared(primary, extra_pages=(second,))
    context = enclosure.project(pages, registry, cert, identity_policy=identity.POLICY)
    data = json.loads(raw)
    texts = [r["corrected_text"] for r in data["pages"]]
    texts[0] = texts[0].replace(token("AX17") + " " + token("BY29"), token("BY29"))
    texts[1] += " " + token("AX17")
    with pytest.raises(review.SemanticAuditError, match="old_multiset"):
        admission.check_eligibility(correction(pages, texts), pages, INVENTORY, RECIPE,
            registry, cert, context, identity_policy=identity.POLICY)


class PermutationScenario:
    def __init__(self, *, repeat_order=False, wrong_pair=False):
        from tests.test_source_enclosure_authority_workflow import EnclosureScenario
        self.base = EnclosureScenario()
        self.payloads = self.base.payloads
        self.repeat_order, self.wrong_pair = repeat_order, wrong_pair

    def __call__(self, body, data):
        data = self.base(body, data)
        field = data["output"][0]["content"][0]
        if "text" not in body:
            field["text"] = field["text"].replace("\n```", " " + token("AX17") + " " + token("BY29") + "\n```")
        else:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == "correction":
                value = json.loads(field["text"])
                replacement = "source_literal_certificate" in payload
                for row in value["pages"]:
                    a, b = ("AX17", "BY29") if replacement and not self.repeat_order else ("BY29", "AX17")
                    row["corrected_text"] += " " + token(a) + " " + token(b) + " " + token("NEWLABEL")
                    if replacement and self.wrong_pair:
                        from tests.test_source_enclosure_authority import VALUE
                        row["corrected_text"] = row["corrected_text"].replace("[" + token(VALUE) + "]", token(VALUE), 1)
                field["text"] = json.dumps(value, ensure_ascii=False)
        return data


@pytest.mark.parametrize("damage", [None, "order", "pair"])
def test_fresh_normal_workflow_single_replacement_blind_final_and_saved_replay(tmp_path, monkeypatch, damage):
    from pathlib import Path
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_semantic_review_model_integration import immutable
    from tests.test_source_enclosure_authority_workflow import start
    scenario = PermutationScenario(repeat_order=damage == "order", wrong_pair=damage == "pair")
    config, http, flow = start(tmp_path, scenario)
    config = replace(config, keep_intermediates=False)
    result = flow.run(config)
    expected = damage is None
    assert result.success is expected, result.error
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved[admission.KEY] == admission.POLICY
    stages = [p["stage"] for p in scenario.payloads]
    assert stages.count("source_literal_authority") == 1 and stages.count("correction") == 2
    assert stages.count("verification") == int(expected)
    audit = result.run_dir / "semantic_audit"
    if expected:
        manifest = json.loads((audit / "manifest.json").read_bytes())
        assert manifest["consumed_cycles"] == 1 and manifest["repair_trigger"] == "source_literal_authority"
        assert manifest["binding"]["semantic_repair_policy"][admission.KEY] == admission.descriptor()
        final = scenario.payloads[-1]
        assert final["stage"] == "verification"
        assert not set(final) & {"source_literal_certificate", "rejected_proposal", admission.KEY, "prior_findings"}
        before = immutable(result.run_dir)
        assert not list((result.run_dir / "pages").glob("*.txt"))
        assert flow.run(replace(config, resume=True)).success
        resumed = TranslationWorkflow(client=http.client, gui_settings={})
        assert resumed.run(replace(config, resume=True)).success
        assert resumed.rebuild_docx(config).is_file()
        assert len(http.requests) == 6 and immutable(result.run_dir) == before
        owner = __import__("os").environ.get("ENCLOSURE_SPECIMEN_INDEX")
        if owner:
            Path(owner).write_text(json.dumps({"run_dir": str(result.run_dir), "config": __import__("dataclasses").asdict(config),
                "saved_recipe": saved, "requests": http.requests}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    else:
        assert not (audit / "manifest.json").exists()
        before = immutable(result.run_dir)
        assert not flow.run(replace(config, resume=True)).success
        assert len(http.requests) == 5 and immutable(result.run_dir) == before


@pytest.mark.parametrize("damage", ["removed", "changed"])
def test_saved_new_permission_cannot_be_downgraded_on_pruned_replay(tmp_path, damage):
    from legalpdf_translate.checkpoint import save_run_state_atomic
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_source_enclosure_authority_workflow import start
    scenario = PermutationScenario()
    config, http, flow = start(tmp_path, scenario)
    config = replace(config, keep_intermediates=False)
    result = flow.run(config)
    assert result.success, result.error
    assert not list((result.run_dir / "pages").glob("*.txt"))
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    if damage == "removed": saved.pop(admission.KEY)
    else: saved[admission.KEY] = "unknown"
    save_run_state_atomic(flow._last_paths.run_state_path, flow._last_state)
    code = "primary_markup_source_binding" if damage == "removed" else "semantic_audit_invalid_enclosure_sequence_repair_policy"
    with pytest.raises(ValueError, match=code):
        flow.run(replace(config, resume=True))
    with pytest.raises(ValueError, match=code):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(http.requests) == 6
