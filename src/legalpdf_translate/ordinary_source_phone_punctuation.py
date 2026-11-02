"""Source-owned punctuation for a corroborated printed telephone qualifier.

This is a source transcription and a narrow target occurrence guard. It never
edits a translation or exempts an unrelated bracket from normal validation.
"""
from __future__ import annotations

import re

KEY = "printed_phone_qualifiers"
MAX_ROWS = 8
MAX_ROW_CHARS = 180


def _fail():
    raise ValueError("ocr_visual_source_requires_review")


def _qualifier(value):
    return (0 < len(value) <= 120 and any(c.isalpha() for c in value)
            and not any(c.isdigit() or c in "()[]{}（）/\\\n\r" for c in value))


def _unmatched_closes(text):
    stack, closes = [], []
    matching = {")": "(", "]": "[", "}": "{"}
    enumerators = {m.end()-1 for m in re.finditer(r"(?m)^[ \t]*(?:\d+|[^\W\d_])\)", text)}
    for index, char in enumerate(text):
        if char in "([{":
            stack.append(char)
        elif char in matching:
            if char == ")" and not stack and index in enumerators:
                continue
            if stack and stack[-1] == matching[char]:
                stack.pop()
            elif char == ")":
                closes.append(index)
    return closes


def plans(lines, existing):
    """Inspect the same printed slot even when API OCR retained the sidebar."""
    from . import ordinary_ocr_visual_source as visual
    result=list(existing)
    for index,row in enumerate(lines):
        found=visual.PHONE.match(row["text"])
        suffix=row["text"][found.end():].strip() if found else ""
        if (found and len(row["text"])<=MAX_ROW_CHARS and _qualifier(suffix.strip(" /()（）"))
                and not any(index in ids and role=="side" for role,ids in existing)):
            result.append(("phone_qualifier",[index]))
    if len(result)>visual.MAX_GROUPS:
        _fail()
    return result


def restore(effective, obligations, coarse, regions, groups):
    """Retain a source row only after the ordinary two-scale reader proves it."""
    from . import ordinary_ocr_visual_source as visual
    result = dict(obligations)
    result[KEY] = []
    uncertain = obligations["uncertain_punctuation"]
    phones = [found.group() for role,rows in groups if role in {"side","phone_qualifier"}
              for row in rows if (found:=visual.PHONE.match(row))
              and row[found.end():].strip().startswith("/")]
    if len(phones) > MAX_ROWS:
        _fail()
    result["literals"]=list(obligations["literals"])
    for phone in phones:
        matches = []
        for region_index, ((role, rows), region) in enumerate(zip(groups, regions)):
            if role not in {"side","phone_qualifier"}:
                continue
            for index, row in enumerate(rows):
                found = visual.PHONE.search(row)
                if found and found.group() == phone:
                    matches.append((region_index, index, row, found, region))
        if len(matches) != 1 or phones.count(phone) != 1:
            _fail()
        region_index, row_index, row, found, region = matches[0]
        suffix = row[found.end():].strip()
        # This capability does not infer a missing opening mark. Other
        # punctuation shapes retain the historical uncertain-source route.
        if (len(row) > MAX_ROW_CHARS or not suffix.startswith("/") or not suffix.endswith(")")
                or not _qualifier(suffix[1:-1]) or found.start() != 0):
            continue
        digits_pattern=r"\s*".join(map(re.escape,re.sub(r"\s+","",phone)))
        phone_pattern=r"(?<!\w)"+digits_pattern+r"(?!\w)"
        if len(list(re.finditer(phone_pattern,"\n".join(r["text"] for r in coarse["lines"])))) != 1:
            _fail()
        source_index = region["coarse_lines"][row_index]
        source_row = coarse["lines"][source_index]
        detail = [r for r in region["detail"] if r["coarse_line"] == source_index]
        scans = detail[0]["scans"] if len(detail) == 1 else region["scans"]
        if (len(detail) > 1 or [s["dpi"] for s in scans] != [288,432]
                or any(visual._read_line(source_row, scan) != row for scan in scans)):
            _fail()
        word_pattern=lambda value:r"\s+".join(map(re.escape,value.split()))
        pattern=(r"(?<!\S)"+digits_pattern+r"\s*(?:/|\(|（)?\s*"
                 +word_pattern(suffix[1:-1])+r"(?:\)|）)?(?!\S)")
        owners=list(re.finditer(pattern,effective))
        if len(owners)!=1 or len(list(re.finditer(phone_pattern,effective)))!=1:
            _fail()
        owner=owners[0]
        proposed=(effective[:owner.start()].rstrip()+"\n"+row+"\n"+effective[owner.end():].lstrip()).strip()
        proposed_obligations=dict(result)
        proposed_obligations["literals"]=result["literals"]+([] if phone in result["literals"] else [phone])
        # Source-owned neighbouring literals keep the telephone with its field
        # group. No location authority is inferred from a globally unique digit.
        from .ar_source_fields import _view
        from .arabic_pre_tokenize import pretokenize_arabic_source
        prepared=pretokenize_arabic_source(visual.prepared_source(proposed,{"obligations":proposed_obligations}),
                                          source_field_policy="baseline_label_value_v1")
        view=_view(prepared)
        if view is None:
            _fail()
        values=[slot[2] for slot in view[2]]
        if values.count(phone)!=1:
            _fail()
        ordinal=values.index(phone)
        row_start=view[0].index(row)
        row_end=row_start+len(row)
        if any(slot[2]!=phone and row_start<=slot[0]<row_end for slot in view[2]):
            continue
        left=[value for value in values[:ordinal] if values.count(value)==1]
        right=[value for value in values[ordinal+1:] if values.count(value)==1]
        if not left and not right:
            continue
        effective=proposed
        result["literals"]=proposed_obligations["literals"]
        closing = effective.index(row) + len(row)-1
        if closing not in _unmatched_closes(effective):
            _fail()
        result[KEY].append({"phone":phone,"source_row":row,"region":region_index,
                            "coarse_line":source_index,"left":left[-1] if left else None,
                            "right":right[0] if right else None})
    restored = {r["phone"] for r in result[KEY]}
    result["uncertain_punctuation"] = [p for p in uncertain if p not in restored]
    return effective, result


def violation(source_view, candidate_view, obligations):
    """Credit an unmatched close only inside its matching telephone field."""
    rows = obligations.get(KEY, ())
    if not rows:
        return None
    defect = "ocr_visual_source_phone_punctuation"
    if type(rows) is not list or len(rows) > MAX_ROWS or source_view is None or candidate_view is None:
        return defect
    source, _, source_slots = source_view
    target, _, target_slots = candidate_view
    source_values = [s[2] for s in source_slots]
    target_values = [s[2] for s in target_slots]
    source_closes, target_closes = _unmatched_closes(source), _unmatched_closes(target)
    owned_source, owned_target = set(), set()
    for row in rows:
        if type(row) is not dict or set(row) != {"phone","source_row","region","coarse_line","left","right"}:
            return defect
        phone, printed = row["phone"], row["source_row"]
        if (not isinstance(phone,str) or not isinstance(printed,str) or len(printed)>MAX_ROW_CHARS
                or source.splitlines().count(printed)!=1 or source_values.count(phone)!=1
                or target_values.count(phone)!=1):
            return defect
        start = source.index(printed)
        closing = start+len(printed)-1
        if closing not in source_closes or closing in owned_source:
            return defect
        owned_source.add(closing)
        si, ti = source_values.index(phone), target_values.index(phone)
        for name, direction in (("left",-1),("right",1)):
            anchor=row[name]
            if anchor is None:
                continue
            if (source_values.count(anchor)!=1 or target_values.count(anchor)!=1
                    or (source_values.index(anchor)-si)*direction<=0
                    or (target_values.index(anchor)-ti)*direction<=0):
                return defect
        a,b,*_=target_slots[ti]
        end=target.find("\n",b)
        if end<0:end=len(target)
        if any(other[2]!=phone and b<=other[0]<end for other in target_slots):
            return defect
        tail=target[b:end].strip()
        # A balanced normalization is valid. Only the printed asymmetric form
        # can contribute a source-backed unmatched closing mark.
        if tail.startswith("/") and tail.endswith(")") and _qualifier(tail[1:-1]):
            close=end-len(target[b:end])+len(target[b:end].rstrip())-1
            if close not in target_closes:
                return defect
            owned_target.add(close)
        elif ((tail.startswith("(") and tail.endswith(")") or tail.startswith("（") and tail.endswith("）"))
              and _qualifier(tail[1:-1])):
            pass
        else:
            return defect
    # Restoring this source field cannot license a different target field.
    if len(target_closes)-len(owned_target)>len(source_closes)-len(owned_source):
        return defect
    return None
