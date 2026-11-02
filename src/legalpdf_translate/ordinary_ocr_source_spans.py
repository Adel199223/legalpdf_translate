"""Bounded V2 virtual rows: source-owned raw spans, whitespace changes only."""
from __future__ import annotations

import re

MAX_OWNERS = 48
MAX_MATCHES = 64


def _fail():
    raise ValueError("ocr_visual_source_requires_review")


def _compact(text):
    return re.sub(r"\s+", "", text)


def _words(text):
    return r"\s+".join(re.escape(word) for word in text.split())


def _whitespace_view(raw):
    chars, offsets = [], []
    for token in re.finditer(r"\S+", raw):
        if chars:
            chars.append(" ")
            offsets.append(token.start()-1)
        chars.extend(token[0])
        offsets.extend(range(token.start(),token.end()))
    return "".join(chars), offsets


def _matches(raw, pattern):
    values = list(re.finditer(r"(?<!\S)(?:" + pattern + r")(?!\S)", raw))
    if len(values) > MAX_MATCHES:
        _fail()
    return values


def _reference(text):
    return re.fullmatch(r"(?i:(?:Referência|Refer[.ª]|Ref[.ª])\b.*?)\s+([0-9]{4,16})", text)


def plans(lines, raw, width, page):
    """Plan only; every added source row must subsequently pass both recrops."""
    from . import ordinary_ocr_visual_source as v
    preview, _ = _whitespace_view(raw)
    # A missing contact block can be discovered even if its retained postcode
    # shares a paragraph. This planning view never supplies effective source.
    for row in lines:
        if v.POSTAL.fullmatch(row["text"]):
            matches = _matches(preview, _words(row["text"]))
            if len(matches) == 1:
                m = matches[0]
                preview = preview[:m.start()] + "\n" + row["text"] + "\n" + preview[m.end():]
    result = []
    for role, ids in v._plans(lines, preview, width, page):
        ids = list(ids)
        reference = None
        following = None
        if role == "mailing" and ids[-1]+1 < len(lines):
            a, b = (v._row_box(lines[i]) for i in (ids[-1], ids[-1]+1))
            if (0 < b[1]-a[3] <= 4*max(a[3]-a[1],b[3]-b[1])
                    and min(a[2],b[2])-max(a[0],b[0]) >= .35*min(a[2]-a[0],b[2]-b[0])
                    and 5 <= len(lines[ids[-1]+1]["text"]) <= 160):
                following = ("mailing_follow", [ids[-1]+1])
        if role == "case" and len(ids) == 1:
            i = ids[0]
            if (i + 1 < len(lines) and _reference(lines[i+1]["text"])
                    and v._same_column(lines[i:i+2], max_gap_lines=8)):
                reference = ("reference", [i+1])
        elif role == "address" and len(ids) == 1:
            i = ids[0]
            if (i + 1 < len(lines) and v.POSTAL.fullmatch(lines[i+1]["text"])
                    and v._same_column(lines[i:i+2])):
                ids.append(i+1)
        result.append((role, ids))
        if reference is not None:
            result.append(reference)
        if following is not None:
            result.append(following)
    # Preserve V1's narrower complete-line conditional admission when the
    # flattened planning view cannot supply its original row boundary.
    for i, row in enumerate(lines):
        if (v.CONDITION.search(row["text"]) and v._conditional_owner(row["text"], raw) is not None
                and not any(i in ids for _, ids in result)):
            result.append(("condition", [i]))
    if len(result) > v.MAX_GROUPS:
        raise ValueError("ocr_visual_source_region_limit")
    return result


def project(raw, groups):
    """Choose all owners against immutable raw text before inserting row breaks.

    Existing source reconciliation still owns every substantive edit. This
    projection cannot insert a character other than whitespace or erase a word.
    Source row ordinals refer to the separately retained two-scale regions.
    """
    from . import ordinary_ocr_visual_source as v
    if type(raw) is not str or len(raw) > v.MAX_CHARS or len(groups) > v.MAX_GROUPS:
        _fail()
    owners = []
    compact_rows, raw_offsets = _whitespace_view(raw)

    def owner(region, row, role, pattern, accepts=lambda value: True, *, optional=False):
        found = [m for m in _matches(raw, pattern) if accepts(" ".join(m[0].split()))]
        if not found and optional:
            return None
        if len(found) != 1:
            _fail()
        m = found[0]
        item = {"region": region, "row": row, "role": role, "start": m.start(), "end": m.end(),
                "raw_sha256": v._sha(m[0])}
        owners.append(item)
        if len(owners) > MAX_OWNERS:
            _fail()
        return item

    def ordered(rows):
        if any(b["start"] < a["end"] or raw[a["end"]:b["start"]].strip()
               for a, b in zip(rows, rows[1:])):
            _fail()

    def address(region, rows):
        text = rows[0]
        parts = re.split(r"\b(?:da|de|do)\b", text, 1)
        pattern = (_words(parts[0].strip()) + r"\s+(?:da|de|do)\s+" + _words(parts[1].strip())
                   if len(parts) == 2 else _words(text))
        first = owner(region, 0, "address", pattern, lambda s: v._address_pair(s, text) or s == text)
        if len(rows) > 1 and v.POSTAL.fullmatch(rows[1]):
            post = owner(region, 1, "postcode", _words(rows[1]))
            ordered([first, post])

    headers = [rows[0] for role, rows in groups if role == "head" and len(rows) == 1]
    attested_mail = {_compact(value).upper() for role, rows in groups if role == "mailing" for value in rows[1:]}
    mailing_owners = []
    for region, (role, rows) in enumerate(groups):
        if role in {"flow_condition", "inline_condition", "condition"}:
            if role == "condition":
                original_row = v._conditional_owner(rows[0], raw) if len(rows) == 1 else None
                if original_row is None:
                    _fail()
                lines = raw.splitlines(keepends=True)
                a = sum(map(len, lines[:original_row]))
                line = lines[original_row]
                a += len(line)-len(line.lstrip())
                b = a+len(line.strip())
                owner(region, 0, role, re.escape(raw[a:b]))
                continue
            scope = (v._flow_condition(rows, compact_rows) if role == "flow_condition" else
                     v._inline_condition(rows[0], compact_rows) if role == "inline_condition" and len(rows) == 1 else
                     None)
            if scope is None or not 0 <= scope[0] < scope[1] <= len(raw_offsets):
                _fail()
            a, b = raw_offsets[scope[0]], raw_offsets[scope[1]-1]+1
            owner(region, 1 if role == "flow_condition" else 0, role, re.escape(raw[a:b]))
        elif role == "mailing":
            if len(rows) != 3 or not v.MAILING_REF.fullmatch(rows[1]) or not v.TRACKING.fullmatch(rows[2]):
                _fail()
            date = owner(region, 0, "mailing_date", _words(rows[0]))
            ref = owner(region, 1, "mailing_reference", re.escape(rows[1]), optional=True)
            code = _compact(rows[2])
            tracking = owner(region, 2, "mailing_tracking", r"\s*".join(map(re.escape, code)), optional=True)
            if tracking and not ref:
                _fail()
            if ref and (ref["start"] < date["end"] or raw[date["end"]:ref["start"]].strip()):
                next_group = groups[region+1] if region+1 < len(groups) else None
                if not next_group or next_group[0] != "mailing_follow" or len(next_group[1]) != 1:
                    _fail()
                following = owner(region+1, 0, "mailing_follow", _words(next_group[1][0]))
                ordered([item for item in (ref, tracking, following) if item])
            else:
                ordered([item for item in (date, ref, tracking) if item])
            mailing_owners.append((date, ref, tracking))
        elif role == "head" and len(rows) == 1 and v.HEADER.fullmatch(rows[0]):
            found = owner(region, 0, "header", _words(rows[0]), optional=True)
            if found and raw[:found["start"]].strip():
                _fail()
        elif role == "case":
            if not rows:
                _fail()
            text = rows[0]
            label = re.fullmatch(rf"(?i:(Processo|Autos|Inquérito))\s+[^\d]{{0,8}}({v.CASE})", text)
            if not label:
                _fail()
            case = owner(region, 0, "case", re.escape(label[1]) + r"\s+[^\d]{0,8}" + v.CASE,
                         lambda s: v._similar(s, text))
            reference_group = (groups[region+1] if region+1 < len(groups) else None)
            if reference_group and reference_group[0] == "reference":
                if len(reference_group[1]) != 1 or not _reference(reference_group[1][0]):
                    _fail()
                ref = owner(region+1, 0, "labelled_reference", _words(reference_group[1][0]))
                ordered([case, ref])
            elif headers:
                # A newly segmented compact header needs its separately printed
                # labelled pair, not a coarse-only reference or global number.
                _fail()
        elif role == "email":
            for row, text in enumerate(rows):
                if not v.EMAIL.fullmatch(text):
                    continue
                matches = list(v.EMAIL.finditer(raw))
                plausible = [m for m in matches if v._similar(m[0], text)]
                # The original V1 spaced local-part case can also have a short
                # leading word. Bind that start to the exact printed prefix;
                # a different @ occurrence still prevents unique ownership.
                prefix = re.split(r"[.+@-]", text, 1)[0]
                local_part = text.split("@", 1)[0]
                whole = [m for m in _matches(raw, v.EMAIL.pattern) if v._similar(m[0], text)
                         and m[0].split("@", 1)[0].casefold() == local_part.casefold()]
                if whole:
                    expanded = whole
                elif len(prefix) >= 3:
                    pattern = re.escape(prefix) + r"[\w.+-]*(?:\s+[\w.+-]+){0,2}@[\w.-]+\.[A-Za-z]{2,12}"
                    expanded = [m for m in _matches(raw, pattern) if v._similar(_compact(m[0]), text)
                                and _compact(m[0]).split("@", 1)[0].casefold() == local_part.casefold()]
                else:
                    expanded = [m for m in _matches(raw, v.EMAIL.pattern) if v._similar(m[0], text)]
                if not expanded:
                    # A complete syntactic email can retain V1's narrow value
                    # correction. This fallback never consumes a prose word.
                    expanded = [m for m in _matches(raw, v.EMAIL.pattern) if v._similar(m[0], text)]
                at_positions = {m.start() + m[0].index("@") for m in plausible + expanded}
                if len(expanded) != 1 or len(at_positions) != 1:
                    _fail()
                m = expanded[0]
                owner(region, row, "email", re.escape(m[0]), lambda s: v._similar(_compact(s), text))
        elif role in {"address", "contact"} and rows:
            address(region, rows)
        elif role == "url":
            for row, text in enumerate(rows):
                link = v.LINK.search(text)
                if not link:
                    continue
                prefix, suffix = text[:link.start()], text[link.end():]
                pattern = ((_words(prefix.strip()) + r"\s+" if prefix.strip() else "")
                           + v.LINK.pattern
                           + (r"\s+" + _words(suffix.strip()) if suffix.strip() else ""))
                def supported_url(value):
                    found = v.LINK.search(value)
                    return (found and found[0].split("/", 3)[:3] == link[0].split("/", 3)[:3]
                            and v._similar(found[0], link[0]))
                owner(region, row, "url", pattern, supported_url)

    # A conflicting inline postal field must not disappear from V1's line-local
    # conflict checker merely because only the desired spans were separated.
    patterns = [r"(?<!\w)[0-9OIL?]{2,4}\s*[-–]\s*[0-9OIL?]{5,13}(?!\w)",
                r"(?<!\w)[A-Z]\s*[A-Z]\s*(?:[0-9OILSBZ?]\s*){7,11}[A-Z]\s*[A-Z](?!\w)"]
    for pattern in patterns:
        for m in re.finditer(pattern, raw, re.I):
            value = _compact(m[0]).upper()
            if value in attested_mail:
                if not any(o["role"] in {"mailing_reference", "mailing_tracking"}
                           and o["start"] == m.start() and o["end"] == m.end() for o in owners):
                    _fail()
                continue
            nearby = any(min(r["start"] for r in (a,b,c) if r) - 64 <= m.start()
                         <= max(r["end"] for r in (a,b,c) if r) + 160 for a,b,c in mailing_owners)
            if nearby or any(v._similar(value, known, .86) for known in attested_mail):
                _fail()
    owners.sort(key=lambda o: (o["start"], o["end"]))
    if any(a["end"] > b["start"] for a, b in zip(owners, owners[1:])):
        _fail()
    # Cuts only at owned, whitespace-delimited spans. Keep every unmatched word
    # exactly where the provider supplied it; join only measured row interiors.
    chunks = []
    cursor = 0
    for item in owners:
        a, b = item["start"], item["end"]
        chunks.extend([raw[cursor:a], "\n", " ".join(raw[a:b].split()), "\n"])
        cursor = b
    chunks.append(raw[cursor:])
    virtual = ("\n".join(line.strip() for line in "".join(chunks).splitlines() if line.strip())
               if owners else raw)
    if _compact(virtual) != _compact(raw) or len(virtual) > v.MAX_CHARS + MAX_OWNERS * 2:
        _fail()
    proof = {"version": "source_owned_virtual_rows_v1", "owners": owners,
             "raw_sha256": v._sha(raw), "virtual_sha256": v._sha(virtual),
             "nonwhitespace_sha256": v._sha(_compact(raw))}
    return virtual, proof
