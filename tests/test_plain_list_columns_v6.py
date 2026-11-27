"""Fresh plain list-role columns: exact ownership, no numbering or text repair."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests.test_ordinary_body_columns_v3 import body_case
from tests.test_ordinary_layout_service import make_case, nonce
from tests import test_ordinary_layout_manager as manager_fixture


def list_case(columns=2, mixed=False):
    snapshot, view, proposal = body_case(columns)
    for choice in proposal['paragraphs'][1:9]:
        choice['role'] = 'list'
    if mixed:
        proposal['paragraphs'][2]['role'] = 'body'
        proposal['paragraphs'][3]['role'] = 'reference'
    return snapshot, view, proposal


@pytest.mark.parametrize('columns', [2,3])
@pytest.mark.parametrize('mixed', [False,True])
def test_v6_changes_only_generated_band_and_preserves_every_choice(columns, mixed):
    snapshot, view, proposal = list_case(columns, mixed)
    before = c.encode([snapshot,view,proposal])
    result = c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V6)
    ids = c.page_ids(view,1)
    expected = deepcopy(proposal['bands'])
    expected[1] = {'kind':'flow','groups':[{'paragraph_ids':ids[1:9],'panel':False}]}
    assert result['bands'] == expected
    for source, target in zip(proposal['paragraphs'], result['paragraphs']):
        assert {k:v for k,v in target.items() if k not in {'regions','unmapped_reason'}} == {k:v for k,v in source.items() if k != 'bbox'}
    assert c.encode([snapshot,view,proposal]) == before
    evidence = c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V6)
    assert evidence['metadata_band_normalization']['version'] == c.BAND_NORMALIZATION_V6
    assert evidence['metadata_band_normalization']['rejected_bands'] == [{
        'index':1,'paragraph_ids':ids[1:9],'reason':'generated_plain_columns_restored_to_text_order'}]
    assert evidence['source_coverage_verified'] is False
    model.validate_decisions(snapshot,view['pages'],result)


@pytest.mark.parametrize('version', [None,c.BAND_NORMALIZATION_V1,c.BAND_NORMALIZATION_V2,
    c.BAND_NORMALIZATION_V3,c.BAND_NORMALIZATION_V4,c.BAND_NORMALIZATION_V5])
def test_old_named_band_policies_keep_the_exact_list_coverage_rejection(version):
    snapshot, view, proposal = list_case()
    with pytest.raises(c.OrdinaryLayoutError, match='proposal_coverage'):
        c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=version)


@pytest.mark.parametrize('fault', ['missing','duplicate','foreign','choices_order','choice_key',
    'band_key','cell_key','group_key','empty','panel','width_boolean','width_nan','width_sum',
    'gutter_nan','gutter_range','signature','folio','partition','field','numbering','numPr',
    'page_break','tab','line_break','control','cross_interval','cross_page'])
def test_v6_does_not_rescue_nonplain_or_unowned_list_columns(fault):
    snapshot, view, proposal = list_case()
    band = proposal['bands'][1]
    group = band['cells'][0]['groups'][0]
    raw = snapshot['paragraphs'][1]
    if fault == 'missing': group['paragraph_ids'].pop()
    elif fault == 'duplicate': group['paragraph_ids'][1] = group['paragraph_ids'][0]
    elif fault == 'foreign': group['paragraph_ids'][0] = 'p999999'
    elif fault == 'choices_order': proposal['paragraphs'][1:3] = proposal['paragraphs'][1:3][::-1]
    elif fault == 'choice_key': proposal['paragraphs'][1]['unexpected'] = True
    elif fault == 'band_key': band['unexpected'] = True
    elif fault == 'cell_key': band['cells'][0]['unexpected'] = True
    elif fault == 'group_key': group['unexpected'] = True
    elif fault == 'empty': group['paragraph_ids'] = []
    elif fault == 'panel': group['panel'] = True
    elif fault == 'width_boolean': band['widths_pct'][0] = True
    elif fault == 'width_nan': band['widths_pct'][0] = float('nan')
    elif fault == 'width_sum': band['widths_pct'] = [40,40]
    elif fault == 'gutter_nan': band['gutter_pt'] = float('nan')
    elif fault == 'gutter_range': band['gutter_pt'] = 37
    elif fault == 'signature': proposal['paragraphs'][1]['role'] = 'signature'
    elif fault == 'folio': proposal['paragraphs'][1]['role'] = 'source_folio'
    elif fault == 'partition': proposal['paragraph_partitions'] = [{'paragraph_id':raw['id'],'split_before':['tail']}]
    elif fault == 'field': raw['has_field'] = True
    elif fault == 'numbering': raw['has_numbering'] = True
    elif fault == 'numPr': raw['ppr_xml'] = '<w:numPr/>'
    elif fault == 'page_break': raw['has_page_break'] = True
    elif fault == 'tab': raw['tokens'].append({'kind':'tab','text':'\t'})
    elif fault == 'line_break': raw['tokens'].append({'kind':'line_break','text':'\n'})
    elif fault == 'control': raw['tokens'][0]['text'] += '\u202e'
    elif fault == 'cross_interval':
        group['paragraph_ids'][0],proposal['bands'][0]['groups'][0]['paragraph_ids'][0] = (
            proposal['bands'][0]['groups'][0]['paragraph_ids'][0],group['paragraph_ids'][0])
    elif fault == 'cross_page': view['decisions']['paragraphs'][1]['regions'][0]['page_number'] = 2
    with pytest.raises(c.OrdinaryLayoutError):
        c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V6)


@pytest.mark.parametrize('where', ['direct','normal_style','based_on','default'])
@pytest.mark.parametrize('empty', [False,True])
def test_actual_direct_or_inherited_numbering_never_creates_a_plain_snapshot(where, empty):
    document = Document()
    paragraph = document.add_paragraph('' if empty else 'Fictional numbered row')
    if where == 'direct': props = paragraph._p.get_or_add_pPr()
    elif where == 'normal_style': props = document.styles['Normal'].element.get_or_add_pPr()
    elif where == 'based_on':
        from docx.enum.style import WD_STYLE_TYPE
        parent = document.styles.add_style('Fictional Numbered Parent',WD_STYLE_TYPE.PARAGRAPH)
        child = document.styles.add_style('Fictional Numbered Child',WD_STYLE_TYPE.PARAGRAPH)
        child.base_style = parent
        paragraph.style = child
        props = parent.element.get_or_add_pPr()
    else:
        root = document.styles.element
        defaults = root.find(model.W+'docDefaults')
        pdefault = defaults.find(model.W+'pPrDefault')
        props = pdefault.find(model.W+'pPr')
        if props is None:
            props = OxmlElement('w:pPr');pdefault.append(props)
    props.append(OxmlElement('w:numPr'))
    buffer = BytesIO();document.save(buffer)
    with pytest.raises(model.SavedDocxLayoutError):
        model.inspect_docx(buffer.getvalue(),'EN')


def test_strict_writer_preserves_plain_list_role_text_without_adding_numbering():
    document = Document()
    for index in range(6): document.add_paragraph(f'Fictional field {index}: complete value')
    buffer = BytesIO();document.save(buffer);raw = buffer.getvalue()
    snapshot = model.inspect_docx(raw,'EN')
    pages = [{'page_number':1,'width_px':100,'height_px':100,'image_sha256':'a'*64}]
    seed = model.default_decisions(snapshot,pages)
    for row in seed['paragraphs']:row['regions']=[{'page_number':1,'bbox_px':[10,10,90,90]}]
    view = {'paragraphs':snapshot['paragraphs'],'pages':pages,'decisions':seed}
    choices = [{k:deepcopy(v) for k,v in row.items() if k not in {'regions','unmapped_reason'}}
               | {'role':'list','bbox':[.1,.1,.9,.9]} for row in seed['paragraphs']]
    ids = [row['paragraph_id'] for row in choices]
    proposal = {'version':c.PROPOSAL_VERSION_V3,'page_number':1,'paragraphs':choices,
        'bands':[{'kind':'columns','widths_pct':[50,50],'gutter_pt':12,
                  'cells':[{'groups':[{'paragraph_ids':ids[::2],'panel':False}]},
                           {'groups':[{'paragraph_ids':ids[1::2],'panel':False}]}]}],
        'paragraph_partitions':[],'source_coverage_findings':[],'source_layout_evidence':[]}
    decisions = c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V6)
    result = writer.build_unreviewed_docx(raw,snapshot,pages,decisions)
    writer.validate_built_docx(result.docx_bytes,result.source_map,original_docx=raw,
        snapshot=snapshot,pages=pages,decisions=decisions,require_review=False)
    assert [p['text'] for p in model.inspect_docx(result.docx_bytes,'EN')['paragraphs']] == [p['text'] for p in snapshot['paragraphs']]
    with ZipFile(BytesIO(result.docx_bytes)) as archive:
        assert b'numPr' not in archive.read('word/document.xml')


def test_v6_inherits_reference_footer_hint_rule_and_reports_selected_version():
    from tests.test_reference_footer_hint_v5 import fixture
    snapshot, view, proposal = fixture()
    evidence = c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V6)
    assert evidence['normalization']['band_normalization_version'] == c.BAND_NORMALIZATION_V6
    assert evidence['normalization']['rejected_hints'][0]['reason'] == 'source_footer_reference_kept_in_flow'
    old = c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V5)
    assert old['normalization']['band_normalization_version'] == c.BAND_NORMALIZATION_V5


def test_new_fresh_policy_keeps_exact_historical_closing_recipe_and_all_capabilities():
    old = auto._terminal_closing_group_policy()
    assert old == 'source_image_unreviewed_v1:e1d8a9d167debf3bd910de5ae014c092c2b59768cce34e24d3309fb8d3d40095'
    v6 = auto._plain_list_columns_v6_policy()
    fresh = auto._in_body_terminal_closing_v8_policy()
    assert fresh == 'source_image_unreviewed_v1:e94583acb61d29114e653489cef5be0685dbd640ca8190a8faa70c4b1a6d48fc' and fresh != v6 != old
    for policy, band in [(old,c.BAND_NORMALIZATION_V5),(v6,c.BAND_NORMALIZATION_V6),(auto._terminal_footer_membership_v7_policy(),c.BAND_NORMALIZATION_V7),(fresh,c.BAND_NORMALIZATION_V8)]:
        fingerprint = policy.split(':',1)[1]
        assert auto._band_normalization_version(fingerprint) == band
        assert policy in auto._metadata_normalization_policies() and policy in auto._source_folio_policies()
        assert auto._source_normalization_version(fingerprint) == c.OPTIONAL_HINT_NORMALIZATION_V3
        assert auto._emphasis_normalization_version(fingerprint) == c.EMPHASIS_NORMALIZATION_V2
        assert auto._clock_direction_version(fingerprint) == 'clock_h_colon_ltr_v1'
        assert auto._source_folio_inline_direction_version(fingerprint) == 'source_bound_folio_separator_ltr_v1'
        assert auto._terminal_source_layout_versions(fingerprint) == {
            'source_footer_placement_version':'terminal_body_flow_v1',
            'source_spacing_version':'baseline_metadata_heading_spacing_v1',
            'source_closing_group_version':('bounded_terminal_signature_context_v3' if policy==fresh else 'bounded_terminal_signature_context_v2' if policy==auto._terminal_footer_membership_v7_policy() else 'bounded_terminal_signature_context_v1')}


@pytest.mark.parametrize('band',[c.BAND_NORMALIZATION_V6,c.BAND_NORMALIZATION_V7])
def test_manager_pins_v6_and_replays_without_another_dispatch(tmp_path, monkeypatch,band):
    case = make_case(tmp_path,monkeypatch)
    original = manager_fixture.proposal
    def proposal(view):
        value = original(view)
        value.update(version=c.PROPOSAL_VERSION_V3,paragraph_partitions=[],source_coverage_findings=[],source_layout_evidence=[])
        return value
    monkeypatch.setattr(manager_fixture,'proposal',proposal)
    paid = manager_fixture.enable_paid(case)
    operation = nonce()
    kwargs = dict(expected_baseline_id=case.view['baseline_id'],band_normalization_version=band,
                  emphasis_normalization_version=c.EMPHASIS_NORMALIZATION_V2)
    result = case.manager.suggest(case.job.job_id,case.view['generation'],operation,[1],**kwargs)
    assert result['status'] == 'applied_unreviewed'
    from legalpdf_translate.ordinary_layout_service import _read
    folder = case.manager.service.root / case.job.job_id / 'baselines' / case.view['baseline_id'] / 'suggestions' / operation
    assert _read(folder/'intent.json')['request']['policy']['band_normalization_version'] == band
    assert _read(folder/'proposal_initial_view.json')['band_normalization_version'] == band
    assert case.manager.suggest(case.job.job_id,case.view['generation'],operation,[1],**kwargs) == result
    assert len(paid.calls) == 1
