"""Exact raw signature-label punctuation, independent keep proofs and history."""
from copy import deepcopy

from lxml import etree
import pytest

from legalpdf_translate import ordinary_terminal_closing_group as closing
from legalpdf_translate import ordinary_terminal_closing_v4 as v4
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests.test_terminal_closing_group import fixture as old_fixture

W = model.W


def fixture():
    args = old_fixture()
    for i, text in [('sign0', 'Witness： ____________________'), ('sign1', 'Interpreter (helper)： ____________________')]:
        node = args[1][i]
        node.find(W+'r/'+W+'t').text = text
        args[3][i]['text'] = text
        args[3][i]['tokens'] = [{'kind': 't', 'text': text}]
    for i, node in args[1].items():
        args[3][i]['paragraph_sha256'] = model._sha(model._c14n(node).encode())
    args[6]['footer_placement'] = 'terminal_body_flow_v1'
    return args


def test_grammar_preserves_exact_fullwidth_delimiter_and_parenthetical_spans():
    text = '  Interpreter (helper)： ______  '
    result = v4.placeholder(text)
    assert result and text[result['delimiter_span']['start']:result['delimiter_span']['end']] == '：'
    assert text[result['label_span']['start']:result['label_span']['end']] == 'Interpreter (helper)'
    assert v4.placeholder('______')['label_span'] is None
    assert v4.placeholder('Witness: ______')


def test_derive_and_full_xml_inverse_preserve_explicit_false_and_prior_property_order():
    args = fixture()
    root, nodes, mapped, rows, choices, owners, plan, members = args
    for name in ['keepNext', 'keepLines']:
        etree.SubElement(nodes['sign0'].find(W+'pPr'), W+name).set(W+'val', 'false')
    original = deepcopy(root)
    pre_nodes = {i: original.xpath(root.getroottree().getpath(n), namespaces=v4.NS)[0] for i, n in nodes.items()}
    before = {'root': original, 'nodes': pre_nodes, 'mapped': deepcopy(mapped), 'members': members}
    assert closing.derive(*args, version=closing.VERSION_V3) == []
    closing.apply(*args, version=v4.VERSION, base_context={})
    assert plan['source_closing_groups'][0]['kind'] == v4.KIND
    closing.verify(root, {'paragraphs': list(mapped.values())}, rows, choices, owners, plan, members,
        base_context={}, pre_closing_context=before)
    assert model._c14n(original) == model._c14n(before['root'])


def writer_case():
    from tests.test_saved_docx_layout import document_bytes, reviewed
    from legalpdf_translate.docx_writer import _configure_styles, _add_page_number_footer
    raw = document_bytes(['Earlier substantive source.', 'Complete closing context one.', 'Complete closing context two.',
        'Witness： ____________________', 'Interpreter (helper)： ____________________', 'Prepared automatically.', '1 / 1'],
        lambda doc: (_configure_styles(doc, 'EN'), _add_page_number_footer(doc, 'EN')))
    snapshot, pages, decisions = reviewed(raw, 'EN')
    ids = [r['id'] for r in snapshot['paragraphs']]
    decisions['review'].update(document_reviewed=False, pages_reviewed=[], reviewer='', note='')
    decisions['bands'] = [{'kind': 'flow', 'groups': [{'paragraph_ids': [i], 'panel': False}]} for i in ids]
    for index, row in enumerate(decisions['paragraphs']):
        row.update(role='institution' if index == 0 else 'signature' if index in (3, 4) else 'source_folio' if index == 6 else 'body',
            regions=[{'page_number': 1, 'bbox_px': [100, 100, 800, 200]}])
    from legalpdf_translate import ordinary_layout_contracts as contracts
    frame = pages[0]
    for row in decisions['paragraphs'][-2:]:
        row['regions'][0]['bbox_px'] = [.2*frame['width_px'], .92*frame['height_px'], .8*frame['width_px'], .96*frame['height_px']]
    proposal = {'version': contracts.PROPOSAL_VERSION_V3, 'page_number': 1, 'paragraphs': [],
        'bands': deepcopy(decisions['bands']), 'paragraph_partitions': [], 'source_coverage_findings': [],
        'source_layout_evidence': [{'kind': 'source_footer', 'paragraph_ids': ids[-2:], 'bbox': [.1, .9, .9, .98]}]}
    for row in decisions['paragraphs']:
        choice = deepcopy(row); region = choice.pop('regions')[0]; choice.pop('unmapped_reason')
        choice['bbox'] = [v/(frame['width_px'] if i % 2 == 0 else frame['height_px']) for i, v in enumerate(region['bbox_px'])]
        proposal['paragraphs'].append(choice)
    view = {'paragraphs': snapshot['paragraphs'], 'pages': pages, 'decisions': decisions}
    record = contracts.proposal_source_evidence(snapshot, view, proposal, band_normalization_version=contracts.BAND_NORMALIZATION_V8)
    evidence = {'version': 'ordinary_source_evidence_v1', 'pages': [record]}
    context = {'selected_pages': [1], 'page_groups': [[1, ids]], 'source_evidence': evidence,
        'source_footer_placement_version': 'terminal_body_flow_v1', 'source_spacing_version': 'baseline_metadata_heading_spacing_v1',
        'source_closing_group_version': v4.VERSION}
    return raw, snapshot, pages, decisions, context


def test_strict_writer_reconstructs_full_preclosing_state_and_old_v3_abstention():
    args = writer_case()
    result = writer.build_unreviewed_docx(*args[:4], ordinary_context=args[4])
    writer.validate_built_docx(result.docx_bytes, result.source_map, original_docx=args[0], snapshot=args[1], pages=args[2],
        decisions=args[3], require_review=False, ordinary_context=args[4])
    assert len(result.source_map['source_layout_plan']['source_closing_groups']) == 1
    args[4]['source_closing_group_version'] = closing.VERSION_V3
    old = writer.build_unreviewed_docx(*args[:4], ordinary_context=args[4])
    assert old.source_map['source_layout_plan']['source_closing_groups'] == []


@pytest.mark.parametrize('text', ['Name ______', 'Name:: ______', 'Name：x ______', 'Name 2： ______',
    'Name\t： ______', 'Name\u00a0： ______', 'Name\u200e： ______', 'Name\n： ______',
    'Name ((helper))： ______', 'Name ()： ______', '(helper)： ______', '\u0301： ______',
    'Name (\u0301)： ______', 'Name (help)： ___ ___', 'Name： __', 'Name： ______ tail',
    'Name!： ______', 'Name： ' + '_'*1601])
def test_raw_grammar_declines_unsupported_whole_representations(text):
    assert v4.placeholder(text) is None


@pytest.mark.parametrize('fault', ['body_role', 'missing_footer', 'retained_only', 'cross_page', 'part',
    'field', 'page_break', 'incoming', 'outgoing', 'nonadjacent', 'ascii_only', 'snapshot_text_changed'])
def test_group_ownership_is_required_beyond_signature_looking_text(fault):
    args = fixture()
    root, nodes, mapped, rows, choices, owners, plan, members = args
    if fault == 'body_role': choices['sign0']['role'] = 'body'
    elif fault == 'missing_footer': plan['source_footers'] = []
    elif fault == 'retained_only':
        plan['retained_terminal_associations'] = deepcopy(plan['source_footers']); plan['source_footers'] = []
    elif fault == 'cross_page': owners[2] = ['sign0']
    elif fault == 'part': mapped['sign0']['parts'] = [{'location': 'foreign'}]
    elif fault == 'field': rows['sign0']['has_field'] = True
    elif fault == 'page_break': etree.SubElement(nodes['sign0'].find(W+'pPr'), W+'pageBreakBefore')
    elif fault == 'incoming': etree.SubElement(nodes['outside'].find(W+'pPr'), W+'keepNext')
    elif fault == 'outgoing': etree.SubElement(nodes['folio'].find(W+'pPr'), W+'keepNext')
    elif fault == 'nonadjacent': root.find(W+'body').insert(4, etree.Element(W+'p'))
    elif fault == 'ascii_only':
        for i in ('sign0', 'sign1'):
            rows[i]['text'] = rows[i]['text'].replace('：', ':'); nodes[i].find(W+'r/'+W+'t').text = rows[i]['text']
    else: rows['sign0']['text'] += ' '
    assert v4.derive(*args) == []


@pytest.mark.parametrize('fault', ['page_float', 'span_bool', 'extra_proof', 'missing_property', 'extra_end_link',
    'property_attributes', 'unrelated_delta', 'mapping'])
def test_independent_actual_group_and_inverse_reject_forgery(fault):
    args = fixture()
    root, nodes, mapped, rows, choices, owners, plan, members = args
    oldroot = deepcopy(root)
    oldnodes = {i: oldroot.xpath(root.getroottree().getpath(n), namespaces=v4.NS)[0] for i, n in nodes.items()}
    before = {'root': oldroot, 'nodes': oldnodes, 'mapped': deepcopy(mapped), 'members': members}
    closing.apply(*args, version=v4.VERSION, base_context={})
    mapping = {'paragraphs': deepcopy(list(mapped.values()))}
    record = plan['source_closing_groups'][0]
    if fault == 'page_float': record['source_page_number'] = 1.0
    elif fault == 'span_bool': record['placeholder_proofs'][0]['label_span']['start'] = False
    elif fault == 'extra_proof': record['placeholder_proofs'][0]['extra'] = True
    elif fault == 'missing_property': nodes['sign0'].find(W+'pPr').remove(nodes['sign0'].find(W+'pPr/'+W+'keepLines'))
    elif fault == 'extra_end_link': etree.SubElement(nodes['folio'].find(W+'pPr'), W+'keepNext')
    elif fault == 'property_attributes': nodes['sign0'].find(W+'pPr/'+W+'keepNext').set(W+'val', '0')
    elif fault == 'unrelated_delta': etree.SubElement(nodes['outside'].find(W+'pPr'), W+'keepLines')
    else: mapping['paragraphs'][0]['location'] = '/w:document/w:body/w:missing'
    with pytest.raises(ValueError):
        closing.verify(root, mapping, rows, choices, owners, plan, members, base_context={}, pre_closing_context=before)


@pytest.mark.parametrize('retained', [False, True])
def test_V4_delegates_both_complete_old_V3_branches_without_package_changes(retained):
    if retained:
        from tests.test_in_body_terminal_closing_v8 import fixture as retained_fixture
        args = retained_fixture()
    else:
        args = list(writer_case())
        # Build a genuine ASCII fixture rather than editing a frozen snapshot.
        from tests.test_terminal_closing_group import writer_fixture
        args = list(writer_fixture())
        from legalpdf_translate.ordinary_layout_contracts import RETAINED_TERMINAL_ASSOCIATIONS_V1
        args[4]['source_evidence']['pages'][0]['retained_terminal_associations'] = {
            'version': RETAINED_TERMINAL_ASSOCIATIONS_V1, 'canonical_proposal_sha256': 'a'*64,
            'associations': [], 'review_required': True}
    args[4]['source_closing_group_version'] = closing.VERSION_V3
    old = writer.build_unreviewed_docx(*args[:4], ordinary_context=args[4])
    args[4]['source_closing_group_version'] = v4.VERSION
    new = writer.build_unreviewed_docx(*args[:4], ordinary_context=args[4])
    assert new.docx_bytes == old.docx_bytes
    assert new.source_map['source_layout_plan']['source_closing_groups'] == old.source_map['source_layout_plan']['source_closing_groups']
    assert new.source_map['source_layout_plan']['source_closing_structural_additions'] == old.source_map['source_layout_plan']['source_closing_structural_additions']


def test_genuine_fresh_V16_empty_group_start_binds_mode_and_reuses_saved_candidate(tmp_path, monkeypatch):
    import json
    import os
    from pathlib import Path
    from legalpdf_translate import ordinary_auto_layout as auto, ordinary_layout_reproposal as attempts
    from legalpdf_translate.ordinary_layout_contracts import decode
    from tests import test_ordinary_layout_reproposal as lifecycle
    lifecycle.isolate_provider(monkeypatch)
    # This existing saved-identity oracle owns the concrete V16 origin.
    monkeypatch.setattr(auto,'frozen_automatic_layout_policy',auto._bounded_signature_label_v16_policy)
    assert auto.frozen_automatic_layout_policy() == auto._bounded_signature_label_v16_policy()
    case = lifecycle.normal_start(tmp_path, monkeypatch)
    result = case.job['result']['automatic_layout']
    assert result['status'] == 'automatic_unreviewed', result
    witness, context = lifecycle.witness_context(case)
    assert len(attempts.verify_witness(witness, **context)[0]) == 3
    mapping = decode((Path(result['output_path']).parent/'source_map.json').read_bytes())
    assert mapping['source_layout_plan']['source_closing_group_version'] == v4.VERSION
    assert mapping['source_layout_plan']['source_closing_groups'] == []  # Identity/replay route, not new-group coverage.
    before = {p: p.read_bytes() for p in case.operation.rglob('*') if p.is_file() and p.suffix != '.lock'}
    reused = auto.run_completed_unreviewed_rebuild(case.manager, case.app.state.ordinary_layouts._accounting, case.job['job_id'])
    assert reused['reused_durable_candidate'] and reused['sha256'] == result['sha256'] and len(case.calls) == 3
    assert all(p.read_bytes() == raw for p, raw in before.items())
    index = os.environ.get('CLOSING_V16_SPECIMEN_INDEX')
    if index:
        Path(index).write_text(json.dumps({'job': case.job, 'operation': str(case.operation), 'pointer': case.pointer,
            'baseline': case.baseline, 'layout_requests': case.calls, 'new_group_count': 0,
            'qualification': 'genuine fresh normalStart saved V16/witness/strict/reuse; new group covered separate generic retained writer'},
            ensure_ascii=False, indent=2, default=str), encoding='utf-8')
