"""Fictional source-footer presentation ownership and exact bridge inversion."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest
from fastapi.testclient import TestClient

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import ordinary_folio_bridges_v4 as bridge
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer

W, LRM = model.W, "\u200e"


def paragraph(numerator="1", denominator="2", *, bare=False, terminal=True,
              first_spaces=(" ",), second_spaces=(" ",), directions=None):
    node = etree.Element(W + "p", nsmap={"w": W[1:-1]})
    etree.SubElement(etree.SubElement(node, W + "pPr"), W + "bidi").set(W + "val", "1")
    number = lambda value: value if bare else LRM + value + LRM
    values = ["الصفحة ", number(numerator), *first_spaces, LRM + "/" + LRM, *second_spaces, number(denominator)]
    direction_values = directions or ["1", "0", *["1"] * len(first_spaces), "0", *["1"] * len(second_spaces), "0"]
    for value, direction in zip(values, direction_values):
        run = etree.SubElement(node, W + "r")
        props = etree.SubElement(run, W + "rPr")
        etree.SubElement(props, W + "rFonts").set(W + "ascii", "Arial")
        etree.SubElement(props, W + "rtl").set(W + "val", direction)
        etree.SubElement(run, W + "t").text = value
    if terminal:
        run = etree.SubElement(node, W + "r")
        etree.SubElement(etree.SubElement(run, W + "rPr"), W + "rtl").set(W + "val", "1")
        etree.SubElement(run, W + "br").set(W + "type", "page")
    text = "".join(values)
    row = {"id": "p000001", "text": text + ("\f" if terminal else ""),
           "tokens": [{"kind": "t", "text": text}] + ([{"kind": "page_break", "text": "\f"}] if terminal else []),
           "has_field": False, "has_numbering": False, "has_page_break": terminal, "ppr_xml": ""}
    return node, row


def after_break(node):
    after = deepcopy(node)
    for br in list(after.iter(W + "br")):
        br.getparent().remove(br)
    return after


@pytest.mark.parametrize("numerator,denominator", [("1", "2"), ("2", "7"), ("١", "٢"), ("۳", "۷")])
@pytest.mark.parametrize("bare", [False, True])
@pytest.mark.parametrize("terminal", [False, True])
def test_only_existing_space_attributes_change_and_inverse_is_exact(numerator, denominator, bare, terminal):
    before, row = paragraph(numerator, denominator, bare=bare, terminal=terminal)
    node = after_break(before)
    original = model._c14n(node)
    old = deepcopy(node)
    assert source._folio_ltr_span(old, controlled_numeric=True) is None
    assert model._c14n(old) == original
    change = bridge.derive(node, before, row)
    assert change is not None
    assert [entry["run_index"] for entry in change["bridge_runs"]] == [2, 4]
    assert change["literal_sha256"] == model._sha(row["text"][change["start"]:change["end"]].encode())
    bridge.apply(node, change)
    assert [(n.tag, n.text, n.tail) for n in node.iter()] == [(n.tag, n.text, n.tail) for n in old.iter()]
    assert model._c14n(bridge.verified_copy(node, old, change)) == original
    assert len(node.findall(W + "r")) == (7 if terminal else 6)


def test_split_whole_bridges_and_already_ltr_bridges_are_accounted_individually():
    before, row = paragraph(first_spaces=(" ", "  "), directions=["1", "0", "0", "1", "0", "1", "0"])
    node = after_break(before)
    change = bridge.derive(node, before, row)
    assert [entry["run_index"] for entry in change["bridge_runs"]] == [3, 5]
    all_ltr, row = paragraph(directions=["1", "0", "0", "0", "0", "0"])
    assert bridge.derive(after_break(all_ltr), all_ltr, row) is None


@pytest.mark.parametrize("limit,allowed", [(80, True), (81, False)])
def test_complete_caption_text_bound_excludes_only_the_owned_terminal_break(limit, allowed):
    before, row = paragraph(first_spaces=(" " * (limit - 17),))
    assert len(row["text"]) - 1 == limit
    assert (bridge.derive(after_break(before), before, row) is not None) is allowed


@pytest.mark.parametrize("count,allowed", [(32, True), (33, False)])
def test_total_run_bound_counts_caption_and_empty_terminal_residue_before_inventory(count, allowed, monkeypatch):
    before, row = paragraph(first_spaces=(" ",) * (count - 6))
    assert len(before.findall(W + "r")) == count
    original = source._inline_folio_run_inventory
    calls = []
    def inventory(*args): calls.append(True); return original(*args)
    monkeypatch.setattr(source, "_inline_folio_run_inventory", inventory)
    assert (bridge.derive(after_break(before), before, row) is not None) is allowed
    assert bool(calls) is allowed


@pytest.mark.parametrize("damage", ["half_number", "protected_fullwidth", "wrong_slash", "extra_fraction",
    "tab", "rtl_carrier", "missing_rtl", "duplicate_rtl", "duplicate_prefix_rtl", "implicit_bridge",
    "hidden", "field", "numbering", "wrapper", "nontext", "unowned_empty", "wrong_break", "after_change"])
def test_new_proof_declines_unsafe_grammar_structure_ownership_and_controls(damage):
    before, row = paragraph()
    runs = before.findall(W + "r")
    if damage in {"half_number", "protected_fullwidth", "wrong_slash", "extra_fraction", "tab"}:
        if damage == "half_number": runs[1].find(W + "t").text = LRM + "1"
        elif damage == "protected_fullwidth": runs[3].find(W + "t").text = LRM + "／" + LRM
        elif damage == "wrong_slash": runs[3].find(W + "t").text = LRM + "⁄" + LRM
        elif damage == "extra_fraction": runs[5].find(W + "t").text += " / 9"
        else: runs[2].find(W + "t").text = "\t"
        text = "".join(t.text or "" for t in before.iter(W + "t"))
        row["text"], row["tokens"][0]["text"] = text + "\f", text
    elif damage == "rtl_carrier": runs[3].find(W + "rPr/" + W + "rtl").set(W + "val", "1")
    elif damage == "missing_rtl": runs[1].find(W + "rPr").remove(runs[1].find(W + "rPr/" + W + "rtl"))
    elif damage in {"duplicate_rtl", "duplicate_prefix_rtl"}:
        etree.SubElement(runs[1 if damage == "duplicate_rtl" else 0].find(W + "rPr"), W + "rtl").set(W + "val", "0")
    elif damage == "implicit_bridge": runs[2].remove(runs[2].find(W + "rPr"))
    elif damage == "hidden": etree.SubElement(runs[1].find(W + "rPr"), W + "vanish")
    elif damage == "field": row["has_field"] = True
    elif damage == "numbering": row["has_numbering"] = True
    elif damage == "wrapper": etree.SubElement(before, W + "dir")
    elif damage == "nontext": etree.SubElement(runs[2], W + "tab")
    elif damage == "unowned_empty": before.insert(1, etree.Element(W + "r"))
    elif damage == "wrong_break": runs[-1].find(W + "br").set(W + "type", "column")
    node = after_break(before)
    if damage == "after_change": node.findall(W + "r")[0].find(W + "rPr/" + W + "rtl").set(W + "val", "0")
    assert bridge.derive(node, before, row) is None


def protected_fixture(monkeypatch):
    from tests import test_ordinary_source_layout as fixture
    original = fixture.document_bytes
    def document_bytes(texts, edit):
        def setup(doc):
            edit(doc)
            for item in doc.paragraphs:
                if item.text.startswith("الصفحة "):
                    for run in list(item._p.findall(W + "r")): item._p.remove(run)
                    node, _ = paragraph(terminal=False)
                    for run in node.findall(W + "r"): item._p.append(deepcopy(run))
        return original(texts, setup)
    monkeypatch.setattr(fixture, "document_bytes", document_bytes)
    args = fixture.fixture("AR")
    args[4]["source_folio_direction_version"] = bridge.VERSION
    return fixture, args


@pytest.mark.parametrize("damage", ["missing", "empty", "duplicate", "page", "offset", "hash", "before", "mode",
                                     "font", "text", "unlisted_rtl", "empty_run"])
def test_independent_strict_inversion_rejects_hash_consistent_plan_and_package_forgeries(tmp_path, monkeypatch, damage):
    fixture, args = protected_fixture(monkeypatch)
    artifact = fixture.build(args)
    fixture.verify(artifact, args)
    mapping = deepcopy(artifact.source_map)
    plan = mapping["source_layout_plan"]
    assert len(plan[bridge.LEDGER]) == 1
    if damage == "missing": plan.pop(bridge.LEDGER)
    elif damage == "empty": plan[bridge.LEDGER] = []
    elif damage == "duplicate": plan[bridge.LEDGER].append(deepcopy(plan[bridge.LEDGER][0]))
    elif damage == "page": plan[bridge.LEDGER][0]["source_page_number"] = 99
    elif damage == "offset": plan[bridge.LEDGER][0]["bridge_runs"][0]["start"] += 1
    elif damage == "hash": plan[bridge.LEDGER][0]["literal_sha256"] = "0" * 64
    elif damage == "before": plan[bridge.LEDGER][0]["bridge_runs"][0]["before_rtl"] = 0
    elif damage == "mode": plan["folio_direction_version"] = "numeric_run_ltr_v3"
    raw = artifact.docx_bytes
    if damage in {"font", "text", "unlisted_rtl", "empty_run"}:
        from tests.test_saved_docx_layout import changed_part
        def change(root):
            node = root.findall(W + "p")[-1]
            runs = node.findall(W + "r")
            if damage == "font": runs[2].find(W + "rPr/" + W + "rFonts").set(W + "ascii", "Courier New")
            elif damage == "text": runs[2].find(W + "t").text += " "
            elif damage == "unlisted_rtl": runs[0].find(W + "rPr/" + W + "rtl").set(W + "val", "0")
            else: etree.SubElement(node, W + "r")
        raw = changed_part(raw, plan["source_footers"][0]["part_uri"], change)
    mapping["docx_sha256"] = model._sha(raw)
    mapping["source_layout_plan_sha256"] = model._sha(model._canonical(plan))
    forged = writer.SavedDocxLayoutArtifact(raw, mapping)
    context = {k: v for k, v in args[4].items() if k not in {"source_evidence", "source_folio_direction_version"}}
    base = writer.build_unreviewed_docx(*args[:4], ordinary_context=context)
    monkeypatch.setattr(source, "transform", lambda *a, **kw: forged)
    with pytest.raises(ValueError):
        source.verify(forged, base, *args[1:4], context, args[4]["source_evidence"], expected_folio_direction=bridge.VERSION)


def test_fresh_v10_changes_only_numeric_identity_and_preserves_named_v9(monkeypatch):
    monkeypatch.setattr(auto, "frozen_automatic_layout_policy", auto._protected_folio_bridges_v10_policy)
    old, new = auto._adjacent_lrm_emphasis_v9_policy(), auto.frozen_automatic_layout_policy()
    assert new == auto._protected_folio_bridges_v10_policy() and old != new
    for policy in (old, new):
        fp = policy.split(":")[1]
        assert auto._band_normalization_version(fp) == c.BAND_NORMALIZATION_V8
        assert auto._emphasis_normalization_version(fp) == c.EMPHASIS_NORMALIZATION_V3
        assert auto._source_folio_inline_direction_version(fp) == source.INLINE_FOLIO_DIRECTION_V1
        assert auto._terminal_source_layout_versions(fp)["source_closing_group_version"] == "bounded_terminal_signature_context_v3"
        assert policy in auto._metadata_normalization_policies() and policy in auto._source_folio_policies()
    assert auto._source_folio_direction_version(old.split(":")[1]) == "numeric_run_ltr_v3"
    assert auto._source_folio_direction_version(new.split(":")[1]) == bridge.VERSION
    assert auto._source_folio_direction_version("0" * 64) is None



@pytest.mark.parametrize("restart", [False, True], ids=["saved_v9_resume", "saved_v9_restart_resume"])
def test_saved_v9_actual_resume_and_restart_remain_v9_under_fresh_v10(tmp_path, monkeypatch, restart):
    monkeypatch.setattr(auto, "frozen_automatic_layout_policy", auto._protected_folio_bridges_v10_policy)
    from tests import test_ordinary_auto_layout_workflow as flow
    from tests.test_terminal_accounting_restore import gmail_fixture, restart_into_app
    from legalpdf_translate.ordinary_layout_service import _read
    original = flow._proposal
    def proposal(*args, **kwargs):
        value = original(*args, **kwargs)
        value.update(version=c.PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[], source_layout_evidence=[])
        return value
    monkeypatch.setattr(flow, "_proposal", proposal)
    source, output = tmp_path / "fictional.pdf", tmp_path / "output"
    output.mkdir()
    flow._source(source, ("digital",))
    app, jobs, sdk, requests = flow._app(tmp_path, monkeypatch, ("Fictional body text.",), (1,))
    loaded, session, gmail = gmail_fixture(source, output)
    form = {"source_path": str(source), "output_dir": str(output), "target_lang": "EN",
            "start_page": 1, "end_page": 1, "image_mode": "off", "ocr_mode": "off", "workers": 1,
            "gmail_batch_context": gmail}
    with TestClient(app) as client:
        with monkeypatch.context() as prior:
            prior.setattr(auto, "frozen_automatic_layout_policy", auto._adjacent_lrm_emphasis_v9_policy)
            response = client.post("/api/translation/jobs/translate", json={"mode": "shadow", "workspace_id": "fictional", "form_values": form})
            assert response.status_code == 200
            job_id = response.json()["normalized_payload"]["job"]["job_id"]
            initial = flow._wait(jobs, job_id)
        assert initial["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        assert auto.frozen_automatic_layout_policy() == auto._protected_folio_bridges_v10_policy()
        run = Path(initial["result"]["run_dir"])
        pointer = json.loads((run / "ordinary_auto_layout/operation.json").read_bytes())
        manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, "shadow", "fictional")
        operation = manager.service.root / job_id / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
        saved = {p: p.read_bytes() for p in operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
        assert _read(operation / "proposal_initial_view.json")["emphasis_normalization_version"] == c.EMPHASIS_NORMALIZATION_V3
        if restart:
            app, jobs = restart_into_app(tmp_path, app, jobs, job_id, loaded, session)
            client = TestClient(app)
        response = client.post("/api/translation/jobs/translate", json={"mode": "shadow", "workspace_id": "fictional", "form_values": {**form, "resume": True}})
        assert response.status_code == 200
        resumed_id = response.json()["normalized_payload"]["job"]["job_id"]
        resumed = flow._wait(jobs, resumed_id)
        assert resumed["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        assert len(sdk.requests) == len(requests) == 1
        assert all(p.read_bytes() == raw for p, raw in saved.items())

