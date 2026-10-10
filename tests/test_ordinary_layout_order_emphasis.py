"""Bounded automatic grouping restoration and emphasis-only punctuation edges."""
from copy import deepcopy
import pytest

from legalpdf_translate.ordinary_layout_contracts import _canonical_flow_groups, normalize_proposals, OrdinaryLayoutError
from legalpdf_translate import saved_docx_layout as model
from tests.test_ordinary_layout_contracts import proposal
from tests.test_ordinary_layout_service import make_case
from tests.test_saved_docx_layout import document_bytes


def flow(groups):
    return [{"kind":"flow","groups":[{"paragraph_ids":ids,"panel":False} for ids in groups]}]


def test_complete_ordered_intervals_restore_without_mutating_choices():
    ids = [f"p{i:06}" for i in range(1,7)]
    value = flow([ids[4:],ids[:2],ids[2:4]])
    old = deepcopy(value)
    restored = _canonical_flow_groups(value,ids)
    assert restored == flow([ids[:2],ids[2:4],ids[4:]])
    assert value == old
    assert _canonical_flow_groups(restored,ids) is restored


@pytest.mark.parametrize("groups", [
    [["p000003"],["p000001","p000002"]],
    [["p000004"],["p000001","p000003"],["p000002"]],
    [["p000004"],["p000002","p000001"],["p000003"]],
    [["p000004"],["p000001","p000002"],["p000002","p000003"]],
])
def test_incomplete_interleaved_reversed_duplicate_groups_are_not_repaired(groups):
    value = flow(groups)
    assert _canonical_flow_groups(value,[f"p{i:06}" for i in range(1,5)]) is value


def test_nonhashable_group_identifier_is_left_for_strict_coverage_rejection():
    value=flow([[['p000001']]])
    assert _canonical_flow_groups(value,['p000001']) is value


def test_actual_normalizer_restores_plain_flow_but_rejects_panels(tmp_path,monkeypatch):
    case = make_case(tmp_path,monkeypatch)
    view = case.view['review']; value = proposal(view)
    ids = [p['paragraph_id'] for p in value['paragraphs']]
    value['bands'] = flow([[ids[1]],[ids[0]]])
    snapshot = model.inspect_docx(case.job.reviewed_docx,'EN')
    manual = deepcopy(view['decisions']); manual['bands'] = deepcopy(value['bands'])
    with pytest.raises(model.SavedDocxLayoutError):
        model.validate_decisions(snapshot,view['pages'],manual)
    normalized = normalize_proposals(snapshot,view,[value])
    assert normalized['bands'] == flow([[ids[0]],[ids[1]]])
    assert value['bands'] == flow([[ids[1]],[ids[0]]])
    value['bands'][0]['groups'][0]['panel'] = True
    with pytest.raises(OrdinaryLayoutError,match='proposal_coverage'):
        normalize_proposals(snapshot,view,[value])


@pytest.mark.parametrize('punctuation',[',',',,',';',':','.','!','?',')','”','،','؛','؟'])
def test_emphasis_complete_phrase_before_closing_cluster(punctuation):
    text = 'A complete three words'+punctuation+' follows'
    row = model.inspect_docx(document_bytes((text,)),'EN')['paragraphs'][0]
    span = {'start':2,'end':len('A complete three words'),'bold':True,'italic':False,'underline':False}
    model._emphasis(row,[span])
    assert not model._phrase_edge(text,span['end'])  # partitions stay strict


@pytest.mark.parametrize('text,offset',[
    ('item,123',4),('item,next',4),('12.34',2),('don\'t',3),
    ('name@example',4),('alpha-beta',5),('alpha/beta',5),('alpha_beta',5),
    ('alpha( next',5),('\u0301, next',1),('alpha\u200d, next',6),
])
def test_emphasis_identifier_connector_opening_and_control_edges_reject(text,offset):
    row = model.inspect_docx(document_bytes((text,)),'EN')['paragraphs'][0]
    with pytest.raises(model.SavedDocxLayoutError,match='unsafe_emphasis_boundary'):
        model._emphasis(row,[{'start':0,'end':offset,'bold':True,'italic':False,'underline':False}])
