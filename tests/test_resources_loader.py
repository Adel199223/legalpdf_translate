from __future__ import annotations

import pytest

from legalpdf_translate.resources_loader import load_system_instructions
from legalpdf_translate.translation_fidelity import FIDELITY_GUIDANCE
from legalpdf_translate.translation_structure import structured_system_instructions
from legalpdf_translate.types import TargetLang


def test_load_system_instructions_en_uses_english_resource() -> None:
    text = load_system_instructions(TargetLang.EN)
    assert "Return ONLY the English translation inside ONE plain-text code block." in text
    assert "Keep the output strictly in French." not in text
    assert "10 de fevereiro de 2026 -> Beja, 10 February 2026" in text
    assert "translate when a stable English equivalent exists (default)" in text
    assert "Do not leave Portuguese residual terms in legal/institutional lines." in text
    assert "if Portuguese is kept due to uncertainty, keep the full institution name in Portuguese" in text


def test_load_system_instructions_fr_uses_french_resource() -> None:
    text = load_system_instructions(TargetLang.FR)
    assert "Retourner UNIQUEMENT la traduction francaise dans UN seul bloc de code texte brut." in text
    assert "Keep the output strictly in English." not in text
    assert "10 de fevereiro de 2026 -> Beja, 10 février 2026" in text
    assert "traduire lorsqu'un equivalent francais stable existe (cas general)" in text
    assert "Interdit de laisser des residus portugais dans les lignes juridiques/institutionnelles." in text
    assert "si vous conservez le portugais par incertitude, conserver la denomination complete en portugais" in text


def test_load_system_instructions_ar_still_uses_arabic_resource() -> None:
    text = load_system_instructions(TargetLang.AR)
    assert "Return ONLY the Arabic translation inside ONE plain-text code block." in text
    assert "MUST be translated into Arabic when a stable equivalent exists (default)." in text
    assert "only when no stable equivalent exists or when uncertain." in text
    assert "allowed only for acronyms on first mention" in text
    assert "[[Official Portuguese title]] — الترجمة العربية الدقيقة" not in text


@pytest.mark.parametrize("lang", list(TargetLang))
def test_both_translation_paths_receive_source_fidelity_guidance(lang: TargetLang) -> None:
    ordinary = load_system_instructions(lang)
    structured = structured_system_instructions(lang)
    for instructions in (ordinary, structured):
        assert instructions.count(FIDELITY_GUIDANCE) == 1
        assert "evidential certainty" in instructions
        assert "rather than asserting a certain fact" in instructions
        assert "placing the case file before" in instructions
        assert "Preserve an actual direction to archive" in instructions
        assert "not a font-dependent private-use glyph" in instructions
    # Sharing fidelity guidance must not merge the incompatible output protocols.
    assert ("bloc de code texte brut" if lang == TargetLang.FR else "code block") in ordinary
    assert "JSON with unchanged IDs" in structured
    assert "code block" not in structured
