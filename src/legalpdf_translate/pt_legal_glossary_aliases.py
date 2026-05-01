from __future__ import annotations

import re

from .glossary import GlossaryEntry


_PT_CITATION_CANONICAL_ORDER: tuple[str, ...] = (
    "p. e p. pelos artigos",
    "alínea",
    "n.º",
)

_PT_CITATION_ALIAS_PATTERNS: dict[str, re.Pattern[str]] = {
    "p. e p. pelos artigos": re.compile(
        r"\bp\s*\.\s*e\s*p\s*\.?\s*pel(?:o|os)\s+art(?:s?\.?|igos?)",
        re.IGNORECASE,
    ),
    "alínea": re.compile(r"\bal\.\s*[a-z0-9](?:\)|\b)", re.IGNORECASE),
    "n.º": re.compile(r"\bn\s*\.?\s*[ºo°]\s*(?=\d)", re.IGNORECASE),
    "O Juiz de Direito": re.compile(r"\bJu[ií]z\s+de\s+Direito\b", re.IGNORECASE),
}


def source_matches_glossary_entry(source_text: str, entry: GlossaryEntry) -> bool:
    lowered = str(source_text or "").casefold()
    needle = entry.source_text.casefold()
    if needle and needle in lowered:
        return True
    if str(entry.source_lang or "").strip().upper() != "PT":
        return False
    pattern = _PT_CITATION_ALIAS_PATTERNS.get(entry.source_text)
    if pattern is None:
        return False
    return pattern.search(source_text or "") is not None


def build_priority_pt_legal_alias_entries(
    source_text: str,
    entries: list[GlossaryEntry],
) -> list[GlossaryEntry]:
    by_canonical: dict[str, GlossaryEntry] = {}
    for entry in entries:
        if str(entry.source_lang or "").strip().upper() != "PT":
            continue
        canonical = entry.source_text.strip()
        if canonical not in _PT_CITATION_ALIAS_PATTERNS:
            continue
        current = by_canonical.get(canonical)
        if current is None or int(entry.tier) < int(current.tier):
            by_canonical[canonical] = entry

    priority_entries: list[GlossaryEntry] = []
    for canonical in _PT_CITATION_CANONICAL_ORDER:
        entry = by_canonical.get(canonical)
        if entry is None:
            continue
        if not source_matches_glossary_entry(source_text, entry):
            continue
        priority_entries.append(
            GlossaryEntry(
                source_text=entry.source_text,
                preferred_translation=entry.preferred_translation,
                match_mode=entry.match_mode,
                source_lang=entry.source_lang,
                tier=1,
            )
        )
    return priority_entries
