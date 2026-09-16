"""Exact block-relevant glossary and source-bound Arabic literal contracts.

No model output, I/O, case/accent repair or general Latin allowlist is used.
Recognized institutional place names are source evidence, not names inferred
from a preferred translation. A preferred Latin span must be present verbatim
in both the actual matched source phrase and its approved target phrase.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
import unicodedata
from typing import Sequence

from .glossary import GlossaryEntry, format_glossary_for_prompt
from .legal_header_glossary import match_legal_header_phrases
from .pt_legal_glossary_aliases import (
    _PT_CITATION_ALIAS_PATTERNS, build_priority_pt_legal_alias_entries,
)
from .structured_arabic_literals import (
    StructuredArabicLiteralError, _NON_NAME_WORDS, _PROSE_WORDS, _Span,
    _choose, _latin, _normalize_with_source_spans, _occurrences, _source_spans, _view,
)


STRUCTURED_GLOSSARY_VERSION = 'structured_glossary_v1'
_ID = re.compile(r'p[0-9]{4,}_b[0-9]{4,}\Z')
_MAX_BLOCKS, _MAX_ENTRIES, _MAX_CHARS = 5000, 2000, 120000
_EXTRA_LEGAL_WORDS = {'direito', 'despacho', 'certificado', 'comparecimento', 'criminal',
    'criminalidade', 'factos', 'fundamentação', 'inquéritos', 'injunções', 'local',
    'suspensão', 'testemunhas', 'termo', 'obrigatório', 'prisão', 'multa'}


class StructuredGlossaryError(ValueError):
    """Content-free preflight code with an optional strictly validated block ID."""
    def __init__(self, code: str, *, block_id: str | None = None):
        self.code = code
        self.block_id = block_id if isinstance(block_id, str) and _ID.fullmatch(block_id) else None
        super().__init__(code)


def _require(value: bool, code: str, block_id: str | None = None) -> None:
    if not value:
        raise StructuredGlossaryError(code, block_id=block_id)


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _source_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _visible(value: str, block_id: str | None = None) -> str:
    try:
        return _view(value)[0]
    except StructuredArabicLiteralError:
        raise StructuredGlossaryError('invalid_glossary_source_text', block_id=block_id) from None


def _word(char: str) -> bool:
    return char.isalnum() or char == '_' or bool(char and unicodedata.category(char).startswith('M'))


def _matches(source: str, phrase: str) -> tuple[tuple[int, int], ...]:
    result, cursor = [], 0
    while phrase and (start := source.find(phrase, cursor)) >= 0:
        end = start + len(phrase)
        cursor = end
        if (start and _word(phrase[0]) and _word(source[start - 1])
                or end < len(source) and _word(phrase[-1]) and _word(source[end])):
            continue
        result.append((start, end))
    return tuple(result)


def _entry(entry: GlossaryEntry) -> GlossaryEntry:
    _require(type(entry) is GlossaryEntry, 'invalid_structured_glossary_entry')
    _require(all(isinstance(value, str) and value.strip() == value and 0 < len(value) <= 4096
                 for value in (entry.source_text, entry.preferred_translation))
             and isinstance(entry.match_mode, str) and entry.match_mode in {'exact', 'contains'}
             and isinstance(entry.source_lang, str) and entry.source_lang in {'PT', 'EN', 'FR', 'AUTO', 'ANY'}
             and type(entry.tier) is int and 1 <= entry.tier <= 6,
             'invalid_structured_glossary_entry')
    _require(not re.search(r'[\r\n\u0000-\u001f\u200e\u200f\u202a-\u202e\u2066-\u2069]',
                           entry.source_text + entry.preferred_translation), 'invalid_structured_glossary_entry')
    # Brackets are protocol packaging, not additional glossary authority.
    _require(_visible(entry.source_text) == entry.source_text,
             'invalid_structured_glossary_entry')
    return entry


def _header_entries(source: str, lang: str) -> tuple[list[GlossaryEntry], tuple[str, ...]]:
    entries, cities = [], []
    lines = source.splitlines()
    for matched in match_legal_header_phrases(source, lang):
        # The old matcher may clean spacing/case in its public surface. Use its
        # exact original span instead; never rewrite source to match the glossary.
        exact = lines[matched.line_index].strip()[matched.start:matched.end]
        if exact:
            entries.append(GlossaryEntry(exact, matched.preferred_translation, 'exact', 'PT', matched.tier))
        city = matched.case_city
        if city and _matches(exact, city) and _place_name(city):
            cities.append(city)
    return entries, tuple(dict.fromkeys(cities))


def _place_name(value: str) -> bool:
    """Source-side city capture must still be a bounded proper-name form.

    The institutional regex alone is greedy enough to capture following prose;
    reject that instead of blessing an untranslated clause as a place name.
    """
    if not value or len(value) > 120 or '\n' in value:
        return False
    words = value.split(' ')
    if not 1 <= len(words) <= 7:
        return False
    forbidden = _NON_NAME_WORDS | _PROSE_WORDS | _EXTRA_LEGAL_WORDS
    for index, word in enumerate(words):
        if word in {'de', 'da', 'do', 'dos', 'das', 'e'} and 0 < index < len(words) - 1:
            continue
        if word.casefold() in forbidden:
            return False
        pieces = re.split("[-'’]", word)
        if not all(part and part[0].isupper() and all(_latin(char) for char in part) for part in pieces):
            return False
    return True


def _alias_entries(source: str, entries: list[GlossaryEntry]) -> list[GlossaryEntry]:
    result = []
    for entry in build_priority_pt_legal_alias_entries(source, entries):
        if _matches(source, entry.source_text):
            result.append(entry)
            continue
        pattern = _PT_CITATION_ALIAS_PATTERNS.get(entry.source_text)
        if pattern is None:
            continue
        for match in pattern.finditer(source):
            exact = match[0]
            if entry.source_text == 'alínea':
                # The recognizer looks ahead through the clause label; only the
                # abbreviation itself is the term, never consume that label.
                exact = exact[:exact.index('.') + 1]
            elif entry.source_text == 'n.º':
                # The recognizer consumes separator whitespace before the number.
                # Keep only the exact observed term span, not its separator/label;
                # configured entries and their strict validation stay untouched.
                exact = exact.rstrip()
            result.append(replace(entry, source_text=exact))
    return result


def _dedupe(entries: Sequence[GlossaryEntry], block_id: str | None) -> tuple[GlossaryEntry, ...]:
    result, targets = [], {}
    for entry in entries:
        key = entry.source_text
        old = targets.get(key)
        _require(old is None or old == entry.preferred_translation,
                 'conflicting_structured_glossary_entries', block_id)
        targets[key] = entry.preferred_translation
        if not any(previous.source_text == key for previous in result):
            result.append(entry)
    return tuple(result)


def _literal_contract(source: str, entries: tuple[GlossaryEntry, ...], block_id: str) -> tuple[tuple[int, int], ...]:
    """Recompute additional source spans; also validate every approved pair."""
    _, cities = _header_entries(source, 'AR')
    accepted = []
    ordinary = _source_spans(source, [])
    for entry in entries:
        matches = _matches(source, entry.source_text)
        _require(bool(matches), 'glossary_entry_not_in_source_block', block_id)
        phrase = entry.source_text
        # Choose only source-recognized cities shared verbatim by this matched
        # source phrase and its preferred target. Output text is never consulted.
        spans = _choose(span for city in cities if _matches(entry.preferred_translation, city)
                        for span in _occurrences(phrase, city))
        for start, end in matches:
            # Preserve the original block context: taking an inline ``p. e p.``
            # abbreviation out of context must not invent a leading list label.
            # A configured phrase may cover only part of a protected entity.
            # Its exact intersecting characters must still survive; otherwise
            # the prompt would demand both preservation and translation.
            existing = [_Span(max(span.start, start) - start, min(span.end, end) - start)
                        for span in ordinary if span.start < end and start < span.end]
            try:
                _normalize_with_source_spans(phrase, _choose([*existing, *spans]), entry.preferred_translation)
            except StructuredArabicLiteralError:
                raise StructuredGlossaryError('incompatible_glossary_literal_contract', block_id=block_id) from None
            accepted.extend(_Span(start + span.start, start + span.end) for span in spans)
    return tuple((span.start, span.end) for span in _choose(accepted))


@dataclass(frozen=True, slots=True)
class BlockGlossaryContract:
    block_id: str
    source_sha256: str
    entries: tuple[GlossaryEntry, ...]
    literal_spans: tuple[tuple[int, int], ...]
    target_lang: str
    fingerprint: str
    version: str = STRUCTURED_GLOSSARY_VERSION


@dataclass(frozen=True, slots=True)
class StructuredGlossary:
    entries: tuple[GlossaryEntry, ...]
    blocks: tuple[BlockGlossaryContract, ...]
    prompt_text: str
    fingerprint: str
    version: str = STRUCTURED_GLOSSARY_VERSION

    def for_block(self, block_id: str) -> BlockGlossaryContract:
        for contract in self.blocks:
            if contract.block_id == block_id:
                return contract
        raise StructuredGlossaryError('glossary_block_not_found', block_id=block_id)


def _contract_payload(block_id, source_hash, entries, spans, target_lang):
    return {'version': STRUCTURED_GLOSSARY_VERSION, 'block_id': block_id,
            'source_sha256': source_hash, 'entries': [asdict(entry) for entry in entries],
            'literal_spans': spans, 'target_lang': target_lang}


def verified_glossary_literal_spans(source: str, contract: BlockGlossaryContract) -> tuple[tuple[int, int], ...]:
    _require(type(contract) is BlockGlossaryContract, 'invalid_block_glossary_contract')
    source = _visible(source, contract.block_id)
    _require(contract.version == STRUCTURED_GLOSSARY_VERSION and contract.target_lang == 'AR'
             and isinstance(contract.block_id, str) and _ID.fullmatch(contract.block_id) is not None
             and type(contract.entries) is tuple and type(contract.literal_spans) is tuple
             and len(contract.entries) <= _MAX_ENTRIES
             and contract.source_sha256 == _source_hash(source), 'changed_block_glossary_contract', contract.block_id)
    for entry in contract.entries:
        _entry(entry)
    expected = _literal_contract(source, contract.entries, contract.block_id)
    payload = _contract_payload(contract.block_id, contract.source_sha256, contract.entries, expected, 'AR')
    _require(expected == contract.literal_spans and _hash(payload) == contract.fingerprint,
             'changed_block_glossary_contract', contract.block_id)
    return expected


def build_structured_glossary(source_blocks: Sequence[dict], entries: Sequence[GlossaryEntry], *,
        target_lang: str, enabled_tiers: Sequence[int] = (1, 2), source_lang: str = 'PT',
        max_entries: int = 50, max_chars: int = 6000) -> StructuredGlossary:
    """Keep only source-block matches, fail on incompatible or over-budget terms.

    Both match modes use an exact, case/accent-preserving bounded phrase match;
    ``exact`` does not require that a whole paragraph equal the glossary term.
    Institutional and known citation aliases retain their existing recognizers,
    but the generated prompt always names an exact observed source surface.
    """
    _require(isinstance(source_blocks, (list, tuple)) and 0 < len(source_blocks) <= _MAX_BLOCKS
             and isinstance(entries, (list, tuple)) and len(entries) <= _MAX_ENTRIES,
             'invalid_structured_glossary_input')
    _require(sum(len(block.get('text', '')) for block in source_blocks
                 if isinstance(block, dict) and isinstance(block.get('text'), str)) <= 1_000_000,
             'structured_glossary_source_limit_exceeded')
    target_lang = getattr(target_lang, 'value', target_lang)
    _require(isinstance(target_lang, str) and target_lang in {'AR', 'EN', 'FR'}
             and isinstance(source_lang, str) and source_lang in {'PT', 'EN', 'FR', 'AUTO'},
             'invalid_structured_glossary_language')
    _require(isinstance(enabled_tiers, (list, tuple))
             and all(type(tier) is int and 1 <= tier <= 6 for tier in enabled_tiers),
             'invalid_structured_glossary_tiers')
    _require(type(max_entries) is int and 1 <= max_entries <= 2000
             and type(max_chars) is int and 1 <= max_chars <= _MAX_CHARS,
             'invalid_structured_glossary_limits')
    allowed = set(enabled_tiers or (1, 2))
    configured = [_entry(entry) for entry in entries]
    relevant, contracts, seen = [], [], set()
    for block in source_blocks:
        _require(isinstance(block, dict) and isinstance(block.get('id'), str)
                 and _ID.fullmatch(block['id']) is not None and block['id'] not in seen
                 and isinstance(block.get('text'), str), 'invalid_structured_glossary_block')
        block_id = block['id']
        seen.add(block_id)
        source = _visible(block['text'], block_id)
        priority, _cities = _header_entries(source, target_lang) if source_lang == 'PT' else ([], ())
        # Generated headers are defaults, not competing configured preferences.
        # Suppress only an exact eligible source key; configured conflicts still
        # reach strict dedupe, and citation-alias priority remains unchanged.
        configured_sources = {entry.source_text for entry in configured if entry.tier in allowed
            and entry.source_lang in {source_lang, 'AUTO', 'ANY'} and _matches(source, entry.source_text)}
        priority = [entry for entry in priority if entry.source_text not in configured_sources]
        priority += _alias_entries(source, configured) if source_lang == 'PT' else []
        candidates = priority + sorted(configured, key=lambda entry: (entry.tier, -len(entry.source_text), entry.source_text))
        matched = _dedupe([entry for entry in candidates if entry.tier in allowed
            and entry.source_lang in {source_lang, 'AUTO', 'ANY'} and _matches(source, entry.source_text)], block_id)
        for entry in matched:
            _entry(entry)
        spans = _literal_contract(source, matched, block_id) if target_lang == 'AR' else ()
        payload = _contract_payload(block_id, _source_hash(source), matched, spans, target_lang)
        contracts.append(BlockGlossaryContract(block_id, _source_hash(source), matched, spans,
                                               target_lang, _hash(payload)))
        relevant.extend(matched)
    kept = _dedupe(relevant, None)
    prompt = format_glossary_for_prompt(target_lang, list(kept), detected_source_lang=source_lang)
    _require(len(kept) <= max_entries and len(prompt) <= max_chars, 'structured_glossary_budget_exceeded')
    identity = {'version': STRUCTURED_GLOSSARY_VERSION, 'target_lang': target_lang,
        'source_lang': source_lang, 'enabled_tiers': sorted(allowed), 'prompt_text': prompt,
        'blocks': [contract.fingerprint for contract in contracts]}
    return StructuredGlossary(kept, tuple(contracts), prompt, _hash(identity))
