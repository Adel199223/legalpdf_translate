"""Deterministic source geometry, vector rule, column, and crest extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import io
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageStat

from .source_document import is_image_source, is_pdf_source


@dataclass(frozen=True, slots=True)
class HeaderCrestAsset:
    """Extracted top institutional emblem/crest image bytes when cleanly detected."""

    image_bytes: bytes
    ext: str
    sha256: str
    width_pt: float
    height_pt: float
    bbox_norm: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class SourceStructuralEvidence:
    """Sanitized deterministic layout evidence for a single source page."""

    page_number: int
    page_width_pt: float
    page_height_pt: float
    orientation: str
    estimated_margins_pt: dict[str, float]
    text_block_count: int
    extracted_char_count: int
    vector_drawing_count: int
    image_count: int
    vector_outlined_text_likely: bool
    two_column_bands_detected: bool
    column_split_ratio: float | None
    horizontal_rule_y_ratios: tuple[float, ...]
    vertical_rule_x_ratios: tuple[float, ...]
    metadata_band_detected: bool
    table_grid_hints: tuple[dict[str, Any], ...]
    dominant_body_size_pt: float | None
    first_line_indent_pt: float | None
    bold_present: bool
    italic_present: bool
    has_top_center_crest: bool
    has_top_left_stamp: bool
    footer_zone_present: bool
    suggested_archetype: str
    crest_asset: HeaderCrestAsset | None = field(default=None, repr=False)

    def prompt_hints(self) -> dict[str, Any]:
        """Return a safe JSON-serializable structural summary with zero document prose."""
        payload = asdict(self)
        payload.pop("crest_asset", None)
        return payload


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round1(value: float) -> float:
    return round(float(value), 1)


def _round3(value: float) -> float:
    return round(float(value), 3)


def _cluster_positions(values: list[float], tolerance: float = 0.015) -> list[float]:
    if not values:
        return []
    ordered = sorted(values)
    clusters: list[list[float]] = [[ordered[0]]]
    for val in ordered[1:]:
        if abs(val - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(val)
        else:
            clusters.append([val])
    return [_round3(sum(c) / len(c)) for c in clusters]


def _extract_nonblank_crest_image(doc: fitz.Document, page: fitz.Page, *, page_w: float, page_h: float) -> tuple[HeaderCrestAsset | None, bool, bool]:
    """Detect top institutional emblem (centered or top-left) & top-left electronic signature stamp."""
    if page_w <= 0 or page_h <= 0:
        return None, False, False
    has_top_left_stamp = False
    crest_asset: HeaderCrestAsset | None = None
    has_center_crest = False
    best_score = -1.0
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:  # noqa: BLE001
        infos = []

    for info in infos:
        bbox = info.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = [float(v) for v in bbox]
        w = x1 - x0
        h = y1 - y0
        if w <= 1.0 or h <= 1.0 or y1 > 0.22 * page_h:
            continue
        x_center = (x0 + x1) * 0.5
        if x1 <= 0.34 * page_w and y1 <= 0.16 * page_h and w <= 160.0 and h <= 110.0:
            has_top_left_stamp = True
        centered = abs(x_center - (page_w * 0.5)) <= 0.15 * page_w
        top_left_crest = x0 <= 0.30 * page_w and y0 <= 0.12 * page_h and y1 <= 0.18 * page_h
        aspect_ratio = w / max(1.0, h)
        # Skip wide horizontal agency wordmarks/banners (e.g. "POLÍCIA..." 4.4:1)
        # so compact emblems/Coats of Arms are extracted instead of brand text graphics.
        if aspect_ratio > 2.6:
            continue
        if not ((centered or top_left_crest) and 18.0 <= w <= 185.0 and 18.0 <= h <= 135.0):
            continue
        xref = int(info.get("xref") or 0)
        if xref <= 0:
            continue
        try:
            extracted = doc.extract_image(xref)
        except Exception:  # noqa: BLE001
            continue
        raw_bytes = extracted.get("image")
        ext = str(extracted.get("ext") or "png").lower()
        if not isinstance(raw_bytes, (bytes, bytearray)) or len(raw_bytes) < 120:
            continue
        raw_bytes = bytes(raw_bytes)
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                rgb = img.convert("RGB")
                stat = ImageStat.Stat(rgb)
                if max(stat.stddev) < 4.5:
                    # Skip solid white or near-uniform spacer rectangles.
                    continue
                if img.width < 12 or img.height < 12:
                    continue
                if ext not in {"png", "jpeg", "jpg"}:
                    buf = io.BytesIO()
                    rgb.save(buf, format="PNG")
                    raw_bytes = buf.getvalue()
                    ext = "png"
        except Exception:  # noqa: BLE001
            continue
        # Prefer centered stationery crest when both exist; otherwise keep largest top crest.
        area_score = (w * h) + (100_000.0 if centered else 0.0)
        if area_score > best_score:
            best_score = area_score
            has_center_crest = centered
            crest_asset = HeaderCrestAsset(
                image_bytes=raw_bytes,
                ext="jpeg" if ext == "jpg" else ext,
                sha256=hashlib.sha256(raw_bytes).hexdigest(),
                width_pt=_round1(w),
                height_pt=_round1(h),
                bbox_norm=(
                    _round3(_clamp(x0 / page_w, 0.0, 1.0)),
                    _round3(_clamp(y0 / page_h, 0.0, 1.0)),
                    _round3(_clamp(x1 / page_w, 0.0, 1.0)),
                    _round3(_clamp(y1 / page_h, 0.0, 1.0)),
                ),
            )
    return crest_asset, has_center_crest, has_top_left_stamp


def _detect_two_column_geometry(
    boxes: list[tuple[float, float, float, float]],
    *,
    page_w: float,
    page_h: float,
) -> tuple[bool, float | None]:
    if len(boxes) < 4 or page_w <= 0 or page_h <= 0:
        return False, None
    body_boxes = [b for b in boxes if b[3] >= 0.08 * page_h and b[1] <= 0.90 * page_h and (b[2] - b[0]) <= 0.54 * page_w]
    if len(body_boxes) < 4:
        return False, None
    best_split: float | None = None
    best_pairs = 0
    for pct in range(36, 59, 2):
        split_x = page_w * (pct / 100.0)
        left_boxes = [b for b in body_boxes if b[2] <= split_x + 8.0]
        right_boxes = [b for b in body_boxes if b[0] >= split_x - 8.0]
        if len(left_boxes) < 2 or len(right_boxes) < 2:
            continue
        overlapping = 0
        for lb in left_boxes:
            for rb in right_boxes:
                if min(lb[3], rb[3]) - max(lb[1], rb[1]) >= -6.0 and abs(lb[1] - rb[1]) <= 90.0:
                    overlapping += 1
        if overlapping > best_pairs:
            best_pairs = overlapping
            best_split = round(pct / 100.0, 2)
    return (best_pairs >= 2, best_split if best_pairs >= 2 else None)


def _detect_table_grids(
    rects: list[tuple[float, float, float, float]],
    *,
    page_w: float,
    page_h: float,
) -> list[dict[str, Any]]:
    """Cluster aligned drawing rectangles into approximate table grid regions."""
    candidates = [
        r for r in rects
        if 20.0 <= (r[2] - r[0]) <= 0.95 * page_w and 10.0 <= (r[3] - r[1]) <= 0.60 * page_h
    ]
    if len(candidates) < 2:
        return []
    # Group vertically adjacent rects into row bands, then cluster contiguous rows into tables.
    candidates.sort(key=lambda r: (round(r[1], 1), round(r[0], 1)))
    row_groups: list[list[tuple[float, float, float, float]]] = []
    for rect in candidates:
        placed = False
        for grp in row_groups:
            ref_y0 = grp[0][1]
            ref_y1 = grp[0][3]
            if abs(rect[1] - ref_y0) <= 6.0 and abs(rect[3] - ref_y1) <= 10.0:
                grp.append(rect)
                placed = True
                break
        if not placed:
            row_groups.append([rect])
    multi_cell_rows = [sorted(g, key=lambda r: r[0]) for g in row_groups if len(g) >= 2]
    if not multi_cell_rows:
        return []

    tables: list[list[list[tuple[float, float, float, float]]]] = [[multi_cell_rows[0]]]
    for row in multi_cell_rows[1:]:
        prev_row = tables[-1][-1]
        prev_y1 = max(r[3] for r in prev_row)
        cur_y0 = min(r[1] for r in row)
        if cur_y0 - prev_y1 <= 14.0 and len(row) == len(prev_row):
            tables[-1].append(row)
        else:
            tables.append([row])

    hints: list[dict[str, Any]] = []
    for tbl in tables:
        if len(tbl) < 1:
            continue
        all_cells = [r for row in tbl for r in row]
        cols = len(tbl[0])
        col_widths_pt = [round(r[2] - r[0], 1) for r in tbl[0]]
        total_w = sum(col_widths_pt) or 1.0
        col_pcts = [int(round(w * 100.0 / total_w)) for w in col_widths_pt]
        hints.append(
            {
                "rows": len(tbl),
                "cols": cols,
                "col_widths_pct": col_pcts,
                "y0_norm": _round3(min(r[1] for r in all_cells) / page_h),
                "y1_norm": _round3(max(r[3] for r in all_cells) / page_h),
            }
        )
    return hints[:8]


def _classify_archetype(
    *,
    two_column_detected: bool,
    metadata_band_detected: bool,
    table_grid_hints: list[dict[str, Any]],
    has_top_center_crest: bool,
    first_line_indent_pt: float | None,
    horiz_rule_count: int,
    top_margin_pt: float,
) -> str:
    if any(t.get("rows", 0) >= 3 and t.get("cols", 0) >= 2 for t in table_grid_hints):
        return "form_record"
    if two_column_detected and (horiz_rule_count >= 2 or not has_top_center_crest):
        return "citius_notification"
    if has_top_center_crest or metadata_band_detected or (first_line_indent_pt is not None and top_margin_pt >= 75.0):
        return "despacho"
    if table_grid_hints:
        return "form_record"
    return "general_legal"


def extract_source_structural_evidence(path: Path, page_index: int) -> SourceStructuralEvidence:
    """Extract deterministic page geometry, rules, columns, and safe header crest from PDF/image."""
    if is_image_source(path):
        with Image.open(path) as img:
            width_px, height_px = img.size
        # Normalize image inputs onto A4-proportioned pt scale for Word assembly.
        scale = 595.3 / float(max(width_px, 1))
        page_w = 595.3
        page_h = round(float(height_px) * scale, 1)
        return SourceStructuralEvidence(
            page_number=1,
            page_width_pt=page_w,
            page_height_pt=page_h,
            orientation="landscape" if page_w > page_h else "portrait",
            estimated_margins_pt={"left": 45.0, "right": 45.0, "top": 42.0, "bottom": 42.0},
            text_block_count=0,
            extracted_char_count=0,
            vector_drawing_count=0,
            image_count=1,
            vector_outlined_text_likely=False,
            two_column_bands_detected=False,
            column_split_ratio=None,
            horizontal_rule_y_ratios=(),
            vertical_rule_x_ratios=(),
            metadata_band_detected=False,
            table_grid_hints=(),
            dominant_body_size_pt=None,
            first_line_indent_pt=None,
            bold_present=False,
            italic_present=False,
            has_top_center_crest=False,
            has_top_left_stamp=False,
            footer_zone_present=False,
            suggested_archetype="general_legal",
            crest_asset=None,
        )

    if not is_pdf_source(path):
        raise ValueError(f"Unsupported source file type: {path}")

    with fitz.open(path) as doc:
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds for {path} ({len(doc)} pages)")
        page = doc[page_index]
        page_w = float(page.rect.width)
        page_h = float(page.rect.height)
        page_dict = page.get_text("dict")
        text_blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0]
        images_meta = page.get_images(full=True)
        drawings = page.get_drawings()

        crest_asset, has_crest, has_top_left_stamp = _extract_nonblank_crest_image(
            doc, page, page_w=page_w, page_h=page_h
        )

        # Analyze typography & embedded text bounding boxes.
        size_chars: dict[float, int] = {}
        total_chars = 0
        bold_present = False
        italic_present = False
        first_line_indents: list[float] = []
        tb_boxes: list[tuple[float, float, float, float]] = []
        for blk in text_blocks:
            bbox = blk.get("bbox")
            lines = blk.get("lines") or []
            blk_text = "".join(sp.get("text", "") for ln in lines for sp in (ln.get("spans") or []))
            if bbox and len(bbox) == 4 and blk_text.strip():
                tb_boxes.append((float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])))
            line_x0s: list[float] = []
            for ln in lines:
                ln_bbox = ln.get("bbox")
                ln_txt = "".join(sp.get("text", "") for sp in (ln.get("spans") or [])).strip()
                if ln_bbox and ln_txt:
                    line_x0s.append(float(ln_bbox[0]))
                for sp in ln.get("spans") or []:
                    txt = str(sp.get("text") or "")
                    stripped_len = len(txt.strip())
                    if stripped_len == 0:
                        continue
                    total_chars += stripped_len
                    sz = round(float(sp.get("size") or 0.0), 1)
                    if blk_bbox := bbox:
                        if blk_bbox[1] >= 0.14 * page_h and blk_bbox[3] <= 0.90 * page_h and sz >= 8.0:
                            size_chars[sz] = size_chars.get(sz, 0) + stripped_len
                    flags = int(sp.get("flags") or 0)
                    font_name = str(sp.get("font") or "").lower()
                    if (flags & 16) or "bold" in font_name:
                        bold_present = True
                    if (flags & 2) or "italic" in font_name or "oblique" in font_name:
                        italic_present = True
            if len(line_x0s) >= 2:
                rest_min_x0 = min(line_x0s[1:])
                delta = line_x0s[0] - rest_min_x0
                if 12.0 <= delta <= 70.0:
                    first_line_indents.append(delta)

        dominant_body_size = (
            max(size_chars.items(), key=lambda item: item[1])[0]
            if size_chars
            else None
        )
        first_line_indent_pt = (
            _round1(sum(first_line_indents) / len(first_line_indents))
            if first_line_indents
            else None
        )

        # Analyze drawings: rules, grid rectangles, and vector ink bounds.
        horiz_y_norms: list[float] = []
        vert_x_norms: list[float] = []
        rect_boxes: list[tuple[float, float, float, float]] = []
        ink_boxes: list[tuple[float, float, float, float]] = list(tb_boxes)
        wide_rule_bands: list[tuple[float, float, float, float]] = []
        for dr in drawings:
            r = dr.get("rect")
            if r is None:
                continue
            w = float(r.x1 - r.x0)
            h = float(r.y1 - r.y0)
            # Ignore full-page clipping frames
            if w >= 0.95 * page_w and h >= 0.95 * page_h:
                continue
            if w <= 0.5 and h <= 0.5:
                continue
            ink_boxes.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))
            if h <= 4.0 and w >= 0.18 * page_w and page_h > 0:
                horiz_y_norms.append(float((r.y0 + r.y1) * 0.5 / page_h))
                wide_rule_bands.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))
            elif w <= 4.0 and h >= 14.0 and page_w > 0:
                vert_x_norms.append(float((r.x0 + r.x1) * 0.5 / page_w))
            elif w >= 20.0 and h >= 10.0:
                rect_boxes.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))

        horiz_rules = tuple(_cluster_positions(horiz_y_norms))
        vert_rules = tuple(_cluster_positions(vert_x_norms))

        # Check PyMuPDF native tables AND rectangle grid heuristics
        table_hints: list[dict[str, Any]] = []
        try:
            native_tabs = page.find_tables()
            for tab in native_tabs.tables:
                rows = tab.extract()
                if rows:
                    table_hints.append(
                        {
                            "rows": len(rows),
                            "cols": len(rows[0]),
                            "y0_norm": _round3(float(tab.bbox[1]) / page_h),
                            "y1_norm": _round3(float(tab.bbox[3]) / page_h),
                        }
                    )
        except Exception:  # noqa: BLE001
            pass
        if not table_hints:
            table_hints = _detect_table_grids(rect_boxes, page_w=page_w, page_h=page_h)

        # Metadata band heuristic: paired upper wide horizontal rules OR top-band 2+ wide rules spaced 16..95pt
        metadata_band_detected = False
        upper_rules = sorted(
            [r for r in wide_rule_bands if r[1] <= 0.36 * page_h and (r[2] - r[0]) >= 0.55 * page_w],
            key=lambda r: r[1],
        )
        for idx in range(len(upper_rules) - 1):
            gap = upper_rules[idx + 1][1] - upper_rules[idx][1]
            if 16.0 <= gap <= 95.0:
                metadata_band_detected = True
                break

        vector_outlined = total_chars == 0 and len(drawings) >= 40
        detect_boxes = tb_boxes if tb_boxes else [b for b in ink_boxes if (b[2] - b[0]) >= 4.0]
        two_col, split_ratio = _detect_two_column_geometry(detect_boxes, page_w=page_w, page_h=page_h)

        # Margin estimation (prefer embedded text boxes in main body if present, else drawing ink boxes)
        margin_source = tb_boxes if len(tb_boxes) >= 3 else ink_boxes
        if margin_source:
            content_boxes = [b for b in margin_source if b[1] >= 0.04 * page_h and b[3] <= 0.94 * page_h] or margin_source
            est_left = _clamp(min(b[0] for b in content_boxes), 26.0, 95.0)
            est_right = _clamp(page_w - max(b[2] for b in content_boxes), 26.0, 95.0)
            est_top = _clamp(min(b[1] for b in margin_source), 26.0, 150.0)
            est_bottom = _clamp(page_h - max(b[3] for b in margin_source), 26.0, 90.0)
        else:
            est_left = est_right = 45.0
            est_top = est_bottom = 42.0

        footer_zone_present = any(b[1] >= 0.88 * page_h for b in margin_source)
        archetype = _classify_archetype(
            two_column_detected=two_col,
            metadata_band_detected=metadata_band_detected,
            table_grid_hints=table_hints,
            has_top_center_crest=has_crest,
            first_line_indent_pt=first_line_indent_pt,
            horiz_rule_count=len(horiz_rules),
            top_margin_pt=est_top,
        )
        return SourceStructuralEvidence(
            page_number=page_index + 1,
            page_width_pt=_round1(page_w),
            page_height_pt=_round1(page_h),
            orientation="landscape" if page_w > page_h else "portrait",
            estimated_margins_pt={
                "left": _round1(est_left),
                "right": _round1(est_right),
                "top": _round1(est_top),
                "bottom": _round1(est_bottom),
            },
            text_block_count=len(text_blocks),
            extracted_char_count=int(total_chars),
            vector_drawing_count=len(drawings),
            image_count=len(images_meta),
            vector_outlined_text_likely=vector_outlined,
            two_column_bands_detected=two_col,
            column_split_ratio=split_ratio,
            horizontal_rule_y_ratios=horiz_rules[:12],
            vertical_rule_x_ratios=vert_rules[:8],
            metadata_band_detected=metadata_band_detected,
            table_grid_hints=tuple(table_hints),
            dominant_body_size_pt=dominant_body_size,
            first_line_indent_pt=first_line_indent_pt,
            bold_present=bold_present,
            italic_present=italic_present,
            has_top_center_crest=has_crest,
            has_top_left_stamp=has_top_left_stamp,
            footer_zone_present=footer_zone_present,
            suggested_archetype=archetype,
            crest_asset=crest_asset,
        )
