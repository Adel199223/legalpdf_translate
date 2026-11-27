"""Whole source-owned labelled fractions; only existing separator RTL flags change."""
from copy import deepcopy
import math
import re

from . import ordinary_folio_bridges_v4 as bridges
from . import saved_docx_layout as model

KEY = "source_labeled_folio_direction_version"
VERSION = "source_owned_labeled_fraction_ltr_v1"
LEDGER = "labeled_folio_direction_spans"
W = model.W
_NUMBER = bridges._NUMBER
_FORMULA = re.compile(rf"(?:الصفحة|صفحة|ص\.) +(?P<formula>(?P<numerator>{_NUMBER})(?P<separator> +\u200e/\u200e +| */ *)(?P<denominator>{_NUMBER})) *\Z")
_CORE = {"start", "end", "literal_sha256", "bridge_runs", "representation"}
_FIELDS = _CORE | {"paragraph_id", "source_page_number", "scope", "footer_association", "canonical_proposal_sha256"}


def occupied(plan):
    return {r["paragraph_id"] for key in ("folio_ltr_spans", "folio_bridge_direction_spans",
        "inline_folio_ltr_spans", "clock_ltr_spans", "in_flow_folio_bridge_direction_spans")
        for r in plan.get(key, [])}


def derive(paragraph, before_break_removal, row):
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
    start, end = match.span("formula")
    return {"start": start, "end": end, "literal_sha256": model._sha(text[start:end].encode()),
        "bridge_runs": changes, "representation": "protected_slash" if protected else "plain_slash"}


def span(node, row):
    if len(node.findall(W + "r")) > bridges.MAX_RUNS or len(row["text"]) > bridges.MAX_TEXT + 1:
        return None
    scratch = deepcopy(node)
    for br in list(scratch.iter(W + "br")):
        br.getparent().remove(br)
    return derive(scratch, node, row)


def record(identifier, page, scope, association, evidence, core):
    pages = [p for p in evidence["pages"] if p["page_number"] == page]
    signature = (pages[0].get("retained_terminal_associations", {}).get("canonical_proposal_sha256")
                 if len(pages) == 1 else None)
    if type(signature) is not str or re.fullmatch(r"[a-f0-9]{64}", signature) is None:
        model._fail("source_labeled_folio_direction_delta")
    return {"paragraph_id": identifier, "source_page_number": page, "scope": scope,
        "footer_association": deepcopy(association), "canonical_proposal_sha256": signature, **core}


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
    if mode is None:
        if KEY in plan or LEDGER in plan:
            model._fail("source_labeled_folio_direction_version")
        return {}
    records = plan.get(LEDGER)
    if mode != VERSION or plan.get(KEY) != VERSION or type(records) is not list or len(records) > len(rows):
        model._fail("source_labeled_folio_direction_version")
    blocked = occupied(plan)
    promoted = {i: p["source_page_number"] for p in plan["source_footers"] for i in p["paragraph_ids"]}
    core = []
    for r in records:
        if (type(r) is not dict or set(r) != _FIELDS or type(r["paragraph_id"]) is not str
                or r["paragraph_id"] in blocked or type(r["scope"]) is not str or r["scope"] not in {"promoted_footer", "retained_body"}
                or type(r["representation"]) is not str or r["representation"] not in {"plain_slash", "protected_slash"}
                or type(r["canonical_proposal_sha256"]) is not str
                or re.fullmatch(r"[a-f0-9]{64}", r["canonical_proposal_sha256"]) is None):
            model._fail("source_labeled_folio_direction_delta")
        item = r["footer_association"]
        if (type(item) is not dict or set(item) != {"kind", "paragraph_ids", "bbox", "source_page_number"}
                or item["kind"] != "source_footer" or type(item["source_page_number"]) is not int
                or item["source_page_number"] != r["source_page_number"]
                or type(item["paragraph_ids"]) is not list or r["paragraph_id"] not in item["paragraph_ids"]
                or not item["paragraph_ids"] or any(type(i) is not str or i not in rows for i in item["paragraph_ids"])
                or len(set(item["paragraph_ids"])) != len(item["paragraph_ids"])
                or type(item["bbox"]) is not list or len(item["bbox"]) != 4
                or any(type(v) not in {int, float} or not math.isfinite(v) for v in item["bbox"])
                or not 0 <= item["bbox"][0] < item["bbox"][2] <= 1 or not .85 <= item["bbox"][1] < item["bbox"][3] <= 1
                or (r["scope"] == "promoted_footer" and promoted.get(r["paragraph_id"]) != r["source_page_number"])
                or (r["scope"] == "retained_body" and r["paragraph_id"] in promoted)):
            model._fail("source_labeled_folio_direction_delta")
        core.append({k: r[k] for k in ("paragraph_id", "source_page_number", "start", "end", "literal_sha256", "bridge_runs")})
    bridges.checked_plan({bridges.LEDGER: core}, bridges.VERSION, rows, owners, selected_pages)
    return {r["paragraph_id"]: r for r in records}


apply = bridges.apply
verified_copy = bridges.verified_copy
