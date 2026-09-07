"""Bounded local physical layout evidence, independent of translation text.

Regions describe editable page containers, not semantic data-table cells. Pixel
evidence may add a shaded panel; neither a model nor a default style invents it.
Unsupported geometry is returned as review-required flow, never certified.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
from statistics import median
from typing import Any

from .document_structure import PageStructure, validate_page_structure

LAYOUT_VERSION = 1
MAX_BANDS = 32
MAX_REGIONS = 64
MAX_PANELS = 64
MAX_COLUMNS = 3
MAX_GEOMETRY_UNITS = 200
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _geometry(source):
    keys = ("id", "role", "bbox", "table_id", "row", "col", "alignment", "uncertain", "document_start")
    return _digest({"page": source.page_number, "size": [source.width_pt, source.height_pt],
                    "source_sha256": source.source_sha256,
                    "blocks": [{key: block.to_dict()[key] for key in keys} for block in source.blocks]})


def _base(source, status="flow", warnings=()):
    return {"version": LAYOUT_VERSION, "status": status, "review_required": bool(warnings) or status == "needs_review",
            "page_number": source.page_number, "source_sha256": source.source_sha256,
            "geometry_sha256": _geometry(source), "bands": [], "warnings": list(warnings)}


def _box(value, width, height):
    if (not isinstance(value, list) or len(value) != 4 or any(type(x) not in {int, float} or not math.isfinite(x) for x in value)
            or not 0 <= value[0] < value[2] <= width or not 0 <= value[1] < value[3] <= height):
        raise ValueError("Invalid physical layout bounds.")
    return value


def _contains(outer, inner, tolerance=0):
    return (outer[0] - tolerance <= inner[0] and outer[1] - tolerance <= inner[1]
            and inner[2] <= outer[2] + tolerance and inner[3] <= outer[3] + tolerance)


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def validate_page_layout(layout: dict[str, Any], structure: PageStructure | dict[str, Any]) -> dict[str, Any]:
    """Validate exact membership and bounded geometry; return a detached dict.

    A translated sidecar with identical source geometry is intentionally valid:
    translation text does not change physical layout identity. Pixel claims are
    hash-bound provenance, not independently re-inspected without image bytes.
    """
    source = validate_page_structure(structure)
    try:
        payload = json.loads(json.dumps(layout, allow_nan=False))
    except (ValueError, TypeError) as exc:
        raise ValueError("Layout must be finite JSON metadata.") from exc
    keys = {"version", "status", "review_required", "page_number", "source_sha256", "geometry_sha256", "bands", "warnings"}
    if (not isinstance(payload, dict) or set(payload) != keys or type(payload["version"]) is not int
            or payload["version"] != LAYOUT_VERSION or not isinstance(payload["status"], str) or payload["status"] not in {"regions", "flow", "needs_review"}
            or type(payload["review_required"]) is not bool or type(payload["page_number"]) is not int or payload["page_number"] != source.page_number
            or payload["source_sha256"] != source.source_sha256 or payload["geometry_sha256"] != _geometry(source)
            or not isinstance(payload["warnings"], list) or len(payload["warnings"]) > 32
            or any(not isinstance(w, str) or not re.fullmatch(r"[a-z0-9_]{1,100}", w) for w in payload["warnings"])
            or not isinstance(payload["bands"], list) or len(payload["bands"]) > MAX_BANDS):
        raise ValueError("Layout schema or source-geometry binding failed.")
    if payload["status"] != "regions":
        if payload["bands"] or (payload["status"] == "needs_review" and not payload["review_required"]):
            raise ValueError("Unsupported layout must use review-required flow without region instructions.")
        return payload
    if not payload["bands"] or source.uncertain or any(b.uncertain for b in source.blocks):
        raise ValueError("Region layout requires certain source geometry.")
    by_id = {b.id: b for b in source.blocks}
    order = {b.id: i for i, b in enumerate(source.blocks)}
    tolerance = max(3.0, source.width_pt * .015)
    owned, containers, identities = [], {}, set()
    region_count = panel_count = 0
    previous_bottom = -1.0
    for band_index, band in enumerate(payload["bands"]):
        if not isinstance(band, dict) or set(band) != {"id", "bbox", "column_edges_pt", "regions"}:
            raise ValueError("Invalid layout band.")
        box = _box(band["bbox"], source.width_pt, source.height_pt)
        if box[1] < previous_bottom - .01:
            raise ValueError("Layout bands overlap or are out of physical order.")
        previous_bottom = box[3]
        edges = band["column_edges_pt"]
        if (not isinstance(edges, list) or not 2 <= len(edges) <= MAX_COLUMNS + 1
                or any(type(v) not in {int, float} or not math.isfinite(v) for v in edges)
                or edges[0] != box[0] or edges[-1] != box[2]
                or any(b - a < 12 for a, b in zip(edges, edges[1:]))):
            raise ValueError("Invalid physical column edges.")
        if not isinstance(band["regions"], list) or not 1 <= len(band["regions"]) <= MAX_COLUMNS:
            raise ValueError("Invalid band regions.")
        used_columns = set()
        for region_index, region in enumerate(band["regions"]):
            region_count += 1
            if (not isinstance(region, dict) or set(region) != {"id", "column_start", "column_span", "bbox", "block_ids", "panels", "alignment"}
                    or type(region["column_start"]) is not int or type(region["column_span"]) is not int
                    or region["column_start"] < 0 or region["column_span"] < 1
                    or region["column_start"] + region["column_span"] > len(edges) - 1
                    or (region["alignment"] is not None and (not isinstance(region["alignment"], str) or region["alignment"] not in {"left", "right", "center", "justify"}))):
                raise ValueError("Invalid physical region span or alignment.")
            columns = set(range(region["column_start"], region["column_start"] + region["column_span"]))
            if used_columns & columns:
                raise ValueError("Region spans overlap.")
            used_columns |= columns
            rb = _box(region["bbox"], source.width_pt, source.height_pt)
            if (not _contains(box, rb) or rb[0] != edges[region["column_start"]]
                    or rb[2] != edges[region["column_start"] + region["column_span"]]):
                raise ValueError("Region must use its physical column boundaries.")
            ids = region["block_ids"]
            if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in by_id for i in ids)
                    or len(set(ids)) != len(ids) or ids != sorted(ids, key=order.get)):
                raise ValueError("Region membership must retain ordered, known, unique block IDs.")
            for identity in ids:
                block = by_id[identity]
                if block.bbox is None or not _contains(rb, block.bbox, tolerance):
                    raise ValueError("Block lies outside its evidenced physical region.")
                if block.document_start and not (band_index == region_index == 0 and identity == ids[0] == source.blocks[0].id):
                    raise ValueError("Independent document boundary cannot be hidden inside a region.")
                if block.table_id:
                    containers.setdefault(block.table_id, set()).add(region["id"])
            owned.extend(ids)
            panels = region["panels"]
            if not isinstance(panels, list) or len(panels) > MAX_PANELS:
                raise ValueError("Invalid panel collection.")
            panel_members = set()
            for panel in panels:
                panel_count += 1
                if not isinstance(panel, dict) or set(panel) != {"id", "bbox", "block_ids", "shading"}:
                    raise ValueError("Invalid panel evidence.")
                pb = _box(panel["bbox"], source.width_pt, source.height_pt)
                members = panel["block_ids"]
                if (not _contains(rb, pb, tolerance) or not isinstance(members, list) or not members
                        or any(not isinstance(i, str) or i not in ids for i in members) or len(set(members)) != len(members)
                        or members != ids[ids.index(members[0]):ids.index(members[0]) + len(members)]
                        or panel_members & set(members)
                        or any(by_id[i].table_id or not _contains(pb, by_id[i].bbox, tolerance) for i in members)):
                    raise ValueError("Panel must contain a contiguous, non-table subset of its physical region.")
                panel_members |= set(members)
                shade = panel["shading"]
                if (not isinstance(shade, dict) or set(shade) != {"fill", "image_sha256", "bbox_px", "image_size_px", "sample_fraction", "evidence"}
                        or not isinstance(shade["fill"], str) or not re.fullmatch(r"[0-9A-F]{6}", shade["fill"])
                        or not isinstance(shade["image_sha256"], str) or not _HASH.fullmatch(shade["image_sha256"])
                        or shade["evidence"] != "pixel_rectangle" or type(shade["sample_fraction"]) not in {int, float}
                        or not .55 <= shade["sample_fraction"] <= 1
                        or not isinstance(shade["image_size_px"], list) or len(shade["image_size_px"]) != 2
                        or any(type(v) is not int or not 1 <= v <= 20000 for v in shade["image_size_px"])
                        or math.prod(shade["image_size_px"]) > 40_000_000):
                    raise ValueError("Panel shading requires bounded pixel evidence, not a default fill.")
                _box(shade["bbox_px"], *shade["image_size_px"])
                mapped = [shade["bbox_px"][i] / shade["image_size_px"][i % 2] * (source.width_pt if i % 2 == 0 else source.height_pt) for i in range(4)]
                if any(abs(a - b) > 2 for a, b in zip(mapped, pb)):
                    raise ValueError("Panel pixels do not map to its source geometry.")
                _identity(panel, identities)
            _identity(region, identities)
        _identity(band, identities)
    if (region_count > MAX_REGIONS or panel_count > MAX_PANELS or len(owned) != len(by_id)
            or set(owned) != set(by_id) or len(set(owned)) != len(owned) or any(len(v) != 1 for v in containers.values())):
        raise ValueError("Region layout must cover every block once without splitting semantic tables.")
    # A semantic table must remain one contiguous group within its region.
    for band in payload["bands"]:
        for region in band["regions"]:
            closed, previous = set(), None
            for identity in region["block_ids"]:
                table = by_id[identity].table_id
                if table != previous and previous:
                    closed.add(previous)
                if table and table in closed:
                    raise ValueError("Semantic table fragments cannot be interleaved.")
                previous = table
    return payload


def _identity(item, used):
    identity = item.get("id")
    if not isinstance(identity, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", identity) or identity in used:
        raise ValueError("Layout container IDs must be bounded and unique.")
    used.add(identity)


def _units(source):
    result = []
    for index, block in enumerate(source.blocks):
        if block.table_id and result and result[-1]["table"] == block.table_id:
            result[-1]["ids"].append(block.id)
            result[-1]["bbox"] = _union([result[-1]["bbox"], block.bbox])
        else:
            result.append({"ids": [block.id], "bbox": list(block.bbox), "table": block.table_id, "order": index})
    return result


def _overlap(a, b):
    return max(0, min(a[3], b[3]) - max(a[1], b[1])) >= min(a[3] - a[1], b[3] - b[1]) * .25


def _columns(units, width):
    extent = _union([u["bbox"] for u in units])
    tolerance = max(3.0, width * .015)
    boundaries = sorted({value for u in units for value in (u["bbox"][0], u["bbox"][2])})
    best = None
    for split in [(a + b) / 2 for a, b in zip(boundaries, boundaries[1:])]:
        if not extent[0] + .2 * (extent[2] - extent[0]) < split < extent[2] - .2 * (extent[2] - extent[0]):
            continue
        left, right, spans = [], [], []
        for unit in units:
            box = unit["bbox"]
            group = left if box[2] <= split + tolerance and (box[0] + box[2]) / 2 < split else right if box[0] >= split - tolerance else spans
            group.append(unit)
        overlap = sum(_overlap(a["bbox"], b["bbox"]) for a in left for b in right)
        if min(len(left), len(right)) < 2 or overlap < 2 or len(spans) > max(3, len(units) * .3):
            continue
        score = (len(left) + len(right), overlap, min(len(left), len(right)))
        if best is None or score > best[0]:
            divider = (max(u["bbox"][2] for u in left) + min(u["bbox"][0] for u in right)) / 2
            best = score, divider, left, right, spans
    return best


def _bands(units, columns):
    _, divider, left, right, spanning = columns
    extent = _union([u["bbox"] for u in units])
    span_groups = []
    for unit in sorted(spanning, key=lambda u: u["bbox"][1]):
        if span_groups and unit["bbox"][1] <= span_groups[-1][1] + .01:
            span_groups[-1][1] = max(span_groups[-1][1], unit["bbox"][3])
            span_groups[-1][2].append(unit)
        else:
            span_groups.append([unit["bbox"][1], unit["bbox"][3], [unit]])
    pieces, pending = [], left + right
    for top, bottom, group in span_groups:
        before = [u for u in pending if u["bbox"][3] <= top + .01]
        pending = [u for u in pending if u not in before]
        if any(u["bbox"][1] < bottom - .01 for u in pending):
            raise ValueError("Full-width and column blocks overlap.")
        if before:
            pieces.append((before, False))
        pieces.append((group, True))
    if pending:
        pieces.append((pending, False))
    bands = []
    for index, (members, full_width) in enumerate(pieces, 1):
        box = _union([u["bbox"] for u in members])
        box[0], box[2] = extent[0], extent[2]
        edges = [extent[0], divider, extent[2]]
        groups = [(0, 2, members)] if full_width else [(0, 1, [u for u in members if u in left]), (1, 1, [u for u in members if u in right])]
        regions = [{"id": f"region_{index:04d}_{start}", "column_start": start, "column_span": span,
                    "bbox": [edges[start], box[1], edges[start + span], box[3]],
                    "block_ids": [identity for u in sorted(group, key=lambda u: u["order"]) for identity in u["ids"]],
                    "panels": [], "alignment": None} for start, span, group in groups if group]
        bands.append({"id": f"band_{index:04d}", "bbox": box, "column_edges_pt": edges, "regions": regions})
    return bands


def _gray_rectangles(image_bytes):
    """Run-length connected components of actual neutral-gray image pixels."""
    from PIL import Image, ImageFilter
    if not isinstance(image_bytes, bytes) or not image_bytes or len(image_bytes) > 20_000_000:
        raise ValueError("Layout image exceeds its bounded input contract.")
    with Image.open(io.BytesIO(image_bytes)) as original:
        size = list(original.size)
        if min(size) < 16 or max(size) > 20000 or size[0] * size[1] > 40_000_000:
            raise ValueError("Unsupported layout image dimensions.")
        rgba = original.convert("RGBA")
        image = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
    image.thumbnail((1000, 1400))
    width, height = image.size
    raw = image.tobytes()
    mask = bytes(1 if 110 <= (r + g + b) / 3 <= 242 and max(r, g, b) - min(r, g, b) <= 10 else 0
                 for r, g, b in zip(raw[0::3], raw[1::3], raw[2::3]))
    # Sever one-pixel antialias/rule connections to distant text. This is a
    # private analysis mask; source image bytes and extracted text never change.
    mask = Image.frombytes("L", (width, height), mask).filter(ImageFilter.MinFilter(3)).tobytes()
    parents, components, previous = [], [], []
    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    for y in range(height):
        line, current, offset = mask[y * width:(y + 1) * width], [], 0
        previous_index = 0
        while (start := line.find(b"\1", offset)) >= 0:
            end = line.find(b"\0", start)
            end = width if end < 0 else end
            while previous_index < len(previous) and previous[previous_index][1] < start:
                previous_index += 1
            neighbours = []
            lookup = previous_index
            while lookup < len(previous) and previous[lookup][0] <= end:
                if previous[lookup][1] >= start:
                    neighbours.append(find(previous[lookup][2]))
                lookup += 1
            if neighbours:
                label = min(neighbours)
                for other in set(neighbours) - {label}:
                    parents[other] = label
                    a, b = components[label], components[other]
                    components[label] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), a[4] + b[4]]
                data = components[label]
                components[label] = [min(data[0], start), data[1], max(data[2], end), y + 1, data[4] + end - start]
            else:
                if len(parents) >= 100000:
                    raise ValueError("Layout image has too many fragmented components.")
                label = len(parents)
                parents.append(label)
                components.append([start, y, end, y + 1, end - start])
            current.append((start, end, label))
            offset = end
        previous = current
    rectangles = []
    for index, (left, top, right, bottom, count) in enumerate(components):
        area = (right - left) * (bottom - top)
        if parents[index] != index or area < width * height * .012 or right - left < width * .12 or bottom - top < height * .035 or count / area < .55:
            continue
        # Filled circles, text clouds and irregular gray graphics are not
        # evidenced rectangular panels just because their bounding box is big.
        edges = [sum(mask[(top + 1) * width + x] for x in range(left, right)) / (right - left),
                 sum(mask[(bottom - 2) * width + x] for x in range(left, right)) / (right - left),
                 sum(mask[y * width + left + 1] for y in range(top, bottom)) / (bottom - top),
                 sum(mask[y * width + right - 2] for y in range(top, bottom)) / (bottom - top)]
        if min(edges) < .65:
            continue
        shades = [raw[position * 3] for y in range(top, bottom, max(1, (bottom - top) // 50))
                  for x in range(left, right, max(1, (right - left) // 50)) if mask[(position := y * width + x)]]
        if not shades:
            continue
        fill = round(median(shades))
        rectangles.append({"bbox_px": [left * size[0] / width, top * size[1] / height, right * size[0] / width, bottom * size[1] / height],
                           "fill": f"{fill:02X}" * 3, "sample_fraction": min(1.0, round(count / area, 5)),
                           "image_size_px": size, "image_sha256": hashlib.sha256(image_bytes).hexdigest(), "evidence": "pixel_rectangle"})
    merged = []
    for rectangle in sorted(rectangles, key=lambda r: (r["bbox_px"][0], r["bbox_px"][1])):
        previous = merged[-1] if merged else None
        a, b = previous["bbox_px"] if previous else [], rectangle["bbox_px"]
        if (previous and previous["fill"] == rectangle["fill"] and abs(a[0] - b[0]) <= 2 and abs(a[2] - b[2]) <= 2
                and 0 <= b[1] - a[3] <= max(4, size[1] / height * 4)):
            combined = _union([a, b])
            area = lambda box: (box[2] - box[0]) * (box[3] - box[1])
            previous["sample_fraction"] = round((area(a) * previous["sample_fraction"] + area(b) * rectangle["sample_fraction"]) / area(combined), 5)
            previous["bbox_px"] = combined
        else:
            merged.append(rectangle)
    return merged


def _attach_panels(layout, source, image_bytes):
    rectangles = _gray_rectangles(image_bytes)
    by_id = {b.id: b for b in source.blocks}
    count = 0
    for shade in rectangles:
        if abs((shade["image_size_px"][0] / shade["image_size_px"][1]) / (source.width_pt / source.height_pt) - 1) > .08:
            raise ValueError("Panel image aspect ratio does not match the full source page.")
        box = [shade["bbox_px"][i] / shade["image_size_px"][i % 2] * (source.width_pt if i % 2 == 0 else source.height_pt) for i in range(4)]
        matched = False
        for band in layout["bands"]:
            for region in band["regions"]:
                if not _contains(region["bbox"], box, max(3.0, source.width_pt * .015)):
                    continue
                ids = [i for i in region["block_ids"] if _contains(box, by_id[i].bbox, 2) and not by_id[i].table_id]
                if not ids:
                    continue
                if ids != region["block_ids"][region["block_ids"].index(ids[0]):region["block_ids"].index(ids[0]) + len(ids)]:
                    continue
                if any(set(ids) & set(panel["block_ids"]) for panel in region["panels"]):
                    continue
                count += 1
                region["panels"].append({"id": f"panel_{count:04d}", "bbox": box, "block_ids": ids, "shading": shade})
                matched = True
        if not matched:
            layout["review_required"] = True
            if "unassigned_panel_evidence" not in layout["warnings"]:
                layout["warnings"].append("unassigned_panel_evidence")


def derive_page_layout(structure: PageStructure | dict[str, Any], image_bytes: bytes | None = None) -> dict[str, Any]:
    """Infer physical side-by-side regions from positive source geometry only."""
    source = validate_page_structure(structure)
    if not source.blocks:
        return _base(source)
    if source.uncertain or any(b.uncertain or not b.bbox for b in source.blocks):
        return _base(source, "needs_review", ["source_geometry_uncertain"])
    try:
        for block in source.blocks:
            _box(list(block.bbox), source.width_pt, source.height_pt)
        units = _units(source)
        if len(units) > MAX_GEOMETRY_UNITS:
            return _base(source, "needs_review", ["layout_geometry_limit"])
        columns = _columns(units, source.width_pt)
        if columns is None:
            side_by_side = any(_overlap(a["bbox"], b["bbox"]) and (a["bbox"][2] + 6 < b["bbox"][0] or b["bbox"][2] + 6 < a["bbox"][0])
                               for index, a in enumerate(units) for b in units[index + 1:])
            return _base(source, "needs_review", ["ambiguous_side_by_side_geometry"]) if side_by_side else _base(source)
        # This bounded detector derives two columns only. Positive nested
        # columns must not silently become one flattened physical region.
        if any(_columns(group, source.width_pt) is not None for group in columns[2:4]):
            return _base(source, "needs_review", ["additional_column_geometry"])
        layout = _base(source, "regions")
        layout["bands"] = _bands(units, columns)
        if image_bytes is None:
            layout["review_required"] = True
            layout["warnings"].append("panel_style_not_evaluated")
        else:
            try:
                _attach_panels(layout, source, image_bytes)
            except (ValueError, OSError):
                layout["review_required"] = True
                layout["warnings"].append("panel_image_unavailable")
        return validate_page_layout(layout, source)
    except (ValueError, KeyError, TypeError):
        return _base(source, "needs_review", ["unsupported_region_geometry"])


def attach_page_layout(structure: PageStructure | dict[str, Any], image_bytes: bytes | None = None) -> PageStructure:
    """Detached source/target structure with layout metadata; text/IDs unchanged."""
    result = validate_page_structure(structure)
    # PageStructure metadata values may themselves be mutable. Detach fully.
    result = validate_page_structure(json.loads(json.dumps(result.to_dict(), allow_nan=False)))
    result.metadata["layout"] = derive_page_layout(result, image_bytes)
    return result
