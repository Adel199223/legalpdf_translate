"""Bounded advisory native PDF text lines for one exact automatic recipe.

This is source document data, never paragraph ownership or a visible-ink proof.
Unsupported pages retain the image path and omit the entire optional line map.
"""
from __future__ import annotations

import math
import re

from .ordinary_layout_contracts import digest, encode, fail

VERSION = "ordinary_native_source_line_map_v1"
KEY = "native_source_line_map"
MAX_LINES = 512
MAX_TEXT_CODEPOINTS = 16000
MAX_TRACES = 2048
MAX_PAGE_BYTES = 65536
MAX_OPERATION_BYTES = 262144
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def recipe_descriptor():
    return {"version": VERSION, "max_lines": MAX_LINES,
        "max_text_codepoints": MAX_TEXT_CODEPOINTS, "max_traces": MAX_TRACES,
        "max_page_bytes": MAX_PAGE_BYTES, "max_operation_bytes": MAX_OPERATION_BYTES,
        "coordinates": "unrotated_zero_crop_normalized_font_metric_bbox_v1",
        "visibility": "opaque_native_fill_flags_advisory_not_ink_proof_v1",
        "overflow": "omit_whole_page_map", "ordering": "native_indices_not_reading_order",
        "request_capacity_fallback": "complete_native_input_bytes_plus_existing_image_bound_omit_whole_map_v1"}


def derive_source_line_map(source_pdf, frame, *, expected_source_sha256, selected_page_count, _verified_image=None):
    """Reproduce a whole-page map from immutable PDF bytes and its retained frame."""
    import fitz
    from .saved_docx_layout_service import RENDER_DPI, MAX_PAGE_PIXELS
    if (type(source_pdf) is not bytes or not 1 <= len(source_pdf) <= 64 * 1024 * 1024
            or type(expected_source_sha256) is not str or not _HASH.fullmatch(expected_source_sha256)
            or digest(source_pdf) != expected_source_sha256
            or type(selected_page_count) is not int or not 1 <= selected_page_count <= 100
            or type(frame) is not dict
            or any(type(frame.get(k)) is not int or frame[k] <= 0 for k in ("page_number", "width_px", "height_px"))
            or frame["width_px"] * frame["height_px"] > MAX_PAGE_PIXELS
            or frame.get("render_dpi") != RENDER_DPI
            or type(frame.get("image_sha256")) is not str or not _HASH.fullmatch(frame["image_sha256"])):
        fail("source_line_map_context_changed", 409)
    image_identity = {k: frame[k] for k in ("width_px", "height_px", "image_sha256", "render_dpi")}
    base = {"version": VERSION, "source_pdf_sha256": expected_source_sha256,
        "page_number": frame["page_number"], "frame": image_identity,
        "bounds_kind": "normalized_native_font_metrics", "advisory": True}
    def unavailable(reason):
        return {**base, "status": "unavailable", "reason": reason, "lines": []}
    try:
        document = fitz.open(stream=source_pdf, filetype="pdf")
    except (RuntimeError, ValueError):
        fail("source_line_map_context_changed", 409)
    with document:
        if document.needs_pass or not 1 <= frame["page_number"] <= len(document):
            fail("source_line_map_context_changed", 409)
        page = document[frame["page_number"] - 1]
        base["page_content_sha256"] = digest(page.read_contents())
        # Only live imported-image ownership or independently rerendered witness
        # lookup may supply this private fast path. Standalone derivation proves
        # the PDF-to-frame relation itself.
        if _verified_image is None:
            raster = page.get_pixmap(matrix=fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72), alpha=False)
            image_bytes = raster.tobytes("png")
        elif type(_verified_image) is bytes:
            image_bytes = _verified_image
            raster = fitz.Pixmap(image_bytes)
        else:
            fail("source_line_map_frame_changed", 409)
        if ((raster.width, raster.height) != (frame["width_px"], frame["height_px"])
                or digest(image_bytes) != frame["image_sha256"]
                or frame.get("rotation") != page.rotation):
            fail("source_line_map_frame_changed", 409)
        if page.rotation or page.cropbox_position != fitz.Point(0, 0):
            return unavailable("unsupported_page_geometry")
        width, height = float(page.rect.width), float(page.rect.height)
        if not all(math.isfinite(v) and v > 0 for v in (width, height)):
            return unavailable("invalid_geometry")
        try:
            traces = page.get_texttrace()
            if len(traces) > MAX_TRACES or sum(len(t.get("chars", ())) for t in traces) > MAX_TEXT_CODEPOINTS:
                return unavailable("limit_exceeded")
            # Conservative availability: this is not a general visibility detector.
            # Hidden/transparent or unusual rendering/layer flags decline the map.
            # Native paint flags do not establish ink visibility or background contrast.
            for trace in traces:
                if (trace.get("type") != 0 or trace.get("opacity") != 1
                        or trace.get("layer") or tuple(trace.get("dir", ())) != (1., 0.)):
                    return unavailable("unsupported_text_visibility")
            data = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES, sort=False)
            lines, count = [], 0
            for block_index, block in enumerate(data["blocks"]):
                for line_index, line in enumerate(block.get("lines", [])):
                    spans = line.get("spans", [])
                    text = "".join(span["text"] for span in spans)
                    if not text:
                        continue
                    count += len(text)
                    if len(lines) >= MAX_LINES or count > MAX_TEXT_CODEPOINTS:
                        return unavailable("limit_exceeded")
                    if (not traces or line.get("wmode") != 0 or tuple(line.get("dir", ())) != (1., 0.)
                            or any(span.get("alpha", 255) != 255 for span in spans)):
                        return unavailable("unsupported_text_visibility")
                    box = line["bbox"]
                    if (len(box) != 4 or any(type(v) not in {int, float} or not math.isfinite(v) for v in box)
                            or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
                        return unavailable("invalid_geometry")
                    lines.append({"line_id": f"p{frame['page_number']:04d}-b{block_index:04d}-l{line_index:04d}",
                        "text": text, "bbox": [box[0] / width, box[1] / height, box[2] / width, box[3] / height]})
            if not lines:
                return unavailable("no_native_text")
            result = {**base, "status": "available", "lines": lines}
            if len(encode(result)) > min(MAX_PAGE_BYTES, MAX_OPERATION_BYTES // selected_page_count):
                return unavailable("limit_exceeded")
            return result
        except (RuntimeError, ValueError, KeyError, TypeError, OverflowError, IndexError):
            return unavailable("unsupported_native_text")
