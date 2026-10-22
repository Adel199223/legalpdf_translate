"""Local, versioned source fractions; no source or translated text is rewritten."""
from copy import deepcopy
import hashlib
import json
import math
import re

VERSION = "ordinary_source_folio_span_proof_v1"
KEY = "local_source_folio_proof"
RECIPE_KEY = "local_source_folio_proof_version"
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"([1-9][0-9]{0,3})\s*/\s*([1-9][0-9]{0,3})")
_NUM = r"[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}"
_TARGET = re.compile(r"(?<![\w/\u060d])(" + _NUM + r")\s*[/\u060d]\s*(" + _NUM + r")(?![\w/\u060d])")
_MARKS = frozenset("\u200e\u200f\u2066\u2067\u2069")
# Provider boxes are coarse; v1 admits at most 2% horizontal frame uncertainty.
# Vertical containment stays exact, and the independently extracted value is exact.
_HORIZONTAL_MARGIN = .02


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _fail():
    raise ValueError("ordinary_source_folio_proof_changed")


def _frames(pages, selected):
    if (type(selected) not in {tuple, list} or not selected
            or any(type(n) is not int or n < 1 for n in selected)
            or list(selected) != sorted(set(selected)) or type(pages) is not list):
        _fail()
    result = []
    for number in selected:
        rows = [p for p in pages if type(p) is dict and p.get("page_number") == number]
        if len(rows) != 1:
            _fail()
        row = rows[0]
        if (any(type(row.get(k)) is not int or row[k] <= 0 for k in ("width_px", "height_px"))
                or type(row.get("image_sha256")) is not str or not _HASH.fullmatch(row["image_sha256"])):
            _fail()
        result.append({k: row[k] for k in ("page_number", "width_px", "height_px", "image_sha256")})
    return result


def derive_proof(source_pdf, pages, selected, source_sha256):
    """Extract one unique standalone lower-page fraction, or retain no evidence."""
    if (type(source_pdf) is not bytes or not source_pdf or len(source_pdf) > 64 * 1024 * 1024
            or hashlib.sha256(source_pdf).hexdigest() != source_sha256):
        _fail()
    frames = _frames(pages, selected)
    result = {"version": VERSION, "source_pdf_sha256": source_sha256,
        "selected_pages": list(selected), "frames": frames,
        "folios": [{"page_number": n, "fraction": None} for n in selected]}
    import fitz
    try:
        with fitz.open(stream=source_pdf, filetype="pdf") as document:
            if document.needs_pass or len(document) > 10000:
                return result
            for row in result["folios"]:
                number = row["page_number"]
                if number > len(document):
                    continue
                page = document[number - 1]
                if page.rotation != 0:
                    continue
                width, height = float(page.rect.width), float(page.rect.height)
                candidates = []
                data = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)
                lines = [line for block in data["blocks"] for line in block.get("lines", [])]
                if len(lines) > 20000:
                    continue
                for line in lines:
                    text = "".join(s["text"] for s in line.get("spans", []))
                    match = _SOURCE.fullmatch(text.strip()) if len(text) <= 80 else None
                    if match:
                        candidates.append((line, text, int(match[1]), int(match[2])))
                if len(candidates) != 1:
                    continue
                line, text, numerator, denominator = candidates[0]
                box = list(line["bbox"])
                if (not 1 <= numerator <= denominator <= 9999 or len(box) != 4
                        or not all(math.isfinite(v) for v in [width, height, *box])
                        or not (0 <= box[0] < box[2] <= width and .85 * height <= box[1] < box[3] <= height)
                        or box[2] - box[0] > .25 * width or box[3] - box[1] > min(24, .05 * height)
                        or tuple(line.get("dir", ())) != (1.0, 0.0)):
                    continue
                row["fraction"] = {"numerator": numerator, "denominator": denominator,
                    "bbox": [box[0]/width, box[1]/height, box[2]/width, box[3]/height],
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    except (RuntimeError, ValueError, KeyError, TypeError, OverflowError):
        # An unreadable/unsupported PDF cannot justify removing output furniture.
        for row in result["folios"]:
            row["fraction"] = None
    return result


def verify_proof(proof, source_pdf, pages, selected, source_sha256):
    expected = derive_proof(source_pdf, pages, selected, source_sha256)
    if _encoded(proof) != _encoded(expected):
        _fail()
    return deepcopy(expected)


def target_spans(snapshot, pages, decisions, context):
    """Recognize complete selected-page coverage using source-bound terminal spans."""
    return _target_spans(snapshot, pages, decisions, context, require_all_pages=True)


def direction_target_spans(snapshot, pages, decisions, context):
    """Qualify pages independently for direction; never authorize PAGE suppression."""
    return _target_spans(snapshot, pages, decisions, context, require_all_pages=False)


def _target_spans(snapshot, pages, decisions, context, *, require_all_pages):
    proof = context.get(KEY)
    if proof is None:
        return []
    selected = context["selected_pages"]
    if (type(proof) is not dict or set(proof) != {"version", "source_pdf_sha256", "selected_pages", "frames", "folios"}
            or proof["version"] != VERSION or type(proof["source_pdf_sha256"]) is not str
            or not _HASH.fullmatch(proof["source_pdf_sha256"])
            or _encoded(proof["selected_pages"]) != _encoded(selected)
            or _encoded(proof["frames"]) != _encoded(_frames(pages, selected))
            or type(proof["folios"]) is not list or len(proof["folios"]) != len(selected)):
        _fail()
    rows = {r["id"]: r for r in snapshot["paragraphs"]}
    owners = {i: p for p, ids in context["page_groups"] for i in ids}
    frames = {p["page_number"]: p for p in pages}
    cuts = {p["paragraph_id"] for p in decisions.get("paragraph_partitions", [])}
    flow = {i for b in decisions["bands"] if b["kind"] == "flow" for g in b["groups"] if not g["panel"] for i in g["paragraph_ids"]}
    result = []
    for number, source in zip(selected, proof["folios"]):
        if type(source) is not dict or set(source) != {"page_number", "fraction"} or type(source["page_number"]) is not int or source["page_number"] != number:
            _fail()
        fraction = source["fraction"]
        if fraction is None:
            continue
        if (type(fraction) is not dict or set(fraction) != {"numerator", "denominator", "bbox", "text_sha256"}
                or any(type(fraction[k]) is not int for k in ("numerator", "denominator"))
                or not 1 <= fraction["numerator"] <= fraction["denominator"] <= 9999
                or type(fraction["text_sha256"]) is not str or not _HASH.fullmatch(fraction["text_sha256"])):
            _fail()
        box = fraction["bbox"]
        if (type(box) is not list or len(box) != 4 or any(type(v) not in {int, float} or not math.isfinite(v) for v in box)
                or not 0 <= box[0] < box[2] <= 1 or not .85 <= box[1] < box[3] <= 1):
            _fail()
        frame = frames[number]
        cx, cy = (box[0]+box[2])*frame["width_px"]/2, (box[1]+box[3])*frame["height_px"]/2
        margin = _HORIZONTAL_MARGIN * frame["width_px"]
        matches = []
        for choice in decisions["paragraphs"]:
            identifier = choice["paragraph_id"]
            if (owners.get(identifier) != number or identifier in cuts or identifier not in flow
                    or choice["role"] != "source_folio" or len(choice["regions"]) != 1):
                continue
            row = rows[identifier]
            tokens = row["tokens"][:-1] if row["tokens"] and row["tokens"][-1]["kind"] == "page_break" else row["tokens"]
            if not tokens or any(t["kind"] != "t" for t in tokens):
                continue
            region = choice["regions"][0]
            x0,y0,x1,y1 = region["bbox_px"]
            horizontal_gap = max(x0-cx, cx-x1, 0)
            within_horizontal = horizontal_gap <= margin or math.isclose(
                horizontal_gap, margin, rel_tol=0, abs_tol=1e-9)  # coordinate arithmetic roundoff only
            if (region["page_number"] != number or y0 < .85*frame["height_px"] or y1-y0 > .12*frame["height_px"]
                    or not within_horizontal or not y0 <= cy <= y1):
                continue
            indexed = [(i,c) for i,c in enumerate(row["text"]) if c not in _MARKS]
            text = "".join(c for _,c in indexed).rstrip()
            candidates = list(_TARGET.finditer(text))
            if len(candidates) != 1 or candidates[0].end() != len(text):
                continue
            match = candidates[0]
            if any(len(v)>1 and int(v[0])==0 for v in match.groups()):
                continue
            if (int(match[1]),int(match[2])) != (fraction["numerator"],fraction["denominator"]):
                continue
            start, end = indexed[match.start()][0], indexed[match.end()-1][0]+1
            matches.append({"page_number": number, "paragraph_id": identifier, "start": start, "end": end,
                "literal_sha256": hashlib.sha256(row["text"][start:end].encode()).hexdigest()})
        if len(matches) == 1:
            result.extend(matches)
    return result if not require_all_pages or len(result) == len(selected) else []
