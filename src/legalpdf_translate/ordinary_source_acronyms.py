"""Source-owned Portuguese acronym occurrences in ordinary Arabic translation."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .ordinary_primary_page_evidence import _earlier_texts, _MAX_PDF_BYTES

POLICY = "source_page_occurrences_v2"
# Ambiguous abbreviations are protected in governed legal prose, but receive a
# meaning only from an actual selected-source expansion or approved terminology.
_NAMES = {
    "GNR": "Guarda Nacional Republicana", "PJ": "Polícia Judiciária",
    "PSP": "Polícia de Segurança Pública", "CPP": "Código de Processo Penal",
    "CPC": "Código de Processo Civil", "PGR": "Procuradoria-Geral da República",
    "DIAP": "Departamento de Investigação e Ação Penal", "O.S.": "Ordem de Serviço",
}
_FORM = re.compile(r"(?<![\w@./-])(?:[A-Z]{2,8}|(?:[A-Z]\.){2,4})(?![\w@/-]|\.[\w])")
_GOVERNED = re.compile(r"\b(?:pel[oa]s?|d[oa]s?|[àa]s?|aos?|n[oa]s?|junto de|para)\s+$")
_MARK = re.compile(r"\[\[([^\]\r\n]+)\]\]")
_NUMBER = re.compile(r"^\s*(?:n[.º°o]*\s*)?(\d{1,8}/\d{2,4})(?![/\w])", re.I)
_GLOSS = re.compile(r"^[ \t\u2069]*\(([^()\n]{1,160})\)")
_GENERIC = {"TEL", "FAX", "REF", "PROC", "MAIL", "EMAIL", "NIF", "NIPC", "IBAN", "EUR", "USD"}
_LETTERS = re.compile(r"[^\W\d_]+")
_STOP = {"de","da","das","do","dos","del","e","a","o","para"}
_LIMIT = 32000


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if not unicodedata.combining(c))


def _words(text):
    return " ".join(_LETTERS.findall(_fold(text)))


def read_selection(pdf_path, numbers, *, expected_sha256=None):
    """All requested pages must have bounded readable text before assigning first use."""
    try:
        path = Path(pdf_path)
        if (not numbers or len(numbers) > 12 or sorted(set(numbers)) != list(numbers)
                or path.suffix.lower() != ".pdf" or not path.is_file()
                or path.stat().st_size > _MAX_PDF_BYTES):
            return ()
        if expected_sha256 is not None:
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
                    return ()
        texts = tuple(_earlier_texts(path, numbers, numbers[-1]))
        if len(texts) != len(numbers) or any(not _usable(s) for s in texts) or sum(map(len, texts)) > 128_000:
            return ()
        return tuple(zip(numbers, texts))
    except (OSError, RuntimeError, ValueError, TypeError, IndexError, ImportError):
        return ()


def _usable(text):
    return isinstance(text, str) and 0 < len(text) <= _LIMIT and "\x00" not in text and "\ufffd" not in text


def _definition(name, text):
    # Only explicit "Full Name (ABC)" defines an unfamiliar source initialism.
    # Do not interpret arbitrary successive capitalized words or initials in IDs.
    for match in re.finditer(r"(?<!\w)([A-ZÀ-Ý][^\W\d_]*(?:[ \t]+(?:de|da|do|dos|das|e|[A-ZÀ-Ý][^\W\d_]*)){1,10})"
                             r"[ \t]*\(" + re.escape(name) + r"\)", text):
        phrase = match[1]
        words = [w for w in _LETTERS.findall(phrase) if _fold(w) not in _STOP]
        if "".join(_fold(w)[0] for w in words) == name.replace(".", "").lower():
            return phrase
    return ""


def _known_meaning(name, current, entire_text, source_words, match):
    full = _NAMES.get(name, "")
    if name == "O.S.":
        number = _NUMBER.match(current[match.end():])
        if not number:
            return ""
        full_key = r"\bordem\s+de\s+servico\s*(?:n[.º°o]*\s*)?" + re.escape(number[1]) + r"(?![\w/])"
        return full if re.search(full_key, _fold(entire_text)) else ""
    if full and (" " + _words(full) + " " in source_words or name in {"GNR", "PSP"}):
        return full
    return _definition(name, entire_text) if "(" + name + ")" in entire_text else ""


def _approved(name, full, terms):
    """Only a matched acronym or its actual full form owns an acronym-sized preference."""
    values = set()
    for term in terms:
        if term.get("source_lang") not in {"PT", "AUTO", "ANY"} or term.get("match_mode") not in {"exact", "contains"}:
            continue
        source = term.get("source_text")
        if (source or "").casefold() == name.casefold() or full and _words(source or "") == _words(full):
            values.add(term["preferred_translation"].strip())
    if not values:
        return "", ""
    if len(values) != 1:
        return "configured", ""
    target = next(iter(values))
    visible = _MARK.sub(lambda m: m[1], target).translate({0x2066:None, 0x2069:None}).strip()
    if visible == name:
        return "bare", target
    pair = re.fullmatch(re.escape(name) + r"\s*\(([^()\n]{1,160})\)", visible)
    possible_gloss = (pair[1] if pair else visible).strip()
    if (0 < len(possible_gloss) <= 160 and re.search(r"[\u0621-\u064a]", possible_gloss)
            and not re.search(r"[A-Za-z0-9()[\]{}]", possible_gloss)):
        return "gloss", possible_gloss
    # Whole phrases, literals, mixed-language or contradictory choices cannot be
    # projected onto one forced Arabic parenthesis. The original glossary stays authoritative.
    return "configured", target


def _protected_spans(text):
    """Keep all protected owners for exclusion; only unique ones establish relative location."""
    from .arabic_pre_tokenize import pretokenize_arabic_source
    prepared = pretokenize_arabic_source(text, source_field_policy="baseline_label_value_v1")
    def plain(fragment):
        return fragment.replace("\u2066", "").replace("\u2069", "")
    if plain(_MARK.sub(lambda m: m[1], prepared)) != text:
        return None
    matches = list(_MARK.finditer(prepared))
    result, last, start = [], 0, 0
    for m in matches:
        value = m[1]
        start += len(plain(prepared[last:m.start()]))
        result.append((start, start + len(value), value))
        last, start = m.end(), start + len(value)
    return result


def _location(text, match, anchors, boundaries):
    start = max((b for b in boundaries if b <= match.start()), default=0)
    end = next((b for b in boundaries if b > match.end()), len(text))
    before = [v for _, b, v in anchors if b < start]
    after = [v for a, _, v in anchors if a >= end]
    return {"before":before[-3:], "after":after[:3], "start":match.start(), "end":match.end(),
            "clause":sum(b <= match.start() for b in boundaries),
            "long_prose":len(_LETTERS.findall(text[start:end])) >= 10,
            "parenthetical":text[match.end():].lstrip().startswith("("),
            "continues":bool(_LETTERS.search(text[end:]))}


def _rows(current, native, earlier, terms, already_seen, interested):
    forms = list(_FORM.finditer(current))
    if not forms or len(forms) > 100:
        return ()
    by_name = {}
    for form in forms:
        if form[0] in interested and form[0] not in _GENERIC:
            by_name.setdefault(form[0], []).append(form)
    if not by_name or len(by_name) > 32:
        return ()
    entire = "\n".join([*earlier, current])
    source_words = " " + _words(entire) + " "
    native_counts = Counter(m[0] for m in _FORM.finditer(native))
    protected = _protected_spans(current)
    if protected is None or len(protected) > 1000:
        return ()
    counts = Counter(value for _, _, value in protected)
    anchors = [span for span in protected if counts[span[2]] == 1]
    boundaries = [m.end() for m in re.finditer(r"[.!?;](?:\s|$)|\n\s*\n", current)]
    rows = []
    for name, candidates in by_name.items():
        if native_counts[name] != len(candidates):
            continue
        full = _known_meaning(name, current, entire, source_words, candidates[0])
        preference, target = _approved(name, full, terms)
        if not (full or name in _NAMES or preference):
            continue
        modes = []
        for match in candidates:
            before = current[max(0, match.start()-160):match.start()]
            after = current[match.end():]
            definition = bool(full and before.rstrip().endswith("(") and _words(before).endswith(_words(full)))
            governed = bool(_GOVERNED.search(before))
            dotted_order = name == "O.S." and bool(_NUMBER.match(after))
            if (not (definition or governed or dotted_order)
                    or any(a <= match.start() and b >= match.end() and v != name for a, b, v in protected)):
                break
            enclosed = re.match(r"^\s*\(([^()\n]{1,160})\)", after)
            if definition or (enclosed and full and _words(enclosed[1]) == _words(full)):
                mode = "printed"
            elif modes or name in already_seen:
                mode = "bare"
            else:
                mode = preference or ("gloss" if full else "uncertain")
            modes.append(mode)
        if len(modes) != len(candidates):
            continue  # a mix of headings/identifiers and governed prose has no page-wide authority
        rows.append({"spelling":name, "count":len(candidates), "modes":modes,
                     "source_meaning":full, "preferred":target,
                     "locations":[_location(current, m, anchors, boundaries) for m in candidates]})
    return tuple(rows)


def page_acronyms(current_source, selected_texts, page_number, terminology=()):
    """A bounded, nonrecursive source pass in selected-page order."""
    if not _usable(current_source) or not 1 <= len(selected_texts) <= 12:
        return ()
    numbers = [n for n, _ in selected_texts]
    if (numbers != sorted(set(numbers)) or page_number not in numbers
            or any(not _usable(s) for _, s in selected_texts)
            or sum(len(s) for _, s in selected_texts) > 128_000):
        return ()
    interested = {m[0] for m in _FORM.finditer(current_source)}
    if not interested:
        return ()
    earlier, seen = [], set()
    for number, original in selected_texts:
        if number == page_number:
            return _rows(current_source, original, earlier, terminology, seen, interested)
        if any(name in original for name in interested):
            seen.update(row["spelling"] for row in _rows(original, original, earlier, terminology, seen, interested))
        earlier.append(original)
    return ()


def capture_matches(data, selection, metadata):
    """Reconstruct the exact contract from source, acquisition path and matched terminology."""
    if (not selection or type(data.get("source_acronyms")) is not list
            or type(data.get("applicable_terminology")) is not list or len(data["applicable_terminology"]) > 50
            or any(type(t) is not dict or not isinstance(t.get("preferred_translation"), str)
                   or not isinstance(t.get("source_text"), str) for t in data["applicable_terminology"])):
        return False
    direct = metadata.get("ocr_used") is False and metadata.get("extraction_integrity_suspect") is False
    rows = (page_acronyms(data["original_source_text"], selection, data["page_number"],
                          data["applicable_terminology"]) if direct else ())
    return json.dumps(rows, sort_keys=True, ensure_ascii=False) == json.dumps(
        data["source_acronyms"], sort_keys=True, ensure_ascii=False)

def wrap_acronyms(pretokenized, rows):
    """Never enter an existing field, postal value, identifier or other protected span."""
    owned = {r["spelling"] for r in rows}
    if not owned:
        return pretokenized
    pieces, end = [], 0
    for token in _MARK.finditer(pretokenized):
        pieces += [_FORM.sub(lambda m: "[["+m[0]+"]]" if m[0] in owned else m[0],
                             pretokenized[end:token.start()]), token[0]]
        end = token.end()
    pieces.append(_FORM.sub(lambda m: "[["+m[0]+"]]" if m[0] in owned else m[0], pretokenized[end:]))
    return "".join(pieces)


def guidance(rows):
    if not rows:
        return ""
    return ("\nSource acronym occurrences in printed order within each spelling. At the source clause "
            "itself keep the exact isolated token. 'gloss' requires the token immediately followed "
            "by its contextual Arabic equivalent in parentheses. 'bare' forbids repeating a "
            "discretionary gloss; 'printed' preserves the actual source expansion and punctuation; "
            "'uncertain' permits the bare token, never guess. 'configured' defers to the matched "
            "glossary without inferring a new gloss. Approved Arabic terms take precedence. "
            "Verification must ground each protected occurrence in the target unit for its original source claim. "
            "A spelled-out agency elsewhere remains a translated full name. Data: "
            + json.dumps([{k: v for k,v in row.items() if k != "locations"} for row in rows],
                         ensure_ascii=False, separators=(",",":")))


def acronym_violation(output, rows):
    """Check wrapped identities, multiplicity and the immediately adjacent first-use pair."""
    if not rows:
        return None
    wrapped = list(_MARK.finditer(output))
    clauses = []
    for row in rows:
        name = row["spelling"]
        matches = [m for m in wrapped if m[1] == name]
        if len(matches) != row["count"]:
            return "acronym_occurrence_count"
        for m, mode, location in zip(matches, row["modes"], row["locations"]):
            gloss = _GLOSS.match(output[m.end():])
            arabic = bool(gloss and re.search(r"[\u0621-\u064a]", gloss[1]))
            if mode == "gloss" and (not arabic or row["preferred"] and
                    " ".join(row["preferred"].split()) != " ".join(gloss[1].split())):
                return "acronym_first_gloss"
            if mode == "gloss" and location["parenthetical"] and (
                    re.search(r"[0-9\u0660-\u0669\[\]]", gloss[1]) or
                    not _GLOSS.match(output[m.end()+gloss.end():])):
                return "acronym_first_gloss"
            if mode == "bare" and arabic and not location["parenthetical"]:
                return "acronym_repeated_gloss"
            end = m.end() + (gloss.end() if gloss else 0)
            if location["long_prose"]:
                # A token moved alone into a heading or appended after a finished
                # sentence is counted, but cannot own the substantive source clause.
                line_start = output.rfind("\n", 0, m.start()) + 1
                before = output[line_start:m.start()]
                if line_start and not before.strip(" \t\u2066\u2069") and re.search(
                        r"(?:إلى|في|على|من|عن|مع|لدى|أمام)\s*$", output[:line_start]):
                    prior_start = output.rfind("\n", 0, line_start-1) + 1
                    before = output[prior_start:m.start()]
                after = output[end:].split("\n", 1)[0]
                left = re.split(r"[.!?؟؛]", _MARK.sub(" ", before))[-1]
                right = re.split(r"[.!?؟؛]", _MARK.sub(" ", after))[0]
                if len(re.findall(r"[\u0621-\u064a]+", left + " " + right)) <= 2:
                    return "acronym_source_clause"
            clauses.append((m.start(), location["clause"]))
            for side in ("before", "after"):
                for value in location[side]:
                    found = [a for a in wrapped if a[1] == value]
                    if len(found) == 1 and (found[0].start() < m.start()) != (side == "before"):
                        return "acronym_source_clause"
            if location["continues"] and not re.search(r"[\u0621-\u064a]", output[end:]):
                return "acronym_source_clause"
    if [clause for _,clause in sorted(clauses)] != sorted(clause for _,clause in clauses):
        return "acronym_source_clause"
    return None


def check_evaluation(result, rows):
    if result.ok and rows and (failure := acronym_violation(result.normalized_text, rows)):
        return replace(result, ok=False, validator_failed=True, ar_violation_kind="expected_token_mismatch",
                       defect_reason=f"Source acronym token failed {failure}.")
    return result


def verified_owners(page, candidate, source_units, inventory, target_units, coverage):
    """Require an independently equivalent claim to link each source occurrence to its target unit."""
    for row in page.source_acronyms:
        matches = [m for m in _MARK.finditer(candidate) if m[1] == row["spelling"]]
        if len(matches) != len(row["locations"]):
            return False
        for span, match in zip(row["locations"], matches):
            owners = {u["unit_id"] for u in source_units if u["page"] == page.page_number
                      and u["start"] <= span["start"] < span["end"] <= u["end"]}
            claims = {c["claim_id"] for c in inventory["claims"] if owners.intersection(c["source_unit_ids"])}
            represented = {claim for u in target_units if u["page"] == page.page_number
                           and u["start"] <= match.start(1) < match.end(1) <= u["end"]
                           for claim in coverage[u["unit_id"]]}
            if not claims.intersection(represented):
                return False
    return True
