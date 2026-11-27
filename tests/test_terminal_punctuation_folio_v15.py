"""Fictional immutable suffix ownership, exact inverse and saved V15 rendering."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_labeled_folio_direction as v1
from legalpdf_translate import ordinary_labeled_folio_direction_v2 as v2
from legalpdf_translate import ordinary_layout_contracts as contracts
from legalpdf_translate import ordinary_layout_reproposal as attempts
from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests import test_labeled_folio_direction_v14 as base
from tests import test_ordinary_layout_reproposal as lifecycle
from tests import test_ordinary_source_layout as layout_fixture

W = model.W
BASE_PARAGRAPH = base.paragraph


@pytest.fixture(autouse=True)
def isolate_provider(monkeypatch):
    lifecycle.isolate_provider(monkeypatch)


def paragraph(*args, suffix=(".",), suffix_rtl=None, **kwargs):
    node, row = BASE_PARAGRAPH(*args, **kwargs)
    if suffix is None: return node, row
    runs = node.findall(W + "r")
    terminal = runs[-1] if row["has_page_break"] else None
    for value, rtl in zip(suffix, suffix_rtl or ("1",) * len(suffix)):
        run = etree.Element(W + "r")
        etree.SubElement(etree.SubElement(run, W + "rPr"), W + "rtl").set(W + "val", rtl)
        etree.SubElement(run, W + "t").text = value
        if terminal is None: node.append(run)
        else: node.insert(node.index(terminal), run)
    text = "".join(n.text or "" for n in node.iter(W + "t"))
    row["text"] = text + ("\f" if row["has_page_break"] else "")
    row["tokens"] = [{"kind": "t", "text": text}] + ([{"kind": "page_break", "text": "\f"}] if row["has_page_break"] else [])
    return node, row


def layout_case(monkeypatch, *, promoted=True, suffix=(".",)):
    def shaped(*args, **kwargs): return paragraph(*args, suffix=suffix, **kwargs)
    monkeypatch.setattr(base, "paragraph", shaped)
    args = base.layout_case(monkeypatch, promoted=promoted)
    args[4][v2.KEY] = v2.VERSION
    return args


@pytest.mark.parametrize("label,separator,numbers,bare,suffix,flags", [
    ("الصفحة", (" ", "\u200e/\u200e", " "), ("1", "2"), False, (".",), ("1",)),
    ("صفحة", (" / ",), ("٢", "٧"), False, (" ", ".", " "), ("0", "1", "0")),
    ("ص.", ("/",), ("۳", "۷"), True, (" . ",), ("0",)),
    ("ص.", (" ", "/", " "), ("1234", "5678"), False, (".", "  "), ("1", "0"))])
@pytest.mark.parametrize("terminal", [False, True])
def test_complete_suffix_never_changes_while_bridge_flags_invert(label, separator, numbers, bare, suffix, flags, terminal):
    before, row = paragraph(label, *numbers, separator=separator, bare=bare, suffix=suffix, suffix_rtl=flags, terminal=terminal)
    after = base.after_break(before); original = deepcopy(after)
    result = v2.derive(after, before, row)
    assert result and result["terminal_suffix"]
    suffix_record = result["terminal_suffix"]
    assert row["text"][suffix_record["start"]:suffix_record["end"]] == "".join(suffix)
    assert suffix_record["literal_sha256"] == model._sha("".join(suffix).encode())
    assert [r["original_rtl"] for r in suffix_record["runs"]] == list(map(int, flags))
    v2.apply(after, result)
    for r in suffix_record["runs"]:
        assert after.findall(W + "r")[r["run_index"]].find(W + "rPr/" + W + "rtl").get(W + "val") == str(r["original_rtl"])
    assert model._c14n(v2.verified_copy(after, original, result)) == model._c14n(original)


def test_exact_v1_proof_is_delegated_with_explicit_null_suffix():
    before, row = paragraph(suffix=None)
    node = base.after_break(before)
    original = v1.derive(node, before, row)
    assert original and v2.derive(node, before, row) == {**original, "terminal_suffix": None}


@pytest.mark.parametrize("fault", ["repeated", "comma", "arabic_period", "unicode_space", "newline", "control",
    "digit", "prose", "shared_denominator", "empty", "missing_RTL", "duplicate_RTL", "hidden", "all_zero"])
def test_suffix_never_grants_permission_to_unknown_or_partial_owners(fault):
    suffix = {"repeated": ("..",), "comma": (",",), "arabic_period": ("۔",), "unicode_space": (".\u00a0",),
        "newline": (".\n",), "control": (".\u200e",), "digit": (".5",), "prose": (". extra",)}.get(fault, (".",))
    kwargs = {"directions": ["1", "0", "0", "0"]} if fault == "all_zero" else {}
    node, row = paragraph(suffix=suffix, **kwargs)
    runs = node.findall(W + "r"); tail = runs[-2]
    if fault == "shared_denominator":
        runs[-3].find(W + "t").text += tail.find(W + "t").text; node.remove(tail)
    elif fault == "empty": node.insert(node.index(tail), etree.Element(W + "r"))
    elif fault == "missing_RTL": tail.find(W + "rPr").remove(tail.find(W + "rPr/" + W + "rtl"))
    elif fault == "duplicate_RTL": etree.SubElement(tail.find(W + "rPr"), W + "rtl").set(W + "val", "1")
    elif fault == "hidden": etree.SubElement(tail.find(W + "rPr"), W + "vanish")
    assert v2.span(node, row) is None


@pytest.mark.parametrize("count,allowed", [(32, True), (33, False)])
def test_total_run_preflight_includes_suffix_before_clone_or_inventory(monkeypatch, count, allowed):
    node, row = paragraph(separator=(" ",) * (count - 6) + (" / ",))
    assert len(node.findall(W + "r")) == count
    copies, inventories = [], []
    clone, inventory = v2.deepcopy, source._inline_folio_run_inventory
    def copying(*args): copies.append(True); return clone(*args)
    def inspect(*args): inventories.append(True); return inventory(*args)
    monkeypatch.setattr(v2, "deepcopy", copying); monkeypatch.setattr(source, "_inline_folio_run_inventory", inspect)
    assert bool(v2.span(node, row)) == allowed
    assert bool(copies) == bool(inventories) == allowed


@pytest.mark.parametrize("length,terminal,allowed", [(80, True, True), (81, True, False), (80, False, True), (81, False, False)])
def test_whole_text_eligibility_and_conservative_owned_FF_prework_bound(monkeypatch, length, terminal, allowed):
    node, row = paragraph(caption_spaces=length - 12, terminal=terminal)
    assert len(row["text"]) - int(terminal) == length
    copies, inventories = [], []
    clone, inventory = v2.deepcopy, source._inline_folio_run_inventory
    def copying(*args): copies.append(True); return clone(*args)
    def inspect(*args): inventories.append(True); return inventory(*args)
    monkeypatch.setattr(v2, "deepcopy", copying); monkeypatch.setattr(source, "_inline_folio_run_inventory", inspect)
    assert bool(v2.span(node, row)) == allowed
    if length == 81 and terminal: assert not copies and not inventories
    if length == 81 and not terminal: assert len(copies) == 1 and len(inventories) == 2


@pytest.mark.parametrize("promoted", [False, True])
def test_public_strict_writer_both_scopes_preserve_suffix_and_complete_XML(monkeypatch, promoted):
    args = layout_case(monkeypatch, promoted=promoted)
    old_context = deepcopy(args[4]); old_context[v1.KEY] = v1.VERSION
    old = writer.build_unreviewed_docx(*args[:4], ordinary_context=old_context)
    current = layout_fixture.build(args); layout_fixture.verify(current, args)
    records = current.source_map["source_layout_plan"][v2.LEDGER]
    assert len(records) == (2 if promoted else 1)
    assert {r["scope"] for r in records} == ({"promoted_footer"} if promoted else {"retained_body"})
    assert all(r["terminal_suffix"] for r in records)
    with ZipFile(BytesIO(old.docx_bytes)) as a, ZipFile(BytesIO(current.docx_bytes)) as b:
        assert [p for p in a.namelist() if a.read(p) != b.read(p)] == ["word/document.xml"]
        x, y = etree.fromstring(a.read("word/document.xml")), etree.fromstring(b.read("word/document.xml"))
        assert [(n.tag, n.text, n.tail) for n in x.iter()] == [(n.tag, n.text, n.tail) for n in y.iter()]
        assert len(list(x.iter(W + "br"))) == len(list(y.iter(W + "br")))


@pytest.mark.parametrize("fault", ["missing", "null", "float_start", "bool_end", "float_RTL", "bool_index",
    "hash", "duplicate_run", "offset", "extra_key", "old_version", "collision"])
def test_hash_consistent_suffix_claims_fail_public_strict_validation(monkeypatch, fault):
    args = layout_case(monkeypatch)
    artifact = layout_fixture.build(args); mapping = deepcopy(artifact.source_map)
    plan = mapping["source_layout_plan"]; record = plan[v2.LEDGER][0]; suffix = record["terminal_suffix"]
    if fault == "missing": record.pop("terminal_suffix")
    elif fault == "null": record["terminal_suffix"] = None
    elif fault == "float_start": suffix["start"] = float(suffix["start"])
    elif fault == "bool_end": suffix["end"] = True
    elif fault == "float_RTL": suffix["runs"][0]["original_rtl"] = float(suffix["runs"][0]["original_rtl"])
    elif fault == "bool_index": suffix["runs"][0]["run_index"] = True
    elif fault == "hash": suffix["literal_sha256"] = "0" * 64
    elif fault == "duplicate_run": suffix["runs"].append(deepcopy(suffix["runs"][0]))
    elif fault == "offset": suffix["runs"][0]["end"] -= 1
    elif fault == "extra_key": suffix["unexpected"] = True
    elif fault == "old_version": plan[v2.KEY] = v1.VERSION
    else: plan["clock_ltr_spans"] = [{"paragraph_id": record["paragraph_id"]}]
    mapping["source_layout_plan_sha256"] = model._sha(model._canonical(plan))
    with pytest.raises(ValueError): layout_fixture.verify(writer.SavedDocxLayoutArtifact(artifact.docx_bytes, mapping), args)


def test_independent_inverse_rejects_an_unlisted_suffix_property_change():
    before, row = paragraph(); node = base.after_break(before); baseline = deepcopy(node)
    record = v2.derive(node, before, row); v2.apply(node, record)
    suffix_run = record["terminal_suffix"]["runs"][0]["run_index"]
    node.findall(W + "r")[suffix_run].find(W + "rPr/" + W + "rtl").set(W + "val", "0")
    with pytest.raises(ValueError): v2.verified_copy(node, baseline, record)


@pytest.fixture(scope="module")
def v15_start(tmp_path_factory):
    patch = pytest.MonkeyPatch(); lifecycle.isolate_provider(patch)
    case = lifecycle.normal_start(tmp_path_factory.mktemp("v15_start"), patch,
        damage=lambda p, n, proposal, *_: lifecycle.invalid_decision(proposal) if p == 2 and n == 0 else None,
        saved_policy=auto._terminal_punctuation_folio_v15_policy())
    yield case
    patch.undo()


def test_genuine_normal_start_binds_V2_and_reuses_exact_candidate(v15_start):
    case = v15_start
    assert auto._terminal_punctuation_folio_v15_policy() == "source_image_unreviewed_v1:f04fe5fa2d6c03c3552819679455442552261a03a4978ed14bec33cbf35bb769"
    result = case.job["result"]["automatic_layout"]
    assert result["status"] == "automatic_unreviewed", result
    assert [p for p, _ in case.calls] == [1, 2, 2, 3]
    witness, context = lifecycle.witness_context(case)
    assert len(attempts.verify_witness(witness, **context)[0]) == 3
    mapping = contracts.decode((Path(result["output_path"]).parent / "source_map.json").read_bytes())
    assert mapping["source_layout_plan"][v2.KEY] == v2.VERSION and mapping["source_layout_plan"][v2.LEDGER] == []
    reused = auto.run_completed_unreviewed_rebuild(case.manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert reused["reused_durable_candidate"] and reused["sha256"] == result["sha256"] and len(case.calls) == 4


def test_saved_V14_registries_and_first_retry_requests_are_exact_under_V15():
    old_policy = auto._labeled_folio_direction_v14_policy()
    assert old_policy == "source_image_unreviewed_v1:f8a091d4e79093cb6c77ebacb07f1fa3392424e9b4088e5e6774991e0de46b49"
    assert old_policy in auto._metadata_normalization_policies() and old_policy in auto._source_folio_policies()
    assert auto._source_normalization_version(old_policy.split(":", 1)[1]) == contracts.OPTIONAL_HINT_NORMALIZATION_V3
    _, view, proposal, _ = lifecycle.synthetic()
    old = attempts.expected_policy(1, attempts.POLICY_V2, old_policy.split(":", 1)[1])
    new = attempts.expected_policy(1, attempts.POLICY_V2, auto._terminal_punctuation_folio_v15_policy().split(":", 1)[1])
    assert attempts.automatic_policy(attempts.POLICY_V2) == auto._per_page_reproposal_v12_policy()
    assert attempts.page_request(view, 1, old) == attempts.page_request(view, 1, new)
    for code in attempts.ELIGIBLE:
        prior = {"intent": {"request_sha256": "1" * 64}, "raw": contracts.encode(proposal).decode(), "validation": {"error_code": code}}
        assert attempts.page_request(view, 1, old, prior=prior) == attempts.page_request(view, 1, new, prior=prior)
