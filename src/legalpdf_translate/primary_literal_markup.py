"""Prospective lossless primary markup and converted-occurrence obligations.

This module never supplies source truth or provider instructions. Historical
callers do not invoke it. All evidence is owned, bounded and independently replayed.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata

KEY = "primary_literal_markup_policy"
POLICY = "whole_line_square_group_v1"
VERSION = "primary_literal_markup_evidence_v1"
DIRECTORY = "primary_markup"
PAGE_HASH = "primary_markup_evidence_sha256"
MAX_CHARS = 120_000
MAX_OCCURRENCES = 512
MAX_LINE = 2048
MAX_COMPONENT = 512
MAX_WORK = 1_200_000
PAGE_BYTES = 1024 * 1024
TOTAL_BYTES = 12 * PAGE_BYTES
LRI, PDI = "\u2066", "\u2069"
_IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9./:_-]*"
_NESTED = re.compile(r"\u2066\[\[(?P<left>" + _IDENTIFIER + r")(?P<sep> {1,8})\[(?P<right>" + _IDENTIFIER + r")\]\]\]\u2069\Z")
_OWNER = re.compile(r"\u2066\[\[([^\u2066\u2069]*)\]\]\u2069")
_TOKEN = re.compile(r"\u2066\[\[([^\[\]\r\n]+)\]\]\u2069")


class PrimaryMarkupError(ValueError):
    def __init__(self, code):
        self.code = "primary_markup_" + code
        super().__init__(self.code)


def fail(code):
    raise PrimaryMarkupError(code)


def encode(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        fail("shape")


def digest(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _primary_file_text(normalized):
    """Mirror the existing page Path.write_text newline producer exactly."""
    return normalized.replace("\n", os.linesep)


def check_policy(value):
    if value not in (None, POLICY) or value is not None and type(value) is not str:
        fail("policy")


def descriptor():
    return {"policy": POLICY, "evidence": VERSION,
        "recognition": "complete_ascii_identifier_square_line_v1",
        "ownership": "raw_derived_complete_sequence_unique_neighbors_v1",
        "page_bytes": PAGE_BYTES, "total_bytes": TOTAL_BYTES,
        "max_chars": MAX_CHARS, "max_occurrences": MAX_OCCURRENCES,
        "max_line": MAX_LINE, "max_component": MAX_COMPONENT, "max_work": MAX_WORK}


class Work:
    def __init__(self):
        self.used = 0
        self.acronym_selection = None

    def charge(self, *texts):
        if any(type(text) is not str for text in texts):
            fail("text")
        self.charge_size(sum(len(text) for text in texts))

    def charge_size(self, amount):
        if amount > MAX_WORK - self.used:
            fail("work_bound")
        self.used += amount


def supported(recipe, *, strip_bidi_controls, assembly_version):
    return (type(recipe) is dict and recipe.get("target_language") == "AR"
        and strip_bidi_controls is True and assembly_version == "terminal_source_bound_folio_v4"
        and recipe.get("semantic_source_review_policy") in ("source_commitment_visual_v7", "source_commitment_visual_v8", "source_commitment_visual_v9")
        and all(recipe.get(key) == value for key, value in {
            "version": "ordinary_semantic_audit_v3",
            "primary_literal_packaging_version": "lossless_source_components_v3",
            "semantic_repair_policy": "source_grounded_repair_once_v4",
            "semantic_literal_authority_policy": "source_literal_authority_v1",
            "semantic_enclosure_authority_policy": "source_enclosure_authority_v1",
            "source_enclosure_identity_policy": "bounded_distinct_additions_v1"}.items()))


def _span(text, start, end):
    return {"start": start, "end": end, "quote": text[start:end],
        "sha256": digest(text[start:end])}


def _signatures(values):
    from .ordinary_semantic_enclosure_authority import _signatures as signatures
    return signatures(values)


def _view(text):
    from .ar_source_fields import _view as view
    result = view(text)
    if result is None:
        fail("wrapper")
    if len(result[2]) > MAX_OCCURRENCES:
        fail("occurrence_bound")
    return result


@dataclass(frozen=True)
class Initial:
    raw: str
    transformed: str
    conversion: dict | None


def prepare_initial(raw, source, required, page, *, work=None):
    """Return a lossless representation or the exact unmodified raw response."""
    from .validators import parse_code_block_output
    work = work or Work()
    if type(raw) is not str or type(source) is not str or type(page) is not int or page < 1:
        fail("initial_binding")
    if (len(raw) + len(source) > MAX_CHARS or type(required) not in (list, tuple)
            or len(required) > MAX_OCCURRENCES
            or any(type(value) is not str or not value or len(value) > MAX_COMPONENT for value in required)):
        return Initial(raw, raw, None)
    work.charge(raw, source, *required)
    parsed = parse_code_block_output(raw)
    if (parsed.block_count != 1 or parsed.outside_has_non_whitespace or parsed.inner_content is None
            or not parsed.inner_content or raw.count(parsed.inner_content) != 1):
        return Initial(raw, raw, None)
    inner = parsed.inner_content
    offset = raw.index(inner)
    work.charge(inner)
    candidates = []
    for line in re.finditer(r"([^\r\n]*)(\r\n|\r|\n|$)", inner):
        value, ending = line[1], line[2]
        match = _NESTED.fullmatch(value) if len(value) <= MAX_LINE else None
        if match is not None:
            left, right = match["left"], match["right"]
            if (left == right or left not in required or right not in required
                    or len(left) > MAX_COMPONENT or len(right) > MAX_COMPONENT):
                return Initial(raw, raw, None)
            candidates.append((offset + line.start(), value, ending, match))
    if len(candidates) != 1:
        return Initial(raw, raw, None)
    start, original, ending, match = candidates[0]
    left, right, sep = match["left"], match["right"], match["sep"]
    converted = LRI + "[[" + left + "]]" + PDI + sep + "[" + LRI + "[[" + right + "]]" + PDI + "]"
    projection = left + sep + "[" + right + "]"
    # The old and new declared owner boundaries independently conserve print.
    if original[3:-3] != projection:
        fail("projection")
    work.charge(raw)
    transformed = raw[:start] + converted + raw[start + len(original):]
    # No partial normalization: every remaining token/control view must parse.
    try:
        work.charge(transformed)
        _view(parse_code_block_output(transformed).inner_content)
    except PrimaryMarkupError as exc:
        if exc.code == "primary_markup_wrapper":
            return Initial(raw, raw, None)
        raise
    conversion = {"page": page, "original_owner": _span(raw, start, start + len(original)),
        "original_line": _span(raw, start, start + len(original)), "line_ending": ending,
        "projection": projection, "projection_sha256": digest(projection),
        "left": left, "right": right, "sep": sep,
        "printed_pair": {"opening": len(left) + len(sep), "closing": len(projection) - 1,
            "depth": 1, "kind": "square"}}
    return Initial(raw, transformed, conversion)


def finalize_group(initial, normalized, *, work=None):
    """Bind the converted group to exact ordinary-normalized primary slots."""
    if initial.conversion is None:
        return []
    work = work or Work(); work.charge(initial.raw, normalized)
    if len(normalized) > MAX_CHARS:
        fail("text_bound")
    visible, _, tokens = _view(normalized)
    group = dict(initial.conversion)
    projection = group["projection"]
    lines = list(re.finditer(r"[^\r\n]+", visible))
    selected = [m for m in lines if m[0] == projection]
    if len(selected) != 1:
        fail("group_ownership")
    line = selected[0]; a = line.start(); left_end = a + len(group["left"])
    right_start = left_end + len(group["sep"]) + 1
    left = [i for i, t in enumerate(tokens) if t[:3] == (a, left_end, group["left"])]
    right = [i for i, t in enumerate(tokens) if t[:3] == (right_start, right_start + len(group["right"]), group["right"])]
    if len(left) != 1 or len(right) != 1 or right[0] != left[0] + 1:
        fail("group_ownership")
    values = [t[2] for t in tokens]; signatures = _signatures(values); counts = Counter(signatures)
    if any(counts[signatures[i]] != 1 for i in (left[0], right[0])):
        fail("ambiguous_neighborhood")
    from .ordinary_semantic_enclosure_authority import _shapes
    if _shapes(visible, tokens)[right[0]] != "square":
        fail("enclosure")
    group.update(canonical_primary_sha256=digest(normalized),
        ordinals=[left[0], right[0]], neighborhoods=[signatures[left[0]], signatures[right[0]]],
        complete_protected_sequence=values,
        canonical_spans=[_span(normalized, tokens[i][3], tokens[i][4]) for i in (left[0], right[0])])
    return [group]


def guard_group(text, baseline, groups, *, work=None, additions=None, original_values=None):
    """Preserve converted slots and their exact printed relation, not counts."""
    if not groups:
        return
    work = work or Work()
    if type(text) is not str or len(text) > MAX_CHARS or type(baseline) is not str:
        fail("candidate_bound")
    work.charge(text, baseline)
    from .ordinary_semantic_enclosure_authority import _candidate_tokens, _shapes
    from .ordinary_semantic_enclosure_identity import AdditionBudget
    from .ordinary_semantic_audit import SemanticAuditError
    old_visible, _, old_tokens = _view(baseline)
    try:
        visible, tokens = _candidate_tokens(text)
    except SemanticAuditError:
        fail("group_identity")
    if len(tokens) > MAX_OCCURRENCES:
        fail("occurrence_bound")
    # Compute the full stack before any projected occurrence mapping.
    try:
        shapes = _shapes(visible, tokens)
    except SemanticAuditError:
        fail("group_enclosure")
    expected = [t[2] for t in old_tokens]
    values = [t[2] for t in tokens]
    try:
        mapping = list(range(len(tokens))) if values == expected else (additions or AdditionBudget()).mapping(
            tokens, expected, original_values if original_values is not None else expected)
    except SemanticAuditError:
        fail("group_identity")
    signatures = _signatures(expected); counts = Counter(signatures)
    for group in groups:
        indices = group["ordinals"]
        if any(type(i) is not int or not 0 <= i < len(old_tokens) for i in indices):
            fail("group_ownership")
        if any(counts[signatures[i]] != 1 for i in indices):
            fail("ambiguous_neighborhood")
        left, right = (mapping[i] for i in indices)
        if right != left + 1 or shapes[right] != "square":
            fail("group_loss")
        a, b = tokens[left][0], tokens[right][1] + 1
        if visible[a:b] != group["projection"]:
            fail("group_loss")
        start = max(visible.rfind("\n", 0, a), visible.rfind("\r", 0, a)) + 1
        ends = [p for p in (visible.find("\n", b), visible.find("\r", b)) if p >= 0]
        end = min(ends) if ends else len(visible)
        if start != a or end != b:
            fail("group_line")
        if sum(line == group["projection"] for line in visible.splitlines()) != 1:
            fail("group_ownership")
        # _view deliberately tolerates unrelated isolates. That tolerance is not
        # permission for ambient controls to change this complete LTR owner.
        def owner(value):
            escaped = re.escape("[[" + value + "]]")
            return "(?:" + re.escape(LRI) + escaped + re.escape(PDI) + "|" + escaped + ")"
        raw_line = owner(group["left"]) + re.escape(group["sep"] + "[") + owner(group["right"]) + r"\]"
        if sum(re.fullmatch(raw_line, line) is not None for line in text.splitlines()) != 1:
            fail("group_controls")


def _read(path, limit, *, work=None):
    """Bounded owned reads; no symlink or nonregular evidence is admissible."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        fail("evidence_missing_or_bound")
    raw = path.read_bytes()
    if len(raw) > limit:
        fail("evidence_bound")
    if work is not None:
        # Encoded byte length conservatively bounds decoded codepoint parsing.
        work.charge_size(len(raw))
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        fail("evidence_shape")
    if encode(value) != raw:
        fail("evidence_encoding")
    return value, raw


def _directory(run_dir, *, create=False):
    path = Path(run_dir) / DIRECTORY
    if (Path(run_dir).is_symlink() or path.is_symlink() or path.resolve().parent != Path(run_dir).resolve()
            or path.exists() and not path.is_dir()):
        fail("evidence_path")
    if create:
        path.mkdir(exist_ok=True)
    return path


def _write(path, value):
    raw = encode(value)
    if len(raw) > PAGE_BYTES:
        fail("evidence_bound")
    if path.is_symlink():
        fail("evidence_path")
    if path.exists():
        if not path.is_file() or path.stat().st_size > PAGE_BYTES or path.read_bytes() != raw:
            fail("evidence_changed")
    else:
        # A crash can leave only an incomplete, non-admissible record; exclusive
        # creation never replaces another page's origin or a previous selection.
        with path.open("xb") as handle:
            handle.write(raw)
    return digest(raw)


def _source(run_dir, state, page, recipe, *, work=None):
    from .ordinary_semantic_audit import MAX_IMAGE_BYTES
    directory = Path(run_dir) / "semantic_source"
    if directory.is_symlink() or directory.resolve().parent != Path(run_dir).resolve():
        fail("source_path")
    data, raw = _read(directory / f"page_{page:04d}.json", MAX_IMAGE_BYTES * 4 // 3 + 2 * MAX_CHARS * 4)
    if (type(data) is not dict or type(data.get("page_number")) is not int
            or data["page_number"] != page or data.get("pdf_sha256") != state.pdf_fingerprint
            or data.get("recipe_sha256") != digest(encode(recipe))
            or data.get("selected_pages") != sorted(int(n) for n in state.pages)
            or digest(raw) != state.pages[str(page)].get("semantic_source_sha256")
            or type(data.get("source_text")) is not str
            or type(data.get("original_source_text")) is not str
            or type(data.get("expected_ar_tokens")) is not list):
        fail("source_binding")
    if "ocr_visual_source_policy" in recipe or "ocr_visual_source" in data:
        from .workflow_semantic_audit import _validate_ocr_acquisition
        _validate_ocr_acquisition(state=state, run_dir=run_dir, page_number=page, recipe=recipe, data=data)
    from . import ordinary_source_postal_band as postal_band
    if postal_band.KEY in recipe or postal_band.FIELD in data or postal_band.ROUTE in data:
        try:
            postal_band.validate_capture(state, recipe, page, data)
        except ValueError:
            fail("postal_source_binding")
    from . import ordinary_source_acronyms as acronyms
    if recipe.get("primary_page_evidence_policy") == acronyms.POLICY:
        from .workflow_semantic_audit import SemanticIntegrationError, _validate_terminology
        try:
            _validate_terminology(data.get("applicable_terminology"), data["original_source_text"])
        except SemanticIntegrationError:
            fail("acronym_source_binding")
        work = work or Work()
        numbers = sorted(int(n) for n in state.pages)
        identity = (state.pdf_path, state.pdf_fingerprint, tuple(numbers))
        if work.acronym_selection is None or work.acronym_selection[0] != identity:
            work.acronym_selection = (identity, acronyms.read_selection(state.pdf_path, numbers,
                                                expected_sha256=state.pdf_fingerprint))
        if (type(data.get("applicable_terminology")) is not list or
                not acronyms.capture_matches(data, work.acronym_selection[1], state.pages[str(page)])):
            fail("acronym_source_binding")
    elif "source_acronyms" in data:
        fail("acronym_source_binding")
    return data, digest(raw)


def _native(run_dir, state, page, response_id, *, expected=None):
    """Bind one settled native call, never the legitimately growing journal."""
    from .usage_accounting import _state_fingerprint, _validate_retained_events
    reference = state.dispatch_accounting
    identifier = reference.get("id") if type(reference) is dict else None
    if (type(identifier) is not str or re.fullmatch(r"[a-f0-9]{32}", identifier) is None
            or type(response_id) is not str or not response_id):
        fail("native_identity")
    parent = Path(run_dir) / "accounting"
    directory = parent / identifier
    path = directory / "dispatch_accounting.json"
    if (parent.is_symlink() or directory.is_symlink()
            or parent.resolve().parent != Path(run_dir).resolve() or directory.resolve().parent != parent.resolve()):
        fail("native_path")
    # The established journal uses indented JSON; unlike this module's own
    # records its serialization is not a canonical encoding contract.
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        fail("native_missing")
    try:
        journal = json.loads(path.read_bytes())
        if type(journal) is not dict or journal.get("fingerprint") != _state_fingerprint(journal):
            fail("native_integrity")
        _validate_retained_events(journal["events"])
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        fail("native_invalid")
    identity = journal.get("run_identity")
    if (type(identity) is not dict or identity.get("accounting_id") != identifier
            or identity.get("source_sha256") != state.pdf_fingerprint
            or identity.get("context_hash") != state.context_hash
            or identity.get("language") != state.lang
            or identity.get("selection") != [state.selection_start_page, state.selection_end_page]
            or identity.get("run_started_at") != state.run_started_at):
        fail("native_identity")
    finishes = [e for e in journal["events"] if e.get("event") == "finish"
        and e.get("response_id") == response_id]
    if len(finishes) != 1:
        fail("native_settlement")
    finish = finishes[0]
    begins = [e for e in journal["events"] if e.get("event") == "begin"
        and e.get("call_id") == finish.get("call_id")]
    if (len(begins) != 1 or type(begins[0].get("page_number")) is not int
            or begins[0]["page_number"] != page or begins[0].get("purpose") not in {"translation", "correction"}
            or finish.get("outcome") != "succeeded" or finish.get("cost_status") != "available"
            or finish.get("usage", {}).get("usage_status") != "available"):
        fail("native_settlement")
    result = {"run_identity": identity, "begin": begins[0], "finish": finish}
    if expected is not None and encode(result) != encode(expected):
        fail("native_changed")
    return result


def _binding(state, page, recipe, source, source_sha256):
    assembly = state.settings.get("primary_assembly_recipe", {})
    if not supported(recipe, strip_bidi_controls=state.settings.get("strip_bidi_controls"),
            assembly_version=assembly.get("version")):
        fail("dependencies")
    return {"page": page, "pdf_sha256": state.pdf_fingerprint,
        "selected_pages": sorted(int(n) for n in state.pages),
        "source_capture_sha256": source_sha256,
        "source_text_sha256": digest(source["source_text"]),
        "original_source_text_sha256": digest(source["original_source_text"]),
        "expected_literals_sha256": digest(encode(source["expected_ar_tokens"])),
        "recipe_sha256": digest(encode(recipe)), "descriptor": descriptor(),
        "target_language": recipe["target_language"], "strip_bidi_controls": True,
        "assembly": assembly}


def evaluate_initial(raw, source, required, page, recipe, *, work=None, acronym_rows=(), source_witness=None, postal_rows=()):
    from .workflow_components.evaluation import evaluate_output
    from .types import TargetLang
    work = work or Work()
    if source_witness and "ocr_visual_source_policy" not in recipe:
        fail("source_binding")
    initial = prepare_initial(raw, source, required, page, work=work)
    from . import ordinary_source_postal_band as postal_band
    if postal_rows:
        if recipe.get(postal_band.KEY) != postal_band.POLICY:
            fail("postal_source_binding")
        initial = replace(initial, transformed=postal_band.derive(initial.transformed, postal_rows))
    work.charge(initial.transformed)
    result = evaluate_output(initial.transformed, TargetLang.AR,
        expected_ar_tokens=required, ar_source_text=source,
        source_field_policy=recipe["source_field_policy"],
        literal_wrapper_policy=recipe["primary_literal_packaging_version"],
        source_inline_address_join_policy=recipe.get("source_inline_address_join_policy"))
    from .ordinary_source_acronyms import check_evaluation
    result = check_evaluation(result, acronym_rows)
    result = postal_band.checked(result, initial.transformed, postal_rows)
    if source_witness:
        from .ordinary_ocr_visual_source import checked
        result = checked(result, source, source_witness)
    groups = finalize_group(initial, result.normalized_text, work=work) if initial.conversion else []
    return initial, result, groups


def evaluate_compliance(raw, initial_result, initial, groups, source, required, recipe, *, work=None, acronym_rows=(), source_witness=None, postal_rows=()):
    from .workflow_components.evaluation import evaluate_output
    from .types import TargetLang
    from .validators import parse_code_block_output
    work = work or Work()
    if source_witness and "ocr_visual_source_policy" not in recipe:
        fail("source_binding")
    if type(raw) is not str or len(raw) > MAX_CHARS:
        fail("candidate_bound")
    from . import ordinary_source_postal_band as postal_band
    if postal_rows:
        if recipe.get(postal_band.KEY) != postal_band.POLICY:
            fail("postal_source_binding")
        raw = postal_band.derive(raw, postal_rows)
    work.charge(raw)
    parsed = parse_code_block_output(raw)
    baseline = initial_result.normalized_text
    if source_witness and parsed.block_count == 1 and not parsed.outside_has_non_whitespace:
        from .ordinary_ocr_visual_source import compliance_baseline
        baseline = compliance_baseline(baseline, parsed.inner_content, source_witness, source=source)
    if groups:
        if parsed.block_count != 1 or parsed.outside_has_non_whitespace or parsed.inner_content is None:
            fail("candidate_parser")
        guard_group(parsed.inner_content, baseline, groups, work=work)
    result = evaluate_output(raw, TargetLang.AR, expected_ar_tokens=required,
        ar_source_text=source, primary_normalized_text=baseline,
        source_field_policy=recipe["source_field_policy"],
        literal_wrapper_policy=recipe["primary_literal_packaging_version"],
        source_inline_address_join_policy=recipe.get("source_inline_address_join_policy"))
    from .ordinary_source_acronyms import check_evaluation
    result = check_evaluation(result, acronym_rows)
    result = postal_band.checked(result, raw, postal_rows)
    if source_witness:
        from .ordinary_ocr_visual_source import checked
        result = checked(result, source, source_witness)
    if result.ok and groups:
        guard_group(result.normalized_text, baseline, groups, work=work)
    return result


def retain_initial(*, state, run_dir, page, recipe, raw, response_id, initial, result, groups):
    source, source_hash = _source(run_dir, state, page, recipe)
    if type(raw) is not str or len(raw) + len(source["source_text"]) > MAX_CHARS:
        fail("initial_bound")
    # Recompute rather than adopt a workflow annotation or guessed raw hash.
    check, evaluated, expected_groups = evaluate_initial(raw, source["source_text"],
        source["expected_ar_tokens"], page, recipe, acronym_rows=source.get("source_acronyms", ()), source_witness=source.get("ocr_visual_source"), postal_rows=source.get("source_postal_bands", ()))
    if (check != initial or evaluated != result or encode(expected_groups) != encode(groups)):
        fail("initial_changed")
    native = _native(run_dir, state, page, response_id)
    if native["begin"]["purpose"] != "translation":
        fail("initial_native_purpose")
    payload = {"version": VERSION, "binding": _binding(state, page, recipe, source, source_hash),
        "raw_initial": raw, "raw_initial_sha256": digest(raw),
        "transformed_sha256": digest(initial.transformed),
        "initial_normalized_sha256": digest(result.normalized_text) if result.normalized_text is not None else None,
        "initial_ok": result.ok, "conversion": initial.conversion, "groups": groups,
        "native": native}
    path = _directory(run_dir, create=True) / f"page_{page:04d}.initial.json"
    return _write(path, payload)


def retain_selection(*, state, run_dir, page, recipe, origin, raw, response_id, normalized):
    if origin not in {"initial", "compliance"}:
        fail("selection_origin")
    directory = _directory(run_dir)
    initial_record, initial_bytes = _read(directory / f"page_{page:04d}.initial.json", PAGE_BYTES)
    selection = {"version": VERSION, "page": page, "initial_sha256": digest(initial_bytes),
        "origin": origin, "raw_selected": raw, "raw_selected_sha256": digest(raw),
        "selected_normalized_sha256": digest(normalized),
        "selected_primary_sha256": digest(_primary_file_text(normalized)),
        "native": _native(run_dir, state, page, response_id)}
    # Full replay before creating the accepting record, including zero groups.
    selected, _ = _replay(state=state, run_dir=run_dir, page=page, recipe=recipe,
        initial_record=initial_record, selection=selection, initial_bytes=initial_bytes)
    if selected != normalized:
        fail("selection_changed")
    if len(initial_bytes) + len(encode(selection)) > PAGE_BYTES:
        fail("page_evidence_bound")
    return _write(directory / f"page_{page:04d}.selection.json", selection)


def _replay(*, state, run_dir, page, recipe, initial_record, selection, initial_bytes, work=None):
    work = work or Work()
    source, source_hash = _source(run_dir, state, page, recipe, work=work)
    if (type(initial_record) is not dict or set(initial_record) != {"version", "binding", "raw_initial",
            "raw_initial_sha256", "transformed_sha256", "initial_normalized_sha256", "initial_ok",
            "conversion", "groups", "native"}
            or type(selection) is not dict or set(selection) != {"version", "page", "initial_sha256",
            "origin", "raw_selected", "raw_selected_sha256", "selected_normalized_sha256", "selected_primary_sha256", "native"}
            or type(initial_record.get("native")) is not dict
            or type(initial_record["native"].get("finish")) is not dict
            or type(selection.get("native")) is not dict or type(selection["native"].get("finish")) is not dict
            or type(initial_record.get("raw_initial")) is not str
            or len(initial_record["raw_initial"]) + len(source["source_text"]) > MAX_CHARS):
        fail("evidence_shape")
    raw = initial_record.get("raw_initial")
    initial, result, groups = evaluate_initial(raw, source["source_text"], source["expected_ar_tokens"],
        page, recipe, work=work, acronym_rows=source.get("source_acronyms", ()), source_witness=source.get("ocr_visual_source"), postal_rows=source.get("source_postal_bands", ()))
    expected = {"version": VERSION, "binding": _binding(state, page, recipe, source, source_hash),
        "raw_initial": raw, "raw_initial_sha256": digest(raw),
        "transformed_sha256": digest(initial.transformed),
        "initial_normalized_sha256": digest(result.normalized_text) if result.normalized_text is not None else None,
        "initial_ok": result.ok, "conversion": initial.conversion, "groups": groups,
        "native": _native(run_dir, state, page,
            initial_record.get("native", {}).get("finish", {}).get("response_id"),
            expected=initial_record.get("native"))}
    if encode(expected) != encode(initial_record):
        fail("initial_evidence_changed")
    if expected["native"]["begin"]["purpose"] != "translation":
        fail("initial_native_purpose")
    origin, selected_raw = selection.get("origin"), selection.get("raw_selected")
    native = _native(run_dir, state, page,
        selection.get("native", {}).get("finish", {}).get("response_id"), expected=selection.get("native"))
    if origin == "initial":
        if (selected_raw != raw or encode(native) != encode(expected["native"])
                or native["begin"]["purpose"] != "translation"):
            fail("selection_origin")
        selected = result
    elif origin == "compliance":
        if (result.ok or native["begin"]["call_id"] == expected["native"]["begin"]["call_id"]
                or native["begin"]["purpose"] != "correction"):
            fail("selection_origin")
        selected = evaluate_compliance(selected_raw, result, initial, groups, source["source_text"],
            source["expected_ar_tokens"], recipe, work=work, acronym_rows=source.get("source_acronyms", ()), source_witness=source.get("ocr_visual_source"), postal_rows=source.get("source_postal_bands", ()))
    else:
        fail("selection_origin")
    if not selected.ok or selected.normalized_text is None or len(selected.normalized_text) > MAX_CHARS:
        fail("selection_invalid")
    expected_selection = {"version": VERSION, "page": page, "initial_sha256": digest(initial_bytes),
        "origin": origin, "raw_selected": selected_raw, "raw_selected_sha256": digest(selected_raw),
        "selected_normalized_sha256": digest(selected.normalized_text),
        "selected_primary_sha256": digest(_primary_file_text(selected.normalized_text)), "native": native}
    if encode(expected_selection) != encode(selection):
        fail("selection_evidence_changed")
    if origin == "compliance" and groups and source.get("ocr_visual_source"):
        groups = finalize_group(initial, selected.normalized_text, work=work)
    return selected.normalized_text, groups


@dataclass(frozen=True)
class Context:
    """Local owned proof, never a provider/public contract or admission flag."""
    state: object
    run_dir: Path
    recipe: dict
    primary: dict
    groups: dict
    evidence_sha256: str


def load_context(*, state, run_dir, completed_only=False):
    from .checkpoint import ordinary_semantic_audit_recipe
    recipe = ordinary_semantic_audit_recipe(state.settings)
    policy = recipe.get(KEY) if recipe else None
    check_policy(policy)
    directory = _directory(run_dir)
    if policy is None:
        if directory.exists() or any(PAGE_HASH in record for record in state.pages.values()):
            fail("policy_missing")
        return None
    if (not supported(recipe, strip_bidi_controls=state.settings.get("strip_bidi_controls"),
            assembly_version=state.settings.get("primary_assembly_recipe", {}).get("version"))
            or not 1 <= len(state.pages) <= 12):
        fail("dependencies")
    numbers = sorted(int(n) for n in state.pages)
    if numbers != list(range(state.selection_start_page, state.selection_end_page + 1)):
        fail("selection")
    names = {f"page_{page:04d}.{kind}.json" for page in numbers for kind in ("initial", "selection")}
    actual_names = set()
    if directory.is_dir():
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file() or path.name not in names or len(actual_names) >= len(names):
                fail("evidence_foreign")
            actual_names.add(path.name)
    if completed_only:
        pending = [page for page in numbers if state.pages[str(page)].get("status") != "done"]
        if any(f"page_{page:04d}.{kind}.json" in actual_names
                for page in pending for kind in ("initial", "selection")):
            fail("incomplete_primary_evidence")
        numbers = [page for page in numbers if page not in pending]
        if not numbers:
            return None
    if (not directory.is_dir() or (not completed_only and actual_names != names)):
        fail("evidence_missing_or_foreign")
    total, primary, groups, pins, work = 0, {}, {}, [], Work()
    for page in numbers:
        remaining = TOTAL_BYTES - total
        initial, raw_initial = _read(directory / f"page_{page:04d}.initial.json",
            min(PAGE_BYTES, remaining), work=work)
        selection, raw_selection = _read(directory / f"page_{page:04d}.selection.json",
            min(PAGE_BYTES - len(raw_initial), remaining - len(raw_initial)), work=work)
        total += len(raw_initial) + len(raw_selection)
        if len(raw_initial) + len(raw_selection) > PAGE_BYTES or total > TOTAL_BYTES:
            fail("evidence_bound")
        metadata = state.pages[str(page)]
        if metadata.get("status") != "done" or metadata.get(PAGE_HASH) != digest(raw_selection):
            fail("checkpoint_binding")
        text, obligations = _replay(state=state, run_dir=run_dir, page=page, recipe=recipe,
            initial_record=initial, selection=selection, initial_bytes=raw_initial, work=work)
        text = _primary_file_text(text)
        original = Path(run_dir) / "pages" / f"page_{page:04d}.txt"
        if original.is_symlink() or original.exists() and (not original.is_file()
                or original.stat().st_size > PAGE_BYTES or original.read_bytes() != text.encode("utf-8")):
            fail("surviving_primary_changed")
        primary[page], groups[page] = text, obligations
        pins.append({"page": page, "initial_sha256": digest(raw_initial),
            "selection_sha256": digest(raw_selection), "selected_primary_sha256": digest(text)})
    return Context(state, Path(run_dir), recipe, primary, groups, digest(encode(pins)))


def validate_context(policy, context, pages, recipe, pdf_sha256, *, repair_policy, identity_policy,
                     source_policy, literal_policy, enclosure_policy):
    check_policy(policy)
    if policy is None:
        if context is not None:
            fail("context_without_policy")
        return None
    if type(context) is not Context:
        fail("context_missing")
    checked = load_context(state=context.state, run_dir=context.run_dir)
    from .semantic_review_model_policy import effective_model
    if (checked is None or encode(checked.primary) != encode(context.primary)
            or encode(checked.groups) != encode(context.groups)
            or encode(checked.recipe) != encode(context.recipe)
            or checked.evidence_sha256 != context.evidence_sha256
            or pdf_sha256 != context.state.pdf_fingerprint
            or checked.recipe[KEY] != policy
            or repair_policy != checked.recipe["semantic_repair_policy"]
            or identity_policy != checked.recipe["source_enclosure_identity_policy"]
            or source_policy != checked.recipe["semantic_source_review_policy"]
            or literal_policy != checked.recipe["semantic_literal_authority_policy"]
            or enclosure_policy != checked.recipe["semantic_enclosure_authority_policy"]
            or recipe.target_language != "AR"
            or recipe.model != effective_model(checked.recipe)
            or any(getattr(recipe, key) != checked.recipe[key] for key in
                ("reasoning_effort", "effort_policy", "configured_image_mode", "source_field_policy"))
            or recipe.source_inline_address_join_policy != checked.recipe.get("source_inline_address_join_policy")
            or {p.page_number for p in pages} != set(checked.primary)):
        fail("context_changed")
    work = Work()
    for page in pages:
        source, _ = _source(context.run_dir, context.state, page.page_number, checked.recipe, work=work)
        if (page.primary_text != checked.primary[page.page_number]
                or page.source_text != source["source_text"]
                or page.original_source_text != source["original_source_text"]
                or tuple(page.expected_ar_tokens) != tuple(source["expected_ar_tokens"])
                or tuple(page.source_acronyms) != tuple(source.get("source_acronyms", ()))
                or page.image_data_url != source["image_data_url"]):
            fail("context_pages")
    return checked


def guard_candidates(context, candidates, *, effective_pages=None, work=None):
    if context is None:
        return
    from .ordinary_semantic_enclosure_identity import AdditionBudget
    work, additions = work or Work(), AdditionBudget()
    if type(candidates) is not dict or set(candidates) != set(context.primary):
        fail("candidate_pages")
    effective = {p.page_number: p.primary_text for p in effective_pages} if effective_pages is not None else context.primary
    if set(effective) != set(context.primary):
        fail("effective_pages")
    from .ordinary_source_acronyms import POLICY as acronym_policy, acronym_violation
    for page, baseline in context.primary.items():
        candidate = candidates[page]
        from . import ordinary_source_postal_band as postal_band
        if postal_band.KEY in context.recipe:
            source, _ = _source(context.run_dir, context.state, page, context.recipe, work=work)
            defect = postal_band.violation(candidate, source[postal_band.FIELD])
            if defect:
                fail(defect)
        if context.recipe.get("primary_page_evidence_policy") == acronym_policy:
            source, _ = _source(context.run_dir, context.state, page, context.recipe, work=work)
            defect = acronym_violation(candidates[page], source["source_acronyms"])
            if defect:
                fail(defect)
        if "ocr_visual_source_policy" in context.recipe:
            from .ordinary_ocr_visual_source import semantic_guard_view, violation
            source, _ = _source(context.run_dir, context.state, page, context.recipe, work=work)
            candidate = semantic_guard_view(candidate, source["source_text"], source.get("ocr_visual_source"))
            defect = violation(candidate, source["source_text"], source.get("ocr_visual_source"))
            if defect:
                fail(defect)
        groups = context.groups[page]
        if groups and effective[page] != baseline:
            # This argument is supplied ONLY after the existing authority
            # certificate/projector has independently licensed exact old slots.
            work.charge(baseline, effective[page])
            _, _, original = _view(baseline)
            _, _, projected = _view(effective[page])
            if len(projected) != len(original):
                fail("projected_occurrences")
            adjusted = []
            for group in groups:
                left, right = [projected[i][2] for i in group["ordinals"]]
                if (left == right or any(len(v) > MAX_COMPONENT or re.fullmatch(_IDENTIFIER, v) is None for v in (left, right))):
                    fail("projected_group")
                conversion = {k: v for k, v in group.items() if k not in {
                    "canonical_primary_sha256", "ordinals", "neighborhoods", "complete_protected_sequence", "canonical_spans"}}
                projection = left + group["sep"] + "[" + right + "]"
                conversion.update(left=left, right=right, projection=projection,
                    projection_sha256=digest(projection), printed_pair={"opening": len(left) + len(group["sep"]),
                        "closing": len(projection) - 1, "depth": 1, "kind": "square"})
                new = finalize_group(Initial("", "", conversion), effective[page], work=work)
                if new[0]["ordinals"] != group["ordinals"]:
                    fail("projected_slots")
                adjusted.extend(new)
            groups = adjusted
        if groups:
            work.charge(baseline)
        original_values = [token[2] for token in _view(baseline)[2]] if groups else None
        guard_group(candidate, effective[page], groups, work=work, additions=additions,
            original_values=original_values)


def guard_correction(context, canonical, working_pages, *, effective_pages=None, work=None):
    if context is None:
        return
    rows = canonical.get("pages") if type(canonical) is dict else None
    if type(rows) is not list or len(rows) != len(working_pages):
        fail("candidate_pages")
    selected = {}
    for row, page in zip(rows, working_pages):
        if type(row) is not dict or type(row.get("page_number")) is not int or row["page_number"] != page.page_number:
            fail("candidate_pages")
        if row.get("status") == "no_change" and row.get("corrected_text") == "":
            selected[page.page_number] = page.primary_text
        elif row.get("status") == "corrected" and type(row.get("corrected_text")) is str:
            selected[page.page_number] = row["corrected_text"]
        else:
            fail("candidate_pages")
    guard_candidates(context, selected, effective_pages=effective_pages, work=work)


def expected_admission(*, state, run_dir, config):
    """Capture from the completing workflow's trusted in-memory saved recipe."""
    if state is None:
        if _directory(run_dir).exists():
            fail("owned_origin_missing")
        return None
    saved = state.settings.get("ordinary_semantic_audit_recipe")
    if type(saved) is not dict or KEY not in saved:
        if _directory(run_dir).exists():
            fail("owned_policy_missing")
        return None
    context = load_context(state=state, run_dir=run_dir)
    if (context is None or config is None or config.target_lang.value != state.lang
            or config.strip_bidi_controls is not True
            or config.effort.value != context.recipe["reasoning_effort"]
            or config.effort_policy.value != context.recipe["effort_policy"]
            or config.image_mode.value != context.recipe["configured_image_mode"]
            or Path(config.pdf_path).resolve() != Path(state.pdf_path).resolve()):
        fail("owned_configuration")
    manifest, manifest_raw = _read(Path(run_dir) / "semantic_audit" / "manifest.json", PAGE_BYTES)
    binding = manifest.get("binding") if type(manifest) is dict else None
    if (type(binding) is not dict or binding.get("primary_markup_evidence_sha256") != context.evidence_sha256
            or type(binding.get("semantic_repair_policy")) is not dict
            or encode(binding["semantic_repair_policy"].get(KEY)) != encode(descriptor())):
        fail("owned_semantic_binding")
    return {"version": "primary_markup_owned_admission_v1", "policy": POLICY,
        "descriptor": descriptor(), "recipe_sha256": digest(encode(context.recipe)),
        "evidence_sha256": context.evidence_sha256,
        "primary_sha256": [{"page": p, "sha256": digest(t)} for p,t in context.primary.items()],
        "run_dir": str(Path(run_dir).resolve()), "run_started_at": state.run_started_at,
        "semantic_binding_sha256": digest(encode(binding)), "semantic_manifest_sha256": digest(manifest_raw),
        "pdf_sha256": state.pdf_fingerprint, "context_hash": state.context_hash,
        "selected_pages": sorted(int(n) for n in state.pages), "target_language": state.lang,
        "configuration": {"source_path": str(Path(config.pdf_path).resolve()),
            "target_language": config.target_lang.value, "strip_bidi_controls": config.strip_bidi_controls,
            "reasoning_effort": config.effort.value, "effort_policy": config.effort_policy.value,
            "image_mode": config.image_mode.value,
            "start_page": config.start_page, "end_page": config.end_page, "max_pages": config.max_pages},
        "assembly": state.settings["primary_assembly_recipe"]}


def admit_owned_job(*, run_dir, source_pdf, selected_pages, target_lang, writer_map,
                    expected=None, config=None):
    """Common service admission, including already-existing candidate reuse."""
    from types import SimpleNamespace
    from .checkpoint import load_run_state, ordinary_semantic_audit_recipe
    from .types import TargetLang, ReasoningEffort, EffortPolicy
    from .workflow_semantic_audit import select_pages
    run_dir = Path(run_dir)
    # The old trusted-job path never loaded translation checkpoints. Keep its
    # absent capability/no-owned-marker route free of that new interpretation.
    if expected is None:
        if _directory(run_dir).exists():
            fail("owned_admission_missing")
        return False
    path = run_dir / "run_state.json"
    if (path.is_symlink() or not path.is_file() or path.stat().st_size > PAGE_BYTES
            or type(expected) is not dict):
        fail("checkpoint_path")
    state = load_run_state(path)
    if state is None:
        fail("checkpoint_missing")
    saved = ordinary_semantic_audit_recipe(state.settings)
    context = load_context(state=state, run_dir=run_dir)
    if context is None or encode(expected_admission(state=state, run_dir=run_dir, config=config)) != encode(expected):
        fail("owned_admission_changed")
    source_path = Path(source_pdf)
    source_limit = 64 * 1024 * 1024
    if source_path.is_symlink() or not source_path.is_file() or source_path.stat().st_size > source_limit:
        fail("owned_source_bound")
    with source_path.open("rb") as handle:
        source_bytes = handle.read(source_limit + 1)
    if len(source_bytes) > source_limit:
        fail("owned_source_bound")
    if (state.lang != target_lang or sorted(int(n) for n in state.pages) != list(selected_pages)
            or digest(source_bytes) != state.pdf_fingerprint
            or Path(state.run_dir_abs).resolve() != run_dir.resolve()):
        fail("owned_job_binding")
    config = SimpleNamespace(pdf_path=Path(source_pdf), target_lang=TargetLang(target_lang),
        effort=ReasoningEffort(saved["reasoning_effort"]), effort_policy=EffortPolicy(saved["effort_policy"]))
    _, result = select_pages(state=state, config=config, run_dir=run_dir, pages_dir=run_dir / "pages")
    if result is None:
        fail("semantic_selection_missing")
    rows = writer_map.get("pages") if type(writer_map) is dict else None
    if type(rows) is not list or len(rows) != len(selected_pages):
        fail("writer_map")
    for row, page in zip(rows, selected_pages):
        # The unchanged writer reads Path.read_text (universal newlines), then
        # hashes those exact UTF-8 characters before any presentation transform.
        text = result.selected_text_by_page[page].replace("\r\n", "\n").replace("\r", "\n")
        if (type(row) is not dict or type(row.get("source_page_number")) is not int
                or row["source_page_number"] != page or row.get("translation_sha256") != digest(text)):
            fail("writer_selection_changed")
    return True


def local_selection(*, state, run_dir):
    """Pruned primaries may authorize only the existing zero-send final chain."""
    from types import SimpleNamespace
    from .types import TargetLang, ReasoningEffort, EffortPolicy
    from .workflow_semantic_audit import select_pages
    from .checkpoint import ordinary_semantic_audit_recipe
    saved = ordinary_semantic_audit_recipe(state.settings)
    if saved is None or saved.get(KEY) != POLICY:
        fail("policy_missing")
    config = SimpleNamespace(pdf_path=Path(state.pdf_path), target_lang=TargetLang(state.lang),
        effort=ReasoningEffort(saved["reasoning_effort"]), effort_policy=EffortPolicy(saved["effort_policy"]))
    return select_pages(state=state, config=config, run_dir=Path(run_dir), pages_dir=Path(run_dir)/"pages")
