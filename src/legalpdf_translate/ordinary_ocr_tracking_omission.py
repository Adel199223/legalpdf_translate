"""Recover a single missing serial digit from a repeatedly read printed mailing field."""
from __future__ import annotations

import re
import unicodedata

from . import ordinary_ocr_visual_source as visual

# Only a complete ASCII, character-spaced row may authorize insertion. The
# broader expression is for detecting competitors, never recovering characters.
SPACED_SHORT = re.compile(r"[A-Z](?: +[A-Z])(?: +[0-9]){8}(?: +[A-Z]){2}", re.ASCII)
GAP = r"\s*"
TRACKING_LIKE = re.compile(rf"(?<![A-Za-z0-9_])[A-Z]{GAP}[A-Z]{GAP}"
                           rf"(?:[0-9OILSBZ?]{GAP}){{7,11}}[A-Z]{GAP}[A-Z](?![A-Za-z0-9_])", re.I)


def _occurrences(text):
    # Refusal view only. Preserve the enclosing original offsets so the
    # authorized raw field must still be the exact ASCII row which was seen.
    offsets = [i for i,c in enumerate(text) if unicodedata.category(c) != "Cf"]
    visible = "".join(text[i] for i in offsets)
    return [(offsets[m.start()], offsets[m.end()-1]+1, "".join(m[0].split()).upper())
            for m in TRACKING_LIKE.finditer(visible)]


def _review():
    raise ValueError("ocr_visual_source_requires_review")


def _attested(region, coarse, expected):
    indices = region["coarse_lines"]
    scans = region["scans"]
    if (len(indices) != len(expected) or [s["dpi"] for s in scans] != [288, 432]
            or indices != list(range(indices[0], indices[0] + len(indices)))):
        _review()
    for index, value in zip(indices, expected):
        row = coarse["lines"][index]
        if row["text"] != value or any(visual._read_line(row, scan) != value for scan in scans):
            _review()


def restore(raw, coarse, regions, groups):
    """Return a provider-text view plus a reconstructible proof of its sole insertion."""
    if not isinstance(raw, str) or len(raw) > visual.MAX_CHARS or len(regions) != len(groups):
        _review()
    # Preserve all original line terminators and outside bytes, including CRLF.
    lines = [m for m in re.finditer(r"[^\r\n]+", raw) if m[0].strip()]
    short = [i for i, m in enumerate(lines) if SPACED_SHORT.fullmatch(m[0].strip(" "))]
    mailing = [i for i, (role, _) in enumerate(groups) if role == "mailing"]
    if not short or not mailing:
        return raw, None
    raw_rows = [m[0].strip(" ") for m in lines]
    anchored = []
    for j in mailing:
        if (len(groups[j][1]) != 3 or j+1 >= len(groups) or groups[j+1][0] != "mailing_follow"
                or len(groups[j+1][1]) != 1):
            continue
        date, ref, _ = groups[j][1]
        following = groups[j+1][1][0]
        for i in short:
            if (2 <= i < len(lines)-1 and raw_rows[i-2:i] == [date, ref]
                    and raw_rows[i+1] == following):
                anchored.append((i,j))
    # Other references on the page remain subject to the pre-existing V3
    # geometry/identity checks. An unrelated short row never activates repair.
    if not anchored:
        return raw, None
    if len(anchored) != 1 or len(short) != 1 or len(mailing) != 1 or len(groups) > visual.MAX_GROUPS:
        _review()
    i, j = anchored[0]
    date, ref, printed = groups[j][1]
    follow = groups[j + 1][1][0]
    code = printed.replace(" ", "")
    if (not re.search(r"\b[0-9]{2}[-/.][0-9]{2}[-/.][0-9]{4}\b", date)
            or not re.fullmatch(r"[0-9]{2,4}-[0-9]{6,12}", ref)
            or not visual.TRACKING.fullmatch(printed) or len(follow) > 160
            or i < 2 or i + 1 >= len(lines)):
        _review()
    slot = raw_rows[i]
    if (len(slot) > 96 or raw_rows[i-2:i+2] != [date, ref, slot, follow]
            or any(raw_rows.count(value) != 1 for value in (date, ref, follow))):
        _review()
    mail_region, follow_region = regions[j:j+2]
    if mail_region["role"] != "mailing" or follow_region["role"] != "mailing_follow":
        _review()
    _attested(mail_region, coarse, [date, ref, printed])
    nearby = [coarse["lines"][i] for i in mail_region["coarse_lines"][:2]]
    if not visual._same_column(nearby, max_gap_lines=8):
        _review()
    _attested(follow_region, coarse, [follow])
    if mail_region["coarse_lines"][-1] + 1 != follow_region["coarse_lines"][0]:
        _review()
    coarse_rows = [row["text"] for row in coarse["lines"]]
    if (any(coarse_rows.count(value) != 1 for value in (date, ref, follow))
            or [value for _, _, value in _occurrences("\n".join(coarse_rows))] != [code]):
        _review()
    start = lines[i].start() + lines[i][0].index(slot)
    end = start + len(slot)
    if [(a,b) for a,b,_ in _occurrences(raw)] != [(start, end)]:
        _review()
    short_code = slot.replace(" ", "")
    # Both neighboring serial digits must survive. An ambiguous index (e.g.
    # adjacent repeated digits) cannot be selected just because the result fits.
    positions = [k for k in range(2, 11) if code[:k] + code[k+1:] == short_code]
    if len(positions) != 1 or positions[0] not in range(3, 10):
        _review()
    index = positions[0]
    insert_at = start + [k for k, char in enumerate(slot) if char != " "][index]
    derived = raw[:insert_at] + code[index] + " " + raw[insert_at:]
    return derived, {
        "raw_sha256": visual._sha(raw), "derived_sha256": visual._sha(derived),
        "raw_span": [start, end], "raw_spelling": slot, "raw_spelling_sha256": visual._sha(slot),
        "insert_at": insert_at, "serial_character_index": index,
        "printed_code": code, "mailing_reference": ref,
        "coarse_lines": mail_region["coarse_lines"] + follow_region["coarse_lines"],
        "coarse_png_sha256": coarse["png_sha256"],
        "mailing_png_sha256": [s["png_sha256"] for s in mail_region["scans"]],
        "following_png_sha256": [s["png_sha256"] for s in follow_region["scans"]],
    }


def obsolete(visible, spelling):
    """Reject the same obsolete field even if its whitespace was resegmented."""
    damaged = spelling.replace(" ", "")
    visible = "".join(c for c in visible if unicodedata.category(c) != "Cf")
    pattern = r"(?<![A-Za-z0-9_])" + GAP.join(map(re.escape, damaged)) + r"(?![A-Za-z0-9_])"
    return re.search(pattern, visible, re.I) is not None
