"""Exact saved role and genuine prechange requests/catalog without provider calls."""
from pathlib import Path
import json
import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy
from legalpdf_translate import ordinary_semantic_review as engine
from legalpdf_translate import semantic_review_model_policy as policy
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
from legalpdf_translate.accounting_policy import ordinary_accounting_policy
from tests.test_workflow_semantic_review_integration import saved_recipe
from tests.test_ordinary_semantic_review import Client as Legacy
from tests.test_ordinary_semantic_unit_refs import Client


def test_fresh_role_keeps_primary_model_and_effective_review_model(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    assert recipe[policy.KEY] == {"version": policy.VERSION, "model": "gpt-6-astra"}
    assert recipe["model"] == "gpt-5.2" and policy.effective_model(recipe) == "gpt-6-astra"
    assert ordinary_semantic_audit_recipe(settings) == recipe
    recipe.pop(policy.KEY)
    assert policy.effective_model(recipe) == "gpt-5.2" and policy.identity_fields(recipe) == {}
    assert policy.KEY not in ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("value", [None, "gpt-6-astra", {}, {"version": policy.VERSION},
    {"version": policy.VERSION, "model": "gpt-5.2"}, {"version": "unknown", "model": "gpt-6-astra"},
    {"version": policy.VERSION, "model": "gpt-6-astra", "tier": "default"}])
def test_invalid_saved_role_cannot_fall_back(tmp_path, value):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe[policy.KEY] = value
    with pytest.raises(SemanticAuditRecipeError, match="semantic_review_model_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("case", ["legacy_absent", "compact32", "compact64_source_v1", "complete_pages_v1"])
def test_genuine_bca_requests_artifacts_fingerprint_and_local_replay_exact(tmp_path, case):
    fixture = json.loads((Path(__file__).parent / "fixtures/semantic_model_prechange_bca.json").read_bytes())
    assert ordinary_accounting_policy().accounting_arguments() == fixture["ordinary_accounting_arguments"]
    entry = fixture["cases"][case]
    pages = tuple(engine.SemanticAuditPage(**p) for p in entry["pages"])
    recipe = engine.SemanticAuditRecipe(**entry["recipe"])
    client = Legacy() if case == "legacy_absent" else Client(); client.model = recipe.model
    args = dict(pages=pages, recipe=recipe, pdf_sha256=entry["pdf_sha256"], evidence_dir=tmp_path / "audit", **entry["options"])
    engine.run_semantic_review(**args, client=client)
    assert engine.audit._json(client.requests) == engine.audit._json(entry["requests"])
    before = {p.relative_to(args["evidence_dir"]).as_posix(): p.read_bytes() for p in args["evidence_dir"].rglob("*") if p.is_file()}
    assert before == {name: data.encode() for name, data in entry["evidence"].items()}
    assert engine.semantic_review_source_fingerprint(pages, recipe, entry["pdf_sha256"], **entry["options"]) == entry["fingerprint"]
    assert engine.load_semantic_review(**args).reused and len(client.requests) == 3
    assert {p.relative_to(args["evidence_dir"]).as_posix():p.read_bytes() for p in args["evidence_dir"].rglob("*") if p.is_file()} == before
