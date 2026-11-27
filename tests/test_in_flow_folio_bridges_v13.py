"""Fictional in-flow ownership, exact flag inversion and closed render identity."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_auto_layout_artifacts as core
from legalpdf_translate import ordinary_folio_bridges_v4 as old
from legalpdf_translate import ordinary_in_flow_folio_bridges as flow
from legalpdf_translate import ordinary_layout_contracts as contracts
from legalpdf_translate import ordinary_layout_reproposal as attempts
from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests import test_ordinary_layout_reproposal as lifecycle
from tests import test_ordinary_source_layout as layout_fixture
from tests.test_protected_folio_bridges_v4 import paragraph

W = model.W


@pytest.fixture(autouse=True)
def no_live_provider(monkeypatch):
    lifecycle.isolate_provider(monkeypatch)


def local_fixture(monkeypatch, *, missing=0, terminal=False):
    original = layout_fixture.document_bytes
    def document_bytes(texts, edit):
        def setup(doc):
            edit(doc)
            for index in (2, 5):
                item = doc.paragraphs[index]
                for run in list(item._p.findall(W + "r")): item._p.remove(run)
                node, _ = paragraph("2" if index == 2 else "7", "7", terminal=terminal and index == 2)
                for run in node.findall(W + "r"): item._p.append(deepcopy(run))
        return original(texts, setup)
    monkeypatch.setattr(layout_fixture, "document_bytes", document_bytes)
    args = layout_fixture.multipage_fixture("AR")
    context = args[4]
    context["source_folio_direction_version"] = old.VERSION
    context[flow.KEY] = flow.VERSION
    context["source_footer_placement_version"] = "terminal_body_flow_v1"
    for index, page in enumerate(context["source_evidence"]["pages"]):
        page["retained_terminal_associations"] = {"version": contracts.RETAINED_TERMINAL_ASSOCIATIONS_V1,
            "canonical_proposal_sha256": contracts.digest(contracts.encode({"fictional_page": page["page_number"]})),
            "associations": [], "review_required": True}
        if index == missing: page["layout"] = []
    return args


@pytest.mark.parametrize("missing,terminal", [(0, False), (1, True)])
def test_locally_accepted_footer_fixes_only_its_bridges_without_global_promotion(monkeypatch, missing, terminal):
    args = local_fixture(monkeypatch, missing=missing, terminal=terminal)
    original_decisions = deepcopy(args[3])
    before_context = deepcopy(args[4])
    before_context.pop(flow.KEY)
    old_artifact = writer.build_unreviewed_docx(*args[:4], ordinary_context=before_context)
    artifact = layout_fixture.build(args)
    layout_fixture.verify(artifact, args)
    plan = artifact.source_map["source_layout_plan"]
    assert plan["source_footers"] == []
    assert plan[flow.KEY] == flow.VERSION and len(plan[flow.LEDGER]) == 1
    record = plan[flow.LEDGER][0]
    assert record["source_page_number"] == (7 if missing == 0 else 2)
    assert record["footer_association"]["source_page_number"] == record["source_page_number"]
    assert len(record["bridge_runs"]) == 2
    assert args[3] == original_decisions
    with ZipFile(BytesIO(old_artifact.docx_bytes)) as a, ZipFile(BytesIO(artifact.docx_bytes)) as b:
        assert set(a.namelist()) == set(b.namelist())
        assert [name for name in a.namelist() if a.read(name) != b.read(name)] == ["word/document.xml"]
        aa, bb = etree.fromstring(a.read("word/document.xml")), etree.fromstring(b.read("word/document.xml"))
        assert [(n.tag, n.text, n.tail) for n in aa.iter()] == [(n.tag, n.text, n.tail) for n in bb.iter()]
        assert len(list(aa.iter(W + "br"))) == len(list(bb.iter(W + "br"))) == int(terminal)


def test_promoted_returned_to_body_folios_never_get_a_second_ledger(monkeypatch):
    args = local_fixture(monkeypatch, missing=None, terminal=True)
    artifact = layout_fixture.build(args)
    layout_fixture.verify(artifact, args)
    plan = artifact.source_map["source_layout_plan"]
    assert len(plan["source_footers"]) == 2 and len(plan[old.LEDGER]) == 2
    assert plan[flow.LEDGER] == []
    assert all(row["part_uri"] == "word/document.xml" for row in artifact.source_map["paragraphs"])


@pytest.mark.parametrize("permission", ["missing_hint", "body_role", "reference_role"])
def test_local_presentation_needs_both_accepted_hint_and_source_folio_role(monkeypatch, permission):
    args = local_fixture(monkeypatch)
    if permission == "missing_hint": args[4]["source_evidence"]["pages"][1]["layout"] = []
    else: args[3]["paragraphs"][-1]["role"] = "body" if permission == "body_role" else "reference"
    if permission == "reference_role":
        with pytest.raises(contracts.OrdinaryLayoutError, match="invalid_source_footer_evidence"):
            layout_fixture.build(args)
        return
    artifact = layout_fixture.build(args)
    layout_fixture.verify(artifact, args)
    assert artifact.source_map["source_layout_plan"][flow.LEDGER] == []


@pytest.mark.parametrize("excluded", [None, "missing_hint", "wrong_role", "parts", "other_part", "nested",
    "wrong_page", "duplicate_owner", "duplicate_hint", "promoted", "folio_ltr_spans",
    "folio_bridge_direction_spans", "inline_folio_ltr_spans", "clock_ltr_spans"])
def test_direct_local_scope_requires_unique_body_ownership_without_direction_collision(excluded):
    node, row = paragraph(terminal=True)
    identifier = row["id"]
    body = etree.Element(W + "body")
    body.append(node)
    mapping = {identifier: {"part_uri": "word/document.xml"}}
    choices = {identifier: {"role": "source_folio"}}
    owners = {1: [identifier]}
    item = {"kind": "source_footer", "paragraph_ids": [identifier], "bbox": [0, .9, 1, 1], "source_page_number": 1}
    layout = [item]
    evidence = {"pages": [{"page_number": 1, "retained_terminal_associations": {"canonical_proposal_sha256": "1" * 64}}]}
    plan = {"source_footers": []}
    if excluded == "missing_hint": layout = []
    elif excluded == "wrong_role": choices[identifier]["role"] = "body"
    elif excluded == "parts": mapping[identifier]["parts"] = [{"location": "/fictional"}]
    elif excluded == "other_part": mapping[identifier]["part_uri"] = "word/footer1.xml"
    elif excluded == "nested": etree.SubElement(body, W + "tc").append(node)
    elif excluded == "wrong_page": item["source_page_number"] = 2
    elif excluded == "duplicate_owner": owners[2] = [identifier]
    elif excluded == "duplicate_hint": layout.append(deepcopy(item))
    elif excluded == "promoted": plan["source_footers"] = [{"paragraph_ids": [identifier]}]
    elif excluded is not None: plan[excluded] = [{"paragraph_id": identifier}]
    before = model._c14n(body)
    result = flow.derive({identifier: node}, mapping, {identifier: row}, choices, owners, [1], layout, evidence, plan, "AR")
    assert len(result) == int(excluded is None)
    assert model._c14n(body) == before


@pytest.mark.parametrize("terminal", [False, True])
def test_bridge_span_and_inverse_keep_the_original_owned_break(terminal):
    node, row = paragraph("۳", "۷", terminal=terminal)
    baseline = deepcopy(node)
    record = flow.bridge_span(node, row)
    assert record is not None
    old.apply(node, record)
    assert model._c14n(flow.verified_copy(node, baseline, record)) == model._c14n(baseline)
    assert len(list(node.iter(W + "br"))) == int(terminal)


@pytest.mark.parametrize("count,allowed", [(32, True), (33, False)])
def test_total_run_bound_precedes_the_new_inventory(monkeypatch, count, allowed):
    node, row = paragraph(first_spaces=(" ",) * (count - 6))
    calls = []
    original = source._inline_folio_run_inventory
    def inventory(*args): calls.append(True); return original(*args)
    monkeypatch.setattr(source, "_inline_folio_run_inventory", inventory)
    assert (flow.bridge_span(node, row) is not None) is allowed
    assert bool(calls) is allowed


@pytest.mark.parametrize("limit,allowed", [(80, True), (81, False)])
def test_caption_limit_preserves_only_the_owned_terminal_break_exception(limit, allowed):
    node, row = paragraph(first_spaces=(" " * (limit - 17),))
    assert len(row["text"]) - 1 == limit
    assert (flow.bridge_span(node, row) is not None) is allowed


@pytest.fixture(scope="module")
def v13_start(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    lifecycle.isolate_provider(patch)
    case = lifecycle.normal_start(tmp_path_factory.mktemp("v13_start"), patch,
        damage=lambda page, ordinal, proposal, *_: lifecycle.invalid_decision(proposal) if page == 2 and ordinal == 0 else None,
        saved_policy=auto._in_flow_folio_bridges_v13_policy())
    yield case
    patch.undo()


def test_v13_normal_start_binds_explicit_renderer_and_mandatory_empty_body_ledger(v13_start):
    case = v13_start
    assert auto._in_flow_folio_bridges_v13_policy() == "source_image_unreviewed_v1:e7a5a9bd3ae6001a528b9f75015382525a944728d7541890be1f5de3802724e5"
    assert [page for page, _ in case.calls] == [1, 2, 2, 3], case.job["result"]["automatic_layout"]
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    witness, kwargs = lifecycle.witness_context(case)
    policy = witness["manifest"]["policy"]
    assert policy[attempts.RENDER_KEY] == auto._in_flow_folio_bridges_v13_policy().split(":", 1)[1]
    assert policy[attempts.KEY] == attempts.POLICY_V2
    assert len(attempts.verify_witness(witness, **kwargs)[0]) == 3
    result = case.job["result"]["automatic_layout"]
    mapping = contracts.decode((Path(result["output_path"]).parent / "source_map.json").read_bytes())
    assert mapping["source_layout_plan"][flow.KEY] == flow.VERSION
    assert mapping["source_layout_plan"][flow.LEDGER] == []


@pytest.mark.parametrize("fault", ["float_page", "bool_as_integer", "claimed_layout", "canonical_proposal"])
def test_portable_source_sidecar_is_exactly_reconstructed_from_selected_raw(v13_start, fault):
    _, kwargs = lifecycle.witness_context(v13_start)
    _, _, _, saved, _ = lifecycle.saved_evidence(v13_start)
    evidence = deepcopy(saved["proposal_evidence"])
    page = evidence["source_evidence"]["pages"][0]
    if fault == "float_page": page["page_number"] = float(page["page_number"])
    elif fault == "bool_as_integer": page["source_coverage_verified"] = 0
    elif fault == "canonical_proposal": page["retained_terminal_associations"]["canonical_proposal_sha256"] = "0" * 64
    else:
        identifier = kwargs["snapshot"]["paragraphs"][0]["id"]
        page["layout"] = [{"kind": "source_footer", "paragraph_ids": [identifier], "bbox": [0, .9, 1, 1]}]
    with pytest.raises(contracts.OrdinaryLayoutError, match="proposal_repair_source_evidence_changed"):
        attempts.verify_evidence(evidence, **kwargs, expected_policy_fingerprint=saved["policy_fingerprint"])


@pytest.mark.parametrize("fault", ["missing_render", "downgraded_inner", "missing_header", "unknown_header"])
def test_v13_trusted_public_entrypoints_reject_render_and_capability_downgrades(v13_start, fault):
    case = v13_start
    service, folder, _, saved, view = lifecycle.saved_evidence(case)
    manifest, reviewed_snapshot, frames = service._load(folder)
    base, _, snapshot = service._ordinary_binding(folder, manifest, reviewed_snapshot, view["generation"])
    evidence = deepcopy(saved["proposal_evidence"])
    if fault == "missing_render": evidence[attempts.EVIDENCE_KEY]["manifest"]["policy"].pop(attempts.RENDER_KEY)
    elif fault == "downgraded_inner": evidence["policy_fingerprint"] = auto._per_page_reproposal_v12_policy().split(":", 1)[1]
    elif fault == "missing_header": evidence.pop(flow.KEY)
    else: evidence[flow.KEY] = "unsupported"
    raw, pdf = (folder / "original.docx").read_bytes(), (folder / "source.pdf").read_bytes()
    with pytest.raises(ValueError):
        core.build_unreviewed_candidate(raw, snapshot, frames, view["decisions"], proposal_evidence=evidence,
            source_pdf_bytes=pdf, policy_fingerprint=base["policy_fingerprint"])
    with pytest.raises(ValueError):
        service.attach_ordinary_binding(view["review_id"], contracts.decode((folder / "ordinary_raw_source_map.json").read_bytes()),
            tuple(base["selected_pages"]), base["policy_fingerprint"], evidence, expected_generation=view["generation"])
    assert len(case.calls) == 4


def test_closed_render_pairs_and_v2_sdk_requests_remain_exact():
    _, view, proposal, v11 = lifecycle.synthetic()
    v12 = attempts.expected_policy(1, attempts.POLICY_V2)
    fp = auto._in_flow_folio_bridges_v13_policy().split(":", 1)[1]
    v13 = attempts.expected_policy(1, attempts.POLICY_V2, fp)
    assert attempts.automatic_policy(attempts.POLICY_V2) == auto._per_page_reproposal_v12_policy()
    assert attempts.RENDER_KEY not in v12 and v13[attempts.RENDER_KEY] == fp
    assert attempts.page_request(view, 1, v12) == attempts.page_request(view, 1, v13)
    prior = {"intent": {"request_sha256": "1" * 64}, "raw": contracts.encode(proposal).decode(),
        "validation": {"error_code": "ordinary_layout_invalid_source_footer_evidence"}}
    assert attempts.page_request(view, 1, v12, prior=prior) == attempts.page_request(view, 1, v13, prior=prior)
    for repair, render in [(attempts.POLICY, fp), (attempts.POLICY_V2, "0" * 64),
                           (attempts.POLICY_V2, auto._per_page_reproposal_v12_policy().split(":", 1)[1])]:
        with pytest.raises(ValueError): attempts.automatic_policy(repair, render)


@pytest.mark.parametrize("fault", ["missing_header", "missing_ledger", "duplicate", "float_page", "bool_page",
    "association", "proposal", "offset", "literal", "before_rtl", "collision", "promoted", "bbox_representation"])
def test_hash_consistent_new_ledger_forgeries_fail_public_strict_validation(monkeypatch, fault):
    args = local_fixture(monkeypatch)
    if fault == "bbox_representation": args[4]["source_evidence"]["pages"][1]["layout"][0]["bbox"] = [0, .9, 1, 1]
    artifact = layout_fixture.build(args)
    mapping = deepcopy(artifact.source_map)
    plan = mapping["source_layout_plan"]
    record = plan[flow.LEDGER][0]
    if fault == "missing_header": plan.pop(flow.KEY)
    elif fault == "missing_ledger": plan.pop(flow.LEDGER)
    elif fault == "duplicate": plan[flow.LEDGER].append(deepcopy(record))
    elif fault == "float_page": record["footer_association"]["source_page_number"] = float(record["source_page_number"])
    elif fault == "bool_page": record["footer_association"]["source_page_number"] = True
    elif fault == "association": record["footer_association"]["paragraph_ids"].reverse()
    elif fault == "proposal": record["canonical_proposal_sha256"] = "0" * 64
    elif fault == "offset": record["bridge_runs"][0]["start"] += 1
    elif fault == "literal": record["literal_sha256"] = "0" * 64
    elif fault == "before_rtl": record["bridge_runs"][0]["before_rtl"] = "0"
    elif fault == "collision": plan["clock_ltr_spans"] = [{"paragraph_id": record["paragraph_id"]}]
    elif fault == "bbox_representation": record["footer_association"]["bbox"] = [0.0, .9, 1.0, 1.0]
    else: plan["source_footers"] = [{"paragraph_ids": [record["paragraph_id"]]}]
    if fault != "bbox_representation": mapping["source_layout_plan_sha256"] = model._sha(model._canonical(plan))
    with pytest.raises(ValueError):
        layout_fixture.verify(writer.SavedDocxLayoutArtifact(artifact.docx_bytes, mapping), args)


@pytest.mark.parametrize("restart", [False, True], ids=["saved_v12_same_manager", "saved_v12_new_manager"])
def test_concrete_v12_actual_binding_resume_and_rebuild_stay_v12_under_v13(tmp_path, monkeypatch, restart):
    from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
    case = lifecycle.normal_start(tmp_path, monkeypatch,
        damage=lambda p, n, proposal, *_: lifecycle.invalid_decision(proposal) if p == 2 and n == 0 else None,
        saved_policy=auto._per_page_reproposal_v12_policy())
    assert auto._in_flow_folio_bridges_v13_policy() == "source_image_unreviewed_v1:e7a5a9bd3ae6001a528b9f75015382525a944728d7541890be1f5de3802724e5"
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    before = {p: p.read_bytes() for p in case.operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
    def forbidden(*args, **kwargs): pytest.fail("Saved V12 attempted provider dispatch or accounting reservation")
    manager = OrdinaryLayoutManager(case.manager.service.root.parents[2], mode="shadow", workspace_id="fictional",
        job_resolver=case.manager.job_resolver, provider_factory=forbidden, accounting_factory=forbidden,
        suggestion_policy=forbidden) if restart else case.manager
    result = auto.run_automatic_layout(manager, case.app.state.ordinary_layouts._accounting,
        case.job["job_id"], auto._per_page_reproposal_v12_policy())
    assert result["reused_durable_candidate"] and len(case.calls) == 4
    rebuilt = auto.run_completed_unreviewed_rebuild(manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert rebuilt["reused_durable_candidate"] and rebuilt["sha256"] == result["sha256"]
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("restart", [False, True], ids=["saved_v13_same_manager", "saved_v13_new_manager"])
def test_concrete_v13_resume_and_rebuild_under_v14_are_local_and_exact(v13_start, restart):
    from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
    case = v13_start
    assert auto._labeled_folio_direction_v14_policy() == "source_image_unreviewed_v1:f8a091d4e79093cb6c77ebacb07f1fa3392424e9b4088e5e6774991e0de46b49"
    before = {p: p.read_bytes() for p in case.operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
    def forbidden(*args, **kwargs): pytest.fail("Saved V13 attempted provider dispatch or accounting reservation")
    manager = OrdinaryLayoutManager(case.manager.service.root.parents[2], mode="shadow", workspace_id="fictional",
        job_resolver=case.manager.job_resolver, provider_factory=forbidden, accounting_factory=forbidden,
        suggestion_policy=forbidden) if restart else case.manager
    result = auto.run_automatic_layout(manager, case.app.state.ordinary_layouts._accounting,
        case.job["job_id"], auto._in_flow_folio_bridges_v13_policy())
    assert result["reused_durable_candidate"] and len(case.calls) == 4
    rebuilt = auto.run_completed_unreviewed_rebuild(manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert rebuilt["reused_durable_candidate"] and rebuilt["sha256"] == result["sha256"]
    assert all(p.read_bytes() == raw for p, raw in before.items())
