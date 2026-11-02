"""Bind a printed registered-mail mark and tracking code to one native PDF band."""
from __future__ import annotations

from functools import lru_cache
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import math
import re
from threading import Lock
import unicodedata
import zlib

import fitz

from .arabic_pre_tokenize import POSTAL_TRACKING_CORE_RE
from .browser_pdf_bundle import browser_pdf_bundle_manifest_path

KEY = "source_postal_band_policy"
POLICY = "registered_glyph_band_v1"
FIELD = "source_postal_bands"
ROUTE = "source_postal_band_route"
MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_FONT_BYTES = 512 * 1024
MAX_CHARS = 120_000
_CODE = re.compile(r"%\*([A-Z]{2}[0-9]{9}[A-Z]{2})\*\Z", re.ASCII)
_RESULTS = {}
_RESULT_LOCK = Lock()

# Audited character designs, rendered at a fixed scale and origin below. The
# percent glyph prints a bordered R and the asterisk prints a delimiter bar.
# Each body glyph also prints its readable character beneath its bars. A font
# name, subset name or glyph number cannot establish any of these identities.
_GLYPHS = {
    "%": "adae6904a66e4e0d217439232557d46057d47668805fb3896c00dc4d55d2519e",
    "*": "ff84c1d5f5877928c2a7d89695968b10a2499355b08ffcc9b87d29703a56138e",
    "0": "cf9622d9a36c6ebf6132d9a72ae242fbf563befab7c991dbe793e3ceba96e2f1",
    "1": "0de1c95f88d91c1c5cb4118b31cc46e95fffeb8254125fd9b1716a08e3a19e32",
    "3": "17bde20c09c685cc3066e123609dcc0cdfbc7b72721057f43ab815405d40b672",
    "4": "e3886f4792ca806cff010fcf1e6577c90cb0ae7577c896575de71a8cc596cbc8",
    "6": "53610a9b93a1706d33c7e3a15c072e3af1dc63497127a97c804f9af67cdd5331",
    "9": "03dff36a4906b974efc0f9499d71098c2629bab6ff663ff4d42fe18f6c055e13",
    "E": "eef82d02711ac32c2f8e2ed847ae0444cf5c79564c35607740d7fa1676bf0cd9",
    "P": "24ed2d07eb01216b2d19879f3101b20d82d3d8e7dd94172de6d3942114892ff0",
    "R": "6eb66575b5c81d62183938e070b47c16112afcdf3dd44bedb475828293f613dc",
    "T": "0704fe32e96ad9fdfdce6fd0a15e74acddefc5082bcb22ef789f9c2f8a2b67ea",
}


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _xref(doc, owner, key, *, array=False):
    kind, value = doc.xref_get_key(owner, key)
    pattern = r"\[(\d+) 0 R\]" if array else r"(\d+) 0 R"
    match = re.fullmatch(pattern, value)
    if kind != ("array" if array else "xref") or not match:
        raise ValueError("unsupported font reference")
    return int(match[1])


def _font_program(page, name):
    fonts = page.get_fonts(full=True)
    matches = [font for font in fonts if font[1:3] == ("ttf", "Type0") and font[5] == "Identity-H"
               and re.sub(r"^[A-Z]{6}\+", "", font[3]) == name]
    if len(fonts) > 128 or len(matches) != 1:
        return None
    doc = page.parent
    descendant = _xref(doc, matches[0][0], "DescendantFonts", array=True)
    descriptor = _xref(doc, descendant, "FontDescriptor")
    stream = _xref(doc, descriptor, "FontFile2")
    kind, length = doc.xref_get_key(stream, "Length1")
    if kind != "int" or not 1 <= int(length) <= MAX_FONT_BYTES or doc.xref_get_key(stream, "DecodeParms")[0] != "null":
        return None
    size_kind, compressed_size = doc.xref_get_key(stream, "Length")
    if size_kind != "int" or not 1 <= int(compressed_size) <= MAX_FONT_BYTES:
        return None
    content = doc.xref_stream_raw(stream)
    if not content or len(content) > MAX_FONT_BYTES:
        return None
    encoding = doc.xref_get_key(stream, "Filter")
    if encoding == ("name", "/FlateDecode"):
        inflater = zlib.decompressobj()
        content = inflater.decompress(content, MAX_FONT_BYTES + 1)
        if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            return None
    elif encoding[0] != "null":
        return None
    return content if len(content) == int(length) else None


def _draw(page, char, origin, size):
    page.insert_text(origin, char, fontsize=size, fontname="PostalProof", color=(0, 0, 0))


@lru_cache(maxsize=24)
def _glyph_matches(program, char):
    if char not in _GLYPHS:
        return False
    with fitz.open() as sample:
        page = sample.new_page(width=128, height=112)
        page.insert_font(fontname="PostalProof", fontbuffer=program)
        _draw(page, char, (16, 84), 64)
        image = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY, alpha=False)
    return _sha(image.samples) == _GLYPHS[char]


def _visible_band(page, trace, letters, program):
    box = fitz.Rect(trace["bbox"])
    if (box.is_empty or not all(map(math.isfinite, box)) or not page.rect.contains(box)
            or box.width * box.height * 16 > 650_000 or trace["type"] != 0 or trace["opacity"] != 1
            or trace["dir"] != (1., 0.) or trace["color"] not in ((0., 0., 0.), (0.,), 0.)
            or not 8 <= trace["size"] <= 72):
        return None
    paints = page.get_bboxlog()
    seq = trace["seqno"]
    if (len(paints) > 20_000 or not 0 <= seq < len(paints) or paints[seq][0] != "fill-text"
            or any(box.intersects(fitz.Rect(item[1])) for item in paints[seq + 1:])):
        return None
    font = fitz.Font(fontbuffer=program)
    if any(not font.has_glyph(ord(char)) or font.has_glyph(ord(char)) != glyph
           for char, (_, glyph, _, _) in zip(letters, trace["chars"])):
        return None
    chars = trace["chars"]
    for left, right in zip(chars, chars[1:]):
        expected_x = left[2][0] + font.glyph_advance(left[0]) * trace["size"]
        if abs(right[2][0] - expected_x) > .12 or abs(right[2][1] - left[2][1]) > .04:
            return None
    if not all(_glyph_matches(program, char) for char in set(letters)):
        return None
    with fitz.open() as sample:
        reference = sample.new_page(width=page.rect.width, height=page.rect.height)
        reference.insert_font(fontname="PostalProof", fontbuffer=program)
        for char, (_, _, origin, _) in zip(letters, trace["chars"]):
            _draw(reference, char, origin, trace["size"])
        options = dict(matrix=fitz.Matrix(4, 4), clip=box, colorspace=fitz.csGRAY, alpha=False)
        actual = page.get_pixmap(**options).samples
        if actual != reference.get_pixmap(**options).samples:
            return None
    return _sha(actual)


def _visible_label(page, trace):
    """A neighboring native text label owns placement only if its visible print matches."""
    names = {"Helvetica": "helv", "Helvetica-Bold": "hebo", "Times-Roman": "tiro", "Courier": "cour"}
    name = names.get(trace["font"])
    box = fitz.Rect(trace["bbox"])
    if (not name or trace["type"] != 0 or trace["opacity"] != 1 or trace["dir"] != (1., 0.)
            or not 5 <= trace["size"] <= 40 or trace["color"] not in ((0., 0., 0.), (0.,), 0.)
            or box.is_empty or not page.rect.contains(box) or box.width * box.height * 16 > 120_000):
        return False
    with fitz.open() as doc:
        reference = doc.new_page(width=page.rect.width, height=page.rect.height)
        for code, _, origin, _ in trace["chars"]:
            reference.insert_text(origin, chr(code), fontsize=trace["size"], fontname=name, color=(0, 0, 0))
        options = dict(matrix=fitz.Matrix(4, 4), clip=box, colorspace=fitz.csGRAY, alpha=False)
        return page.get_pixmap(**options).samples == reference.get_pixmap(**options).samples


def _read_page(page, pdf_sha256):
    if (page.rotation or page.cropbox_position != fitz.Point(0, 0) or page.rect.is_empty
            or page.rect.width > 900 or page.rect.height > 980):
        return []
    plain = page.get_text("text", flags=fitz.TEXTFLAGS_TEXT)
    if len(plain) > 32_000 or not re.search(r"%\*[A-Z]{2}[0-9]{9}[A-Z]{2}\*", plain):
        return []
    traces = page.get_texttrace()
    if len(traces) > 2_000 or sum(len(t["chars"]) for t in traces) > 32_000:
        return []
    texts = ["".join(chr(c[0]) for c in t["chars"]) for t in traces]
    candidates = [(t, value, match[1]) for t, value in zip(traces, texts) if (match := _CODE.fullmatch(value))]
    if len(candidates) != 1:
        return []
    trace, letters, core = candidates[0]
    if len(_occurrences(plain, core)) != 1 or len(_occurrences(" ".join(texts), core)) != 1:
        return []
    box = fitz.Rect(trace["bbox"])
    # A separate nearby printed symbol is not a barcode delimiter. Decline the
    # entire new authority when another text span shares this contact row.
    margin = max(2., trace["size"] * .4)
    strip = fitz.Rect(box.x0 - margin, box.y0, box.x1 + margin, box.y1)
    neighborhood = fitz.Rect(strip.x0, box.y0 - trace["size"], strip.x1, box.y1 + trace["size"])
    other_texts = [(other, value.strip()) for other, value in zip(traces, texts) if other is not trace]
    if any(re.search(r"(?<![A-Za-z0-9])R(?![A-Za-z0-9])", value) or strip.intersects(fitz.Rect(other["bbox"]))
           or ("%" in value or "*" in value) and neighborhood.intersects(fitz.Rect(other["bbox"]))
           for other, value in other_texts):
        return []
    # A distinct mailing label immediately above the band provides a further
    # location check when the original actually prints such a number.
    labels = [(other, value) for other, value in other_texts if re.fullmatch(r"[0-9]{2,4}-[0-9]{6,12}", value)
              and 0 <= box.y0 - other["bbox"][3] <= trace["size"]
              and box.x0 <= (other["bbox"][0] + other["bbox"][2]) / 2 <= box.x1]
    if len(labels) > 1 or labels and (plain.count(labels[0][1]) != 1 or not _visible_label(page, labels[0][0])):
        return []
    program = _font_program(page, trace["font"])
    pixels = _visible_band(page, trace, letters, program) if program else None
    if not pixels:
        return []
    return [{"pdf_sha256": pdf_sha256, "page": page.number + 1, "core": core, "mark": "R", "label": labels[0][1] if labels else None,
             "font_sha256": _sha(program), "trace_sha256": _sha(_encoded(trace["chars"])),
             "bbox": list(box), "pixels_sha256": pixels}]


def _from_bytes(content, digest, numbers):
    with fitz.open(stream=content, filetype="pdf") as doc:
        if not doc.is_pdf or doc.needs_pass or doc.is_repaired or doc.xref_length() > 16_000 or max(numbers) > len(doc):
            return b"{}"
        found = {}
        for number in numbers:
            rows = _read_page(doc[number - 1], digest)
            if rows:
                found[str(number)] = rows
        return _encoded(found)


def read_selection(pdf_path, numbers, fingerprint):
    """Return newly allocated records; unknown and ambiguous originals abstain."""
    path = Path(pdf_path)
    try:
        numbers = tuple(numbers)
        if (not 1 <= len(numbers) <= 12 or any(type(n) is not int or n <= 0 for n in numbers)
                or tuple(sorted(set(numbers))) != numbers or path.suffix.lower() != ".pdf"
                or path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PDF_BYTES
                or browser_pdf_bundle_manifest_path(path).parent.exists()):
            return {}
        with path.open("rb") as stream:
            content = stream.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES or _sha(content) != fingerprint:
            return {}
        key = fingerprint, numbers
        with _RESULT_LOCK:
            cached = _RESULTS.get(key)
        if cached is None:
            cached = _from_bytes(content, fingerprint, numbers)
            with _RESULT_LOCK:
                if key not in _RESULTS and len(_RESULTS) >= 8:
                    del _RESULTS[next(iter(_RESULTS))]
                _RESULTS[key] = cached
        return json.loads(cached)
    except (ValueError, TypeError, OSError, RuntimeError, KeyError, IndexError, OverflowError, zlib.error):
        return {}


def captured_rows(state, number, source, required):
    selection = read_selection(state.pdf_path, sorted(int(p) for p in state.pages), state.pdf_fingerprint)
    if not selection:
        raise ValueError("postal source selection changed")
    rows = selection.get(str(number), [])
    if any(required.count(value) != 1 or source.count("[[" + value + "]]") != 1
           for row in rows for value in (row["core"], row["label"]) if value is not None):
        raise ValueError("postal source literal changed")
    return rows


def validate_capture(state, recipe, number, data):
    if KEY not in recipe:
        if FIELD in data or ROUTE in data:
            raise ValueError("unexpected postal source evidence")
        return
    route = data.get(ROUTE)
    metadata = state.pages[str(number)]
    if route not in {"direct_text", "unqualified"} or route == "direct_text" and ("ocr_text_acquisition" in data or not data.get("image_data_url")):
        raise ValueError("postal source route changed")
    if metadata.get("semantic_source_sha256") and (metadata.get("source_route") == "direct_text" and not metadata.get("ocr_used")) != (route == "direct_text"):
        raise ValueError("postal source route changed")
    expected = captured_rows(state, number, data["source_text"], data["expected_ar_tokens"]) if route == "direct_text" else []
    if recipe[KEY] != POLICY or data.get(FIELD) != expected:
        raise ValueError("postal source evidence changed")
    if expected:
        original = data.get("original_source_text")
        if not isinstance(original, str):
            raise ValueError("postal source text missing")
        lines = [line.strip() for line in original.splitlines()]
        for row in expected:
            if lines.count("%*" + row["core"] + "*") != 1 or row["label"] and lines.count(row["label"]) != 1:
                raise ValueError("postal source text owner changed")


def _target_row(core):
    spaced = " ".join(core)
    return re.compile(r"^(?:\u2066\[\[" + re.escape(spaced) + r"\]\]\u2069|\[\[" + re.escape(spaced) + r"\]\])(?=\r?$)", re.M)


def _occurrences(text, core):
    # Refusal-only view. Ignore invisible formatting when detecting collisions,
    # while the conversion below still requires literal single ASCII spaces.
    visible = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return list(re.finditer(r"(?<![A-Za-z0-9])" + r"\s*".join(core) + r"(?![A-Za-z0-9])", visible, re.I))


def derive(raw, rows):
    """Remove only inter-character ASCII spaces inside one complete source-owned token row."""
    if len(rows) != 1 or len(raw) > MAX_CHARS:
        return raw
    core = rows[0]["core"]
    if not core.isascii() or not POSTAL_TRACKING_CORE_RE.fullmatch(core) or len(_occurrences(raw, core)) != 1:
        return raw
    matches = list(_target_row(core).finditer(raw))
    if len(matches) != 1:
        return raw
    match = matches[0]
    candidate = raw[:match.start()] + match[0].replace(" ".join(core), core) + raw[match.end():]
    return raw if violation(candidate, rows) else candidate


def violation(candidate, rows):
    if not rows:
        return None
    if len(rows) != 1 or not isinstance(candidate, str) or len(candidate) > MAX_CHARS:
        return "postal_band_owner"
    core = rows[0]["core"]
    # Protocol isolates and brackets do not change the visible postal band.
    text = re.sub(r"(?:\u2066\[\[([^\[\]\r\n]+)\]\]\u2069|\[\[([^\[\]\r\n]+)\]\])",
                  lambda match: match[1] or match[2], candidate)
    hits = _occurrences(text, core)
    if len(hits) != 1 or hits[0][0] != core:
        return "postal_band_tracking"
    lines = text.splitlines()
    core_lines = [i for i,line in enumerate(lines) if core in line]
    if len(core_lines) != 1:
        return "postal_band_owner"
    index = core_lines[0]
    if len(re.findall(r"(?<![A-Za-z0-9])R(?![A-Za-z0-9])", text)) != 1:
        return "postal_band_mark"
    neighbors = [next((line.strip() for line in lines[index + 1:] if line.strip()), "")]
    before = [line.strip() for line in lines[:index] if line.strip()]
    if before and before[-1] == "R":
        before.pop()
    if before:
        neighbors.append(before[-1])
    if any(re.fullmatch(r"[%*]+", value) for value in neighbors):
        return "postal_band_delimiter"
    label = rows[0].get("label")
    if label:
        locations = [i for i, line in enumerate(lines) if line.strip() == label]
        if (len(locations) != 1 or text.count(label) != 1 or locations[0] >= index
                or any(line.strip() not in {"", "R"} for line in lines[locations[0] + 1:index])):
            return "postal_band_label"
    if lines[index].strip() == "R " + core:
        return None if sum(line.strip() == "R" for line in lines) == 0 else "postal_band_mark"
    if (lines[index].strip() != core or index == 0 or lines[index - 1].strip() != "R"
            or sum(line.strip() == "R" for line in lines) != 1):
        return "postal_band_mark"
    return None


def checked(result, raw, rows):
    if result.ok and rows:
        failure = violation(raw, rows) or violation(result.normalized_text, rows)
        if failure:
            return replace(result, ok=False, validator_failed=True, ar_violation_kind="expected_token_mismatch",
                           defect_reason="The printed postal band failed " + failure + ".")
    return result


def guidance(rows):
    if not rows:
        return ""
    return ("\nThe independently matched printed registered-mail band contains the separate capital R and the "
            "tracking identifier " + rows[0]["core"] + ". Keep the R beside the single compact identifier. "
            "The font's encoding delimiters do not print as percent signs or asterisks in this band.")
