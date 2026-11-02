"""Versioned whole terminal-period ownership; V1 source and mechanics stay exact."""
from copy import deepcopy
import re

from . import ordinary_labeled_folio_direction as v1
from . import ordinary_folio_bridges_v4 as bridges
from . import saved_docx_layout as model

KEY, LEDGER, W = v1.KEY, v1.LEDGER, model.W
VERSION = "source_owned_labeled_fraction_ltr_v2"
_CORE = v1._CORE | {"terminal_suffix"}
_FIELDS = v1._FIELDS | {"terminal_suffix"}
_NUMBER = bridges._NUMBER
_FORMULA = re.compile(rf"(?:الصفحة|صفحة|ص\.) +(?P<formula>(?P<numerator>{_NUMBER})(?P<separator> +\u200e/\u200e +| */ *)(?P<denominator>{_NUMBER}))(?P<suffix> *\. *)\Z")
occupied, record, apply, verified_copy = v1.occupied, v1.record, v1.apply, v1.verified_copy


def derive(paragraph, before_break_removal, row):
    # Bound both public entrypoints before new inventory or cloning.
    if (len(paragraph.findall(W + "r")) > bridges.MAX_RUNS
            or len(before_break_removal.findall(W + "r")) > bridges.MAX_RUNS
            or len(row["text"]) > bridges.MAX_TEXT + 1):
        return None
    original = v1.derive(paragraph, before_break_removal, row)
    if original is not None:
        return {**original, "terminal_suffix": None}
    return _period_derive(paragraph, before_break_removal, row)


def _period_derive(paragraph, before_break_removal, row):
    """Prove a complete closed representation against its unchanged owned baseline."""
    if (len(paragraph.findall(W + "r")) > bridges.MAX_RUNS
            or len(before_break_removal.findall(W + "r")) > bridges.MAX_RUNS):
        return None
    from .ordinary_source_layout import _inline_folio_run_inventory
    inventory = _inline_folio_run_inventory(before_break_removal, row)
    if inventory is None:
        return None
    text, offsets = inventory
    if len(text) > bridges.MAX_TEXT:
        return None
    match = _FORMULA.fullmatch(text)
    if match is None:
        return None
    expected = deepcopy(before_break_removal)
    for br in list(expected.iter(W + "br")):
        br.getparent().remove(br)
    if model._c14n(expected) != model._c14n(paragraph):
        return None
    if any(n.tag in {W + "pPrChange", W + "rPrChange", W + "ins", W + "del"}
           for n in before_break_removal.iter()):
        return None
    runs = paragraph.findall(W + "r")
    original = before_break_removal.findall(W + "r")
    for index, left, right, run, value in offsets:
        if len(run.findall(W + "rPr/" + W + "rtl")) > 1:
            return None
        if left == right:
            children = [c for c in original[index] if c.tag != W + "rPr"]
            if (index != len(runs) - 1 or len(children) != 1 or children[0].tag != W + "br"
                    or dict(children[0].attrib) != {W + "type": "page"}):
                return None
    for name in ("numerator", "denominator"):
        left, right = match.span(name)
        owners = [r for r in offsets if r[1] < right and r[2] > left]
        if len(owners) != 1 or owners[0][1:3] != (left, right):
            return None
        rtl = bridges._rtl(runs[owners[0][0]])
        if rtl is None or rtl.get(W + "val") != "0":
            return None
    left, right = match.span("separator")
    owners = [r for r in offsets if r[1] < right and r[2] > left]
    if (not owners or owners[0][1] != left or owners[-1][2] != right
            or any(a[2] != b[1] for a, b in zip(owners, owners[1:]))):
        return None
    protected = "\u200e" in match["separator"]
    slash_count = 0
    changes = []
    for index, start, end, _, value in owners:
        rtl = bridges._rtl(runs[index])
        if not value or rtl is None:
            return None
        if protected and value == "\u200e/\u200e":
            if rtl.get(W + "val") != "0":
                return None
            slash_count += 1
            continue
        if protected and set(value) != {" "} or not protected and not set(value) <= {" ", "/"}:
            return None
        slash_count += value.count("/")
        if rtl.get(W + "val") == "1":
            changes.append({"run_index": index, "start": start, "end": end, "before_rtl": 1, "after_rtl": 0})
    if slash_count != 1 or not changes:
        return None
    suffix_start, suffix_end = match.span("suffix")
    suffix_owners = [r for r in offsets if r[1] < suffix_end and r[2] > suffix_start]
    if (not suffix_owners or suffix_owners[0][1] != suffix_start or suffix_owners[-1][2] != suffix_end
            or any(a[2] != b[1] for a, b in zip(suffix_owners, suffix_owners[1:]))):
        return None
    suffix_runs = []
    for index, left, right, _, value in suffix_owners:
        rtl = bridges._rtl(runs[index])
        if not value or not set(value) <= {" ", "."} or rtl is None:
            return None
        suffix_runs.append({"run_index": index, "start": left, "end": right,
                            "original_rtl": int(rtl.get(W + "val"))})
    suffix = {"start": suffix_start, "end": suffix_end,
        "literal_sha256": model._sha(text[suffix_start:suffix_end].encode()), "runs": suffix_runs}
    start, end = match.span("formula")
    return {"start": start, "end": end, "literal_sha256": model._sha(text[start:end].encode()),
        "bridge_runs": changes, "representation": "protected_slash" if protected else "plain_slash", "terminal_suffix": suffix}


def span(node, row):
    if len(node.findall(W + "r")) > bridges.MAX_RUNS or len(row["text"]) > bridges.MAX_TEXT + 1:
        return None
    scratch = deepcopy(node)
    for br in list(scratch.iter(W + "br")):
        br.getparent().remove(br)
    return derive(scratch, node, row)


def retained(nodes, mapped, rows, choices, owners, selected_pages, layout, evidence, plan, target_lang):
    if target_lang != "AR":
        return []
    promoted = {i for footer in plan["source_footers"] for i in footer["paragraph_ids"]}
    blocked = promoted | occupied(plan)
    result = []
    for identifier, row in rows.items():
        items = [a for a in layout if a["kind"] == "source_footer" and identifier in a["paragraph_ids"]]
        node, mapping = nodes[identifier], mapped[identifier]
        if (len(items) != 1 or identifier in blocked or choices[identifier]["role"] != "source_folio"
                or mapping.get("parts") or mapping.get("part_uri", "word/document.xml") != "word/document.xml"
                or node.getparent() is None or node.getparent().tag != W + "body"):
            continue
        page = items[0]["source_page_number"]
        if type(page) is not int or page not in selected_pages or [p for p, ids in owners.items() if identifier in ids] != [page]:
            continue
        core = span(node, row)
        if core is not None:
            result.append(record(identifier, page, "retained_body", items[0], evidence, core))
    return result


def checked_plan(plan, mode, rows, owners, selected_pages):
    if mode != VERSION or plan.get(KEY) != VERSION:
        model._fail("source_labeled_folio_direction_version")
    records = plan.get(LEDGER)
    if type(records) is not list or len(records) > len(rows):
        model._fail("source_labeled_folio_direction_delta")
    if any(type(r) is not dict or set(r) != _FIELDS for r in records):
        model._fail("source_labeled_folio_direction_delta")
    # Typed validation view only, never a rewritten serialized policy/witness.
    view = {**plan, KEY: v1.VERSION,
        LEDGER: [{k: value for k, value in r.items() if k != "terminal_suffix"} for r in records]}
    v1.checked_plan(view, v1.VERSION, rows, owners, selected_pages)
    for r in records:
        row = rows[r["paragraph_id"]]
        terminal = row["tokens"] and row["tokens"][-1]["kind"] == "page_break"
        text = row["text"][:-1] if terminal and row["text"].endswith("\f") else row["text"]
        suffix = r["terminal_suffix"]
        if suffix is None:
            match = v1._FORMULA.fullmatch(text)
            if match is None or match.span("formula") != (r["start"], r["end"]):
                model._fail("source_labeled_folio_direction_delta")
            continue
        if (type(suffix) is not dict or set(suffix) != {"start", "end", "literal_sha256", "runs"}
                or type(suffix["start"]) is not int or type(suffix["end"]) is not int
                or not r["end"] == suffix["start"] < suffix["end"] == len(text)
                or type(suffix["literal_sha256"]) is not str
                or suffix["literal_sha256"] != model._sha(text[suffix["start"]:suffix["end"]].encode())
                or type(suffix["runs"]) is not list or not 1 <= len(suffix["runs"]) <= bridges.MAX_RUNS):
            model._fail("source_labeled_folio_direction_delta")
        match = _FORMULA.fullmatch(text)
        if (match is None or match.span("formula") != (r["start"], r["end"])
                or match.span("suffix") != (suffix["start"], suffix["end"])):
            model._fail("source_labeled_folio_direction_delta")
        last_index, offset = None, suffix["start"]
        changed = {c["run_index"] for c in r["bridge_runs"]}
        for item in suffix["runs"]:
            if (type(item) is not dict or set(item) != {"run_index", "start", "end", "original_rtl"}
                    or any(type(value) is not int for value in item.values())
                    or not 0 <= item["run_index"] < bridges.MAX_RUNS or item["run_index"] in changed
                    or last_index is not None and item["run_index"] != last_index + 1
                    or item["original_rtl"] not in {0, 1}
                    or not item["start"] == offset < item["end"] <= suffix["end"]):
                model._fail("source_labeled_folio_direction_delta")
            last_index, offset = item["run_index"], item["end"]
        if offset != suffix["end"]:
            model._fail("source_labeled_folio_direction_delta")
    return {r["paragraph_id"]: r for r in records}
