"""Corroborate bounded source slots on image-only pages without changing the OCR answer."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import fitz

KEY = "ocr_visual_source_policy"
POLICY = "local_source_slots_v1"
POLICY_V2 = "local_source_slots_v2"
POLICY_V3 = "local_source_slots_v3"
POLICY_V4 = "local_source_slots_v4"
FRESH_POLICY = POLICY_V4
SUPPORTED_POLICIES = (POLICY, POLICY_V2, POLICY_V3, POLICY_V4)
MAX_CHARS = 32000
MAX_LINES = 180
MAX_GROUPS = 12
MAX_BYTES = 2_000_000
CASE = r"[0-9]{1,9}/[0-9]{2}\.[0-9]{1,3}[A-Z][A-Z0-9]{1,12}"
HEADER = re.compile(rf"(?P<case>{CASE})\s+\[(?P<ref>[0-9]{{4,16}})\]")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,12}", re.ASCII)
LINK = re.compile(r"https?://[A-Za-z0-9][A-Za-z0-9./_?=%&#~-]*[A-Za-z0-9/]", re.ASCII)
PHONE = re.compile(r"(?<!\d)\d{3}(?: \d{3}){2}(?!\d)")
DOMAIN = re.compile(r"\bwww\.[a-z0-9.-]+\.[a-z]{2,10}\b", re.ASCII | re.I)
POSTAL = re.compile(r"\d{4}-\d{3}\s+[^\W\d_][\w .'-]{1,40}")
PHONE_CONTIGUOUS = re.compile(r"(?<!\d)\d{9}(?!\d)")
CLOCK = re.compile(r"\b(?:[01]\d|2[0-3])h[0-5]\d\b")
MAILING_REF = re.compile(r"\d{2,4}-\d{6,12}")
TRACKING = re.compile(r"[A-Z]{2} *[0-9]{9} *[A-Z]{2}")
ADDRESS = re.compile(r"\b(?:Rua|Praça|Avenida|Largo|Travessa|Alameda)\b", re.I)
CONDITION = re.compile(r"\bse\b", re.I)


def _sha(data):
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def _fail():
    raise ValueError("ocr_visual_source_evidence_changed")


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _open_page(pdf_path, number):
    from .browser_pdf_bundle import load_browser_pdf_bundle
    if load_browser_pdf_bundle(Path(pdf_path)) is not None:
        return None
    doc = fitz.open(pdf_path)
    try:
        page = doc[number - 1]
        if (not doc.is_pdf or page.rotation or page.get_text("text").strip()
                or not 0 < page.rect.width <= 900 or not 0 < page.rect.height <= 980):
            doc.close()
            return None
        return doc
    except Exception:
        doc.close()
        raise


def selection_qualifies(config, pages):
    if (os.name != "nt" or config.image_mode.value == "off" or config.ocr_mode.value == "off"
            or config.ocr_engine.value not in {"api", "local_then_api"} or not config.strip_bidi_controls
            or len(pages) > 12):
        return False
    path = Path(config.pdf_path)
    try:
        if path.suffix.lower() != ".pdf" or not path.is_file() or path.stat().st_size > 64_000_000:
            return False
        for number in pages:
            doc = _open_page(path, number)
            if doc is not None:
                doc.close()
                return True
    except (OSError, ValueError, IndexError, RuntimeError):
        return False
    return False


def eligible_page(pdf_path, number, raw):
    if not isinstance(raw, str) or len(raw) > MAX_CHARS:
        return False
    doc = _open_page(pdf_path, number)
    if doc is None:
        return False
    doc.close()
    return True


def _row_box(row):
    words = row["words"]
    return (min(w["box"][0] for w in words), min(w["box"][1] for w in words),
            max(w["box"][0] + w["box"][2] for w in words),
            max(w["box"][1] + w["box"][3] for w in words))


def _lines(value, width, height):
    if not isinstance(value, (list, tuple)) or len(value) > MAX_LINES:
        _fail()
    count = 0
    for row in value:
        if (type(row) is not dict or set(row) != {"text", "words"} or type(row["text"]) is not str
                or not 0 < len(row["text"]) <= 1600 or not isinstance(row["words"], (list, tuple))
                or not 1 <= len(row["words"]) <= 200):
            _fail()
        count += len(row["text"])
        for word in row["words"]:
            if (type(word) is not dict or set(word) != {"text", "box"} or type(word["text"]) is not str
                    or not 0 < len(word["text"]) <= 400 or len(word["box"]) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in word["box"])):
                _fail()
            x, y, w, h = word["box"]
            if x < 0 or y < 0 or min(w, h) <= 0 or x+w > width+1 or y+h > height+1:
                _fail()
        if row["text"] != " ".join(w["text"] for w in row["words"]):
            _fail()
    if count > MAX_CHARS:
        _fail()
    return list(value)


def _represented(text, raw):
    return " ".join(text.lower().split()) in " ".join(raw.lower().split())


def _plans(lines, raw, width, page=None):
    plans = []
    grouped = set()
    for i in range(1,len(lines)-1):
        if (page is not None and MAILING_REF.fullmatch(lines[i]["text"])
                and TRACKING.fullmatch(lines[i+1]["text"]) and _mailing_geometry(page,lines[i:i+2])
                and re.search(r"\b\d{2}[-/.]\d{2}[-/.]\d{4}\b",lines[i-1]["text"])):
            plans.append(("mailing",[i-1,i,i+1]))
    for i,row in enumerate(lines):
        if not EMAIL.fullmatch(row["text"]) or "@" in raw:
            continue
        # A short contact block may disappear wholesale from a postal letter.
        # Locate the postal and address owners in the same printed column.
        for post in range(max(1,i-7),i):
            candidate = lines[post-1:i+1]
            zip_line = lines[post]["text"]
            if (POSTAL.fullmatch(zip_line) and raw.splitlines().count(zip_line)==1
                    and ADDRESS.search(candidate[0]["text"]) and PHONE_CONTIGUOUS.search(" ".join(r["text"] for r in candidate[2:]))
                    and _same_column(candidate, max_gap_lines=7)
                    and _same_column(candidate[:2]) and _same_column(candidate[2:])):
                ids=list(range(post-1,i+1))
                plans.append(("contact",ids))
                grouped.update(ids)
                break
    sidebar = []
    # Only recover a distinct leading column when multiple printed contact/navigation
    # anchors identify the same missing block, beside a separately represented body.
    for i, row in enumerate(lines):
        x0, _, x1, _ = _row_box(row)
        if x1 > width * .50 or x0 > width * .32:
            break
        sidebar.append(i)
    side = " ".join(lines[i]["text"] for i in sidebar)
    right = lines[len(sidebar):]
    recover = (5 <= len(sidebar) <= 40 and PHONE.search(side) and DOMAIN.search(side)
               and not any(_represented(lines[i]["text"], raw) for i in sidebar if len(lines[i]["text"]) >= 14)
               and any(_row_box(row)[0] >= width * .40 and _represented(row["text"], raw)
                       for row in right if len(row["text"]) >= 12))
    if recover:
        # Small bands keep line locations independently checkable across scales.
        for off in range(0, len(sidebar), 5):
            plans.append(("side", sidebar[off:off+5]))
    for i, row in enumerate(lines):
        if i in grouped or (recover and i in sidebar):
            continue
        text = row["text"]
        if i == 0 and HEADER.fullmatch(text):
            role = "head"
        elif "@" in text:
            role = "email"
        elif LINK.search(text):
            role = "url"
        elif re.match(r"^(?:Processo|Autos|Inquérito)\b", text, re.I) and re.search(r"\d{2}.*[A-Z]{2,}", text):
            role = "case"
        elif ADDRESS.search(text) and re.search(r"\s[-–]\s", text):
            role = "address"
        elif CONDITION.search(text):
            if _conditional_owner(text, raw) is not None:
                role = "condition"
            elif _inline_condition(text,raw) is not None:
                role = "inline_condition"
            elif 0<i<len(lines)-1 and _same_column(lines[i-1:i+2]) and _flow_condition(
                    [r["text"] for r in lines[i-1:i+2]],raw) is not None:
                plans.append(("flow_condition",[i-1,i,i+1]))
                continue
            else:
                continue
        else:
            continue
        plans.append((role, [i]))
    if len(plans) > MAX_GROUPS:
        raise ValueError("ocr_visual_source_region_limit")
    return plans


def _same_column(rows, *, max_gap_lines=4):
    boxes = [_row_box(row) for row in rows]
    return (max(b[0] for b in boxes)-min(b[0] for b in boxes) < 52 and
            all(0 < b[1]-a[1] <= max_gap_lines*max(a[3]-a[1],b[3]-b[1]) for a,b in zip(boxes,boxes[1:])))


def _mailing_geometry(page,rows):
    # Identify the intervening graphic. Its bars never supply characters.
    a,b=(_row_box(row) for row in rows)
    left,right=min(a[0],b[0]),max(a[2],b[2])
    if (b[1]<=a[3] or b[1]-a[3]>110 or min(a[2],b[2])<=max(a[0],b[0])):
        return False
    clip=fitz.Rect(left/2,a[3]/2,right/2,b[1]/2)
    pix=page.get_pixmap(matrix=fitz.Matrix(2,2),clip=clip,colorspace=fitz.csGRAY,alpha=False)
    if pix.width<35 or pix.height<8:
        return False
    samples=pix.samples
    for y in (pix.height*2//5,pix.height//2,pix.height*3//5):
        line=samples[y*pix.stride:y*pix.stride+pix.width]
        if sum(x>155 and z<100 for x,z in zip(line,line[1:]))<12:
            return False
    return True


def _inline_condition(text,raw):
    if len(text.split())<7 or not CONDITION.search(text):
        return None
    changed,count=re.subn(r"\b(de|em) que\b",r"\1 quem",text)
    if count==1 and raw.count(changed)==1 and text not in raw:
        return raw.index(changed),raw.index(changed)+len(changed)
    return None


def _flow_condition(lines,raw):
    if len(lines)!=3:
        return None
    before,text,after=lines
    if not CONDITION.search(text) or len(before.split())<4 or len(after.split())<4:
        return None
    left=r"\s+".join(map(re.escape,before.split()[-4:]))
    right=r"\s+".join(map(re.escape,after.split()[:4]))
    matches=list(re.finditer(r"(?<!\w)"+left+r"\s+([^\n]{1,145}?)\s+"+right+r"(?!\w)",raw))
    if len(matches)!=1:
        return None
    prior=matches[0][1]
    old, new = prior.casefold().split(), text.casefold().split()
    edits = [(tuple(old[a:b]),tuple(new[c:d])) for op,a,b,c,d in
             SequenceMatcher(None,old,new,autojunk=False).get_opcodes() if op!="equal"]
    # This narrow connective repair cannot consume a number, participant,
    # unrelated verb or token retained in the original phrase.
    allowed = {(("ou",),("se",)), (("após",),("não","for")), (("foi",),("for",))}
    if (len(set(old) & set(new)) >= 4 and (("ou",),("se",)) in edits
            and all(edit in allowed for edit in edits)):
        return matches[0].span(1)
    return None


def _conditional_owner(text, raw):
    words = text.split()
    if not 5 <= len(words) <= 25:
        return None
    found = []
    for i, line in enumerate(raw.splitlines()):
        prior = line.split()
        if len(prior) != len(words):
            continue
        # Match the same source line, including at least four unchanged words.
        diffs = [(a.casefold(), b.casefold()) for a, b in zip(prior, words) if a != b]
        if (len(words) - len(diffs) >= 4 and 1 <= len(diffs) <= 2
                and ("ou", "se") in diffs and all(pair in {("ou", "se"), ("foi", "for")} for pair in diffs)):
            found.append(i)
    return found[0] if len(found) == 1 else None


def _clip(page, rows):
    rect = fitz.Rect()
    height = 0.
    for row in rows:
        box = _row_box(row)
        rect |= fitz.Rect(*(v / 2 for v in box))
        height = max(height, max(w["box"][3] for w in row["words"]) / 2)
    return (rect + (-height, -height, height, height)) & page.rect


def _scan(page, dpi, clip, recognizer, stored=None):
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), clip=clip, alpha=False)
    if max(pix.width, pix.height) > 4096 or pix.width*pix.height > 16_000_000:
        _fail()
    png = pix.tobytes("png")
    identity = {"dpi": dpi, "bounds": list(pix.irect), "png_sha256": _sha(png)}
    if stored is None:
        lines = recognizer(png)
    else:
        if type(stored) is not dict or set(stored) != set(identity) | {"lines"} or any(stored[k] != v for k,v in identity.items()):
            _fail()
        lines = stored["lines"]
    return {**identity, "lines": _lines(lines, pix.width, pix.height)}


def _read_line(row, scan):
    """Rediscover the same physical line by overlap in source-page coordinates."""
    x0,y0,x1,y1 = _row_box(row)
    found = []
    for observed in scan["lines"]:
        bx0,by0,bx1,by1 = _row_box(observed)
        scale = 144 / scan["dpi"]
        a,b,c,d = scan["bounds"]
        bx0,bx1 = (bx0+a)*scale,(bx1+a)*scale
        by0,by1 = (by0+b)*scale,(by1+b)*scale
        if (min(y1,by1)-max(y0,by0) >= .55*min(y1-y0,by1-by0)
                and min(x1,bx1)-max(x0,bx0) >= .65*max(x1-x0,bx1-bx0)):
            found.append(observed["text"])
    return found[0] if len(found)==1 else None


def _similar(left, right, threshold=.80):
    return SequenceMatcher(None, left.casefold(), right.casefold(), autojunk=False).ratio() >= threshold


def _owner(lines, accept):
    matches = [(i,l) for i,l in enumerate(lines) if accept(l)]
    if len(matches) > 1:
        raise ValueError("ocr_visual_source_requires_review")
    return matches[0] if len(matches)==1 else None


def _check_mailing_neighbours(lines, center, groups):
    """A different printed or OCR-like value in this field cannot be added to or replaced."""
    attested = {label.replace(" ","") for kind, rows in groups if kind=="mailing"
                for label in rows[1:]}
    nonempty = [i for i,line in enumerate(lines) if line.strip()]
    index = nonempty.index(center)
    near = set(nonempty[max(0,index-3):index+4])
    for i,line in enumerate(lines):
        value = "".join(line.split()).upper()
        if value in attested:
            continue
        ref_like = re.fullmatch(r"[0-9OIL?]{2,4}[-–][0-9OIL?]{5,13}",value)
        track_like = re.fullmatch(r"[A-Z]{2}[0-9OILSBZ?]{7,11}[A-Z]{2}",value)
        if ((ref_like or track_like) and sum(c.isdigit() for c in value)>=5
                and (i in near or any(_similar(value,known,.86) for known in attested))):
            raise ValueError("ocr_visual_source_requires_review")


def _derive(raw, groups):
    original = raw.split("\n")
    lines = list(original)
    claimed = set()
    def apply(index, replacement):
        if index in claimed:
            raise ValueError("ocr_visual_source_requires_review")
        claimed.add(index)
        lines[index] = replacement + ("\r" if original[index].endswith("\r") and not replacement.endswith("\r") else "")
    head = None
    prefix = []
    locks = []
    cases = []
    aliases = []
    conditionals = []
    uncertain = []
    added_contact = False
    phone_slots = []
    mailing = []
    for role, seen in groups:
        if role=="mailing":
            if len(seen)!=3:
                raise ValueError("ocr_visual_source_requires_review")
            label,ref,tracking=seen
            if not MAILING_REF.fullmatch(ref) or not TRACKING.fullmatch(tracking):
                raise ValueError("ocr_visual_source_requires_review")
            code=tracking.replace(" ","")
            known=_owner(original,lambda line: line.strip()==ref)
            old_code=_owner(original,lambda line: line.strip().replace(" ","")==code)
            if ref in raw and known is None or code in raw.replace(" ","") and old_code is None:
                raise ValueError("ocr_visual_source_requires_review")
            if known is None:
                anchor=_owner(original,lambda line: line.strip()==label)
                if anchor is None or old_code is not None:
                    raise ValueError("ocr_visual_source_requires_review")
                _check_mailing_neighbours(original,anchor[0],groups)
                apply(anchor[0],anchor[1]+"\n"+ref+"\n"+code)
            else:
                _check_mailing_neighbours(original,known[0],groups)
                if old_code is None:
                    apply(known[0],known[1]+"\n"+code)
                elif old_code[0]<=known[0] or any(line.strip() for line in original[known[0]+1:old_code[0]]):
                    raise ValueError("ocr_visual_source_requires_review")
                elif old_code[1].strip()!=code:
                    apply(old_code[0],code)
            locks.extend([ref,code])
            mailing.append([ref,code])
            continue
        if role in {"inline_condition","flow_condition"}:
            scope = (_inline_condition(seen[0],raw) if role=="inline_condition" and len(seen)==1
                     else _flow_condition(seen,raw))
            if scope is None:
                raise ValueError("ocr_visual_source_requires_review")
            start,end=scope
            index=raw.count("\n",0,start)
            if "\n" in raw[start:end]:
                raise ValueError("ocr_visual_source_requires_review")
            offset=start-(raw.rfind("\n",0,start)+1)
            text=seen[0] if role=="inline_condition" else seen[1]
            apply(index,original[index][:offset]+text+original[index][offset+end-start:])
            conditionals.append(text)
            continue
        if role=="contact":
            if len(seen)<4:
                raise ValueError("ocr_visual_source_requires_review")
            address,postcode,*tail=seen
            postal=_owner(original,lambda line: line.strip()==postcode)
            body=" ".join(tail)
            phones=PHONE_CONTIGUOUS.findall(body)
            mail=tail[-1]
            if (not postal or not POSTAL.fullmatch(postcode) or postal[0]<1 or not EMAIL.fullmatch(mail)
                    or len(phones)!=1 or phones[0] in raw or "@" in raw
                    or not ADDRESS.search(address) or not _address_pair(original[postal[0]-1],address)
                    or any(_represented(line,raw) for line in tail)
                    or re.search(r"\d{1,2}h[0-9Oo]{2}\b",CLOCK.sub("",body))):
                raise ValueError("ocr_visual_source_requires_review")
            index=postal[0]
            before=original[index-1]
            if before!=address:
                aliases.append([before,address])
            apply(index-1,address)
            apply(index,original[index]+"\n"+"\n".join(tail))
            locks.extend([address,phones[0],*CLOCK.findall(body),mail])
            times=CLOCK.findall(body)
            if times:
                phone_slots.append([postcode,phones[0],times[0]])
            added_contact=True
            continue
        for text in seen:
            if role == "side":
                # A numeric contact line may have imperfect adjoining punctuation.
                # Only its validated telephone literal is transcribed in this slot.
                phone = PHONE.search(text)
                if phone:
                    locks.append(phone.group())
                    suffix = text[phone.end():]
                    if re.fullmatch(r"\s*/[^\W\d_].*\)\s*", suffix):
                        # OCR repeatedly confuses the small punctuation beside
                        # this field. Keep the words and let the image establish
                        # the uncorroborated enclosures around them.
                        text = text[:phone.end()] + " " + suffix.strip()[1:-1]
                        uncertain.append(phone.group())
                elif len(text) < 3 or not any(ch.isalpha() for ch in text):
                    continue
                domain = DOMAIN.search(text)
                if domain:
                    locks.append(domain.group())
                prefix.append(text)
                continue
            if role == "head" and HEADER.fullmatch(text):
                head = text
                continue
            if role == "condition":
                owner = _conditional_owner(text, raw)
                if owner is not None:
                    apply(owner, text)
                    conditionals.append(text)
                continue
            if role == "case":
                local = re.fullmatch(rf"(?i:(Processo|Autos|Inquérito))\s+[^\d]{{0,8}}({CASE})",text)
                if not local:
                    continue
                value = local[2]
                def case_match(line):
                    return line.casefold().startswith(local[1].casefold() + " ") and re.search(CASE+r"$",line) and _similar(line,text)
                match = _owner(original, case_match)
                if match:
                    i, prior = match
                    old = re.search(CASE + r"$", prior)[0]
                    if old != value:
                        aliases.append([old, value])
                    apply(i, re.sub(CASE+r"$",lambda _:value,prior))
                    cases.append(value)
                elif value not in raw:
                    raise ValueError("ocr_visual_source_requires_review")
                continue
            if role == "email" and EMAIL.fullmatch(text):
                match = _owner(original, lambda line: line.count("@")==1 and len(line.split())<=3
                               and _similar(line.replace(" ",""),text))
                value = text
            elif role == "url" and (link := LINK.search(text)):
                value = link.group()
                match = _owner(original, lambda line: (old := LINK.search(line)) and
                               old[0].split("/",3)[:3] == value.split("/",3)[:3]
                               and _similar(old[0],value) and line[:old.start()] == text[:link.start()]
                               and line[old.end():] == text[link.end():])
            elif role == "address" and ADDRESS.search(text):
                match = _owner(original, lambda line: _address_pair(line,text))
                value = text
            else:
                continue
            if match:
                i, prior = match
                apply(i, LINK.sub(lambda _: value, prior, count=1) if role=="url" else text)
                old = LINK.search(prior)[0] if role == "url" else prior
                if old != value:
                    aliases.append([old, value])
                locks.append(value)
            elif role in {"email", "url"} and value not in raw:
                raise ValueError("ocr_visual_source_requires_review")
    headers = []
    if head:
        h = HEADER.fullmatch(head)
        # A missing top line is admitted only when its two exact components
        # are independently printed in a unique adjacent labelled field pair.
        label = re.compile(r"(?i)^(?:Referência|Refer[.ª]|Ref[.ª])\b.*?:?\s+"+re.escape(h["ref"])+r"\s*$")
        links = [i for i in range(len(lines)-1) if lines[i].rstrip().endswith(h["case"]) and label.fullmatch(lines[i+1])]
        if cases == [h["case"]] and len(links) == 1:
            first = next((l for l in lines if l.strip()), "")
            if first == head and lines.count(head) == 1:
                headers.append([h["case"],h["ref"]])
            elif (sum(l.count(h["ref"]) for l in lines) == 1
                  and not re.search(r"\d+\s*[/\[]|\d{4,}",first)):
                lines.insert(0,head)
                headers.append([h["case"],h["ref"]])
        if not headers:
            raise ValueError("ocr_visual_source_requires_review")
    effective = "\n".join(prefix+lines)
    for old,_ in aliases:
        if any(old in text for _, seen in groups for text in seen):
            raise ValueError("ocr_visual_source_requires_review")
    # An OCR spelling also printed elsewhere is not a safe correction exemption.
    aliases = [pair for pair in aliases if pair[0] not in effective]
    return effective, {"headers":headers, "literals":list(dict.fromkeys(locks + cases)),
                       "aliases": aliases, "conditions": conditionals, "uncertain_punctuation": uncertain,
                       "supplemented_column": bool(prefix), "supplemented_contact": added_contact,
                       "mailing_labels":mailing, "phone_slots":phone_slots}


def _address_pair(old,new):
    return (ADDRESS.search(old) and ADDRESS.search(new) and
            re.split(r"\b(?:da|de|do)\b",old,1)==re.split(r"\b(?:da|de|do)\b",new,1)
            and _similar(old,new,.96))


def _condition_gap(rows, raw):
    """Locate two intact neighboring rows and only the attested grammatical changes."""
    before, printed, after = rows
    if (not 4 <= len(before.split()) <= 30 or not 4 <= len(after.split()) <= 30
            or not 5 <= len(printed.split()) <= 25 or not CONDITION.search(printed)):
        return None
    lines = [m for m in re.finditer(r"[^\r\n]+", raw) if m[0].strip()]
    trimmed = [m[0].strip(" \t") for m in lines]
    if trimmed.count(before) != 1 or trimmed.count(after) != 1:
        return None
    i = trimmed.index(before) + 1
    if i + 1 >= len(lines) or trimmed[i + 1] != after or trimmed.count(trimmed[i]) != 1:
        return None
    text = lines[i][0]
    old = list(re.finditer(r"\S+", text))
    new = printed.split()
    if (len(old) != len(new) or any(c not in " \t" and c.isspace() for c in text)):
        return None
    edits = [(m.start(), m.end(), m[0], word) for m, word in zip(old, new) if m[0] != word]
    pairs = [(a,b) for _,_,a,b in edits]
    if (pairs not in ([("e","se")], [("e","se"),("há","for")])
            or len(new) - len(edits) < 4):
        return None
    if len(edits) == 2:
        aux = next(i for i, m in enumerate(old) if m.start() == edits[1][0])
        if aux == 0 or old[aux-1][0] != "não" or new[aux-1] != "não":
            return None
    for start, end, _, word in reversed(edits):
        text = text[:start] + word + text[end:]
    return lines[i].start(), lines[i].end(), text


def _condition_gap_plans(lines, plan, raw):
    result = list(plan)
    owned = {i for _, indices in plan for i in indices}
    printed = [row["text"] for row in lines]
    for i in range(1, len(lines) - 1):
        middle = lines[i]["text"]
        if i in owned or not CONDITION.search(middle):
            continue
        rows = lines[i-1:i+2]
        if (_same_column(rows) and all(printed.count(row["text"]) == 1 for row in rows)
                and _condition_gap([row["text"] for row in rows], raw) is not None):
            result.append(("condition_gap", [i-1, i, i+1]))
            if len(result) > MAX_GROUPS:
                raise ValueError("ocr_visual_source_region_limit")
    return result


def _restore_condition_gaps(effective, obligations, coarse, regions, groups):
    for region, (role, rows) in zip(regions, groups):
        if role != "condition_gap":
            continue
        # _build rediscovered the same physical lines in both higher-resolution crops.
        if rows != [coarse["lines"][i]["text"] for i in region["coarse_lines"]]:
            raise ValueError("ocr_visual_source_requires_review")
        span = _condition_gap(rows, effective)
        if span is None:
            raise ValueError("ocr_visual_source_requires_review")
        start, end, replacement = span
        effective = effective[:start] + replacement + effective[end:]
        obligations["conditions"].append(rows[1])
    return effective


def _build(page, raw, number, digest, recognizer, saved=None, *, policy=POLICY):
    if (policy not in SUPPORTED_POLICIES or saved is not None
            and (type(saved) is not dict or saved.get("policy") != policy)):
        _fail()
    coarse = _scan(page,144,None,recognizer,None if saved is None else saved["coarse"])
    if policy in (POLICY_V2, POLICY_V3, POLICY_V4):
        from .ordinary_ocr_source_spans import plans, project
        plan = plans(coarse["lines"],raw,coarse["bounds"][2],page)
    else:
        plan = _plans(coarse["lines"],raw,coarse["bounds"][2],page)
    if policy in (POLICY_V3, POLICY_V4):
        from .ordinary_source_phone_punctuation import plans as punctuation_plans
        plan = punctuation_plans(coarse["lines"], plan)
    if policy == POLICY_V4:
        plan = _condition_gap_plans(coarse["lines"], plan, raw)
    if saved is not None and len(saved["regions"]) != len(plan):
        _fail()
    regions = []
    groups = []
    rescans = 0
    for j,(role,ids) in enumerate(plan):
        rows = [coarse["lines"][i] for i in ids]
        clip = _clip(page, rows)
        scans = [_scan(page,dpi,clip,recognizer,None if saved is None else saved["regions"][j]["scans"][k])
                 for k,dpi in enumerate((288,432))]
        stable = []
        detail = []
        for index, row in zip(ids, rows):
            a,b = (_read_line(row, scan) for scan in scans)
            if role == "side" and (not a or not b or a != b):
                # A small label can disappear when scanned beside a dense group.
                # Re-read its own printed location. Never borrow a neighbouring word.
                rescans += 1
                if rescans > 2:
                    raise ValueError("ocr_visual_source_requires_review")
                pair = [_scan(page,dpi,_clip(page,[row]),recognizer,
                              None if saved is None else saved["regions"][j]["detail"][len(detail)]["scans"][k])
                        for k,dpi in enumerate((288,432))]
                a,b = (_read_line(row, scan) for scan in pair)
                detail.append({"coarse_line":index,"scans":pair})
            if a and a == b:
                stable.append(a)
        if (role in {"side", "head", "contact", "flow_condition", "inline_condition", "mailing", "phone_qualifier", "condition_gap"}
                or policy in (POLICY_V2, POLICY_V3, POLICY_V4) and role in {"case", "address", "reference", "mailing_follow"}) and len(stable) != len(rows):
            raise ValueError("ocr_visual_source_requires_review")
        regions.append({"role":role,"coarse_lines":ids,"scans":scans,"detail":detail})
        groups.append((role,stable))
    projection = None
    omission = None
    project_input = raw
    if policy == POLICY_V4:
        from .ordinary_ocr_tracking_omission import restore as restore_tracking
        project_input, omission = restore_tracking(raw, coarse, regions, groups)
    if policy in (POLICY_V2, POLICY_V3, POLICY_V4):
        virtual, projection = project(project_input, groups)
        effective, obligations = _derive(virtual,groups)
    else:
        effective, obligations = _derive(raw,groups)
    if policy in (POLICY_V3, POLICY_V4):
        from .ordinary_source_phone_punctuation import restore
        effective, obligations = restore(effective, obligations, coarse, regions, groups)
    if policy == POLICY_V4:
        effective = _restore_condition_gaps(effective, obligations, coarse, regions, groups)
    value = {"policy":policy,"page":number,"pdf_sha256":digest,"raw_sha256":_sha(raw),
             "coarse":coarse,"regions":regions,"effective_sha256":_sha(effective),"obligations":obligations}
    if omission is not None:
        value["tracking_omission"] = omission
        obligations["tracking_omission_alias"] = omission["raw_spelling"]
        for old in (omission["raw_spelling"], omission["raw_spelling"].replace(" ", "")):
            obligations["aliases"].append([old, omission["printed_code"]])
    if projection is not None:
        value["raw_span_projection"] = projection
    if len(_encode(value))>MAX_BYTES or (saved is not None and value!=saved):
        _fail()
    return effective, value


def _path(run_dir,number):
    root=Path(run_dir)
    folder=root/"ocr_transport"/f"page_{number:04d}"
    path=folder/"visual_source.json"
    if (root.is_symlink() or folder.parent.is_symlink() or folder.is_symlink() or path.is_symlink()
            or folder.resolve().parent.parent!=root.resolve() or not folder.is_dir()):
        _fail()
    return path


def acquire(pdf_path, number, raw, fingerprint, run_dir, *, policy=POLICY):
    if policy not in SUPPORTED_POLICIES:
        _fail()
    from .ordinary_windows_ocr_worker import recognize_png
    if len(raw)>MAX_CHARS:
        return raw,None
    doc=_open_page(pdf_path,number)
    if doc is None:
        return raw,None
    path=_path(run_dir,number)
    try:
        if path.exists():
            return replay(pdf_path,number,raw,fingerprint,run_dir,policy=policy)
        deadline = time.monotonic() + 45.
        def bounded_recognize(png):
            if time.monotonic() > deadline:
                raise ValueError("ocr_visual_source_timeout")
            return recognize_png(png)
        effective,value=_build(doc[number-1],raw,number,fingerprint,bounded_recognize,policy=policy)
        _publish(path, _encode(value), staging_dir=path.parent.parent)
        return effective,{"sha256":_sha(_encode(value)), "obligations":value["obligations"]}
    finally:
        doc.close()


def _publish(path, encoded, *, staging_dir=None):
    # The paid OCR envelope owns its page directory. Keep even an interrupted
    # staging write outside that directory, on the same output volume.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=staging_dir or path.parent, prefix=".visual-", delete=False) as file:
            temporary = Path(file.name)
            file.write(encoded)
            file.flush()
            os.fsync(file.fileno())
        try:
            if os.name=="nt":
                os.rename(temporary,path)
            else:
                os.link(temporary,path)
        except FileExistsError:
            if path.is_symlink() or path.stat().st_size != len(encoded) or path.read_bytes() != encoded:
                _fail()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_ocr_reentry(pdf_path, number, raw, fingerprint, run_dir, reference, *, policy=POLICY):
    """A completed local proof belongs to this exact settled OCR answer and source page."""
    if policy not in SUPPORTED_POLICIES:
        _fail()
    path = _path(run_dir, number)
    capture = Path(run_dir)/"semantic_source"/f"page_{number:04d}.json"
    if capture.is_symlink() or capture.parent.is_symlink():
        _fail()
    if not path.exists() and not capture.exists():
        return
    data = None
    if capture.exists():
        if not capture.is_file() or capture.stat().st_size>48*1024*1024:
            _fail()
        data=json.loads(capture.read_bytes())
        if type(data) is not dict or data.get("pdf_sha256")!=fingerprint or data.get("page_number")!=number:
            _fail()
    if not path.exists():
        if "ocr_visual_source" in data or eligible_page(pdf_path,number,raw):
            _fail()
        return
    effective, proof = replay(pdf_path,number,raw,fingerprint,run_dir,policy=policy)
    if data is not None:
        acquisition = {"reference":reference, "selected_source_sha256":_sha(effective),
                       "composition":"verified_source_slots_v1"}
        if (data.get("original_source_text")!=effective or data.get("ocr_visual_source")!=proof
                or data.get("ocr_text_acquisition")!=acquisition):
            _fail()


def replay(pdf_path,number,raw,fingerprint,run_dir, *, policy=POLICY):
    path=_path(run_dir,number)
    if not path.is_file() or path.stat().st_size>MAX_BYTES:
        _fail()
    encoded=path.read_bytes()
    from .checkpoint import sha256_of_file
    if sha256_of_file(Path(pdf_path)) != fingerprint:
        _fail()
    text, proof = _replay(str(pdf_path), number, raw, fingerprint, encoded, policy)
    return text, json.loads(proof)


@lru_cache(maxsize=4)
def _replay(pdf_path, number, raw, fingerprint, encoded, policy=POLICY):
    try:
        saved=json.loads(encoded)
        doc=_open_page(pdf_path,number)
        if doc is None:
            _fail()
        with doc:
            effective,value=_build(doc[number-1],raw,number,fingerprint,None,saved,policy=policy)
        if _encode(value)!=encoded:
            _fail()
        return effective, _encode({"sha256":_sha(encoded),"obligations":value["obligations"]})
    except (TypeError, KeyError, IndexError, OverflowError, UnicodeError) as exc:
        raise ValueError("ocr_visual_source_evidence_changed") from exc


@lru_cache(maxsize=4)
def _image_digest(pdf_path, fingerprint, number):
    from .config import IMAGE_MAX_DATA_URL_BYTES_AR
    from .source_document import render_source_page_image_data_url
    image = render_source_page_image_data_url(Path(pdf_path), number-1, max_data_url_bytes=IMAGE_MAX_DATA_URL_BYTES_AR)
    return _sha(image.data_url)


def image_matches(pdf_path, fingerprint, number, primary, visual):
    return (type(primary) is str and primary == visual
            and _sha(primary) == _image_digest(str(pdf_path), fingerprint, number))


def prepared_source(text, witness):
    """Protect complete witnessed owners before the standard tokenizer handles other spans."""
    if not witness:
        return text
    for value in witness["obligations"]["literals"]:
        if value and (ADDRESS.search(value) or PHONE.fullmatch(value) or DOMAIN.fullmatch(value)
                      or CLOCK.fullmatch(value) or TRACKING.fullmatch(value) or MAILING_REF.fullmatch(value)):
            text = re.sub(r"(?<![\w\[])"+re.escape(value)+r"(?![\w\]])",lambda _: "[["+value+"]]",text)
    return text


def guidance(witness):
    if not witness or not any(witness["obligations"].values()):
        return ""
    evidence = witness["obligations"]
    instructions = ["\nSource-pixel cross-check: preserve each occurrence in its own printed field."]
    if evidence["headers"]:
        instructions.append("Preserve the compact header's printed [reference] and the separate labelled "
                            "reference's own punctuation; retain every other printed enclosure in place.")
    if evidence["supplemented_column"]:
        instructions.append("Translate the recovered sidebar once, in its own column; keep its labels, "
                            "links, instructions and form choices connected to their owners.")
    if evidence["supplemented_contact"]:
        instructions.append("Keep the telephone, office hours and email with their witnessed postal contact block.")
    if evidence["mailing_labels"]:
        instructions.append("Retain both human-readable mailing identifiers beside their barcode and inspect "
                            "the original image for its postal mark, addressee and address.")
    if evidence["conditions"]:
        instructions.append("Preserve the scope of the source conditional clauses listed below.")
    if evidence["aliases"]:
        instructions.append("The alias pairs list a rejected OCR reading followed by its printed replacement.")
    if evidence["uncertain_punctuation"]:
        instructions.append("Read the punctuation adjacent to the listed uncertain fields from the image.")
    if evidence.get("printed_phone_qualifiers"):
        instructions.append("Keep each witnessed telephone qualifier and its punctuation with its telephone. "
                            "A balanced punctuation normalization may preserve the same qualifier; "
                            "never move a closing mark to another field.")
    # Keep the same wire order as fresh V1 captures, including on replay from
    # the independently canonical (sorted-key) evidence encoding.
    fields=("headers","literals","aliases","conditions","uncertain_punctuation",
            "supplemented_column","supplemented_contact","mailing_labels","phone_slots")
    instructions.append(json.dumps({key:evidence[key] for key in fields if evidence[key]},ensure_ascii=False))
    if evidence.get("printed_phone_qualifiers"):
        instructions.append(json.dumps({"printed_phone_qualifiers":[{"phone":row["phone"],
            "source_row":row["source_row"]} for row in evidence["printed_phone_qualifiers"]]},ensure_ascii=False))
    return " ".join(instructions)


def semantic_guard_view(candidate, source, witness):
    """Read one witnessed touching header enclosure as the evaluator will.

    This is a local guard view, not a new candidate or source authority. The
    ordinary evaluator still owns normalization and selection of the unchanged
    raw correction. Only its existing invisible bracket-token repair is used.
    """
    if (not witness or not isinstance(candidate, str) or not isinstance(source, str)
            or len(candidate) + len(source) > 2 * MAX_CHARS):
        return candidate
    from .ar_source_fields import _view
    from .output_normalize import LRI, PDI, repair_bracket_wrapped_ar_tokens
    if _view(candidate) is not None:
        return candidate
    headers = witness.get("obligations", {}).get("headers", [])
    if len(headers) != 1 or len(headers[0]) != 2:
        return candidate
    case, ref = headers[0]
    source_view = _view(source)
    printed = case + " [" + ref + "]"
    if (source_view is None or not HEADER.fullmatch(printed)
            or next((line for line in source_view[0].splitlines() if line.strip()), "") != printed):
        return candidate
    touching = "[[[" + ref + "]]]"
    first_line = next((line for line in candidate.splitlines() if line.strip()), "")
    if touching not in first_line or candidate.count(touching) != 1:
        return candidate
    prepared, count = repair_bracket_wrapped_ar_tokens(candidate)
    expected = candidate.replace(touching, "[" + LRI + "[[" + ref + "]]" + PDI + "]", 1)
    if count != 1 or prepared != expected or violation(prepared, source, witness) is not None:
        return candidate
    return prepared


def violation(candidate, source, witness):
    if not witness:
        return None
    from .ar_source_fields import _view
    from .arabic_pre_tokenize import extract_locked_tokens
    view = _view(candidate)
    if view is None:
        return "ocr_visual_source_wrapper"
    visible, _, slots = view
    values = [t[2] for t in slots]
    required = extract_locked_tokens(source)
    for value in witness["obligations"]["literals"]:
        if value in required and values.count(value)!=required.count(value):
            return "ocr_visual_source_literal"
    for case, ref in witness["obligations"]["headers"]:
        header_line = next((l for l in visible.splitlines() if l.strip()), "")
        if (values.count(case)!=required.count(case) or values.count(ref)!=required.count(ref)
                or not re.fullmatch(re.escape(case)+r"[ \t]+\["+re.escape(ref)+r"\]",header_line)
                or visible.count("["+ref+"]")!=1):
            return "ocr_visual_source_header"
        # A later printed field carries the bare reference. Disallow displaced
        # or mismatched single bracket fragments as well as a second pair.
        for start,end,value,*_ in slots:
            if value == ref and start > len(header_line) and (
                    visible[:start].rstrip().endswith("[") or visible[end:].lstrip().startswith("]")):
                return "ocr_visual_source_header"
    obsolete_spelling = witness["obligations"].get("tracking_omission_alias")
    if obsolete_spelling:
        from .ordinary_ocr_tracking_omission import obsolete
        if obsolete(visible, obsolete_spelling):
            return "ocr_visual_source_obsolete_literal"
    if any(old in visible for old, _ in witness["obligations"]["aliases"]):
        return "ocr_visual_source_obsolete_literal"
    if witness["obligations"].get("printed_phone_qualifiers"):
        from .ordinary_source_phone_punctuation import violation as phone_violation
        if defect := phone_violation(_view(source), view, witness["obligations"]):
            return defect
    return None


def checked(result, source, witness):
    if result.ok and witness and (defect := violation(result.normalized_text,source,witness)):
        from dataclasses import replace
        return replace(result, ok=False, validator_failed=True, defect_reason=defect,
                       ar_violation_kind="expected_token_mismatch")
    return result


def compliance_baseline(baseline, candidate, witness, *, source=""):
    """Credit only a measured replacement in the same literal slot and neighbourhood."""
    from .ar_source_fields import _view
    if not witness or not isinstance(baseline, str) or not isinstance(candidate, str):
        return baseline
    original = _view(baseline)
    corrected = _view(candidate)
    if original is None or corrected is None:
        return baseline
    before = [slot[2] for slot in original[2]]
    after = [slot[2] for slot in corrected[2]]
    if len(before) != len(after) or len(before)<2:
        return baseline
    changes = []
    replacements=list(witness["obligations"]["aliases"])
    for left,value,right in witness["obligations"].get("phone_slots",()):
        if not source or before.count(left)!=1 or before.count(right)!=1:
            continue
        i=before.index(left)+1
        if i+1>=len(before) or before[i+1]!=right or after[i]!=value:
            continue
        old=before[i]
        if (PHONE_CONTIGUOUS.fullmatch(old) and old not in source
                and sum(a!=b for a,b in zip(old,value))==1):
            replacements.append((old,value))
    for old, new in replacements:
        if before.count(old)!=1 or after.count(new)!=1 or new in before or old in after:
            continue
        i = before.index(old)
        if (after[i]!=new or before[max(i-1,0):i]!=after[max(i-1,0):i]
                or before[i+1:i+2]!=after[i+1:i+2]):
            continue
        _,_,_,a,b=original[2][i]
        offset=baseline.index(old,a,b)
        changes.append((offset, old, new))
    for offset,old,new in sorted(changes,reverse=True):
        baseline=baseline[:offset]+new+baseline[offset+len(old):]
    return baseline

