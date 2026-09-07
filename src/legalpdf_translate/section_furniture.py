"""Pure source-bound planning for real Word section headers/contact footers.

The caller must supply complete source evidence and hash-validated saved target
pages. This adds no OCR authority: correct transcription/roles still require
source review. Canonical target wording is the earliest retained occurrence, not
a new translation or a claim that all repeated target strings were identical.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import unicodedata
from typing import Any, Sequence

from .document_structure import PageStructure, text_sha256
from .formatting_support import _contact_furniture

SECTION_FURNITURE_POLICY = "source_section_furniture_v1"
MAX_PAGES = 1000
MAX_PART_BLOCKS = 4
MAX_TARGET_PART_CHARACTERS = 600
MAX_TARGET_PART_LINES = 8
GEOMETRY_TOLERANCE_PT = 4.0
_INSTITUTION = re.compile(
    r"^(?:tribunal\b|ministerio publico\b|procuradoria\b|juizo\b|comarca\b|"
    r"departamento de investigacao e acao penal\b|secretaria\b|nucleo\b|"
    r"(?:\d{1,2}[.ºª°]*\s+)?seccao\b)"
)
_CASE_OR_LEGAL_DATA = re.compile(
    r"\b(?:processo|referencia|arguid[oa]s?|autora?|reu|notificacao|sentenca|despacho|"
    r"decisao|acusacao|data|assinad[oa]|certificad[oa]|prazo|artigos?|obrigacao|"
    r"devera|deverao|recurso|decreto)\b|\bref\.|\d{1,6}/\d{2,4}(?:\b|\.)|"
    r"\b\d{1,2}[-.]\d{1,2}[-.]\d{2,4}\b|\b\d{4}-\d{3}\b"
)
_OPERATIVE_PROSE = re.compile(
    r"\b(?:nao|deve|devem|devera|deverao|pode|podem|podera|poderao|fica|ficam|"
    r"comparec[a-z]*|conden[a-z]*|absolv[a-z]*|proib[a-z]*|determin[a-z]*|"
    r"orden[a-z]*|notific[a-z]*|requer[a-z]*|apresent[a-z]*|entreg[a-z]*|"
    r"cumpr[a-z]*|pagar|pagamento|sob pena|tem direito|decide|decidem)\b"
)


class _PreservedRegions(ValueError):
    """Known physical regions stay intact without implying a review failure."""


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _fold(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                            if not unicodedata.combining(c)).split())


def _safe_header(block: dict) -> bool:
    text = block["text"]
    folded = _fold(text)
    return bool(0 < len(text) <= 300 and len(text.splitlines()) <= 3
                and all(_INSTITUTION.search(_fold(line)) for line in text.splitlines() if line.strip())
                and not _CASE_OR_LEGAL_DATA.search(folded) and not _OPERATIVE_PROSE.search(folded))


def _inside_page(block: dict, page: dict) -> bool:
    box = block.get("bbox")
    return bool(box and 0 <= box[0] < box[2] <= page["width_pt"]
                and 0 <= box[1] < box[3] <= page["height_pt"])


def _bound_pair(pair: Any) -> tuple[dict, dict]:
    if not isinstance(pair, (tuple, list)) or len(pair) != 2:
        raise ValueError("Missing complete source/target pair")
    source, target = (PageStructure.from_dict(page).to_dict() for page in pair)
    if (not source["source_file_sha256"] or source["translation_sha256"] is not None
            or source["source_text_sha256"] != source["source_sha256"]
            or text_sha256("\n".join(b["text"] for b in source["blocks"])) != source["source_sha256"]
            or not target["translation_sha256"]
            or text_sha256("\n".join(b["text"] for b in target["blocks"])) != target["translation_sha256"]):
        raise ValueError("Stale or incomplete source/target text evidence")
    for key in ("page_number", "source_file_sha256", "source_sha256", "source_text_sha256",
                "width_pt", "height_pt", "document_start", "continuation_from_previous", "continuation_to_next"):
        if source[key] != target[key]:
            raise ValueError("Source/target identity mismatch")
    if not source["blocks"] or len(source["blocks"]) != len(target["blocks"]):
        raise ValueError("Incomplete block coverage")
    if source["uncertain"] or target["uncertain"]:
        raise ValueError("Uncertain page evidence")
    for a, b in zip(source["blocks"], target["blocks"]):
        if a["text"].strip() and not b["text"].strip():
            raise ValueError("Empty translation of a nonempty source block")
        if {k: v for k, v in a.items() if k != "text"} != {k: v for k, v in b.items() if k != "text"}:
            raise ValueError("Source/target block evidence mismatch")
    if (any(b["document_start"] for b in source["blocks"][1:])
            or source["blocks"][0]["document_start"] and not source["document_start"]):
        raise ValueError("Interior document boundary cannot become section furniture")
    for page in (source, target):
        layout = page["metadata"].get("layout")
        if isinstance(layout, dict) and layout.get("status") == "regions" and not layout.get("review_required"):
            raise _PreservedRegions("Preserve physical notice regions")
        if layout is not None and (not isinstance(layout, dict) or layout.get("status") != "flow"
                                   or layout.get("review_required") or layout.get("bands")):
            raise ValueError("Layout regions or uncertain layout must remain intact")
        if page["metadata"].get("document_boundary_review_required"):
            raise ValueError("Uncertain document boundary")
    return source, target


def _candidates(source: dict) -> tuple[list[dict], list[dict]]:
    # Position rather than block-list edges permits a preceding source signature
    # to stay ordinary body text while a genuine top court header is adopted.
    headers = [b for b in source["blocks"] if b["role"] == "header"]
    footers = [b for b in source["blocks"] if b["role"] == "footer"
               or b["role"] == "address" and b.get("bbox") and b["bbox"][1] >= source["height_pt"] * .80]
    for part, blocks in (("header", headers), ("footer", footers)):
        if len(blocks) > MAX_PART_BLOCKS:
            raise ValueError("Too many furniture blocks")
        for block in blocks:
            if (block["uncertain"] or block["continuation_of"]
                    or block["table_id"] or not block["text"].strip() or not _inside_page(block, source)):
                raise ValueError("Uncertain furniture evidence")
            if part == "header" and (block["bbox"][3] > source["height_pt"] * .25 or not _safe_header(block)):
                raise ValueError("Not an evidenced top institutional header")
            if part == "footer" and block["bbox"][1] < source["height_pt"] * .80:
                raise ValueError("Not an evidenced bottom footer")
        blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        if len({b["text"] for b in blocks}) != len(blocks):
            raise ValueError("Ambiguous duplicate furniture spans")
    if footers and (not _contact_furniture(footers)
                    or any(_OPERATIVE_PROSE.search(_fold(block["text"])) for block in footers)):
        raise ValueError("Footer is not short contact-only furniture")
    return headers, footers


def _same_words(a: list[dict], b: list[dict]) -> bool:
    return len(a) == len(b) and all(x["text"] == y["text"] for x, y in zip(a, b))


def _same_part(a: list[dict], b: list[dict]) -> bool:
    return _same_words(a, b) and all(
        all(x[k] == y[k] for k in ("role", "alignment", "bold", "italic"))
        and all(abs(v - w) <= GEOMETRY_TOLERANCE_PT for v, w in zip(x["bbox"], y["bbox"]))
        for x, y in zip(a, b)
    )


def _same_section(a: dict, b: dict) -> bool:
    x, y = a["source"], b["source"]
    return bool(y["page_number"] == x["page_number"] + 1 and not y["document_start"]
                and x["source_file_sha256"] == y["source_file_sha256"]
                and all(abs(x[k] - y[k]) <= 1 for k in ("width_pt", "height_pt"))
                and _same_part(a["header"], b["header"]) and _same_part(a["footer"], b["footer"]))


def _short_target_parts(target: dict, headers: list[dict], footers: list[dict]) -> bool:
    by_id = {block["id"]: block for block in target["blocks"]}
    for blocks in (headers, footers):
        texts = [by_id[block["id"]]["text"] for block in blocks]
        if (sum(map(len, texts)) > MAX_TARGET_PART_CHARACTERS
                or sum(len(text.splitlines()) for text in texts) > MAX_TARGET_PART_LINES):
            return False
    return True


def _part(group: list[dict], name: str) -> dict | None:
    first = group[0]
    source_blocks = first[name]
    if not source_blocks:
        return None
    canonical_ids = [b["id"] for b in source_blocks]
    targets = {b["id"]: b for b in first["target"]["blocks"]}
    canonical = [targets[identity] for identity in canonical_ids]
    aliases = []
    for item in group:
        target_blocks = {b["id"]: b for b in item["target"]["blocks"]}
        for source, chosen in zip(item[name], canonical):
            original = target_blocks[source["id"]]["text"]
            aliases.append({"page_index": item["index"], "page_number": item["source"]["page_number"],
                            "block_id": source["id"], "canonical_block_id": chosen["id"],
                            "source_text_sha256": text_sha256(source["text"]),
                            "target_text_sha256": text_sha256(original),
                            "target_variant": original != chosen["text"], "original_target_text": original})
    return {"part": name, "source_signature": _fingerprint([
                {k: b[k] for k in ("text", "role", "bbox", "alignment", "bold", "italic")}
                for b in source_blocks]),
            "geometry_tolerance_pt": GEOMETRY_TOLERANCE_PT,
            "canonical_page_index": first["index"], "canonical_blocks": deepcopy(canonical), "aliases": aliases}


def plan_section_furniture(
    page_pairs: Sequence[tuple[dict, dict] | None], *, page_breaks: bool = False,
) -> dict[str, Any]:
    """Plan bounded intervals without mutating or writing source/target data.

    None and invalid evidence are singleton barriers. Valid headerless/footerless
    intervals are explicit, so downstream Word sections cannot inherit furniture
    from another document. One-off/changed metadata remains ordinary body text.
    The writer may preserve its legacy flow entirely when no group is admitted.
    """
    if not isinstance(page_pairs, (list, tuple)) or len(page_pairs) > MAX_PAGES or type(page_breaks) is not bool:
        raise ValueError("Page pairs and page-break preference must be bounded")
    pages, items = [], []
    for index, pair in enumerate(page_pairs):
        page = {"index": index, "page_number": None, "section_id": None,
                "adopted_header_ids": [], "adopted_footer_ids": [], "review_required": False, "warnings": []}
        pages.append(page)
        try:
            source, target = _bound_pair(pair)
            page["page_number"] = source["page_number"]
            headers, footers = _candidates(source)
            if not _short_target_parts(target, headers, footers):
                raise ValueError("Target furniture is too large for conservative section adoption")
            items.append({"index": index, "source": source, "target": target, "header": headers, "footer": footers})
        except _PreservedRegions:
            page["warnings"].append("section_furniture_region_preserved")
            items.append(None)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            page["review_required"] = True
            page["warnings"].append("section_furniture_source_evidence_unavailable")
            items.append(None)
    # Same words alone cannot excuse changed roles, alignment or unstable boxes.
    # Use the first geometry in a group as anchor to avoid transitive drift.
    sections = []
    cursor = 0
    while cursor < len(items):
        first = items[cursor]
        end = cursor + 1
        if first is not None:
            while (end < len(items) and items[end] is not None
                   and _same_section(items[end - 1], items[end])
                   and all(abs(first["source"][k] - items[end]["source"][k]) <= 1
                           for k in ("width_pt", "height_pt"))
                   and _same_part(first["header"], items[end]["header"])
                   and _same_part(first["footer"], items[end]["footer"])):
                end += 1
        group = items[cursor:end]
        consolidated = bool(not page_breaks and first is not None and end - cursor >= 2
                            and (first["header"] or first["footer"]))
        section_id = "sf_" + _fingerprint({"policy": SECTION_FURNITURE_POLICY, "start": cursor, "end": end,
            "pages": [(item["source"]["page_number"], item["source"]["source_file_sha256"],
                       item["source"]["source_sha256"], item["target"]["translation_sha256"],
                       item["source"]["width_pt"], item["source"]["height_pt"],
                       [{k: block[k] for k in ("id", "role", "bbox", "alignment", "bold", "italic")}
                        for block in item["source"]["blocks"]])
                      if item is not None else None for item in group]})[:20]
        section = {"section_id": section_id, "start_index": cursor, "end_index_exclusive": end,
                   "page_numbers": [item["source"]["page_number"] for item in group if item is not None],
                   "source_file_sha256": first["source"]["source_file_sha256"] if first else None,
                   "page_size_pt": [first["source"]["width_pt"], first["source"]["height_pt"]] if first else None,
                   "consolidated": consolidated,
                   "parts": {part: _part(group, part) if consolidated else None for part in ("header", "footer")}}
        sections.append(section)
        standardized_variants = consolidated and any(
            part and any(alias["target_variant"] for alias in part["aliases"])
            for part in section["parts"].values()
        )
        for position in range(cursor, end):
            pages[position]["section_id"] = section_id
            if standardized_variants:
                # Review the whole adopted group, including the earliest label
                # now reused elsewhere. Every original variant remains in aliases.
                pages[position]["review_required"] = True
                pages[position]["warnings"].append("section_furniture_target_variant_standardized")
            if consolidated:
                for name in ("header", "footer"):
                    pages[position][f"adopted_{name}_ids"] = [b["id"] for b in items[position][name]]
        cursor = end
    for previous, current in zip(items, items[1:]):
        if previous is None or current is None:
            continue
        if (current["source"]["page_number"] != previous["source"]["page_number"] + 1
                or current["source"]["document_start"]
                or current["source"]["source_file_sha256"] != previous["source"]["source_file_sha256"]):
            continue
        for name in ("header", "footer"):
            if (previous[name] and _same_words(previous[name], current[name])
                    and not _same_part(previous[name], current[name])):
                for item in (previous, current):
                    page = pages[item["index"]]
                    page["review_required"] = True
                    if "section_furniture_geometry_or_style_changed" not in page["warnings"]:
                        page["warnings"].append("section_furniture_geometry_or_style_changed")
    return {"version": 1, "policy": SECTION_FURNITURE_POLICY, "sections": sections, "pages": pages,
            "review_required": any(p["review_required"] for p in pages)}
