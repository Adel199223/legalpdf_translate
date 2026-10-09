from copy import deepcopy
import pytest
from legalpdf_translate.ordinary_layout_contracts import normalize_proposals, OrdinaryLayoutError
from legalpdf_translate.saved_docx_layout import inspect_docx
from tests.test_ordinary_layout_contracts import proposal
from tests.test_ordinary_layout_service import make_case


@pytest.mark.parametrize('spacing', [None, 0, 0.0, 1, True, False])
def test_page_boundary_only_null_or_numeric_zero_in_plain_flow(tmp_path, monkeypatch, spacing):
    case = make_case(tmp_path, monkeypatch)
    view = case.view['review']
    snapshot = inspect_docx(case.job.reviewed_docx, 'EN')
    snapshot['paragraphs'][0]['has_page_break'] = True
    value = proposal(view)
    value['paragraphs'][0].update(role='body', heading_level=0, heading_size_pt=None,
        bold=False, alignment='inherit', space_before_pt=spacing, space_after_pt=spacing)
    value['bands'] = [{'kind':'flow','groups':[{'paragraph_ids':[p['paragraph_id'] for p in value['paragraphs']], 'panel':False}]}]
    original = deepcopy(value)
    if spacing is None or type(spacing) in {int,float} and spacing == 0:
        normalize_proposals(snapshot, view, [value])
        for key, changed in [('bold',True), ('alignment','center'), ('space_before_pt',1)]:
            invalid = deepcopy(value); invalid['paragraphs'][0][key] = changed
            with pytest.raises(OrdinaryLayoutError, match='page_break_requires_flow'):
                normalize_proposals(snapshot, view, [invalid])
        invalid=deepcopy(value); invalid['bands'][0]['groups'][0]['panel']=True
        with pytest.raises(OrdinaryLayoutError): normalize_proposals(snapshot,view,[invalid])
        invalid=proposal(view); invalid['paragraphs'][0]=deepcopy(value['paragraphs'][0])
        with pytest.raises(OrdinaryLayoutError): normalize_proposals(snapshot,view,[invalid])
    else:
        with pytest.raises(OrdinaryLayoutError, match='page_break_requires_flow'):
            normalize_proposals(snapshot,view,[value])
    assert value == original
