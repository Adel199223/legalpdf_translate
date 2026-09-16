"""Synthetic public place/header fixtures; no private response text is copied."""
from dataclasses import FrozenInstanceError, replace

import pytest

from legalpdf_translate.glossary import (
    GlossaryEntry, default_ar_entries, default_en_entries, default_fr_entries,
)
from legalpdf_translate.structured_glossary import (
    BlockGlossaryContract, StructuredGlossaryError, build_structured_glossary as build,
    verified_glossary_literal_spans,
)
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError, prepare_structured_arabic_source as prepare,
    normalize_structured_arabic_translation as normalize,
)
from legalpdf_translate.validators import validate_ar


def row(source, target, *, tier=1, language='PT', mode='exact'):
    return GlossaryEntry(source, target, mode, language, tier)


def blocks(*texts):
    return [{'id': f'p0001_b{index:04d}', 'text': text} for index, text in enumerate(texts, 1)]


def contract(source, entries=(), **options):
    result = build(blocks(source), list(entries), target_lang='AR', **options)
    return result, result.for_block('p0001_b0001')


def accepted(source, translated, entries=()):
    glossary, proof = contract(source, entries)
    prepared = prepare(source, glossary_contract=proof)
    normalized = normalize(prepared, translated, glossary_contract=proof)
    assert validate_ar(normalized).ok
    assert prepare(prepared, glossary_contract=proof) == prepared
    assert normalize(prepared, normalized, glossary_contract=proof) == normalized
    return glossary, prepared, normalized


def test_dynamic_institutional_header_literal_is_exact_without_configured_city_row():
    source = 'Ministério Público - Procuradoria da República da Comarca de Évora'
    glossary, prepared, translated = accepted(source, 'النيابة العامة - نيابة الجمهورية لدائرة Évora')
    assert len(glossary.entries) == 1
    assert '[[Évora]]' in prepared and '\u2066[[Évora]]\u2069' in translated
    assert 'Évora' in glossary.prompt_text
    # Without the explicit glossary contract the old strict path remains closed.
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), 'النيابة العامة في Évora')


def test_dynamic_sections_retain_actual_separator_spacing_and_ordinal_source():
    source = 'Procuradoria do Juízo Local Criminal- 1ª Sec Inquéritos de Beja'
    glossary, prepared, normalized = accepted(source,
        'نيابة الدائرة الجنائية المحلية - القسم 1 وحدة التحقيقات في Beja')
    assert [entry.source_text for entry in glossary.entries] == [
        'Procuradoria do Juízo Local Criminal- 1ª Sec', 'Inquéritos de Beja']
    assert '[[1]]ª' in prepared and '[[Beja]]' in prepared
    assert '[[1]]' in normalized and '[[Beja]]' in normalized


@pytest.mark.parametrize('place', ['Beja', 'Évora', 'Castelo Branco', 'Vila Nova de Famalicão'])
def test_source_recognized_places_are_coherent_exact_runs(place):
    source = f'Tribunal Judicial da Comarca de {place}'
    _, prepared, normalized = accepted(source, f'المحكمة القضائية لدائرة {place}')
    assert f'[[{place}]]' in prepared and f'\u2066[[{place}]]\u2069' in normalized


@pytest.mark.parametrize('wrong', ['Evora', 'ÉvoraX', 'ÉVORA', 'Porto', 'Évora Évora'])
def test_city_changes_and_duplication_fail_without_fuzzy_repair(wrong):
    source = 'Tribunal Judicial da Comarca de Évora'
    _, proof = contract(source)
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source, glossary_contract=proof), f'المحكمة في {wrong}', glossary_contract=proof)


def test_two_city_order_count_and_block_binding_stay_exact():
    source = 'Inquéritos de Évora; Inquéritos de Beja'
    glossary, proof = contract(source)
    assert len(glossary.entries) == 2
    prepared = prepare(source, glossary_contract=proof)
    for translation in ('التحقيقات Beja؛ التحقيقات Évora', 'التحقيقات Évora', 'التحقيقات Évora Évora Beja'):
        with pytest.raises(StructuredArabicLiteralError):
            normalize(prepared, translation, glossary_contract=proof)
    with pytest.raises(StructuredGlossaryError, match='changed_block_glossary_contract'):
        prepare('Inquéritos de Beja', glossary_contract=proof)


def test_only_block_relevant_tiers_and_languages_enter_prompt():
    rows = [row('arguido', 'المتهم', tier=2), row('prazo', 'الأجل', tier=2),
            row('honorários', 'الأتعاب', tier=1), row('arguido', 'متهم', tier=3),
            row('arguido', 'étranger', language='FR')]
    glossary = build(blocks('O arguido tem um prazo.', 'Sem relação.'), rows, target_lang='AR')
    assert {entry.source_text for entry in glossary.entries} == {'arguido', 'prazo'}
    assert len(glossary.for_block('p0001_b0001').entries) == 2
    assert glossary.for_block('p0001_b0002').entries == ()
    assert 'honorários' not in glossary.prompt_text and 'étranger' not in glossary.prompt_text
    assert len(build(blocks('O arguido.'), rows, target_lang='AR', enabled_tiers=[1]).entries) == 0


def test_exact_relevance_never_strips_accents_changes_case_or_matches_inside_words():
    entries = [row('arguido', 'المتهم'), row('réu', 'المتهم'), row('AÇÃO', 'الدعوى')]
    glossary = build(blocks('arguidos reu ação'), entries, target_lang='AR')
    assert glossary.entries == () and glossary.prompt_text == ''


def test_known_citation_alias_uses_actual_source_spelling_without_consuming_label():
    rows = [row('p. e p. pelos artigos', 'المنصوص والمعاقب عليها بموجب المواد', tier=2),
            row('alínea', 'الفقرة', tier=2), row('n.º', 'رقم', tier=2)]
    glossary = build(blocks('Factos p. e p. pelos arts. 15, al. a), n.º 2'), rows, target_lang='AR')
    assert {entry.source_text for entry in glossary.entries} == {'p. e p. pelos arts.', 'al.', 'n.º'}
    assert 'al. a)' not in glossary.prompt_text
    assert all(entry.tier == 1 for entry in glossary.entries)


@pytest.mark.parametrize('target_lang,target', [('AR', 'رقم'), ('FR', 'nº'), ('EN', 'No.')])
@pytest.mark.parametrize('term', ['nº', 'n°', 'no', 'Nº', 'N.º', 'n. o'])
@pytest.mark.parametrize('separator', [' ', '   ', '\u00a0', '\t', '\n'])
def test_ordinal_alias_excludes_only_separator_from_exact_source_term(target_lang, target, term, separator):
    source = f'Referência: {term}{separator}27'
    source_blocks = blocks(source)
    configured = [row('n.º', target, tier=2)]
    glossary = build(source_blocks, configured, target_lang=target_lang)
    assert glossary.entries == (row(term, target, tier=1),)
    assert glossary.for_block('p0001_b0001').entries == glossary.entries
    assert source_blocks == blocks(source)
    assert configured == [row('n.º', target, tier=2)]
    assert source[len('Referência: ') + len(term):] == separator + '27'


def test_ordinal_alias_does_not_override_ambiguous_arabic_list_label_contract():
    # A line-initial "n. " is also a protected enumerator. Do not erase it by
    # treating the entire spaced alias as a term with no preserved literal.
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
        contract('n. o 27', [row('n.º', 'رقم', tier=2)])


def test_ordinal_alias_repeated_variants_dedupe_without_consuming_numbers_or_literals():
    source = 'nº 2; nº 3; N° 27; às 09:30'
    glossary, prepared, normalized = accepted(source,
        'رقم 2؛ رقم 3؛ رقم 27؛ في 09:30', [row('n.º', 'رقم', tier=2)])
    assert [entry.source_text for entry in glossary.entries] == ['nº', 'N°']
    for literal in ('2', '3', '27', '09', '30'):
        assert prepared.count(f'[[{literal}]]') == 1
        assert normalized.count(f'\u2066[[{literal}]]\u2069') == 1
    assert '[[09]]:[[30]]' in prepared
    assert '\u2066[[09]]\u2069:\u2066[[30]]\u2069' in normalized


@pytest.mark.parametrize('source,expected', [
    ('n.º 2', ['n.º']), ('n.º\t2', ['n.º']),
    # Characterize existing canonical precedence and compact-term boundaries.
    # The separator repair must not silently widen either matching contract.
    ('n.º 2; nº 3', ['n.º']), ('nº2', []), ('no2', []), ('n.º2', []),
    ('n°2', ['n°']), ('anº 2', []), ('_nº 2', []), ('nºx 2', []),
    ('nº', []), ('nº fim', []), ('(nº 2)', ['nº']), ('nº 2.', ['nº']),
])
def test_ordinal_alias_keeps_existing_recognizer_and_exact_match_boundaries(source, expected):
    glossary = build(blocks(source), [row('n.º', 'No.', tier=2)], target_lang='EN')
    assert [entry.source_text for entry in glossary.entries] == expected


@pytest.mark.parametrize('source,tiers,expected', [
    ('nº 2', [1], [('nº', 1)]), ('nº 2', [2], []),
    ('n.º 2', [1], [('n.º', 1)]), ('n.º 2', [2], [('n.º', 2)]),
])
def test_ordinal_alias_preserves_priority_and_enabled_tiers(source, tiers, expected):
    glossary = build(blocks(source), [row('n.º', 'No.', tier=2)], target_lang='EN', enabled_tiers=tiers)
    assert [(entry.source_text, entry.tier) for entry in glossary.entries] == expected


@pytest.mark.parametrize('configured_lang,source_lang', [
    ('FR', 'PT'), ('EN', 'PT'), ('AUTO', 'PT'), ('ANY', 'PT'),
    ('PT', 'FR'), ('PT', 'EN'), ('PT', 'AUTO'),
])
def test_ordinal_alias_does_not_expand_non_portuguese_configuration(configured_lang, source_lang):
    glossary = build(blocks('nº 2'), [row('n.º', 'No.', tier=2, language=configured_lang)],
                     target_lang='EN', source_lang=source_lang)
    assert glossary.entries == ()


@pytest.mark.parametrize('invalid_term', ['n.º ', ' n.º', 'n.º\t', 'n.º\n', 'n.\to', 'n.\no', 'n\u202eº'])
def test_ordinal_separator_fix_never_cleans_invalid_configured_entries(invalid_term):
    with pytest.raises(StructuredGlossaryError, match='invalid_structured_glossary_entry'):
        build(blocks('nº 2'), [row(invalid_term, 'No.')], target_lang='EN')


@pytest.mark.parametrize('source,target', [
    ('Inquéritos de Beja', 'وحدة التحقيقات في Porto'),
    ('Inquéritos de Évora', 'وحدة التحقيقات في Evora'),
    ('Prazo de pagamento', 'Prazo de pagamento'),
    ('O requerente deve pagar', 'deve دفع المبلغ'),
    ('Obrigação', 'الالتزام XYZ'),
    ('Montante 12 EUR', 'المبلغ 13 EUR'),
])
def test_incompatible_glossary_fails_before_model_output_exists(source, target):
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract|conflicting_structured_glossary_entries'):
        contract(source, [row(source, target)])


def test_place_must_be_grounded_in_matching_source_phrase_not_elsewhere_on_page():
    source = 'Inquéritos de Évora; Obrigação'
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
        contract(source, [row('Obrigação', 'الالتزام Évora')])
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
        build(blocks('Inquéritos de Évora', 'Obrigação'), [row('Obrigação', 'الالتزام Évora')], target_lang='AR')


def test_header_like_prose_cannot_be_blessed_as_city_or_name():
    for source in ('Inquéritos de Deve Pagar', 'Inquéritos de Beja deve pagar', 'Inquéritos de Justiça'):
        with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
            contract(source)


def test_configured_header_precedence_preserves_custom_pair_and_identical_duplicates():
    # Approved precedence change: a synthesized header is a fallback, not a
    # competing configured preference. Conflicting configured rows stay errors.
    source = 'Inquéritos de Évora'
    custom = row(source, 'تحقيق خاص في Évora')
    chosen, _ = contract(source, [custom])
    duplicated, _ = contract(source, [custom, custom])
    assert chosen.entries == duplicated.entries == (custom,)
    assert chosen.fingerprint == duplicated.fingerprint
    original, _ = contract(source)
    duplicate, _ = contract(source, [original.entries[0], original.entries[0]])
    assert original.entries == duplicate.entries and original.fingerprint == duplicate.fingerprint


@pytest.mark.parametrize('source', ['audiência de julgamento', 'Audiência de julgamento'])
@pytest.mark.parametrize('lang,defaults,lower,capitalized', [
    ('FR', default_fr_entries, 'audience de jugement', 'Audience de jugement'),
    ('EN', default_en_entries, 'trial hearing', 'Trial hearing'),
    ('AR', default_ar_entries, 'جلسة المحاكمة', 'جلسة المحاكمة'),
])
def test_configured_header_precedence_preserves_public_preset_case(source, lang, defaults, lower, capitalized):
    configured = defaults()
    before = list(configured)
    source_blocks = blocks(source)
    result = build(source_blocks, configured, target_lang=lang)
    expected = lower if source[0].islower() else capitalized
    assert result.entries == (row(source, expected, tier=2),)
    assert result.for_block('p0001_b0001').entries == result.entries
    assert configured == before and source_blocks == blocks(source)


@pytest.mark.parametrize('tier,mode,language', [
    (3, 'contains', 'PT'), (1, 'exact', 'AUTO'), (2, 'contains', 'ANY'),
])
def test_configured_header_precedence_keeps_exact_custom_metadata(tier, mode, language):
    source = 'audiência de julgamento'
    custom = row(source, 'AUDIENCE choisie', tier=tier, mode=mode, language=language)
    result = build(blocks(source), [custom], target_lang='FR', enabled_tiers=[1, 2, 3])
    assert result.entries == (custom,)
    assert result.for_block('p0001_b0001').entries == (custom,)
    assert 'AUDIENCE choisie' in result.prompt_text


def test_configured_header_precedence_keeps_sorted_same_target_duplicate_metadata():
    source = 'audiência de julgamento'
    lower_priority = row(source, 'Chosen hearing', tier=2, language='PT')
    first = row(source, 'Chosen hearing', tier=1, mode='contains', language='ANY')
    tied = replace(first, match_mode='exact', source_lang='AUTO')
    result = build(blocks(source), [lower_priority, first, tied], target_lang='EN')
    assert result.entries == (first,)
    reversed_tie = build(blocks(source), [lower_priority, tied, first], target_lang='EN')
    assert reversed_tie.entries == (tied,)


@pytest.mark.parametrize('other', [
    row('audiência de julgamento', 'Second choice', tier=1),
    row('audiência de julgamento', 'Second choice', tier=2, mode='contains', language='ANY'),
])
def test_configured_header_precedence_never_resolves_conflicting_configured_rows(other):
    configured = [row('audiência de julgamento', 'First choice', tier=2), other]
    with pytest.raises(StructuredGlossaryError, match='^conflicting_structured_glossary_entries$'):
        build(blocks('audiência de julgamento'), configured, target_lang='FR')


@pytest.mark.parametrize('invalid', [
    row('audiência de julgamento ', 'Invalid disabled term', tier=6),
    row('audiência de julgamento', 'Invalid\nwrong-language target', language='FR'),
    row('absent term', '', tier=6, language='FR'),
])
def test_configured_header_precedence_still_validates_invalid_inactive_rows(invalid):
    with pytest.raises(StructuredGlossaryError, match='^invalid_structured_glossary_entry$'):
        build(blocks('audiência de julgamento'), [invalid], target_lang='FR')


@pytest.mark.parametrize('inactive', [
    row('audiência de julgamento', 'Disabled choice', tier=6),
    row('audiência de julgamento', 'Wrong-language choice', language='FR'),
    row('Audiência de julgamento', 'Different-case choice'),
    row('audiencia de julgamento', 'Different-accent choice'),
    row('audiência de julgamentox', 'Nonmatching choice'),
])
def test_configured_header_precedence_ineligible_rows_leave_header_fallback(inactive):
    source = 'audiência de julgamento'
    fallback = build(blocks(source), [], target_lang='FR')
    result = build(blocks(source), [inactive], target_lang='FR')
    assert result.entries == (row(source, 'Audience de jugement', tier=2),)
    assert result.fingerprint == fallback.fingerprint


def test_configured_header_precedence_shorter_matching_phrase_does_not_hide_full_header():
    source = 'audiência de julgamento'
    shorter = row('julgamento', 'Judgment', tier=2)
    result = build(blocks(source), [shorter], target_lang='EN')
    assert result.entries == (row(source, 'Trial hearing', tier=2), shorter)


def test_configured_header_precedence_does_not_change_alias_priority_or_alias_conflicts():
    source = 'audiência de julgamento; nº 2'
    preferred = row('audiência de julgamento', 'Chosen hearing', tier=2)
    canonical = row('n.º', 'Number', tier=2)
    result = build(blocks(source), [preferred, canonical], target_lang='EN')
    assert set(result.entries) == {preferred, row('nº', 'Number', tier=1)}
    # Exact configured source preference overrides headers only, not a genuine
    # conflict with the independently derived citation alias.
    with pytest.raises(StructuredGlossaryError, match='^conflicting_structured_glossary_entries$'):
        build(blocks(source), [preferred, canonical, row('nº', 'Other number', tier=2)], target_lang='EN')


@pytest.mark.parametrize('source_lang', ['EN', 'FR', 'AUTO'])
def test_configured_header_precedence_keeps_non_portuguese_behavior(source_lang):
    source = 'audiência de julgamento'
    custom = row(source, 'Explicit source-language choice', tier=2, language=source_lang)
    assert build(blocks(source), [], target_lang='FR', source_lang=source_lang).entries == ()
    result = build(blocks(source), [custom], target_lang='FR', source_lang=source_lang)
    assert result.entries == (custom,)


def test_configured_header_precedence_remains_bound_to_arabic_literals_and_fingerprint():
    source = 'Inquéritos de Évora'
    custom = row(source, 'تحقيق خاص في Évora')
    result, prepared, translated = accepted(source, custom.preferred_translation, [custom])
    assert '[[Évora]]' in prepared and '\u2066[[Évora]]\u2069' in translated
    changed, _ = contract(source, [replace(custom, preferred_translation='وحدة خاصة في Évora')])
    assert result.fingerprint != changed.fingerprint
    proof = result.for_block('p0001_b0001')
    with pytest.raises(StructuredGlossaryError, match='^changed_block_glossary_contract$'):
        verified_glossary_literal_spans(source, replace(proof, fingerprint='0' * 64))
    with pytest.raises(StructuredGlossaryError, match='^incompatible_glossary_literal_contract$'):
        contract(source, [replace(custom, preferred_translation='تحقيق خاص في Porto')])


@pytest.mark.parametrize('limits', [{'max_entries': 1}, {'max_chars': 1}])
def test_configured_header_precedence_does_not_relax_glossary_limits(limits):
    rows = [row('audiência de julgamento', 'Chosen hearing', tier=2), row('arguido', 'Defendant')]
    with pytest.raises(StructuredGlossaryError, match='^structured_glossary_budget_exceeded$'):
        build(blocks('audiência de julgamento; arguido'), rows, target_lang='EN', **limits)


def test_limit_exhaustion_is_not_silent_term_dropping():
    rows = [row('arguido', 'المتهم'), row('prazo', 'الأجل')]
    for limits in ({'max_entries': 1}, {'max_chars': 50}):
        with pytest.raises(StructuredGlossaryError, match='structured_glossary_budget_exceeded'):
            contract('O arguido tem prazo.', rows, **limits)


def test_contract_is_immutable_source_bound_and_recomputed_not_arbitrary_allowlist():
    source = 'Inquéritos de Évora'
    glossary, proof = contract(source)
    with pytest.raises(FrozenInstanceError):
        proof.source_sha256 = '0' * 64
    for changed in (replace(proof, source_sha256='0' * 64), replace(proof, fingerprint='0' * 64),
                    replace(proof, literal_spans=((0, len(source)),)), replace(proof, entries=()),
                    replace(proof, target_lang='EN'), replace(proof, version='unknown')):
        with pytest.raises(StructuredGlossaryError, match='changed_block_glossary_contract'):
            verified_glossary_literal_spans(source, changed)
    with pytest.raises(StructuredGlossaryError, match='invalid_block_glossary_contract'):
        prepare(source, glossary_contract=['Évora'])
    with pytest.raises(StructuredGlossaryError, match='glossary_block_not_found'):
        glossary.for_block('p0001_b0002')


def test_contract_hash_covers_target_and_exact_source_but_not_irrelevant_terms():
    source = 'O arguido tem prazo.'
    first, _ = contract(source, [row('arguido', 'المتهم')])
    irrelevant, _ = contract(source, [row('arguido', 'المتهم'), row('ausente', 'الغائب')])
    changed, _ = contract(source, [row('arguido', 'متهم')])
    spacing, _ = contract(source + ' ', [row('arguido', 'المتهم')])
    assert first.fingerprint == irrelevant.fingerprint
    assert first.fingerprint != changed.fingerprint != spacing.fingerprint


@pytest.mark.parametrize('target', ['EN', 'FR'])
def test_other_languages_receive_relevant_terms_without_arabic_latin_restriction(target):
    glossary = build(blocks('O arguido.'), [row('arguido', 'the defendant')], target_lang=target)
    assert len(glossary.entries) == 1 and glossary.for_block('p0001_b0001').literal_spans == ()


def test_errors_are_content_free_with_safe_block_id():
    with pytest.raises(StructuredGlossaryError) as caught:
        contract('PRIVATE_SAMPLE', [row('PRIVATE_SAMPLE', 'SECRET_UNGROUNDED')])
    assert caught.value.block_id == 'p0001_b0001'
    assert 'PRIVATE_SAMPLE' not in repr(caught.value) and 'SECRET_UNGROUNDED' not in repr(caught.value)


@pytest.mark.parametrize('change', [
    {'enabled_tiers': [True]}, {'enabled_tiers': '12'}, {'max_entries': 0},
    {'max_chars': True}, {'source_lang': 'XX'}, {'target_lang': 'XX'},
    {'source_lang': []}, {'target_lang': []},
])
def test_invalid_options_are_rejected(change):
    options = {'target_lang': 'AR', **change}
    with pytest.raises(StructuredGlossaryError):
        build(blocks('Texto.'), [], **options)


@pytest.mark.parametrize('invalid', [None, 'arguido', {'source': 'arguido'},
    GlossaryEntry('arguido', 'المتهم', 'unknown'),
    GlossaryEntry('arguido', 'المتهم', 'exact', tier=True),
    GlossaryEntry('[[arguido]]', 'المتهم', 'exact'),
    GlossaryEntry('arguido', 'المتهم\nEXTRA', 'exact'),
    GlossaryEntry('arguido', 'المتهم', 'exact', source_lang='XX'),
    GlossaryEntry('arguido', 'المتهم', []),
    GlossaryEntry('arguido', 'المتهم', 'exact', source_lang=[]),
])
def test_malformed_entries_fail_content_free(invalid):
    with pytest.raises(StructuredGlossaryError, match='invalid_structured_glossary_entry'):
        contract('arguido', [invalid])


@pytest.mark.parametrize('invalid', [[], None, 'text', [{'id': 1, 'text': 'a'}],
    [{'id': 'private text', 'text': 'a'}], [{'id': 'p0001_b0001', 'text': 3}],
    [{'id': 'p0001_b0001', 'text': 'a'}, {'id': 'p0001_b0001', 'text': 'b'}],
])
def test_malformed_block_shapes_fail_safely(invalid):
    with pytest.raises(StructuredGlossaryError):
        build(invalid, [], target_lang='AR')


def test_malformed_contract_block_id_is_not_a_type_error_or_content_leak():
    _, proof = contract('Inquéritos de Évora')
    with pytest.raises(StructuredGlossaryError, match='changed_block_glossary_contract'):
        verified_glossary_literal_spans('Inquéritos de Évora', replace(proof, block_id=None))


def test_aggregate_source_limit_is_checked_before_header_matching(monkeypatch):
    import legalpdf_translate.structured_glossary as module
    monkeypatch.setattr(module, 'match_legal_header_phrases', lambda *a: pytest.fail('Limit before expensive matching.'))
    with pytest.raises(StructuredGlossaryError, match='structured_glossary_source_limit_exceeded'):
        build(blocks(*(['a' * 120000] * 9)), [], target_lang='AR')


def test_disabled_dynamic_headers_do_not_silently_reenable_tiers():
    glossary, proof = contract('Inquéritos de Évora', enabled_tiers=[2])
    assert glossary.entries == () and proof.literal_spans == ()
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare('Inquéritos de Évora', glossary_contract=proof), 'التحقيقات Évora', glossary_contract=proof)


def test_same_source_place_in_other_block_does_not_allow_arbitrary_extra_latin():
    source = blocks('Inquéritos de Évora', 'Sem informação adicional.')
    glossary = build(source, [], target_lang='AR')
    proof = glossary.for_block('p0001_b0002')
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
        normalize(prepare(source[1]['text'], glossary_contract=proof), 'لا معلومات Évora', glossary_contract=proof)


def test_empty_cells_support_exact_shared_5000_block_limit():
    from legalpdf_translate.structured_glossary import _MAX_BLOCKS
    source = blocks(*([''] * _MAX_BLOCKS))
    assert len(build(source, [], target_lang='AR').blocks) == 5000
    source.append({'id': 'p0001_b5001', 'text': ''})
    with pytest.raises(StructuredGlossaryError, match='invalid_structured_glossary_input'):
        build(source, [], target_lang='AR')
