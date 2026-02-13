"""Minimal file-based glossary enforcement for preferred legal phrasing."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .types import TargetLang

_ISOLATE_CONTROL_RE = re.compile(r"[\u2066-\u2069]")
_PROTECTED_TOKEN_RE = re.compile(r"(?:[\u2066\u2067\u2068])?\[\[.*?\]\](?:\u2069)?", re.DOTALL)
_VALID_TABLE_MATCHES = {"exact", "contains"}

GlossaryMatch = Literal["exact", "contains"]


@dataclass(frozen=True, slots=True)
class GlossaryRule:
    target_lang: str
    match_type: str
    match: str
    replace: str
    pattern: re.Pattern[str] | None = None


GlossaryRules = tuple[GlossaryRule, ...]


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    source: str
    target: str
    match: GlossaryMatch


_BUILTIN_GLOSSARY_V1: dict[str, object] = {
    "version": 1,
    "rules": [
        {
            "target_lang": "AR",
            "match_type": "regex",
            "match": r"صرف\s+(?:الأتعاب|الاتعاب)(?:\s+(?:المستحقة|المقررة|الواجبة))?",
            "replace": "دفع الأتعاب المستحقة",
        },
        {
            "target_lang": "AR",
            "match_type": "regex",
            "match": r"لا\s+يخضع\s+لأي\s+(?:حجز|اقتطاع|استقطاع)(?:\s*(?:من)?\s*\(?(?:IRS)\)?)?",
            "replace": "لا يخضع لأي استقطاع (IRS)",
        },
    ],
}


_DEFAULT_AR_ENTRIES: tuple[GlossaryEntry, ...] = (
    GlossaryEntry(
        source="صرف الأتعاب",
        target="دفع الأتعاب المستحقة",
        match="contains",
    ),
    GlossaryEntry(
        source="لا يخضع لأي حجز (IRS)",
        target="لا يخضع لأي استقطاع (IRS)",
        match="contains",
    ),
)


def _lang_code(value: TargetLang | str) -> str:
    if isinstance(value, TargetLang):
        return value.value
    return str(value).strip().upper()


def supported_target_langs() -> list[str]:
    return [lang.value for lang in TargetLang]


def default_ar_entries() -> list[GlossaryEntry]:
    return list(_DEFAULT_AR_ENTRIES)


def _coerce_glossary_entry(raw: object) -> GlossaryEntry | None:
    source: str
    target: str
    match_raw: object
    if isinstance(raw, GlossaryEntry):
        source = raw.source
        target = raw.target
        match_raw = raw.match
    elif isinstance(raw, dict):
        source = str(raw.get("source", "") or "")
        target = str(raw.get("target", "") or "")
        match_raw = raw.get("match", "exact")
    else:
        return None

    source_clean = source.strip()
    target_clean = target.strip()
    if source_clean == "" or target_clean == "":
        return None
    if _ISOLATE_CONTROL_RE.search(source_clean) or _ISOLATE_CONTROL_RE.search(target_clean):
        return None

    match = str(match_raw or "exact").strip().lower()
    if match not in _VALID_TABLE_MATCHES:
        return None
    return GlossaryEntry(source=source_clean, target=target_clean, match=match)  # type: ignore[arg-type]


def normalize_glossaries(
    glossaries_by_lang: object,
    supported_langs: list[str],
) -> dict[str, list[GlossaryEntry]]:
    normalized_langs: list[str] = []
    seen_langs: set[str] = set()
    for lang in supported_langs:
        code = _lang_code(lang)
        if code == "" or code in seen_langs:
            continue
        seen_langs.add(code)
        normalized_langs.append(code)

    raw_by_lang: dict[str, object] = {}
    if isinstance(glossaries_by_lang, dict):
        for raw_lang, raw_entries in glossaries_by_lang.items():
            code = _lang_code(str(raw_lang))
            if code != "":
                raw_by_lang[code] = raw_entries

    output: dict[str, list[GlossaryEntry]] = {}
    for lang in normalized_langs:
        rows = raw_by_lang.get(lang)
        if not isinstance(rows, list):
            output[lang] = []
            continue
        normalized_rows: list[GlossaryEntry] = []
        seen_rows: set[tuple[str, str, str]] = set()
        for raw_row in rows:
            entry = _coerce_glossary_entry(raw_row)
            if entry is None:
                continue
            row_key = (entry.source, entry.target, entry.match)
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            normalized_rows.append(entry)
        output[lang] = normalized_rows
    return output


def serialize_glossaries(glossaries_by_lang: dict[str, list[GlossaryEntry]]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = {}
    for lang in supported_target_langs():
        rows = glossaries_by_lang.get(lang, [])
        output[lang] = [
            {
                "source": entry.source,
                "target": entry.target,
                "match": entry.match,
            }
            for entry in rows
        ]
    return output


def format_glossary_for_prompt(target_lang: str, entries: list[GlossaryEntry]) -> str:
    if not entries:
        return ""
    lang = _lang_code(target_lang)
    lines = [
        "<<<BEGIN GLOSSARY>>>",
        f"Target language: {lang}",
        "Use preferred translations exactly when a source phrase matches.",
        "Do not rewrite IDs, IBANs, case numbers, addresses, dates, or names.",
    ]
    for index, entry in enumerate(entries, start=1):
        source_text = entry.source.replace("\r", " ").replace("\n", " ").strip()
        target_text = entry.target.replace("\r", " ").replace("\n", " ").strip()
        lines.append(f"{index}. [{entry.match}] {source_text} => {target_text}")
    lines.append("<<<END GLOSSARY>>>")
    return "\n".join(lines)


def entries_from_legacy_rules(path: Path | None) -> dict[str, list[GlossaryEntry]]:
    output: dict[str, list[GlossaryEntry]] = {lang: [] for lang in supported_target_langs()}
    if path is None:
        return output
    try:
        rules = load_glossary(path)
    except Exception:
        return output

    for rule in rules:
        if rule.match_type != "literal":
            continue
        lang = _lang_code(rule.target_lang)
        if lang not in output:
            continue
        entry = GlossaryEntry(source=rule.match.strip(), target=rule.replace.strip(), match="exact")
        if entry.source == "" or entry.target == "":
            continue
        if entry not in output[lang]:
            output[lang].append(entry)
    return output


def _validate_and_build_rules(payload: object, *, source: str) -> GlossaryRules:
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid glossary at {source}: root must be an object.")

    version = payload.get("version")
    if version != 1:
        raise ValueError(f"Invalid glossary at {source}: version must be 1.")

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError(f"Invalid glossary at {source}: rules must be a list.")

    rules: list[GlossaryRule] = []
    for index, raw_rule in enumerate(raw_rules):
        where = f"{source} rule[{index}]"
        if not isinstance(raw_rule, dict):
            raise ValueError(f"Invalid glossary {where}: rule must be an object.")

        target_lang = str(raw_rule.get("target_lang", "")).strip().upper()
        if target_lang not in {"EN", "FR", "AR"}:
            raise ValueError(f"Invalid glossary {where}: target_lang must be EN, FR, or AR.")

        match_type = str(raw_rule.get("match_type", "")).strip().lower()
        if match_type not in {"literal", "regex"}:
            raise ValueError(f"Invalid glossary {where}: match_type must be literal or regex.")

        match = raw_rule.get("match")
        replace = raw_rule.get("replace")
        if not isinstance(match, str) or match == "":
            raise ValueError(f"Invalid glossary {where}: match must be a non-empty string.")
        if not isinstance(replace, str) or replace == "":
            raise ValueError(f"Invalid glossary {where}: replace must be a non-empty string.")
        if _ISOLATE_CONTROL_RE.search(replace):
            raise ValueError(f"Invalid glossary {where}: replace cannot contain isolate controls.")

        pattern: re.Pattern[str] | None = None
        if match_type == "regex":
            try:
                pattern = re.compile(match)
            except re.error as exc:
                raise ValueError(f"Invalid glossary {where}: bad regex pattern: {exc}") from exc

        rules.append(
            GlossaryRule(
                target_lang=target_lang,
                match_type=match_type,
                match=match,
                replace=replace,
                pattern=pattern,
            )
        )
    return tuple(rules)


def parse_glossary_payload(payload: object, *, source: str = "payload") -> GlossaryRules:
    """Validate a glossary payload object and return compiled rules."""
    return _validate_and_build_rules(payload, source=source)


def load_glossary_from_text(text: str, *, source: str = "<memory>") -> GlossaryRules:
    """Parse and validate glossary JSON text."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid glossary JSON at {source}: {exc}") from exc
    return parse_glossary_payload(payload, source=source)


def builtin_glossary_payload() -> dict[str, object]:
    """Return a mutable copy of the built-in glossary payload."""
    return deepcopy(_BUILTIN_GLOSSARY_V1)


def builtin_glossary_json(*, indent: int = 2) -> str:
    """Return the built-in glossary payload serialized as JSON text."""
    return json.dumps(builtin_glossary_payload(), ensure_ascii=False, indent=indent)


def load_glossary(path: Path | None) -> GlossaryRules:
    """Load glossary rules from file, or use built-in defaults when path is None."""
    if path is None:
        return parse_glossary_payload(builtin_glossary_payload(), source="builtin")

    glossary_path = path.expanduser().resolve()
    try:
        raw = glossary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read glossary file: {glossary_path}") from exc

    return load_glossary_from_text(raw, source=str(glossary_path))


def _apply_rules_to_segment(text: str, *, rules: GlossaryRules) -> str:
    transformed = text
    for rule in rules:
        if rule.target_lang != "AR":
            continue
        if rule.match_type == "literal":
            transformed = transformed.replace(rule.match, rule.replace)
        else:
            assert rule.pattern is not None
            transformed = rule.pattern.sub(rule.replace, transformed)
    return transformed


def apply_glossary(text: str, target_lang: TargetLang | str, rules: GlossaryRules) -> str:
    """Apply glossary rules conservatively to AR output only."""
    if text == "":
        return text
    if _lang_code(target_lang) != "AR":
        return text
    if not rules:
        return text

    output: list[str] = []
    cursor = 0
    for token_match in _PROTECTED_TOKEN_RE.finditer(text):
        start, end = token_match.span()
        output.append(_apply_rules_to_segment(text[cursor:start], rules=rules))
        output.append(token_match.group(0))
        cursor = end
    output.append(_apply_rules_to_segment(text[cursor:], rules=rules))
    return "".join(output)
