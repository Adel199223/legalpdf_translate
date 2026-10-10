"""Container limitations never authorize removal of safe source footer text."""
from copy import deepcopy
import pytest
from legalpdf_translate.ordinary_layout_contracts import (
    proposal_source_evidence, OrdinaryLayoutError,
    OPTIONAL_HINT_NORMALIZATION_V1, OPTIONAL_HINT_NORMALIZATION_V2)
from tests.test_ordinary_source_evidence import fixture
from tests.test_optional_layout_hint_recovery import column_rule


def column_footer():
    s, v, p = fixture()
    s['paragraphs'][0]['tokens'] = [{'kind': 't', 'text': 'Reply instruction. Page 1'}]
    p['paragraphs'][0]['role'] = 'body'
    p['bands'] = [{'kind': 'columns', 'cells': [
        {'groups': [{'paragraph_ids': ['p000001'], 'panel': False}]}]}]
    p['source_layout_evidence'] = [{'kind': 'source_footer',
        'paragraph_ids': ['p000001'], 'bbox': [.1, .9, .9, .98]}]
    return s, v, p


def test_safe_column_footer_retains_exact_inputs_and_versioned_review():
    values = column_footer()
    before = deepcopy(values)
    result = proposal_source_evidence(*values)
    assert values == before
    assert result['layout'] == []
    assert result['source_coverage_verified'] is False
    assert result['normalization']['version'] == OPTIONAL_HINT_NORMALIZATION_V2
    assert result['normalization']['rejected_hints'] == [{
        'index': 0, 'kind': 'source_footer', 'paragraph_ids': ['p000001'],
        'reason': 'source_footer_requires_plain_flow'}]
    assert result['normalization']['review_required'] is True


def test_historical_v1_refuses_footer_and_rule_recipe_is_byte_equivalent():
    with pytest.raises(OrdinaryLayoutError, match='invalid_source_layout_evidence'):
        proposal_source_evidence(*column_footer(), normalization_version=OPTIONAL_HINT_NORMALIZATION_V1)
    assert proposal_source_evidence(*column_rule()) == proposal_source_evidence(
        *column_rule(), normalization_version=OPTIONAL_HINT_NORMALIZATION_V1)
    with pytest.raises(OrdinaryLayoutError, match='normalization_version'):
        proposal_source_evidence(*column_footer(), normalization_version='unknown')


@pytest.mark.parametrize('unsafe', ['field', 'numbering', 'tab', 'panel', 'partition', 'role', 'bbox', 'blank', 'unknown_id'])
def test_container_quarantine_runs_after_all_safety_checks(unsafe):
    s, v, p = column_footer()
    row = s['paragraphs'][0]
    if unsafe == 'field': row['has_field'] = True
    elif unsafe == 'numbering': row['has_numbering'] = True
    elif unsafe == 'tab': row['tokens'].append({'kind': 'tab', 'text': '\t'})
    elif unsafe == 'panel': p['bands'][0]['cells'][0]['groups'][0]['panel'] = True
    elif unsafe == 'partition': p['paragraph_partitions'] = [{'paragraph_id': 'p000001'}]
    elif unsafe == 'role': p['paragraphs'][0]['role'] = 'signature'
    elif unsafe == 'bbox': p['source_layout_evidence'][0]['bbox'][1] = .5
    elif unsafe == 'blank': row['tokens'][0]['text'] = ' '
    else: p['source_layout_evidence'][0]['paragraph_ids'] = ['unknown']
    with pytest.raises(OrdinaryLayoutError): proposal_source_evidence(s, v, p)


def test_retained_v1_candidate_bytes_verify_under_new_capability(tmp_path):
    from tests.test_ordinary_auto_layout_artifacts import _candidate_fixture
    from legalpdf_translate.ordinary_auto_layout_artifacts import build_unreviewed_candidate, verify_unreviewed_candidate
    raw, snapshot, frames, decisions, evidence, _ = _candidate_fixture(tmp_path)
    record = proposal_source_evidence(*column_rule(), normalization_version=OPTIONAL_HINT_NORMALIZATION_V1)
    record['page_number'] = 2
    evidence['source_evidence'] = {'version': 'ordinary_source_evidence_v1', 'pages': [record]}
    candidate = build_unreviewed_candidate(raw, snapshot, frames, decisions, proposal_evidence=evidence)
    before = (candidate.docx_bytes, candidate.source_map_bytes, candidate.receipt_bytes)
    verify_unreviewed_candidate(raw, snapshot, frames, decisions, candidate, proposal_evidence=evidence)
    assert before == (candidate.docx_bytes, candidate.source_map_bytes, candidate.receipt_bytes)


def test_mixed_pages_do_not_partially_move_source_footers():
    from tests.test_ordinary_source_layout import multipage_fixture, build, verify
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    from legalpdf_translate.saved_docx_layout import W
    args = multipage_fixture('AR')
    pages = args[4]['source_evidence']['pages']
    pages[1]['layout'] = []
    pages[1]['normalization'] = {'version': OPTIONAL_HINT_NORMALIZATION_V2,
        'canonical_proposal_sha256': 'a'*64, 'review_required': True,
        'rejected_hints': [{'index': 0, 'kind': 'source_footer',
            'paragraph_ids': args[4]['page_groups'][1][1][-2:],
            'reason': 'source_footer_requires_plain_flow'}]}
    artifact = build(args)
    verify(artifact, args)
    with ZipFile(BytesIO(artifact.docx_bytes)) as archive:
        body = etree.fromstring(archive.read('word/document.xml'))
        rendered = [''.join(p.itertext()) for p in body.findall('.//'+W+'p')]
        # No source footer may move when full selected-page evidence is absent.
        for page, ids in args[4]['page_groups']:
            for pid in ids[-2:]:
                raw = next(row for row in args[1]['paragraphs'] if row['id'] == pid)
                text = ''.join(t['text'] for t in raw['tokens'] if t['kind'] == 't')
                assert any(text in value for value in rendered)


def test_terminal_break_in_column_still_fails_full_base_validation(tmp_path):
    from tests.test_ordinary_auto_layout_artifacts import _candidate_fixture
    from tests.test_ordinary_auto_layout_workflow import _proposal
    from legalpdf_translate.ordinary_layout_contracts import normalize_proposals, PROPOSAL_VERSION_V3
    raw, bound, frames, decisions, _, _ = _candidate_fixture(tmp_path)
    snapshot = deepcopy(bound.saved_snapshot)
    view = {'paragraphs': snapshot['paragraphs'], 'pages': frames, 'decisions': decisions}
    proposals = [_proposal(view, page) for page in (2, 3)]
    p = proposals[0]
    ids = [row['paragraph_id'] for row in p['paragraphs']]
    p.update(version=PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[],
        source_layout_evidence=[{'kind': 'source_footer', 'paragraph_ids': [ids[-1]], 'bbox': [.1,.9,.9,.98]}])
    p['paragraphs'][-1]['role'] = 'source_folio'
    p['bands'] = [{'kind': 'columns', 'widths_pct': [50,50], 'gutter_pt':12,
        'cells':[{'groups':[{'paragraph_ids':[pid], 'panel':False}]} for pid in ids]}]
    terminal = next(row for row in snapshot['paragraphs'] if row['id'] == ids[-1])
    terminal['tokens'].append({'kind':'page_break','text':''})
    terminal['has_page_break'] = True
    assert proposal_source_evidence(snapshot, view, p)['normalization']['review_required'] is True
    with pytest.raises(OrdinaryLayoutError): normalize_proposals(snapshot, view, proposals)
