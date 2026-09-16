"""Pure document-local folio consistency for the reviewed formatting v2 lane.

This does not approve source, recognize pixels, infer document groups, or change
text. The caller MUST first verify the externally pinned full source-review
envelope/evidence and the exact original commits/images. Adapter metadata below
is rechecked for consistency, not treated as a new source-acceptance decision.
In particular genuine adapter source_acceptance remains not_evaluated.

The existing v1 global/slash-only formatting contract does not call this helper.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import unicodedata
from typing import Mapping, Sequence

from .document_structure import validate_page_structure

FOLIO_POLICY = "reviewed_document_local_folios_v1"
MAX_PAGES = 1000
MAX_FRAGMENTS = 5000
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_CASE_BYTES = 128 * 1024 * 1024
_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z", re.ASCII)
_DIGITS = "0-9\u0660-\u0669"
_BIDI_OPEN = {"\u202a": "embedding", "\u202b": "embedding", "\u202d": "embedding", "\u202e": "embedding",
              "\u2066": "isolate", "\u2067": "isolate", "\u2068": "isolate"}
_BIDI_MARKS = frozenset("\u061c\u200e\u200f\ufeff")
_CONTROLS = frozenset(_BIDI_OPEN) | _BIDI_MARKS | {"\u202c", "\u2069"}
_TOKEN = re.compile(r"\[\[([^\[\]]+)\]\]")
# A closed Portuguese docket field is not a printed page ratio. This grammar
# is used only with source/target preservation and reviewed top-quarter owner
# checks below; it is deliberately NOT an exception in the broad _hint scan.
_DOCKET_FIELD = re.compile(
    r"(?P<docket>[0-9]{1,8}/[0-9]{2}\.[0-9][A-Z][A-Z0-9]{1,11})"
    r"(?:[ \t]+\[(?P<reference>[0-9]{1,20})\])?(?:[ \t]+\|)?\Z", re.ASCII)


class ReviewedFolioError(ValueError):
    """Only bounded content-free categories leave this module."""


@dataclass(frozen=True, slots=True)
class FolioFragmentInput:
    rendering_id: str
    parent_block_id: str
    source_range: tuple[int, int]
    target_range: tuple[int, int]
    role: str
    bbox_px: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class FolioPageInput:
    source_structure: Mapping
    target_structure: Mapping
    image_height_px: int
    folio_fragment_id: str | None
    fragments: tuple[FolioFragmentInput, ...]
    region_layout: dict | None = None
    image_width_px: int | None = None


@dataclass(frozen=True, slots=True)
class ValidatedFolioPage:
    source_page: int
    document_index: int
    start_page: int
    end_page: int
    local_page: int
    local_total: int
    folio_fragment_id: str | None
    source_form: str | None
    target_form: str | None
    source_numbers: tuple[str, str] | None
    target_numbers: tuple[str, str] | None
    source_folio_sha256: str | None
    target_folio_sha256: str | None


def _require(condition, code):
    if not condition:
        raise ReviewedFolioError(code)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash(value):
    _require(type(value) is str and _HASH.fullmatch(value) is not None, "folio_evidence_hash_invalid")
    return value


def _snapshot(value):
    _require(isinstance(value, Mapping), "folio_structure_invalid")
    raw = json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _require(0 < len(raw) <= MAX_PAGE_BYTES, "folio_structure_oversized")
    result = json.loads(raw)
    validate_page_structure(result)
    _require(type(result.get("version")) is int and result["version"] == 1, "folio_structure_invalid")
    return result, len(raw)


def _groups(value, count):
    _require(type(value) is list and 0 < len(value) <= count, "folio_groups_invalid")
    expected, contexts = 1, []
    for index, group in enumerate(value, 1):
        _require(type(group) is dict and set(group) == {"start_page", "end_page"}, "folio_groups_invalid")
        start, end = group["start_page"], group["end_page"]
        _require(type(start) is int and type(end) is int and start == expected and start <= end <= count,
                 "folio_groups_invalid")
        contexts.extend((index, start, end, number - start + 1, end - start + 1) for number in range(start, end + 1))
        expected = end + 1
    _require(expected == count + 1, "folio_groups_incomplete")
    return tuple(contexts)


def _source_pair(source, target, *, number, source_hash):
    _require(source.get("page_number") == target.get("page_number") == number
             and source.get("source_file_sha256") == source_hash
             and source.get("provenance") == "reviewed_image_source_v1"
             and source.get("uncertain") is True and source.get("translation_sha256") is None,
             "folio_source_identity_invalid")
    fixed = (set(source) | set(target)) - {"blocks", "metadata", "translation_sha256"}
    _require(all(source.get(key) == target.get(key) for key in fixed), "folio_source_target_changed")
    left, right = source["blocks"], target["blocks"]
    _require(left and len(left) == len(right), "folio_source_target_changed")
    for a, b in zip(left, right):
        _require(a.get("role") == "paragraph" and a.get("uncertain") is True
                 and a.get("table_id") is None and a.get("continuation_of") is None
                 and {k: v for k, v in a.items() if k != "text"} == {k: v for k, v in b.items() if k != "text"},
                 "folio_source_target_changed")
    source_text = "\n".join(block["text"] for block in left)
    _require(source.get("source_sha256") == source.get("source_text_sha256") == _sha(source_text)
             and target.get("translation_sha256") == _sha("\n".join(block["text"] for block in right)),
             "folio_source_target_text_changed")
    _require(all(target.get("metadata", {}).get(key) == value for key, value in source.get("metadata", {}).items()),
             "folio_source_metadata_changed")


def _boundary(source, *, start, source_hash):
    metadata = source["metadata"]
    identity, review = metadata.get("source_page_identity"), metadata.get("reviewed_source")
    _require(type(identity) is dict and set(identity) == {"source_file_sha256", "image_sha256", "source_type", "paper_size_basis"}
             and identity["source_file_sha256"] == source_hash and identity["source_type"] in {"image", "browser_pdf_image"}
             and identity["paper_size_basis"] in {"source_pdf", "a4_assumed"}, "folio_source_image_binding_invalid")
    _hash(identity["image_sha256"])
    _require(metadata.get("selected_text_sha256") == source["source_sha256"]
             and metadata.get("source_coverage_status") == "reviewed_image_transcription"
             and metadata.get("document_boundary_review_required") is False
             and metadata.get("document_boundary_basis") == "explicit_reviewed_image_boundary"
             and type(review) is dict and review.get("version") == "reviewed_image_source_v1"
             and review.get("review_kind") in {"ai_test_review", "operator_review"}
             and review.get("source_acceptance") == review.get("layout_acceptance") == "not_evaluated"
             and review.get("geometry_status") == "not_verified"
             and review.get("review_image_sha256") == identity["image_sha256"], "folio_boundary_evidence_invalid")
    pins = tuple(_hash(review.get(key)) for key in ("candidate_file_sha256", "candidate_sha256", "manifest_sha256"))
    _hash(review.get("review_evidence_sha256"))
    boundary = review.get("boundary")
    _require(type(boundary) is dict and set(boundary) == {"decision", "rationale"}
             and boundary["decision"] == ("start" if start else "continuation")
             and type(boundary["rationale"]) is str and 0 < len(boundary["rationale"].strip()) <= 100_000
             and source.get("document_start") is start
             and all(block.get("document_start") is (start and index == 0) for index, block in enumerate(source["blocks"]))
             and (not start or source.get("continuation_from_previous") is False), "folio_boundary_group_mismatch")
    mapping, variants = review.get("mapping"), review.get("raw_variants")
    _require(type(mapping) is list and len(mapping) == len(source["blocks"])
             and type(variants) is list and 0 < len(variants) <= MAX_FRAGMENTS, "folio_provenance_mapping_invalid")
    actions = set()
    for row, block in zip(mapping, source["blocks"]):
        _require(type(row) is dict and set(row) == {"id", "action_id", "baseline_block_ids"}
                 and row["id"] == block["id"] and type(row["action_id"]) is str
                 and _ID.fullmatch(row["action_id"]) is not None and row["action_id"] not in actions,
                 "folio_provenance_mapping_invalid")
        actions.add(row["action_id"])
        ids = row["baseline_block_ids"]
        # A reviewed transcribe action can recover text absent from every
        # baseline block. The external action/evidence guard authenticates it.
        _require(type(ids) is list and len(ids) <= MAX_FRAGMENTS
                 and all(type(item) is str and _ID.fullmatch(item) is not None for item in ids)
                 and len(set(ids)) == len(ids), "folio_provenance_mapping_invalid")
    variant_ids = set()
    for variant in variants:
        _require(type(variant) is dict and set(variant) == {"id", "text_sha256", "tsv_sha256", "structure_sha256"}
                 and type(variant["id"]) is str and _ID.fullmatch(variant["id"]) is not None
                 and variant["id"] not in variant_ids, "folio_provenance_mapping_invalid")
        variant_ids.add(variant["id"])
        for key in ("text_sha256", "tsv_sha256", "structure_sha256"):
            _hash(variant[key])
    return pins


def _visible(text):
    """Closed display-only cleanup; malformed tokens/scopes cannot hide labels."""
    value = _TOKEN.sub(lambda match: match[1], text)
    _require("[" not in value and "]" not in value, "folio_placeholder_invalid")
    stack, result = [], []
    for char in value:
        if char in _BIDI_OPEN:
            stack.append(_BIDI_OPEN[char])
        elif char in {"\u202c", "\u2069"}:
            expected = "embedding" if char == "\u202c" else "isolate"
            _require(stack and stack[-1] == expected, "folio_bidi_scope_invalid")
            stack.pop()
        elif char not in _BIDI_MARKS:
            result.append(char)
    _require(not stack, "folio_bidi_scope_invalid")
    return "".join(result).strip()


def _hint(text):
    # Broad intent classification is deliberately separate from acceptance.
    # A malformed folio cannot evade validation by being labelled body/footer.
    value = "".join(char for char in text if char not in _CONTROLS and char not in "[]").strip().casefold()
    for prefix in ("página", "pagina", "pág", "page", "الصفحة", "صفحة", "ص"):
        if not value.startswith(prefix):
            continue
        suffix = value[len(prefix):]
        if prefix == "ص":
            # A vocalized or joined word beginning with sad is not a page
            # abbreviation. Skip only marks/joiners for this word-boundary
            # decision; the closed folio parser still sees the complete text.
            while suffix and (unicodedata.category(suffix[0]).startswith("M") or suffix[0] in "\u200c\u200d"):
                suffix = suffix[1:]
        if not suffix or not suffix[0].isalpha():
            return True
    # Hint-only classification deliberately includes Unicode whitespace. A
    # NBSP from PDF extraction must not turn a printed folio into absent/body.
    # The closed acceptance grammar below remains separately enforced.
    return re.match(r"[+-]?[0-9\u0660-\u0669\u06f0-\u06f9]+(?:[.,][0-9]+)?\s*/", value) is not None


def _numbers(tokens, *, source):
    result = []
    for token in tokens:
        alphabets = {"ascii" if "0" <= char <= "9" else "arabic" for char in token}
        _require(len(alphabets) == 1 and (not source or alphabets == {"ascii"}), "folio_digits_invalid")
        result.append("".join(char if "0" <= char <= "9" else str(ord(char) - 0x0660) for char in token))
    return tuple(result)


def _parse(text, *, lang, source=False):
    value = _visible(text)
    _require(0 < len(value) <= 160 and "\n" not in value and "\r" not in value, "folio_line_invalid")
    digits = "0-9" if source else _DIGITS
    number = f"([{digits}]{{1,6}})"
    slash = re.fullmatch(number + r"[ \t]*/[ \t]*" + number, value)
    if slash:
        return "slash", _numbers(slash.groups(), source=source)
    patterns = (("pt_pag_de", r"Pág\."), ("pt_pagina_de", "Página")) if source else {
        "AR": (("ar_definite_page_min", "الصفحة"), ("ar_page_min", "صفحة"),
               ("ar_abbreviated_page_min", r"ص\.")),
        "EN": (("en_page_of", "Page"),), "FR": (("fr_page_sur", "Page"),)}[lang]
    connector = "de" if source else {"AR": "من", "EN": "of", "FR": "sur"}[lang]
    for form, prefix in patterns:
        match = re.fullmatch(prefix + r"[ \t]+" + number + r"[ \t]+" + connector + r"[ \t]+" + number,
                             value, flags=re.IGNORECASE)
        if match:
            return form, _numbers(match.groups(), source=source)
    raise ReviewedFolioError("folio_form_invalid")


def _docket_display(text):
    """Closed display cleanup for a possible docket, preserving literal [ref].

    None means this is not an exemptible field. Its original text remains in
    the normal scans, where malformed folio/docket-looking text still fails.
    """
    value = _TOKEN.sub(lambda match: match[1], text)
    if "[[" in value or "]]" in value:
        return None
    stack, result = [], []
    for char in value:
        if char in _BIDI_OPEN:
            stack.append(_BIDI_OPEN[char])
        elif char in {"\u202c", "\u2069"}:
            expected = "embedding" if char == "\u202c" else "isolate"
            if not stack or stack[-1] != expected:
                return None
            stack.pop()
        elif char not in _BIDI_MARKS:
            result.append(char)
    return None if stack else "".join(result).strip(" \t\r\n")


def _pipe_spans(line):
    """Raw fields only; no whitespace, placeholder or bidi cleanup changes offsets."""
    start = 0
    while True:
        end = line.find("|", start)
        if end < 0:
            yield start, len(line)
            return
        yield start, end
        start = end + 1


def _metadata_docket(line):
    """Only a complete first docket field in a closed 2–4-field metadata row.

    The remaining fields are never part of the mask. They still undergo folio
    intent scanning, including fields following malformed separator spacing.
    """
    if not 1 <= line.count("|") <= 3:
        return None
    spans = list(_pipe_spans(line))
    if (any(not line[start:end].strip(" \t\r\n") for start, end in spans)
            or any(end == 0 or end + 1 >= len(line)
                   or line[end - 1] not in " \t" or line[end + 1] not in " \t"
                   for _, end in spans[:-1])):
        return None
    end = spans[0][1]
    visible = _docket_display(line[:end])
    match = _DOCKET_FIELD.fullmatch(visible) if visible is not None else None
    return (end + 1, match) if match is not None else None


def _docket_fields(text):
    fields, offset = [], 0
    for line in text.splitlines(keepends=True):
        visible = _docket_display(line)
        match = _DOCKET_FIELD.fullmatch(visible) if visible is not None else None
        if match is not None:
            fields.append((offset, offset + len(line), match["docket"], match["reference"]))
        else:
            metadata = _metadata_docket(line)
            if metadata is not None:
                end, match = metadata
                fields.append((offset, offset + end, match["docket"], match["reference"]))
        offset += len(line)
    return fields


def _docket_masks(page, rendered):
    """Bind every exemption to its exact source fragment and target field.

    Offsets refer to retained raw text. Masks are classification-only spaces;
    no stored text, mapped text, hash or visible output is changed. A docket
    may occupy a complete line, a reviewed cell ending in its literal pipe,
    or the first complete field of a closed pipe-delimited metadata row.
    A bracketed numeric reference is part of that same closed field and must
    remain exact, including brackets, after permitted display cleanup.
    """
    masks = {"source": {}, "target": {}}
    for fragment, source_text, target_text in rendered.values():
        if fragment.role not in {"header", "body"} or fragment.bbox_px[3] > page.image_height_px * .25:
            continue
        left = _docket_fields(source_text)
        if not left:
            continue
        right = _docket_fields(target_text)
        _require(len(left) == len(right)
                 and [(row[2], row[3]) for row in left] == [(row[2], row[3]) for row in right],
                 "folio_docket_target_changed")
        for side, fields in (("source", left), ("target", right)):
            start = getattr(fragment, side + "_range")[0]
            spans = masks[side].setdefault(fragment.parent_block_id, [])
            spans.extend((start + row[0], start + row[1]) for row in fields)
    return masks


def _scan(structure, *, lang, source, rendered, masks):
    """Scan original parent lines AND every rendered fragment/cell start.

    Only source-proven docket spans are masked. Line breaks and codepoint
    positions stay unchanged. A later cell's page label cannot hide behind a
    preceding reference/docket in the parent's single transcription line.
    Each raw pipe field is inspected separately, so masking a docket cannot
    hide another field's real or malformed folio. This scan is broader than the
    closed metadata exemption: even malformed delimiter spacing does not hide
    folio intent. The same ordinary folio in both views is counted only once.
    """
    result, masked = set(), {}
    for block in structure["blocks"]:
        text = block["text"]
        spans = masks.get(block["id"], [])
        if spans:
            pieces, previous = [], 0
            for start, end in sorted(spans):
                _require(previous <= start < end <= len(text), "folio_docket_span_invalid")
                pieces.append(text[previous:start])
                pieces.append("".join(char if char in "\r\n" else " " for char in text[start:end]))
                previous = end
            text = "".join((*pieces, text[previous:]))
        masked[block["id"]] = text

    def inspect(parent, text, offset):
        for line in text.splitlines(keepends=True):
            for start, end in _pipe_spans(line):
                field = line[start:end]
                if _hint(field):
                    form, numbers = _parse(field, lang=lang, source=source)
                    result.add((parent, offset + start, offset + end, form, numbers))
            offset += len(line)

    for parent, text in masked.items():
        inspect(parent, text, 0)
    for fragment, _, _ in rendered.values():
        span = fragment.source_range if source else fragment.target_range
        inspect(fragment.parent_block_id, masked[fragment.parent_block_id][slice(*span)], span[0])
    return sorted(result)


def _fragments(page, source, target, *, number):
    _require(type(page.fragments) is tuple and 0 < len(page.fragments) <= MAX_FRAGMENTS
             and type(page.image_height_px) is int and 0 < page.image_height_px <= 100_000,
             "folio_fragment_inputs_invalid")
    source_blocks = {block["id"]: block["text"] for block in source["blocks"]}
    target_blocks = {block["id"]: block["text"] for block in target["blocks"]}
    ends = {side: {key: 0 for key in source_blocks} for side in ("source", "target")}
    seen, rendered, inline_edges, cell_boundaries = set(), {}, set(), {}
    previous = None
    _require((page.region_layout is None) == (page.image_width_px is None), "folio_cell_context_invalid")
    for fragment in page.fragments:
        _require(type(fragment) is FolioFragmentInput and type(fragment.rendering_id) is str
                 and re.fullmatch(rf"p{number:04d}_f[0-9]{{4,}}", fragment.rendering_id) is not None
                 and fragment.rendering_id not in seen and fragment.parent_block_id in source_blocks
                 and fragment.role in {"header", "body", "signature", "footer", "folio"}, "folio_fragment_inputs_invalid")
        seen.add(fragment.rendering_id)
        box = fragment.bbox_px
        _require(type(box) is tuple and len(box) == 4 and all(type(n) in (int, float) and math.isfinite(n) for n in box)
                 and 0 <= box[0] < box[2] <= 100_000 and 0 <= box[1] < box[3] <= page.image_height_px,
                 "folio_geometry_invalid")
        texts = []
        for side, blocks in (("source", source_blocks), ("target", target_blocks)):
            span, original = getattr(fragment, side + "_range"), blocks[fragment.parent_block_id]
            _require(type(span) is tuple and len(span) == 2 and all(type(n) is int for n in span)
                     and span[0] == ends[side][fragment.parent_block_id] and span[0] < span[1] <= len(original),
                     "folio_partition_invalid")
            whole_start = span[0] == 0 or original[span[0] - 1] == "\n"
            whole_end = span[1] == len(original) or original[span[1] - 1] == "\n"
            if not (whole_start and whole_end):
                _require(page.region_layout is not None and fragment.role == "body", "folio_partition_invalid")
                from .reviewed_cell_boundaries import pipe_cell_boundaries
                key = (side, fragment.parent_block_id)
                if key not in cell_boundaries:
                    cell_boundaries[key] = pipe_cell_boundaries(original)
                _require((whole_start or span[0] in cell_boundaries[key])
                         and (whole_end or span[1] in cell_boundaries[key]), "folio_partition_invalid")
                if not whole_start:
                    _require(previous is not None and previous.parent_block_id == fragment.parent_block_id,
                             "folio_cell_adjacency_invalid")
                    inline_edges.add((previous.rendering_id, fragment.rendering_id))
            ends[side][fragment.parent_block_id] = span[1]
            texts.append(original[slice(*span)])
        rendered[fragment.rendering_id] = (fragment, *texts)
        previous = fragment
    _require(all(ends[side][key] == len(text) for side, blocks in (("source", source_blocks), ("target", target_blocks))
                 for key, text in blocks.items()), "folio_partition_incomplete")
    if page.region_layout is not None:
        from .reviewed_cell_boundaries import validated_inline_cell_pairs
        from .reviewed_regions import RegionFragmentInput
        pairs = validated_inline_cell_pairs(page.region_layout,
            fragments=tuple(RegionFragmentInput(f.rendering_id, f.role, f.bbox_px) for f in page.fragments),
            page_number=number, image_size_px=(page.image_width_px, page.image_height_px))
        _require(inline_edges <= pairs, "folio_cell_adjacency_invalid")
    return rendered


def _page_folio(page, source, target, *, number, lang, local, total):
    rendered = _fragments(page, source, target, number=number)
    masks = _docket_masks(page, rendered)
    source_lines = _scan(source, lang=lang, source=True, rendered=rendered, masks=masks["source"])
    target_lines = _scan(target, lang=lang, source=False, rendered=rendered, masks=masks["target"])
    declared = page.folio_fragment_id
    roles = [fragment.rendering_id for fragment in page.fragments if fragment.role == "folio"]
    if not source_lines:
        _require(declared is None and not roles and not target_lines, "folio_false_absence_or_invention")
        return (None,) * 7
    _require(len(source_lines) == len(target_lines) == 1 and type(declared) is str
             and roles == [declared] and declared in rendered, "folio_missing_duplicate_or_relabelled")
    fragment, source_text, target_text = rendered[declared]
    _require(fragment.bbox_px[1] >= page.image_height_px * .80, "folio_geometry_invalid")
    for side, lines in (("source", source_lines), ("target", target_lines)):
        parent, start, end, _, _ = lines[0]
        span = getattr(fragment, side + "_range")
        _require(parent == fragment.parent_block_id and span[0] <= start < end <= span[1], "folio_line_owner_changed")
    source_form, source_numbers = _parse(source_text, lang=lang, source=True)
    target_form, target_numbers = _parse(target_text, lang=lang, source=False)
    _require((source_form == "slash") == (target_form == "slash"), "folio_form_family_changed")
    _require(source_numbers == target_numbers and tuple(map(int, source_numbers)) == (local, total),
             "folio_numbering_changed")
    return declared, source_form, target_form, source_numbers, target_numbers, _sha(source_text), _sha(target_text)


def validate_document_local_folios(document_groups, *, pages: Sequence[FolioPageInput],
                                  source_file_sha256: str, target_lang: str) -> tuple[ValidatedFolioPage, ...]:
    """Validate explicit v2 groups and all folio-like lines without side effects.

    Metadata is only consistent with an accepted source when the caller has
    separately verified the original envelope/evidence/commits and image bytes.
    Unknown folio-like body lines fail closed, including ambiguous bare ratios;
    relabelling them is not an escape hatch for this deliberately narrow lane.
    """
    try:
        _hash(source_file_sha256)
        _require(type(target_lang) is str and target_lang in {"AR", "EN", "FR"}, "folio_language_invalid")
        _require(type(pages) in (list, tuple) and 0 < len(pages) <= MAX_PAGES
                 and all(type(page) is FolioPageInput for page in pages), "folio_page_inputs_invalid")
        contexts = _groups(document_groups, len(pages))
        result, common_pins, total_bytes, total_fragments = [], None, 0, 0
        for number, (page, context) in enumerate(zip(pages, contexts), 1):
            source, size = _snapshot(page.source_structure)
            target, target_size = _snapshot(page.target_structure)
            total_bytes += size + target_size
            total_fragments += len(page.fragments)
            _require(total_bytes <= MAX_CASE_BYTES and total_fragments <= 100_000, "folio_case_oversized")
            _source_pair(source, target, number=number, source_hash=source_file_sha256)
            index, start, end, local, total = context
            pins = _boundary(source, start=number == start, source_hash=source_file_sha256)
            _require(common_pins is None or pins == common_pins, "folio_mixed_source_review_provenance")
            common_pins = pins
            folio = _page_folio(page, source, target, number=number, lang=target_lang, local=local, total=total)
            result.append(ValidatedFolioPage(number, index, start, end, local, total, *folio))
        return tuple(result)
    except ReviewedFolioError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, RecursionError, UnicodeError):
        raise ReviewedFolioError("folio_contract_invalid") from None
