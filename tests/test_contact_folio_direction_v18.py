"""A real source footer can authorize one local slash change on an Arabic contact row."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_reproposal as reproposal
from legalpdf_translate import ordinary_source_folio_proof as proof
from legalpdf_translate import ordinary_source_layout as layout
from tests.test_source_folio_span_proof import fixture


def contact(tmp_path, *, text=None):
    text = text or "البريد: \u2066[[desk@example.pt 3]]\u2069 / \u2066[[3]]\u2069"
    raw, snapshot, frames, decisions, evidence, _, _ = fixture(
        tmp_path, labels=("الصفحة 1 / 3", "الصفحة 2 / 3", text))
    context = {"selected_pages":[1,2,3], "page_groups":snapshot.page_groups, proof.KEY:evidence[proof.KEY]}
    choice = next(c for c in decisions["paragraphs"] if c["role"]=="source_folio" and c["regions"][0]["page_number"]==3)
    source = evidence[proof.KEY]["folios"][2]["fraction"]["bbox"]
    cx = (source[0]+source[2])/2
    choice["regions"][0]["bbox_px"] = [(cx+.025)*1000, 1290, 960, 1350]
    identifier = choice["paragraph_id"]
    member = next(i for i in dict(snapshot.page_groups)[3] if i != identifier)
    footer = {"kind":"source_footer","paragraph_ids":[member,identifier],"source_page_number":3,
              "bbox":[cx+.015,.92,.96,.99]}
    return raw,snapshot.saved_snapshot,frames,decisions,context,choice,footer


def spans(values, footers):
    _,snap,frames,decisions,context,_,_=values
    return proof.direction_target_spans(snap,frames,decisions,context,accepted_footers=footers)


def test_membership_can_supply_horizontal_extent_only_for_direction(tmp_path):
    values = contact(tmp_path)
    _,snap,frames,decisions,context,choice,footer=values
    assert [s["page_number"] for s in spans(values,[]) ] == [1,2]
    result = spans(values,[footer])
    assert [s["page_number"] for s in result] == [1,2,3]
    assert result[-1]["paragraph_id"]==choice["paragraph_id"] and result[-1]["footer_association"]==footer
    assert proof.target_spans(snap,frames,decisions,context)==[]
    assert [s["page_number"] for s in spans(values,[footer,deepcopy(footer)])] == [1,2]
    # A previously qualified row keeps its historical span and does not acquire a second owner.
    choice["regions"][0]["bbox_px"][0]=25
    result=spans(values,[footer])
    assert len(result)==3 and "footer_association" not in result[-1]


@pytest.mark.parametrize("bad", ["outside_horizontal","outside_vertical","wrong_page","absent_member","duplicate",
                                   "non_folio","split","other_terminal_fraction"])
def test_extent_owner_and_unique_fraction_are_all_required(tmp_path,bad):
    values=contact(tmp_path)
    _,snap,_,decisions,_,choice,footer=values
    if bad=="outside_horizontal":footer["bbox"][0]+=.02
    elif bad=="outside_vertical":footer["bbox"][3]=.93
    elif bad=="wrong_page":footer["source_page_number"]=17
    elif bad=="absent_member":footer["paragraph_ids"]=footer["paragraph_ids"][:1]
    elif bad=="duplicate":footer["paragraph_ids"].append(choice["paragraph_id"])
    elif bad=="non_folio":choice["role"]="body"
    elif bad=="split":decisions["paragraph_partitions"]=[{"paragraph_id":choice["paragraph_id"]}]
    else:
        sibling=next(r for r in snap["paragraphs"] if r["id"]==footer["paragraph_ids"][0])
        sibling["text"]="مرجع 3 / 3"
    if bad=="duplicate":
        with pytest.raises(ValueError,match="source_folio_proof_changed"):spans(values,[footer])
    else:
        assert all(s["page_number"]!=3 for s in spans(values,[footer]))


@pytest.mark.parametrize("text", ["المادة 3 / 3","CASE99/3 3 / 3","desk@example.pt3 / 3",
    "https://service.test/?q=desk@example.pt 3 / 3","desk@example.pt 2 / 3",
    "desk@example.pt 1/3 and 3 / 3","desk@example.pt 3 / 3 extra"])
def test_generic_sources_and_numeric_near_misses_never_create_a_new_owner(tmp_path,text):
    values=contact(tmp_path,text=text)
    assert all(s["page_number"]!=3 for s in spans(values,[values[-1]]))


def test_exact_mutable_attribute_and_proposal_provenance(tmp_path):
    raw,snap,frames,decisions,context,choice,footer=contact(tmp_path)
    W=layout.W
    with ZipFile(BytesIO(raw)) as z:
        root=etree.fromstring(z.read("word/document.xml"))
    nodes={r["id"]:node for r,node in zip(snap["paragraphs"],root.iter(W+"p"),strict=True)}
    mapped={r["id"]:dict(part_uri="word/document.xml") for r in snap["paragraphs"]}
    evidence={"pages":[{"page_number":3,"retained_terminal_associations":{"canonical_proposal_sha256":"7"*64}}]}
    found=layout._inline_folio_expected(nodes,mapped,snap,frames,decisions,context,
                                        accepted_footers=[footer],evidence=evidence)
    chosen=next(s for s in found if s["paragraph_id"]==choice["paragraph_id"])
    assert chosen["canonical_proposal_sha256"]=="7"*64 and len(chosen["separator_runs"])==1
    node=nodes[chosen["paragraph_id"]];original=deepcopy(node)
    change=chosen["separator_runs"][0];run=node.findall(W+"r")[change["run_index"]]
    assert "".join(run.itertext())==" / "
    layout._clock_rtl(run).set(W+"val","0")
    assert layout.model._c14n(layout._verified_inline_folio_copy(node,original,
        next(r for r in snap["paragraphs"] if r["id"]==choice["paragraph_id"]),[chosen]))==layout.model._c14n(original)
    layout._clock_rtl(run).set(W+"val","1")
    with pytest.raises(layout.model.SavedDocxLayoutError,match="source_inline_folio_direction_delta"):
        layout._inline_folio_expected(nodes,mapped,snap,frames,decisions,context,
                                      accepted_footers=[footer],evidence={"pages":[]})


def test_new_identity_inherits_existing_provider_policy_and_keeps_v17():
    old=auto._local_footer_closing_v17_policy().split(":")[1]
    new=auto._contact_folio_v18_policy().split(":")[1]
    assert old!=new and auto._source_folio_inline_direction_version(old)==layout.INLINE_FOLIO_DIRECTION_V1
    assert auto._source_folio_inline_direction_version(new)==layout.INLINE_FOLIO_DIRECTION_V2
    assert auto._terminal_source_layout_versions(old)==auto._terminal_source_layout_versions(new)
    assert auto._proposal_repair_version(old)==auto._proposal_repair_version(new)==reproposal.POLICY_V2
    assert reproposal.automatic_policy(reproposal.POLICY_V2,new)==auto._contact_folio_v18_policy()


def test_normal_start_and_saved_artifact_use_v18_with_same_proposal_requests(tmp_path, monkeypatch):
    from pathlib import Path
    from legalpdf_translate.ordinary_layout_contracts import decode, encode
    from tests import test_ordinary_layout_reproposal as lifecycle

    monkeypatch.setattr(auto,"frozen_automatic_layout_policy",auto._contact_folio_v18_policy)
    lifecycle.isolate_provider(monkeypatch)
    case = lifecycle.normal_start(tmp_path,monkeypatch)
    result = case.job["result"]["automatic_layout"]
    assert result["status"] == "automatic_unreviewed", result
    witness, context = lifecycle.witness_context(case)
    assert len(reproposal.verify_witness(witness, **context)[0]) == 3
    plan = decode((Path(result["output_path"]).parent/"source_map.json").read_bytes())["source_layout_plan"]
    assert plan["inline_folio_direction_version"] == layout.INLINE_FOLIO_DIRECTION_V2
    assert plan["inline_folio_ltr_spans"] == []
    manifest = witness["manifest"]
    v17 = reproposal.expected_policy(3,reproposal.POLICY_V2,auto._local_footer_closing_v17_policy().split(":")[1])
    for number in (1,2,3):
        assert encode(reproposal.page_request(manifest["initial_view"],number,manifest["policy"])) == encode(
            reproposal.page_request(manifest["initial_view"],number,v17))
