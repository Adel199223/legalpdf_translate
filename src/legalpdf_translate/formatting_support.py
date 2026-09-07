"""Passive formatting support for saved, source-bound document evidence.

No translation prompts, provider clients, model policy, source preparation or
output evaluation belong here. Existing translated text is never regenerated.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping, Sequence

LAYOUT_PROFILE_VERSION = "compact_legal_v7_sections_spacing"


def _row(block: Any) -> dict[str, Any]:
    if isinstance(block, Mapping):
        return dict(block)
    return asdict(block) if is_dataclass(block) else dict(vars(block))


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint(value: Any) -> str:
    return digest_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


def flatten_blocks(blocks: Sequence[Any]) -> str:
    return "\n".join(str(_row(block)["text"]) for block in blocks)


def save_translated_structure(
    *, path: Path, source_structure: Any, translated_blocks: Sequence[Any],
    translated_text: str, translation_fingerprint: str = "", review_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = source_structure.to_dict() if hasattr(source_structure, "to_dict") else dict(source_structure)
    rows = {block["id"]: block["text"] for block in map(_row, translated_blocks)}
    payload = dict(source)
    payload["blocks"] = [{**block, "text": rows[block["id"]]} for block in source["blocks"]]
    if flatten_blocks(payload["blocks"]) != translated_text:
        raise ValueError("Translated structure does not match page text")
    payload["translation_sha256"] = digest_text(translated_text)
    payload["metadata"] = {**source.get("metadata", {}), "translation_fingerprint": translation_fingerprint,
                           "review": dict(review_metadata or {})}
    write_json_atomic(path, payload)
    return payload


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def formatting_fingerprint(config: Any) -> str:
    return fingerprint({"profile": LAYOUT_PROFILE_VERSION, "lang": config.target_lang.value,
                        "page_breaks": config.page_breaks, "strip_bidi_controls": config.strip_bidi_controls})


def rebase_structure(payload: Any, *, page_number: int, source_file_sha256: str):
    from .document_structure import PageStructure
    source = payload.to_dict() if hasattr(payload, "to_dict") else dict(payload)
    previous_ids = {block["id"]: f"p{page_number:04d}_b{index:04d}"
                    for index, block in enumerate(source["blocks"], 1)}
    source["page_number"] = page_number
    source["source_file_sha256"] = source_file_sha256
    source["blocks"] = [{**block, "id": previous_ids[block["id"]],
                         "continuation_of": previous_ids.get(block.get("continuation_of"), block.get("continuation_of"))}
                        for block in source["blocks"]]
    return PageStructure.from_dict(source)


def _furniture_geometry(block: dict, page: dict, *, top: bool) -> bool:
    box = block.get("bbox")
    return bool(box and not block.get("uncertain") and not block.get("table_id")
                and (box[3] <= page["height_pt"] * 0.25 if top else box[1] >= page["height_pt"] * 0.80))


def _same_furniture(first: list[dict], second: list[dict], previous: dict, current: dict) -> bool:
    if len(first) != len(second):
        return False
    for left, right in zip(first, second):
        if left["role"] != right["role"] or left["text"].strip() != right["text"].strip():
            return False
        for index, (a, b) in enumerate(zip(left["bbox"], right["bbox"])):
            dimension = "width_pt" if index % 2 == 0 else "height_pt"
            if abs(a / previous[dimension] - b / current[dimension]) > 0.025:
                return False
    return True


def _contact_furniture(blocks: list[dict]) -> bool:
    """Recognize only short address/contact lines, never a generic legal footer."""
    if not blocks or len(blocks) > 4:
        return False
    text = "\n".join(block["text"] for block in blocks)
    if len(text) > 600:
        return False
    folded = "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char))
    if re.search(r"\b(?:prazo|deve|ferias|artigo|lei|decreto|obrigacao|recurso|notificacao|sentenca)\b", folded):
        return False
    has_contact = bool(re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:telef?|telefone|fax)\.?\s*:?\s*\+?[\d ()-]{6,}", folded))
    allowed_line = re.compile(r"^(?:rua\b|largo\b|avenida\b|av\.|praca\b|travessa\b|estrada\b|alameda\b|beco\b|"
                              r"\d{4}-\d{3}\b|telef?\b|telefone\b|fax\b|e-?mail\b|mail\b|correio eletronico\b|"
                              r"[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|https?://|www\.)")
    lines = [line.strip() for line in folded.splitlines() if line.strip()]
    return has_contact and bool(lines) and all(allowed_line.search(line) for line in lines)


def confirmed_source_continuation(previous: Any, current: Any) -> dict[str, Any] | None:
    """Recompute positive source proof; incoming continuation flags are not proof.

    Only exact repeated, geometrically stable header/address or contact-footer
    furniture can intervene. All furniture remains substantive editable output;
    this proof permits moving just the split body fragment ahead of furniture.
    """
    previous = previous.to_dict() if hasattr(previous, "to_dict") else dict(previous)
    current = current.to_dict() if hasattr(current, "to_dict") else dict(current)
    if (previous["page_number"] + 1 != current["page_number"] or current.get("document_start")
            or current.get("uncertain") or previous.get("uncertain")
            or previous.get("source_file_sha256") != current.get("source_file_sha256")):
        return None
    left = [b for b in previous["blocks"] if b["role"] == "paragraph" and b["text"].strip()]
    right = [b for b in current["blocks"] if b["role"] == "paragraph" and b["text"].strip()]
    if not left or not right:
        return None
    tail, head = left[-1], right[0]
    tail_index, head_index = previous["blocks"].index(tail), current["blocks"].index(head)
    before, after = tail["text"].rstrip(), head["text"].lstrip()
    boxes = tail.get("bbox"), head.get("bbox")
    if (head.get("document_start") or tail.get("table_id") or head.get("table_id")
            or tail.get("uncertain") or head.get("uncertain")
            or not boxes[0] or not boxes[1] or boxes[0][3] < previous["height_pt"] * 0.72
            or boxes[1][1] > current["height_pt"] * 0.32
            or len(before) <= 40 or not after[0].islower() or before[-1] in ".!?;:"):
        return None
    trailing_all, leading_all = previous["blocks"][tail_index + 1:], current["blocks"][:head_index]
    if any(block.get("document_start") or block["role"] in {"heading", "table_cell", "signature", "reference"}
           for block in trailing_all + leading_all):
        return None
    trailing = [block for block in trailing_all if block["text"].strip()]
    leading = [block for block in leading_all if block["text"].strip()]
    pairs = []
    if leading:
        if any(block["role"] not in {"header", "address"} or not _furniture_geometry(block, current, top=True) for block in leading):
            return None
        first_body = previous["blocks"].index(left[0])
        witnesses = [block for block in previous["blocks"][:first_body] if block["text"].strip()
                     and block["role"] in {"header", "address"} and _furniture_geometry(block, previous, top=True)]
        if not _same_furniture(witnesses, leading, previous, current):
            return None
        pairs.extend(zip(witnesses, leading))
    if trailing:
        if any(block["role"] not in {"footer", "address"} or not _furniture_geometry(block, previous, top=False) for block in trailing) or not _contact_furniture(trailing):
            return None
        last_body = current["blocks"].index(right[-1])
        witnesses = [block for block in current["blocks"][last_body + 1:] if block["text"].strip()
                     and block["role"] in {"footer", "address"} and _furniture_geometry(block, current, top=False)]
        if not _contact_furniture(witnesses) or not _same_furniture(trailing, witnesses, previous, current):
            return None
        pairs.extend(zip(trailing, witnesses))
    return {"version": 1, "kind": "repeated_source_furniture" if pairs else "adjacent_source_fragment",
            "previous_page": previous["page_number"], "current_page": current["page_number"],
            "previous_source_sha256": previous["source_sha256"], "current_source_sha256": current["source_sha256"],
            "previous_block_id": tail["id"], "current_block_id": head["id"],
            "previous_trailing_ids": [block["id"] for block in trailing],
            "current_leading_ids": [block["id"] for block in leading],
            "furniture_pairs": [{"previous_id": a["id"], "current_id": b["id"], "source_text_sha256": digest_text(a["text"].strip())}
                                for a, b in pairs]}


def link_source_continuations(structures: Mapping[int, Any]) -> dict[int, Any]:
    """Link only adjacent body fragments with positive geometry/syntax evidence.

    Every fragment stays assigned to its own request. Joining changes only the
    Word paragraph separator; uncertain/missing evidence never joins documents.
    """
    from .document_structure import PageStructure
    pages = {number: value.to_dict() for number, value in structures.items()}
    # These are derived automatic links, not user decisions. Recompute them from
    # evidence on every pass; stale flags must not bootstrap their own proof.
    for page in pages.values():
        page["continuation_from_previous"] = False
        page["continuation_to_next"] = False
        metadata = page.setdefault("metadata", {})
        if metadata.get("continuation_evidence") in ("adjacent_source_fragment", "repeated_source_furniture"):
            metadata.pop("continuation_evidence")
        page["metadata"].pop("continuation_bridge", None)
        for block in page["blocks"]:
            block["continuation_of"] = None
    for number in sorted(pages):
        current, previous = pages[number], pages.get(number - 1)
        if previous is None:
            continue
        proof = confirmed_source_continuation(previous, current)
        if proof is None:
            continue
        previous["continuation_to_next"] = True
        current["continuation_from_previous"] = True
        head = next(block for block in current["blocks"] if block["id"] == proof["current_block_id"])
        head["continuation_of"] = proof["previous_block_id"]
        current.setdefault("metadata", {}).setdefault("continuation_evidence", proof["kind"])
        if proof["furniture_pairs"]:
            current["metadata"]["continuation_bridge"] = proof
    return {number: PageStructure.from_dict(value) for number, value in pages.items()}
