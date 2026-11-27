"""Source-owned printed enclosures at the semantic raw/normalized boundary."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from legalpdf_translate import ordinary_ocr_visual_source as visual
from legalpdf_translate import primary_literal_markup as markup
from legalpdf_translate.ar_source_fields import _view
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.output_normalize import LRI, PDI, normalize_output_text
from legalpdf_translate.types import TargetLang
from tests.test_workflow_semantic_audit_integration import offline


CASE, REF, EMAIL = "304/25.3ABCD", "718662", "porto.correio@tribunal.org.pt"


def fixture():
    raw = f"Tribunal\nProcesso nº {CASE}\nReferência deste documento: {REF}\n{EMAIL}"
    effective, obligations = visual._derive(raw, [("head", [f"{CASE} [{REF}]"]), ("case", [f"Processo nº {CASE}"])])
    witness = {"obligations": obligations}
    source = pretokenize_arabic_source(effective)
    candidate = f"[[{CASE}]] [[[{REF}]]]\nالنص العربي محفوظ.\n[[{CASE}]] [[{REF}]]\n[[{EMAIL}]]"
    return source, witness, candidate


def context(monkeypatch, *, saved=True):
    source, witness, candidate = fixture()
    normalized = normalize_output_text(candidate, lang=TargetLang.AR, expected_ar_tokens=extract_locked_tokens(source))
    ctx = SimpleNamespace(recipe={visual.KEY: visual.POLICY} if saved else {},
        primary={1: normalized}, groups={1: []}, run_dir=None, state=None)
    monkeypatch.setattr(markup, "_source", lambda *a, **k: ({"source_text": source, "ocr_visual_source": witness}, "pin"))
    return ctx, source, witness, candidate


def test_source_owned_guard_view_is_invisible_and_does_not_publish_or_mutate():
    source, witness, candidate = fixture()
    before = deepcopy(witness)
    assert visual.violation(candidate, source, witness) == "ocr_visual_source_wrapper"
    prepared = visual.semantic_guard_view(candidate, source, witness)
    assert prepared != candidate
    assert prepared.replace(LRI, "").replace(PDI, "") == candidate
    assert _view(prepared)[0].splitlines()[0] == f"{CASE} [{REF}]"
    assert visual.violation(prepared, source, witness) is None
    assert witness == before
    normalized = normalize_output_text(candidate, lang=TargetLang.AR, expected_ar_tokens=extract_locked_tokens(source))
    assert _view(normalized)[0] == _view(prepared)[0]
    assert visual.semantic_guard_view(normalized, source, witness) == normalized


def test_existing_guard_uses_only_authenticated_source_and_keeps_candidate_raw(monkeypatch):
    ctx, source, witness, candidate = context(monkeypatch)
    selected = {1: candidate}
    markup.guard_candidates(ctx, selected)
    assert selected == {1: candidate}
    def changed(*a, **k):
        markup.fail("source_binding")
    monkeypatch.setattr(markup, "_source", changed)
    with pytest.raises(markup.PrimaryMarkupError, match="source_binding"):
        markup.guard_candidates(ctx, selected)


@pytest.mark.parametrize("damage", [
    "missing_pair", "duplicate_pair", "later_pair", "displaced_header", "wrong_ref", "wrong_case",
    "lost_case", "lost_ref", "extra_case", "extra_ref", "half", "nested", "other_malformed",
    "ambient_isolate", "wrong_shape", "wrong_visible_punctuation",
])
def test_wrong_occurrences_or_printed_enclosures_remain_rejected(monkeypatch, damage):
    ctx, source, witness, candidate = context(monkeypatch)
    header, *rest = candidate.splitlines()
    changes = {
        "missing_pair": candidate.replace(f"[[[{REF}]]]", f"[[{REF}]]", 1),
        "duplicate_pair": candidate.replace(f"[[{CASE}]] [[{REF}]]", header),
        "later_pair": candidate.replace(header, f"[[{CASE}]] [[{REF}]]", 1).replace(
            f"[[{CASE}]] [[{REF}]]\n[[{EMAIL}]]", header+f"\n[[{EMAIL}]]"),
        "displaced_header": "عنوان\n"+candidate,
        "wrong_ref": candidate.replace(f"[[[{REF}]]]", "[[[718663]]]"),
        "wrong_case": candidate.replace(CASE, "304/25.3ABCE", 1),
        "lost_case": candidate.replace(f"[[{CASE}]] [[{REF}]]", f"[[{REF}]]"),
        "lost_ref": candidate.replace(f"[[{CASE}]] [[{REF}]]", f"[[{CASE}]]"),
        "extra_case": candidate+f"\n[[{CASE}]]",
        "extra_ref": candidate+f"\n[[{REF}]]",
        "half": candidate.replace(f"[[[{REF}]]]", f"[[[{REF}]]"),
        "nested": candidate.replace(f"[[[{REF}]]]", f"[[[[{REF}]]]]"),
        "other_malformed": candidate+"\n[[[99999]]]",
        "ambient_isolate": LRI+candidate+PDI,
        "wrong_shape": candidate.replace(f"[[[{REF}]]]", f"([[{REF}]])"),
        "wrong_visible_punctuation": candidate.replace(f"[[[{REF}]]]", f"[[[{REF}]]]."),
    }
    altered = changes[damage]
    with pytest.raises(markup.PrimaryMarkupError):
        markup.guard_candidates(ctx, {1: altered})


@pytest.mark.parametrize("binding", ["none", "bare", "multiple", "foreign", "late_source", "oversized"])
def test_unproven_or_unbounded_input_is_exact_noop(binding):
    source, witness, candidate = fixture()
    if binding == "none": witness = None
    elif binding == "bare": witness["obligations"]["headers"] = []
    elif binding == "multiple": witness["obligations"]["headers"] *= 2
    elif binding == "foreign": witness["obligations"]["headers"] = [[CASE, "718663"]]
    elif binding == "late_source": source = "Outro título\n"+source
    else: candidate += "ا"*(2*visual.MAX_CHARS)
    assert visual.semantic_guard_view(candidate, source, witness) == candidate


def test_old_saved_scope_never_consults_new_guard(monkeypatch):
    ctx, _, _, candidate = context(monkeypatch, saved=False)
    monkeypatch.setattr(visual, "semantic_guard_view", lambda *a: pytest.fail("historical scope consulted new view"))
    markup.guard_candidates(ctx, {1: candidate})


def test_semantic_typed_failure_reaches_normal_workflow_status(tmp_path, monkeypatch):
    from tests.test_semantic_review_model_integration import setup
    config, http, flow = setup(tmp_path)
    def fail_closed(*args, **kwargs):
        markup.fail("ocr_visual_source_header")
    monkeypatch.setattr(markup, "guard_correction", fail_closed)
    result = flow.run(config)
    assert not result.success
    assert result.error == "semantic_audit_primary_markup_ocr_visual_source_header"
    assert len(http.requests) == 3
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
