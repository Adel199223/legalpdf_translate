"""Source-qualified body-flow application of the unchanged V4 bridge proof."""
from copy import deepcopy
import re

from . import ordinary_folio_bridges_v4 as bridges
from . import saved_docx_layout as model

VERSION = "in_flow_protected_folio_bridges_v1"
KEY = "source_in_flow_folio_direction_version"
LEDGER = "in_flow_folio_bridge_direction_spans"
W = model.W
_BASE_KEYS = {"paragraph_id", "source_page_number", "start", "end", "literal_sha256", "bridge_runs"}
_EXTRA_KEYS = {"footer_association", "canonical_proposal_sha256"}


def _direction_owners(plan):
    return {row["paragraph_id"] for key in (
        "folio_ltr_spans", "folio_bridge_direction_spans", "inline_folio_ltr_spans", "clock_ltr_spans")
        for row in plan.get(key, [])}


def bridge_span(node, row):
    """Use a scratch copy only; never remove a represented body page break."""
    if len(node.findall(W + "r")) > bridges.MAX_RUNS or len(row["text"]) > bridges.MAX_TEXT + 1:
        return None
    from .ordinary_source_layout import _inline_folio_run_inventory
    if _inline_folio_run_inventory(node, row) is None:
        return None
    scratch = deepcopy(node)
    for br in list(scratch.iter(W + "br")):
        br.getparent().remove(br)
    return bridges.derive(scratch, node, row)


def derive(nodes, mapped, rows, choices, owners, selected_pages, layout, evidence, plan, target_lang):
    """Only revalidated accepted footer members, never a retained/rejected hint."""
    if target_lang != "AR":
        return []
    promoted = {identifier for footer in plan["source_footers"] for identifier in footer["paragraph_ids"]}
    occupied = _direction_owners(plan)
    source_owners = {}
    for page, ids in owners.items():
        for identifier in ids:
            source_owners.setdefault(identifier, []).append(page)
    associations = {}
    for item in layout:
        if item["kind"] == "source_footer":
            for identifier in item["paragraph_ids"]:
                associations.setdefault(identifier, []).append(item)
    page_records = {page["page_number"]: page for page in evidence["pages"]}
    result = []
    for identifier, row in rows.items():
        accepted = associations.get(identifier, [])
        node, mapping = nodes[identifier], mapped[identifier]
        if (len(accepted) != 1 or identifier in promoted or identifier in occupied
                or choices[identifier]["role"] != "source_folio" or mapping.get("parts")
                or mapping.get("part_uri", "word/document.xml") != "word/document.xml"
                or node.getparent() is None or node.getparent().tag != W + "body"):
            continue
        item = accepted[0]
        page = item["source_page_number"]
        if type(page) is not int or page not in selected_pages or source_owners.get(identifier) != [page]:
            continue
        # This header supplies identity only. Its retained associations confer no
        # authority here; accepted `layout` above is independently requalified.
        signature = page_records[page].get("retained_terminal_associations", {}).get("canonical_proposal_sha256")
        if type(signature) is not str or re.fullmatch(r"[a-f0-9]{64}", signature) is None:
            model._fail("source_in_flow_folio_direction_delta")
        record = bridge_span(node, row)
        if record is not None:
            result.append({"paragraph_id": identifier, "source_page_number": page,
                "footer_association": deepcopy(item), "canonical_proposal_sha256": signature, **record})
    return result


def apply(nodes, mapped, rows, choices, owners, selected_pages, layout, evidence, plan, target_lang):
    records = derive(nodes, mapped, rows, choices, owners, selected_pages, layout, evidence, plan, target_lang)
    plan[KEY], plan[LEDGER] = VERSION, records
    for record in records:
        # Keep the original body paragraph and its exact represented terminal FF.
        bridges.apply(nodes[record["paragraph_id"]], record)


def checked_plan(plan, mode, rows, owners, selected_pages):
    if mode is None:
        if KEY in plan or LEDGER in plan:
            model._fail("source_in_flow_folio_direction_version")
        return {}
    records = plan.get(LEDGER)
    if mode != VERSION or plan.get(KEY) != VERSION or type(records) is not list or len(records) > len(rows):
        model._fail("source_in_flow_folio_direction_version")
    occupied = _direction_owners(plan)
    promoted = {i for footer in plan["source_footers"] for i in footer["paragraph_ids"]}
    core = []
    for record in records:
        if (type(record) is not dict or set(record) != _BASE_KEYS | _EXTRA_KEYS
                or type(record.get("paragraph_id")) is not str
                or record.get("paragraph_id") in occupied | promoted
                or type(record.get("canonical_proposal_sha256")) is not str
                or re.fullmatch(r"[a-f0-9]{64}", record["canonical_proposal_sha256"]) is None):
            model._fail("source_in_flow_folio_direction_delta")
        item = record["footer_association"]
        if (type(item) is not dict or set(item) != {"kind", "paragraph_ids", "bbox", "source_page_number"}
                or item["kind"] != "source_footer" or type(item["source_page_number"]) is not int
                or item["source_page_number"] != record["source_page_number"]
                or type(item["paragraph_ids"]) is not list or record["paragraph_id"] not in item["paragraph_ids"]
                or any(type(i) is not str or i not in rows for i in item["paragraph_ids"])
                or len(set(item["paragraph_ids"])) != len(item["paragraph_ids"])
                or type(item["bbox"]) is not list or len(item["bbox"]) != 4
                or any(type(v) not in {int, float} or not 0 <= v <= 1 for v in item["bbox"])
                or not item["bbox"][0] < item["bbox"][2] or not .85 <= item["bbox"][1] < item["bbox"][3]):
            model._fail("source_in_flow_folio_direction_delta")
        core.append({key: record[key] for key in _BASE_KEYS})
    bridges.checked_plan({bridges.LEDGER: core}, bridges.VERSION, rows, owners, selected_pages)
    return {record["paragraph_id"]: record for record in records}


def verified_copy(actual, baseline, record):
    """Undo only the listed existing attributes, retaining all break/control XML."""
    return bridges.verified_copy(actual, baseline, record)
