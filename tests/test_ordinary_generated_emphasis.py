from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from legalpdf_translate.ordinary_layout_contracts import _generated_emphasis, OrdinaryLayoutError, EMPHASIS_NORMALIZATION_V2
from legalpdf_translate.saved_docx_layout import inspect_docx, _emphasis, SavedDocxLayoutError

def row(text="Alpha beta gamma."):
    document=Document();document.add_paragraph(text);stream=BytesIO();document.save(stream)
    return inspect_docx(stream.getvalue(),"EN")["paragraphs"][0]

def span(start,end,**changes):
    return {"start":start,"end":end,"bold":True,"italic":False,"underline":False}|changes


def lrm_row(prefix="نص ",inside="ABC123",suffix=". بقي",marks="\u200e"):
    document=Document();paragraph=document.add_paragraph(prefix)
    paragraph.add_run(marks+inside+marks);paragraph.add_run(suffix)
    stream=BytesIO();document.save(stream)
    value=inspect_docx(stream.getvalue(),"AR")["paragraphs"][0]
    return value,len(prefix),len(prefix)+len(marks+inside+marks)


@pytest.mark.parametrize("prefix,suffix",[("نص ",". بقي"),("", ". بقي"),("نص ","")])
@pytest.mark.parametrize("style",["bold","italic","underline"])
def test_v2_omits_only_complete_single_lrm_owner_with_exact_warning(prefix,suffix,style):
    value,start,end=lrm_row(prefix=prefix,suffix=suffix);before=deepcopy(value)
    original=[span(start,end,bold=style=="bold",italic=style=="italic",underline=style=="underline")]
    rejected=[]
    assert _generated_emphasis(value,original,normalization_version=EMPHASIS_NORMALIZATION_V2,rejected=rejected)==[]
    assert rejected==[{"span":original[0],"reason":"complete_lrm_owner_emphasis_omitted"}]
    assert value==before
    for version in (None,"ordinary_optional_emphasis_normalization_v1"):
        with pytest.raises(OrdinaryLayoutError):_generated_emphasis(value,original,normalization_version=version)
    with pytest.raises(SavedDocxLayoutError):_emphasis(value,original)


def test_v2_keeps_valid_whole_paragraph_lrm_emphasis_and_unrelated_span():
    value,start,end=lrm_row(prefix="",suffix="")
    original=[span(start,end)]
    assert _generated_emphasis(value,original,normalization_version=EMPHASIS_NORMALIZATION_V2)==original
    value,start,end=lrm_row(suffix=". Other body")
    last=span(end+2,len(value["text"]))
    assert _generated_emphasis(value,[span(start,end),last],normalization_version=EMPHASIS_NORMALIZATION_V2)==[last]


@pytest.mark.parametrize("damage",["partial","no_left","no_right","interior_mark","outside_control","other_control","unmatched_scope","two_runs","duplicate_owner","missing_owner","nontext","later_unsafe","later_overlap","later_bad_shape"])
def test_v2_complete_owner_drop_never_hides_unsafe_or_malformed_span(damage):
    value,start,end=lrm_row();styles=[span(start,end)]
    if damage=="partial":styles=[span(start+2,end-1)]
    elif damage=="no_left":styles=[span(start+1,end)]
    elif damage=="no_right":styles=[span(start,end-1)]
    elif damage=="interior_mark":value,start,end=lrm_row(inside="AB\u200eCD");styles=[span(start,end)]
    elif damage=="outside_control":value,start,end=lrm_row(prefix="نص \u200f");styles=[span(start,end)]
    elif damage=="other_control":value,start,end=lrm_row(marks="\u200f");styles=[span(start,end)]
    elif damage=="unmatched_scope":value,start,end=lrm_row(prefix="نص \u2066");styles=[span(start,end)]
    elif damage=="two_runs":
        owner=next(r for r in value["runs"] if (r["start"],r["end"])==(start,end));value["runs"].remove(owner)
        value["runs"].extend([{**owner,"end":start+3},{**owner,"start":start+3}])
    elif damage=="duplicate_owner":value["runs"].append(deepcopy(next(r for r in value["runs"] if (r["start"],r["end"])==(start,end))))
    elif damage=="missing_owner":value["runs"]=[r for r in value["runs"] if (r["start"],r["end"])!=(start,end)]
    elif damage=="nontext":value["tokens"].append({"kind":"tab","start":start,"end":start+1})
    elif damage=="later_unsafe":value,start,end=lrm_row(suffix=" A\u200dB");styles=[span(start,end),span(end+2,end+4)]
    elif damage=="later_overlap":styles.append(span(end-1,end+1))
    else:styles.append(span(end+1,end+2,bold="true"))
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(value,styles,normalization_version=EMPHASIS_NORMALIZATION_V2)


def test_v2_evidence_retains_original_hash_exact_span_and_review_gate():
    from legalpdf_translate.ordinary_layout_contracts import proposal_source_evidence,source_evidence_review_fields,digest,encode
    from tests.test_ordinary_source_evidence import fixture
    snapshot,view,proposal=fixture();actual,start,end=lrm_row();actual["id"]="p000001";snapshot["paragraphs"]=[actual]
    original_span=span(start,end);proposal["paragraphs"][0]["emphasis"]=[original_span];before=deepcopy(proposal)
    evidence=proposal_source_evidence(snapshot,view,proposal,emphasis_normalization_version=EMPHASIS_NORMALIZATION_V2)
    item=evidence["optional_emphasis_normalization"]
    assert item=={"version":EMPHASIS_NORMALIZATION_V2,"canonical_proposal_sha256":digest(encode(proposal)),
        "rejected_spans":[{"paragraph_id":"p000001","span":original_span,"reason":"complete_lrm_owner_emphasis_omitted"}],"review_required":True}
    assert evidence["source_coverage_verified"] is False and source_evidence_review_fields([evidence])["source_layout_review_required"]
    assert proposal==before


@pytest.mark.parametrize("version",["ordinary_layout_proposal_v1","ordinary_layout_proposal_v2"])
@pytest.mark.parametrize("reader",["evidence","crash_recovery"])
@pytest.mark.parametrize("damage",["missing","wrong"])
def test_v2_initial_marker_bound_for_all_supported_response_schemas(tmp_path,monkeypatch,version,reader,damage):
    import json
    from fastapi.testclient import TestClient
    from tests import test_ordinary_auto_layout_workflow as flow
    from legalpdf_translate import ordinary_auto_layout as auto
    from legalpdf_translate.ordinary_layout_service import _read, _write
    original=flow._proposal
    def proposal(*args,**kwargs):
        value=original(*args,**kwargs);value['version']=version
        if version.endswith('v2'):value['paragraph_partitions']=[]
        return value
    monkeypatch.setattr(flow,'_proposal',proposal)
    source=tmp_path/'source.pdf';flow._source(source,('digital',));output=tmp_path/'output';output.mkdir()
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,('Fictional page text.',),(1,))
    with TestClient(app) as client:
        job_id=flow._start(client,source,output,'EN',start=1,end=1,image_mode='off')
        job=flow._wait(jobs,job_id);assert job['result']['automatic_layout']['status']=='automatic_unreviewed'
        pointer=json.loads((Path(job['result']['run_dir'])/'ordinary_auto_layout/operation.json').read_bytes())
        manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        operation=manager.service.root/pointer['origin_job_id']/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        initial_path=operation/'proposal_initial_view.json';record=_read(initial_path)
        assert record['emphasis_normalization_version']==EMPHASIS_NORMALIZATION_V2
        if damage=='missing':record.pop('emphasis_normalization_version')
        else:record['emphasis_normalization_version']='ordinary_optional_emphasis_normalization_v1'
        initial_path.unlink();_write(initial_path,record)
        if reader=='evidence':
            with pytest.raises(OrdinaryLayoutError,match='source_evidence_response_changed'):
                auto._proposal_evidence(manager,pointer['origin_job_id'],pointer['baseline_id'],pointer['review_id'],pointer['operation_nonce'],(1,),auto.frozen_automatic_layout_policy())
        else:
            (operation/'result.json').unlink()
            with pytest.raises(OrdinaryLayoutError,match='source_evidence_response_changed'):
                auto._recover_settled_result(manager,pointer,[1],policy_fingerprint=auto.frozen_automatic_layout_policy().split(':',1)[1])
        assert len(sdk.requests)==len(requests)==1


def test_exact_old_and_new_emphasis_policies_preserve_direction_capabilities():
    from legalpdf_translate import ordinary_auto_layout as auto
    old=auto._inline_folio_direction_policy()
    complete=auto._complete_lrm_emphasis_policy()
    terminal=auto._terminal_source_layout_policy()
    fresh=auto.frozen_automatic_layout_policy()
    assert old=='source_image_unreviewed_v1:7c54ccb193b2fb707fc8164f591f5cb9769e6ab800300be8bda227307dcbf2dd'
    assert complete=='source_image_unreviewed_v1:f60c0c62ac3964ad6231764b98132529fa0afe6b9cb3149bff9145c56d370b58'
    assert terminal=='source_image_unreviewed_v1:98a25bdde6fa1f5b950c3b073653a5fc634fdf6248f4015fa9d13ddfae039099'
    assert fresh=='source_image_unreviewed_v1:e1d8a9d167debf3bd910de5ae014c092c2b59768cce34e24d3309fb8d3d40095'
    for policy in (old,complete,terminal,fresh):
        fingerprint=policy.split(':',1)[1]
        assert auto._band_normalization_version(fingerprint)=='ordinary_metadata_band_normalization_v5'
        assert auto._clock_direction_version(fingerprint)=='clock_h_colon_ltr_v1'
        assert auto._source_folio_inline_direction_version(fingerprint)=='source_bound_folio_separator_ltr_v1'
        assert policy in auto._metadata_normalization_policies() and policy in auto._source_folio_policies()
    assert auto._emphasis_normalization_version(old.split(':',1)[1])=='ordinary_optional_emphasis_normalization_v1'
    for policy in (complete,terminal,fresh):
        assert auto._emphasis_normalization_version(policy.split(':',1)[1])==EMPHASIS_NORMALIZATION_V2
    assert auto._terminal_source_layout_versions(complete.split(':',1)[1])=={}
    assert auto._terminal_source_layout_versions(terminal.split(':',1)[1])=={
        'source_footer_placement_version':'terminal_body_flow_v1',
        'source_spacing_version':'baseline_metadata_heading_spacing_v1'}
    assert auto._terminal_source_layout_versions(fresh.split(':',1)[1])=={
        'source_footer_placement_version':'terminal_body_flow_v1',
        'source_spacing_version':'baseline_metadata_heading_spacing_v1',
        'source_closing_group_version':'bounded_terminal_signature_context_v1'}
    assert auto._emphasis_normalization_version('0'*64) is None


def test_drops_only_word_interior_span_and_preserves_valid_styles():
    original=[span(1,5),span(6,10,italic=True)]
    before=deepcopy(original)
    assert _generated_emphasis(row(),original)==[original[1]]
    assert original==before
    with pytest.raises(SavedDocxLayoutError,match="unsafe_emphasis_boundary"):_emphasis(row(),original)

@pytest.mark.parametrize("invalid",[
    span(1,3,unknown=True),span(True,3),span(1,3,bold=1),span(1,3,bold=False),
    span(-1,3),span(1,999),span(3,3),span(5,3),
])
def test_entire_original_shape_is_rejected_before_filtering(invalid):
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(row(),[invalid])

@pytest.mark.parametrize("spans",[[span(6,8),span(1,3)],[span(1,8),span(6,10)]])
def test_bad_order_or_overlap_is_never_hidden_by_dropping(spans):
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(row(),spans)

@pytest.mark.parametrize("text,start,end",[("A\u200dB value",1,3),("A\u2066B value",1,3)])
def test_nonlexical_or_control_edges_remain_rejected(text,start,end):
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(row(text),[span(start,end)])

def test_protected_identifier_interior_remains_rejected():
    # Existing literal-token protection remains strict even for lexical endpoints.
    document=Document();p=document.add_paragraph("نص ");run=p.add_run("[[AB123456789CD]]")
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    rtl=OxmlElement("w:rtl");rtl.set(qn("w:val"),"0");run._r.get_or_add_rPr().append(rtl)
    stream=BytesIO();document.save(stream);snapshot=inspect_docx(stream.getvalue(),"AR")
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(snapshot["paragraphs"][0],[span(4,8)])

def test_nontext_token_overlap_remains_rejected():
    value=row();value["tokens"].append({"kind":"tab","start":2,"end":3})
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(value,[span(1,5)])

@pytest.mark.parametrize("text",["Alpha beta gamma.","École café fin.","نص عربي طويل"])
def test_optional_interior_drop_never_expands_or_rewrites_text(text):
    value=row(text);before=deepcopy(value)
    assert _generated_emphasis(value,[span(1,len(text))])==[]
    assert value==before


@pytest.mark.parametrize("text,cut", [("الجهة：عنوان", 6), ("Label:Value", 6), ("A/B value", 1), ("A—B value", 1)])
def test_safe_punctuation_edges_drop_optional_styles_without_changing_text(text, cut):
    value = row(text); before = deepcopy(value)
    styles = [span(0, cut), span(cut, len(text), bold=False, underline=True)]
    rejected = []
    assert _generated_emphasis(value, styles, rejected=rejected) == []
    assert len(rejected) == 2
    assert all(item["reason"] == "unsupported_optional_emphasis_edge" for item in rejected)
    assert value == before
    with pytest.raises(OrdinaryLayoutError):
        _generated_emphasis(value, styles, drop_unsupported_edges=False)
    with pytest.raises(SavedDocxLayoutError):
        _emphasis(value, styles)


def test_unsupported_safe_span_does_not_hide_later_control_or_overlap():
    value = row("Label:Value")
    with pytest.raises(OrdinaryLayoutError):
        _generated_emphasis(value, [span(0, 6), span(5, 11)])
    value = row("Label:Value A\u200dB")
    with pytest.raises(OrdinaryLayoutError):
        _generated_emphasis(value, [span(0, 6), span(13, 15)])


def test_emphasis_evidence_is_versioned_reviewable_and_legacy_absence_preserved():
    from legalpdf_translate.ordinary_layout_contracts import proposal_source_evidence, source_evidence_review_fields
    from tests.test_ordinary_source_evidence import fixture
    snapshot, view, proposal = fixture()
    actual = row("Label:Value"); actual["id"] = "p000001"
    snapshot["paragraphs"] = [actual]
    proposal["paragraphs"][0]["emphasis"] = [span(0, 6), span(6, 11)]
    original = deepcopy(proposal)
    result = proposal_source_evidence(snapshot, view, proposal)
    evidence = result["optional_emphasis_normalization"]
    assert evidence["version"] == "ordinary_optional_emphasis_normalization_v1"
    assert len(evidence["rejected_spans"]) == 2
    assert source_evidence_review_fields([result])["source_layout_review_required"] is True
    assert "optional_emphasis_normalization" not in proposal_source_evidence(
        snapshot, view, proposal, emphasis_normalization_version=None)
    assert proposal == original



def test_settled_optional_edge_recovery_has_no_dispatch_and_binds_warning(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from tests import test_ordinary_auto_layout_workflow as flow
    from legalpdf_translate import ordinary_layout_manager as manager_module, ordinary_auto_layout as automatic
    from legalpdf_translate.ordinary_layout_contracts import PROPOSAL_VERSION_V3, normalize_proposals, OrdinaryLayoutError
    from legalpdf_translate.ordinary_layout_service import _read, _write
    original = flow._proposal
    def proposal(view, page, columns=0):
        result = original(view, page, columns)
        result.update(version=PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[], source_layout_evidence=[])
        result['paragraphs'][0]['emphasis'] = [span(0, 6), span(6, 11)]
        return result
    monkeypatch.setattr(flow, '_proposal', proposal)
    source = tmp_path/'source.pdf'; flow._source(source, ('digital',))
    output = tmp_path/'output'; output.mkdir()
    app, jobs, sdk, requests = flow._app(tmp_path, monkeypatch, ('Label:Value\nOther body.',), (1,))
    scope = '?mode=shadow&workspace=fictional'
    with TestClient(app) as client:
        with monkeypatch.context() as historical:
            historical.setattr(manager_module, 'normalize_proposals',
                lambda *args, **kwargs: normalize_proposals(*args, **{**kwargs, 'emphasis_normalization_version': None}))
            job_id = flow._start(client, source, output, 'EN', start=1, end=1, image_mode='off')
            initial = flow._wait(jobs, job_id)
        assert initial['result']['automatic_layout']['status'] == 'raw_fallback'
        manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, 'shadow', 'fictional')
        failed = [_read(path) for path in manager.service.root.rglob('result.json')]
        assert any(item.get('error_code') == 'ordinary_layout_invalid_proposal_decisions' for item in failed)
        prior_cost = manager.layout_costs(job_id)['known_cost_usd']
        provider = manager.provider_factory
        def forbidden(*args):
            value = provider(*args)
            value._client.responses.create = lambda **kwargs: pytest.fail('Retained style recovery must not dispatch')
            return value
        manager.provider_factory = forbidden
        checker = automatic._proposal_evidence
        tampered = []
        def missing_marker(manager, origin, baseline, review, nonce, *args, **kwargs):
            path = manager.service.root/origin/'baselines'/baseline/'suggestions'/nonce/'source_evidence.json'
            before = path.read_bytes(); changed = _read(path)
            changed['pages'][0].pop('optional_emphasis_normalization')
            path.unlink(); _write(path, changed)
            result_path = path.with_name('result.json'); before_result = result_path.read_bytes()
            result = _read(result_path)
            import hashlib
            from legalpdf_translate.ordinary_layout_contracts import encode
            result['source_layout_evidence_sha256'] = hashlib.sha256(encode(changed['pages'])).hexdigest()
            result_path.unlink(); _write(result_path, result)
            try:
                with pytest.raises(OrdinaryLayoutError, match='source_evidence_response_changed'):
                    checker(manager, origin, baseline, review, nonce, *args, **kwargs)
                tampered.append(True)
                raise OrdinaryLayoutError('ordinary_layout_source_evidence_response_changed', 409)
            finally:
                path.write_bytes(before)
                result_path.write_bytes(before_result)
        with monkeypatch.context() as mutation:
            mutation.setattr(automatic, '_proposal_evidence', missing_marker)
            assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
            assert flow._wait(jobs, job_id)['result']['automatic_layout']['status'] == 'raw_fallback'
        assert tampered == [True]
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        final = flow._wait(jobs, job_id)['result']['automatic_layout']
        assert final['status'] == 'automatic_unreviewed', final
        assert final['source_layout_review_required'] is True
        assert len(final['source_layout_rejected_hints']) == 2
        assert all(item['kind'] == 'optional_emphasis' for item in final['source_layout_rejected_hints'])
        from decimal import Decimal
        assert Decimal(final['layout_costs']['known_cost_usd']) == Decimal(prior_cost)
        assert final['layout_costs']['complete'] is True
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        again = flow._wait(jobs, job_id)['result']['automatic_layout']
        assert again['sha256'] == final['sha256']
        assert again['layout_costs'] == final['layout_costs']
        assert again['source_layout_rejected_hints'] == final['source_layout_rejected_hints']
        assert len(requests) == len(sdk.requests) == 1


@pytest.mark.parametrize("version", ["ordinary_layout_proposal_v1", "ordinary_layout_proposal_v2", "ordinary_layout_proposal_v3"])
def test_only_v3_can_drop_new_edges_with_bound_evidence(tmp_path, monkeypatch, version):
    from tests import test_ordinary_layout_service as service
    from tests.test_ordinary_layout_contracts import proposal
    from legalpdf_translate.ordinary_layout_contracts import normalize_proposals
    document = Document(); document.add_paragraph("Label:Value"); document.add_paragraph("Other body.")
    stream = BytesIO(); document.save(stream); raw = stream.getvalue()
    monkeypatch.setattr(service, 'docx_bytes', lambda *args, **kwargs: raw)
    case = service.make_case(tmp_path, monkeypatch)
    view = case.view['review']; value = proposal(view)
    value['version'] = version; value['paragraphs'][0]['emphasis'] = [span(0, 6), span(6, 11)]
    if version != 'ordinary_layout_proposal_v1': value['paragraph_partitions'] = []
    if version == 'ordinary_layout_proposal_v3':
        value.update(source_coverage_findings=[], source_layout_evidence=[])
        result = normalize_proposals(inspect_docx(raw, 'EN'), view, [value])
        assert result['paragraphs'][0]['emphasis'] == []
    else:
        with pytest.raises(OrdinaryLayoutError, match='invalid_proposal_decisions'):
            normalize_proposals(inspect_docx(raw, 'EN'), view, [value])
