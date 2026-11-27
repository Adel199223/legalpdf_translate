"""Fictional complete fractions, source ownership, strict inverse and saved render identity."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_folio_bridges_v4 as inherited
from legalpdf_translate import ordinary_in_flow_folio_bridges as flow
from legalpdf_translate import ordinary_labeled_folio_direction as labeled
from legalpdf_translate import ordinary_layout_contracts as contracts
from legalpdf_translate import ordinary_layout_reproposal as attempts
from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests import test_ordinary_layout_reproposal as lifecycle
from tests import test_ordinary_source_layout as layout_fixture

W, LRM = model.W, "\u200e"


@pytest.fixture(autouse=True)
def isolate_provider(monkeypatch):
    lifecycle.isolate_provider(monkeypatch)


def paragraph(label="ص.", numerator="1", denominator="2", *, separator=(" / ",), bare=False,
              terminal=True, directions=None, caption_spaces=1):
    p = etree.Element(W + "p", nsmap={"w": W[1:-1]})
    etree.SubElement(etree.SubElement(p, W + "pPr"), W + "bidi").set(W + "val", "1")
    number = lambda value: value if bare else LRM + value + LRM
    values = [label + " " * caption_spaces, number(numerator), *separator, number(denominator)]
    flags = directions or ["1", "0", *["0" if s == LRM + "/" + LRM else "1" for s in separator], "0"]
    assert len(flags) == len(values)
    for text, rtl in zip(values, flags):
        r = etree.SubElement(p, W + "r")
        etree.SubElement(etree.SubElement(r, W + "rPr"), W + "rtl").set(W + "val", rtl)
        etree.SubElement(r, W + "t").text = text
    if terminal:
        etree.SubElement(etree.SubElement(p, W + "r"), W + "br").set(W + "type", "page")
    text = "".join(values)
    row = {"id": "p000001", "text": text + ("\f" if terminal else ""),
        "tokens": [{"kind": "t", "text": text}] + ([{"kind": "page_break", "text": "\f"}] if terminal else []),
        "has_field": False, "has_numbering": False, "has_page_break": terminal, "ppr_xml": ""}
    return p, row


def after_break(node):
    result = deepcopy(node)
    for br in list(result.iter(W + "br")): br.getparent().remove(br)
    return result


@pytest.mark.parametrize("label,separator,bare", [
    ("ص.", (" / ",), False), ("صفحة", (" ", "/", " "), True),
    ("الصفحة", ("/",), False), ("ص.", (" ", LRM + "/" + LRM, " "), False)])
@pytest.mark.parametrize("terminal", [False, True])
def test_whole_separator_flags_only_with_exact_inverse(label, separator, bare, terminal):
    before, row = paragraph(label, separator=separator, bare=bare, terminal=terminal)
    node = after_break(before); baseline = deepcopy(node)
    change = labeled.derive(node, before, row)
    assert change and change["bridge_runs"]
    assert change["representation"] == ("protected_slash" if LRM + "/" + LRM in separator else "plain_slash")
    labeled.apply(node, change)
    assert [(n.tag, n.text, n.tail) for n in node.iter()] == [(n.tag, n.text, n.tail) for n in baseline.iter()]
    assert model._c14n(labeled.verified_copy(node, baseline, change)) == model._c14n(baseline)


@pytest.mark.parametrize("digits", [("١", "٢"), ("۳", "۷"), ("1234", "5678")])
def test_inherited_finite_numeral_scripts_and_mixed_separator_flags(digits):
    node, row = paragraph(numerator=digits[0], denominator=digits[1], separator=(" ", "/", " "),
        directions=["1", "0", "0", "1", "0", "0"])
    assert [r["run_index"] for r in labeled.span(node, row)["bridge_runs"]] == [3]


@pytest.mark.parametrize("fault", ["other_label", "fullwidth_slash", "arabic_slash", "extra_slash", "tab",
    "stray_LRM", "LRI", "padding", "number_RTL", "shared_number", "field", "hidden", "revision",
    "duplicate_RTL", "extra_empty", "unowned_break", "protected_no_spaces", "all_zero"])
def test_unsupported_representation_gets_no_new_permission(fault):
    options = {}
    if fault == "other_label": options["label"] = "رقم"
    elif fault in {"fullwidth_slash", "arabic_slash", "extra_slash", "tab", "stray_LRM", "LRI", "protected_no_spaces"}:
        options["separator"] = ({"fullwidth_slash": (" ／ ",), "arabic_slash": (" ؍ ",), "extra_slash": (" / / ",),
            "tab": ("\t/ ",), "stray_LRM": (" /" + LRM + " ",), "LRI": (" \u2066/\u2069 ",),
            "protected_no_spaces": (LRM + "/" + LRM,)}[fault])
    elif fault == "padding": options["numerator"] = "1 "
    elif fault == "number_RTL": options["directions"] = ["1", "1", "1", "0"]
    elif fault == "all_zero": options["directions"] = ["1", "0", "0", "0"]
    node, row = paragraph(**options)
    if fault == "shared_number":
        runs = node.findall(W + "r"); runs[1].find(W + "t").text += runs[2].find(W + "t").text; node.remove(runs[2])
    elif fault == "field": row["has_field"] = True
    elif fault == "hidden": etree.SubElement(node.findall(W + "r")[2].find(W + "rPr"), W + "vanish")
    elif fault == "revision": etree.SubElement(node.find(W + "pPr"), W + "pPrChange")
    elif fault == "duplicate_RTL": etree.SubElement(node.findall(W + "r")[2].find(W + "rPr"), W + "rtl").set(W + "val", "1")
    elif fault == "extra_empty": node.insert(2, etree.Element(W + "r"))
    elif fault == "unowned_break": row["has_page_break"] = False
    assert labeled.span(node, row) is None


@pytest.mark.parametrize("count,allowed", [(32, True), (33, False)])
def test_all_direct_runs_are_charged_before_inventory(monkeypatch, count, allowed):
    node, row = paragraph(separator=(" ",) * (count - 5) + ("/",))
    calls = []
    clones = []
    original = source._inline_folio_run_inventory
    clone = labeled.deepcopy
    def inventory(*args): calls.append(True); return original(*args)
    def copying(*args): clones.append(True); return clone(*args)
    monkeypatch.setattr(source, "_inline_folio_run_inventory", inventory)
    monkeypatch.setattr(labeled, "deepcopy", copying)
    assert (labeled.span(node, row) is not None) == allowed
    assert bool(calls) == allowed
    assert bool(clones) == allowed


@pytest.mark.parametrize("count,allowed", [(80, True), (81, False)])
def test_whole_caption_bound_excludes_only_owned_terminal_break(count, allowed):
    node, row = paragraph(caption_spaces=count - 11)
    assert len(row["text"]) - 1 == count
    assert (labeled.span(node, row) is not None) == allowed


def layout_case(monkeypatch, *, promoted=True, inherited_owner=False):
    original = layout_fixture.document_bytes
    def document_bytes(texts, edit):
        def setup(doc):
            edit(doc)
            for index in (2, 5):
                item = doc.paragraphs[index]
                for r in list(item._p.findall(W + "r")): item._p.remove(r)
                node, _ = paragraph("الصفحة" if inherited_owner else "ص.", "2" if index == 2 else "7", "7",
                    separator=(" ", LRM + "/" + LRM, " ") if inherited_owner else (" / ",))
                for r in node.findall(W + "r"): item._p.append(deepcopy(r))
        return original(texts, setup)
    monkeypatch.setattr(layout_fixture, "document_bytes", document_bytes)
    args = layout_fixture.multipage_fixture("AR")
    args[4].update(source_folio_direction_version=inherited.VERSION, source_footer_placement_version="terminal_body_flow_v1")
    args[4][flow.KEY], args[4][labeled.KEY] = flow.VERSION, labeled.VERSION
    for index, page in enumerate(args[4]["source_evidence"]["pages"]):
        page["retained_terminal_associations"] = {"version": contracts.RETAINED_TERMINAL_ASSOCIATIONS_V1,
            "canonical_proposal_sha256": contracts.digest(contracts.encode({"fictional_page": page["page_number"]})),
            "associations": [], "review_required": True}
        if not promoted and index == 0: page["layout"] = []
    return args


@pytest.mark.parametrize("promoted", [False, True])
def test_public_writer_both_source_scopes_preserve_package_and_break_ownership(monkeypatch, promoted):
    args = layout_case(monkeypatch, promoted=promoted)
    old_context = deepcopy(args[4]); old_context.pop(labeled.KEY)
    old = writer.build_unreviewed_docx(*args[:4], ordinary_context=old_context)
    artifact = layout_fixture.build(args); layout_fixture.verify(artifact, args)
    records = artifact.source_map["source_layout_plan"][labeled.LEDGER]
    assert len(records) == (2 if promoted else 1)
    assert {r["scope"] for r in records} == ({"promoted_footer"} if promoted else {"retained_body"})
    with ZipFile(BytesIO(old.docx_bytes)) as a, ZipFile(BytesIO(artifact.docx_bytes)) as b:
        assert [n for n in a.namelist() if a.read(n) != b.read(n)] == ["word/document.xml"]
        left, right = etree.fromstring(a.read("word/document.xml")), etree.fromstring(b.read("word/document.xml"))
        assert [(n.tag, n.text, n.tail) for n in left.iter()] == [(n.tag, n.text, n.tail) for n in right.iter()]
        assert len(list(left.iter(W + "br"))) == len(list(right.iter(W + "br")))


def test_inherited_owner_keeps_exact_artifact_and_empty_new_ledger(monkeypatch):
    args = layout_case(monkeypatch, inherited_owner=True)
    ctx = deepcopy(args[4]); ctx.pop(labeled.KEY)
    old = writer.build_unreviewed_docx(*args[:4], ordinary_context=ctx)
    new = layout_fixture.build(args); layout_fixture.verify(new, args)
    assert old.docx_bytes == new.docx_bytes
    assert new.source_map["source_layout_plan"][labeled.LEDGER] == []
    assert len(new.source_map["source_layout_plan"][inherited.LEDGER]) == 2


@pytest.mark.parametrize("fault", ["missing_header", "missing_ledger", "duplicate", "float_page", "bool_page",
    "bbox_representation", "scope", "collision", "offset", "extra_key", "literal", "proposal", "before_rtl"])
def test_hash_consistent_ledger_forgeries_fail_public_strict_writer(monkeypatch, fault):
    args = layout_case(monkeypatch)
    if fault == "bbox_representation":
        for page in args[4]["source_evidence"]["pages"]:
            page["layout"][-1]["bbox"] = [0, .9, 1, 1]
    artifact = layout_fixture.build(args); mapping = deepcopy(artifact.source_map)
    plan = mapping["source_layout_plan"]; r = plan[labeled.LEDGER][0]
    if fault == "missing_header": plan.pop(labeled.KEY)
    elif fault == "missing_ledger": plan.pop(labeled.LEDGER)
    elif fault == "duplicate": plan[labeled.LEDGER].append(deepcopy(r))
    elif fault == "float_page": r["footer_association"]["source_page_number"] = float(r["source_page_number"])
    elif fault == "bool_page": r["source_page_number"] = True
    elif fault == "bbox_representation":
        r["footer_association"]["bbox"] = [0.0, .9, 1.0, 1.0]
    elif fault == "scope": r["scope"] = "retained_body"
    elif fault == "collision": plan["clock_ltr_spans"] = [{"paragraph_id": r["paragraph_id"]}]
    elif fault == "offset": r["bridge_runs"][0]["start"] += 1
    elif fault == "extra_key": r["unexpected"] = True
    elif fault == "literal": r["literal_sha256"] = "0" * 64
    elif fault == "proposal": r["canonical_proposal_sha256"] = "0" * 64
    else: r["bridge_runs"][0]["before_rtl"] = False
    mapping["source_layout_plan_sha256"] = model._sha(model._canonical(plan))
    with pytest.raises(ValueError): layout_fixture.verify(writer.SavedDocxLayoutArtifact(artifact.docx_bytes, mapping), args)


@pytest.fixture(scope="module")
def v14_start(tmp_path_factory):
    patch = pytest.MonkeyPatch(); lifecycle.isolate_provider(patch)
    case = lifecycle.normal_start(tmp_path_factory.mktemp("v14_start"), patch,
        damage=lambda p, n, proposal, *_: lifecycle.invalid_decision(proposal) if p == 2 and n == 0 else None,
        saved_policy=auto._labeled_folio_direction_v14_policy())
    yield case
    patch.undo()


def test_normal_start_binds_new_header_ledger_and_exact_saved_reuse(v14_start):
    case = v14_start
    assert auto._labeled_folio_direction_v14_policy() == "source_image_unreviewed_v1:f8a091d4e79093cb6c77ebacb07f1fa3392424e9b4088e5e6774991e0de46b49"
    assert [p for p, _ in case.calls] == [1, 2, 2, 3]
    result = case.job["result"]["automatic_layout"]
    assert result["status"] == "automatic_unreviewed", result
    witness, context = lifecycle.witness_context(case)
    assert len(attempts.verify_witness(witness, **context)[0]) == 3
    mapping = contracts.decode((Path(result["output_path"]).parent / "source_map.json").read_bytes())
    assert mapping["source_layout_plan"][labeled.KEY] == labeled.VERSION
    assert mapping["source_layout_plan"][labeled.LEDGER] == []
    reused = auto.run_completed_unreviewed_rebuild(case.manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert reused["reused_durable_candidate"] and reused["sha256"] == result["sha256"] and len(case.calls) == 4


def test_new_render_pair_and_all_first_retry_SDK_bodies_are_unchanged():
    _, view, proposal, _ = lifecycle.synthetic()
    old = attempts.expected_policy(1, attempts.POLICY_V2, auto._in_flow_folio_bridges_v13_policy().split(":", 1)[1])
    new = attempts.expected_policy(1, attempts.POLICY_V2, auto._labeled_folio_direction_v14_policy().split(":", 1)[1])
    assert attempts.automatic_policy(attempts.POLICY_V2) == auto._per_page_reproposal_v12_policy()
    assert attempts.page_request(view, 1, old) == attempts.page_request(view, 1, new)
    for code in attempts.ELIGIBLE:
        prior = {"intent": {"request_sha256": "1" * 64}, "raw": contracts.encode(proposal).decode(), "validation": {"error_code": code}}
        assert attempts.page_request(view, 1, old, prior=prior) == attempts.page_request(view, 1, new, prior=prior)
    with pytest.raises(ValueError): attempts.automatic_policy(attempts.POLICY, new[attempts.RENDER_KEY])


def test_concrete_v13_registries_and_normalization_survive_the_fresh_v14_selector():
    saved = auto._in_flow_folio_bridges_v13_policy()
    assert auto.frozen_automatic_layout_policy() != saved
    assert saved in auto._metadata_normalization_policies()
    assert saved in auto._source_folio_policies()
    assert auto._source_normalization_version(saved.split(":", 1)[1]) == contracts.OPTIONAL_HINT_NORMALIZATION_V3


@pytest.mark.parametrize("restart", [False, True], ids=["saved_v14_same_manager", "saved_v14_new_manager"])
def test_saved_v14_resume_and_rebuild_under_new_default_are_local_and_exact(v14_start, restart):
    from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
    case = v14_start
    saved = auto._labeled_folio_direction_v14_policy()
    assert auto.frozen_automatic_layout_policy() != saved
    before = {p: p.read_bytes() for p in case.operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
    def forbidden(*args, **kwargs): pytest.fail("Saved V14 attempted provider dispatch or accounting reservation")
    manager = OrdinaryLayoutManager(case.manager.service.root.parents[2], mode="shadow", workspace_id="fictional",
        job_resolver=case.manager.job_resolver, provider_factory=forbidden, accounting_factory=forbidden,
        suggestion_policy=forbidden) if restart else case.manager
    result = auto.run_automatic_layout(manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"], saved)
    assert result["reused_durable_candidate"] and len(case.calls) == 4
    rebuilt = auto.run_completed_unreviewed_rebuild(manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert rebuilt["reused_durable_candidate"] and rebuilt["sha256"] == result["sha256"]
    assert all(p.read_bytes() == raw for p, raw in before.items())
