"""Closed source-footer bridge attributes; no text or source-proof changes."""
from copy import deepcopy
import re

from . import saved_docx_layout as model

VERSION = "numeric_run_ltr_v4"
LEDGER = "folio_bridge_direction_spans"
MAX_RUNS = 32
MAX_TEXT = 80
W = model.W
_DIGITS = r"[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}"
_NUMBER = rf"(?:\u200e{_DIGITS}\u200e|{_DIGITS})"
_FORMULA = re.compile(rf"(?:الصفحة|صفحة) +(?P<formula>(?P<numerator>{_NUMBER}) +(?P<separator>\u200e/\u200e) +(?P<denominator>{_NUMBER})) *\Z")


def _rtl(run):
    props = run.findall(W + "rPr")
    if len(props) != 1:
        return None
    values = props[0].findall(W + "rtl")
    if (len(values) != 1 or set(values[0].attrib) != {W + "val"}
            or len(values[0]) or values[0].text
            or values[0].get(W + "val") not in {"0", "1"}):
        return None
    return values[0]


def derive(paragraph, before_break_removal, row):
    """Return only changed whole-space bridges after the existing owned break step."""
    # Charge the total direct run count before any detailed new-branch inventory.
    if (len(paragraph.findall(W + "r")) > MAX_RUNS
            or len(before_break_removal.findall(W + "r")) > MAX_RUNS):
        return None
    from .ordinary_source_layout import _inline_folio_run_inventory
    inventory = _inline_folio_run_inventory(before_break_removal, row)
    if inventory is None:
        return None
    text, offsets = inventory
    if len(text) > MAX_TEXT:
        return None
    match = _FORMULA.fullmatch(text)
    if match is None:
        return None
    expected = deepcopy(before_break_removal)
    for br in list(expected.iter(W + "br")):
        br.getparent().remove(br)
    if model._c14n(expected) != model._c14n(paragraph):
        return None
    if any(node.tag in {W + "pPrChange", W + "rPrChange", W + "ins", W + "del"}
           for node in before_break_removal.iter()):
        return None
    runs = paragraph.findall(W + "r")
    original_runs = before_break_removal.findall(W + "r")
    for index, left, right, run, value in offsets:
        props = run.find(W + "rPr")
        if props is not None and len(props.findall(W + "rtl")) > 1:
            return None
        if left == right:
            # Only the exact previously owned terminal break may leave residue.
            children = [child for child in original_runs[index] if child.tag != W + "rPr"]
            if (index != len(runs) - 1 or len(children) != 1 or children[0].tag != W + "br"
                    or dict(children[0].attrib) != {W + "type": "page"}):
                return None
    carriers = []
    for name in ("numerator", "separator", "denominator"):
        left, right = match.span(name)
        overlapping = [item for item in offsets if item[1] < right and item[2] > left]
        if len(overlapping) != 1 or overlapping[0][1:3] != (left, right):
            return None
        carrier = overlapping[0]
        direction = _rtl(runs[carrier[0]])
        if direction is None or direction.get(W + "val") != "0":
            return None
        carriers.append(carrier)
    changes = []
    for first, last in zip(carriers, carriers[1:]):
        left, right = first[2], last[1]
        bridges = [item for item in offsets if item[1] < right and item[2] > left]
        if (not bridges or bridges[0][1] != left or bridges[-1][2] != right
                or any(a[2] != b[1] for a, b in zip(bridges, bridges[1:]))):
            return None
        for index, start, end, _, value in bridges:
            direction = _rtl(runs[index])
            if not value or set(value) != {" "} or direction is None:
                return None
            if direction.get(W + "val") == "1":
                changes.append({"run_index": index, "start": start, "end": end,
                                "before_rtl": 1, "after_rtl": 0})
    if not changes:
        return None
    start, end = match.span("formula")
    return {"start": start, "end": end, "literal_sha256": model._sha(text[start:end].encode("utf-8")),
            "bridge_runs": changes}


def apply(paragraph, record):
    runs = paragraph.findall(W + "r")
    for change in record["bridge_runs"]:
        direction = _rtl(runs[change["run_index"]])
        if direction is None or direction.get(W + "val") != "1":
            model._fail("source_folio_bridge_direction_delta")
        direction.set(W + "val", "0")


def checked_plan(plan, mode, rows, owners, selected_pages):
    if mode != VERSION:
        if LEDGER in plan:
            model._fail("source_folio_bridge_direction_version")
        return {}
    records = plan.get(LEDGER)
    if type(records) is not list or len(records) > len(rows):
        model._fail("source_folio_bridge_direction_delta")
    order = {identifier: index for index, identifier in enumerate(rows)}
    by_id, previous = {}, -1
    for record in records:
        if (type(record) is not dict or set(record) != {"paragraph_id", "source_page_number", "start", "end", "literal_sha256", "bridge_runs"}
                or type(record["paragraph_id"]) is not str or record["paragraph_id"] not in rows
                or type(record["source_page_number"]) is not int or record["source_page_number"] not in selected_pages
                or [page for page, ids in owners.items() if record["paragraph_id"] in ids] != [record["source_page_number"]]
                or type(record["start"]) is not int or type(record["end"]) is not int
                or not 0 <= record["start"] < record["end"] <= len(rows[record["paragraph_id"]]["text"])
                or type(record["literal_sha256"]) is not str or re.fullmatch(r"[a-f0-9]{64}", record["literal_sha256"]) is None
                or type(record["bridge_runs"]) is not list or not 1 <= len(record["bridge_runs"]) <= MAX_RUNS):
            model._fail("source_folio_bridge_direction_delta")
        index = order[record["paragraph_id"]]
        if index <= previous:
            model._fail("source_folio_bridge_direction_delta")
        previous = index
        last_index, last_end = -1, record["start"]
        for change in record["bridge_runs"]:
            if (type(change) is not dict or set(change) != {"run_index", "start", "end", "before_rtl", "after_rtl"}
                    or any(type(change[key]) is not int for key in change)
                    or not last_index < change["run_index"] < MAX_RUNS
                    or not last_end <= change["start"] < change["end"] <= record["end"]
                    or change["before_rtl"] != 1 or change["after_rtl"] != 0):
                model._fail("source_folio_bridge_direction_delta")
            last_index, last_end = change["run_index"], change["end"]
        by_id[record["paragraph_id"]] = record
    return by_id


def verified_copy(actual, baseline, record):
    """Independently undo only the listed existing bridge attributes, then compare all XML."""
    restored = deepcopy(actual)
    runs, before = restored.findall(W + "r"), baseline.findall(W + "r")
    if len(runs) != len(before):
        model._fail("source_folio_bridge_direction_delta")
    for change in record["bridge_runs"]:
        index = change["run_index"]
        if index >= len(runs):
            model._fail("source_folio_bridge_direction_delta")
        direction, original = _rtl(runs[index]), _rtl(before[index])
        if (direction is None or original is None or direction.get(W + "val") != "0"
                or original.get(W + "val") != "1"):
            model._fail("source_folio_bridge_direction_delta")
        direction.set(W + "val", "1")
    if model._c14n(restored) != model._c14n(baseline):
        model._fail("source_folio_bridge_direction_delta")
    return restored
