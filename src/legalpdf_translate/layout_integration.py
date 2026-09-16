"""Local, source-bound layout reuse without altering saved translation evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Sequence

from .document_structure import PageStructure, validate_page_structure
from .layout_cache import LayoutCache
from .formatting_support import digest_text, fingerprint, write_json_atomic

LAYOUT_DERIVATION_VERSION = "source_regions_v5"
LAYOUT_RENDER_DPI = 120
_PAGE_FILE = re.compile(r"page_[0-9]{4,}\.txt\Z")
_MAX_SIDECAR_BYTES = 8 * 1024 * 1024
REVIEWED_PROFILE_NOTICE_CODES = frozenset({
    "reviewed_profile_unsupported_selection", "reviewed_profile_requires_page_breaks",
    "reviewed_profile_requires_bidi_stripping", "reviewed_profile_unsupported_reviewer",
    "reviewed_profile_unsupported_source_reviewer", "reviewed_profile_unsupported_protocol",
    "reviewed_profile_unsupported_source_provenance", "reviewed_profile_stale_edited_target",
    "reviewed_profile_review_missing", "reviewed_profile_stale_review",
    "reviewed_profile_review_profile_mismatch",
})


def _read_json(path: Path) -> dict:
    if path.stat().st_size > _MAX_SIDECAR_BYTES:
        raise ValueError("Layout evidence exceeds the local bound.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Layout evidence must be an object.")
    return value


def _file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _review_layout(structure: PageStructure | dict, warning: str) -> dict:
    from .document_layout import derive_page_layout

    layout = derive_page_layout(structure)
    layout.update(status="needs_review", review_required=True, bands=[])
    layout["warnings"] = sorted(set(layout.get("warnings", []) + [warning]))
    return layout


def _render_source(path: Path, page_number: int) -> bytes:
    from .browser_pdf_bundle import browser_pdf_bundle_page_image_path
    from .source_document import is_image_source, is_pdf_source

    def image_png(image_path: Path) -> bytes:
        import io
        from PIL import Image

        try:
            opened = Image.open(image_path)
        except Image.DecompressionBombError as exc:
            raise ValueError("Source image exceeds the local layout bound.") from exc
        with opened as original:
            if original.width * original.height > 40_000_000:
                raise ValueError("Source image exceeds the local layout bound.")
            original.thumbnail((1600, 1600))
            if original.mode in {"RGBA", "LA"} or "transparency" in original.info:
                rgba = original.convert("RGBA")
                image = Image.new("RGBA", rgba.size, "white")
                image.alpha_composite(rgba)
                image = image.convert("RGB")
            else:
                image = original.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

    if is_pdf_source(path):
        image = browser_pdf_bundle_page_image_path(path, page_number)
        if image is not None:
            return image_png(image)
        import fitz
        with fitz.open(path) as document:
            page = document.load_page(page_number - 1)
            rect = page.rect
            if min(rect.width, rect.height) <= 0:
                raise ValueError("Invalid source page size.")
            dpi = min(LAYOUT_RENDER_DPI, 1600 * 72 / max(rect.width, rect.height))
            return page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False).tobytes("png")
    if is_image_source(path) and page_number == 1:
        return image_png(path)
    raise ValueError("Unsupported source for local layout rendering.")


def derive_source_layout(
    structure: PageStructure | dict,
    source_path: Path,
    *,
    cache_dir: Path | None = None,
    source_fingerprint: str | None = None,
    cancelled: Callable[[], bool] | None = None,
    layout_eligibility: dict | None = None,
) -> dict:
    """Determine layout locally; source-only cache is reusable across languages.

    The caller may supply its already-computed file fingerprint. No OCR, model
    client or credentials are used. Failure retains the text and requires review.
    """
    from .document_layout import derive_page_layout, validate_page_layout
    from .browser_pdf_bundle import browser_pdf_bundle_page_image_path
    from .source_document import is_pdf_source

    source = validate_page_structure(structure)
    from .reviewed_source import REVIEWED_SOURCE_VERSION
    if source.provenance == REVIEWED_SOURCE_VERSION or "reviewed_source" in source.metadata:
        return _review_layout(source, "reviewed_source_geometry_not_verified")
    if source.metadata.get("document_boundary_review_required"):
        # Do not reuse a geometry-only cache or derive regions across an
        # unresolved joined-document boundary. No new render is needed to stop.
        return _review_layout(source, "document_boundary_unresolved")
    if cancelled and cancelled():
        return _review_layout(source, "layout_derivation_cancelled")
    preliminary = derive_page_layout(source, layout_eligibility=layout_eligibility)
    if not source.blocks or not any(block.bbox for block in source.blocks):
        return preliminary
    try:
        actual = source_fingerprint or _file_hash(source_path)
        if not source.source_file_sha256 or actual != source.source_file_sha256:
            return _review_layout(source, "layout_source_file_mismatch")
        # A separately checked OCR record admits only simple flow; it cannot
        # authorize the digital/region detector or acquire panel/table authority.
        if source.uncertain and layout_eligibility is not None:
            from .source_layout_eligibility import valid_layout_eligibility
            from .source_document import source_page_identity
            if source_page_identity(source_path, source.page_number) != source.metadata.get("source_page_identity"):
                return _review_layout(source, "layout_source_raster_mismatch")
            if valid_layout_eligibility(source, layout_eligibility):
                return preliminary
        image_path = browser_pdf_bundle_page_image_path(source_path, source.page_number) if is_pdf_source(source_path) else None
        image_identity = _file_hash(image_path) if image_path else actual
        key = fingerprint({"version": LAYOUT_DERIVATION_VERSION, "dpi": LAYOUT_RENDER_DPI,
                           "source_file": actual, "image": image_identity,
                           "geometry": preliminary["geometry_sha256"]})
        cache = LayoutCache(cache_dir or source_path.parent, enabled=cache_dir is not None)
        cached = cache.get(key)
        if cached is not None:
            try:
                return validate_page_layout(cached["layout"], source)
            except (KeyError, ValueError, TypeError):
                pass
        if cancelled and cancelled():
            return _review_layout(source, "layout_derivation_cancelled")
        pixels = _render_source(source_path, source.page_number)
        if cancelled and cancelled():
            return _review_layout(source, "layout_derivation_cancelled")
        layout = validate_page_layout(derive_page_layout(source, image_bytes=pixels), source)
        try:
            cache.set(key, {"layout": layout})
        except OSError:
            pass  # Cache persistence is optional; usable local evidence remains.
        return layout
    except (OSError, ValueError, TypeError, RuntimeError, ImportError):
        return _review_layout(source, "layout_source_render_unavailable")


def _derive_rebuild_eligibility(source: PageStructure, source_path: Path) -> dict | None:
    """Reinspect the exact retained raster, never recognize/extract text again.

    Original browser raster bytes and RGB/PNG OCR input bytes have separate
    hashes. Reuse the original image-rendering function to validate that link.
    Non-bundle PDFs keep their existing native geometry/review path.
    """
    from .browser_pdf_bundle import browser_pdf_bundle_page_image_path
    from .source_document import source_page_identity, is_pdf_source, is_image_source
    from .source_layout_eligibility import derive_layout_eligibility
    from .ocr_helpers import render_image_png
    from PIL import Image

    if source.provenance != "local_ocr_tsv" or not source.uncertain:
        return None
    identity = source_page_identity(source_path, source.page_number)
    if identity != source.metadata.get("source_page_identity"):
        raise ValueError("Retained OCR source/raster identity changed.")
    path = (browser_pdf_bundle_page_image_path(source_path, source.page_number)
            if is_pdf_source(source_path) else source_path if is_image_source(source_path) else None)
    if path is None:
        return None
    try:
        opened = Image.open(path)
    except Image.DecompressionBombError as exc:
        raise ValueError("Eligibility raster exceeds the local bound.") from exc
    with opened as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("Eligibility raster exceeds the local bound.")
    pixels = render_image_png(path)
    if source_page_identity(source_path, source.page_number) != identity:
        raise ValueError("Source/raster changed during layout derivation.")
    return derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)


def load_layout_eligibility(page_path: Path, source: PageStructure | dict, target: dict) -> dict | None:
    """Load only a source-bound derivative for this exact saved translation."""
    from .source_layout_eligibility import valid_layout_eligibility

    try:
        record = _read_json(page_path.with_suffix(".layout_eligibility.json"))
        if (set(record) != {"version", "translation_sha256", "eligibility"}
                or type(record["version"]) is not int or record["version"] != 1
                or record["translation_sha256"] != target.get("translation_sha256")
                or not valid_layout_eligibility(source, record["eligibility"])):
            return None
        return record["eligibility"]
    except (OSError, ValueError, TypeError, KeyError):
        return None


def load_rebuild_layout(page_path: Path, structure: dict) -> dict | None:
    """Load an optional format-only derivative, never invalidate valid text IDs."""
    from .document_layout import validate_page_layout

    path = page_path.with_suffix(".layout.json")
    if not path.exists():
        return None
    try:
        record = _read_json(path)
        if (record.get("version") != 1 or record.get("derivation_version") != LAYOUT_DERIVATION_VERSION
                or record.get("translation_sha256") != structure.get("translation_sha256")
                or record.get("source_file_sha256") != structure.get("source_file_sha256")):
            raise ValueError("Stale layout derivative.")
        return validate_page_layout(record["layout"], structure)
    except (OSError, ValueError, TypeError, KeyError):
        return _review_layout(structure, "invalid_layout_derivative")


def prepare_layout_rebuild(
    pages_dir: Path,
    source_path: Path,
    *,
    cache_dir: Path | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> dict:
    """Create only new layout sidecars from matching complete retained sources.

    Source/TXT/translation sidecars and review/model fingerprints stay byte-for-
    byte intact. Missing originals/evidence produce review-required derivatives,
    not new extraction or a fabricated association to a different source.
    """
    try:
        source_file_hash = _file_hash(source_path)
    except OSError:
        source_file_hash = ""
    result = {"prepared_pages": [], "review_required_pages": [], "legacy_pages": [], "cancelled": False}
    for page_path in sorted(pages_dir.glob("page_*.txt")):
        if not _PAGE_FILE.fullmatch(page_path.name):
            continue
        if cancelled and cancelled():
            result["cancelled"] = True
            break
        number = int(page_path.stem.split("_")[1])
        try:
            target = validate_page_structure(_read_json(page_path.with_suffix(".structure.json")))
            text = page_path.read_text(encoding="utf-8")
            if target.page_number != number or target.translation_sha256 != digest_text(text) or target.text != text:
                raise ValueError("Saved target coverage does not match.")
        except (OSError, ValueError, TypeError, KeyError):
            result["legacy_pages"].append(number)
            continue
        eligibility = None
        try:
            source_sidecar = page_path.with_suffix(".source_structure.json")
            if not source_sidecar.exists():
                source_sidecar = page_path.with_suffix(".source.json")
            raw = _read_json(source_sidecar)
            source = PageStructure.from_dict(raw.get("structure", raw))
            if (not source_file_hash or source.source_file_sha256 != source_file_hash
                    or target.source_file_sha256 != source_file_hash or source.page_number != number
                    or source.source_sha256 != digest_text(source.text)
                    or source.source_text_sha256 != source.source_sha256
                    or target.source_sha256 != source.source_sha256):
                raise ValueError("Source evidence does not match the requested original.")
            source_rows, target_rows = source.to_dict()["blocks"], target.to_dict()["blocks"]
            # Confirmed cross-page links are derived after extraction and are
            # revalidated independently by assembly. They do not relocate boxes.
            ignored = {"text", "continuation_of"}
            if len(source_rows) != len(target_rows) or any(
                {k: v for k, v in a.items() if k not in ignored} != {k: v for k, v in b.items() if k not in ignored}
                for a, b in zip(source_rows, target_rows)
            ):
                raise ValueError("Source and target geometry/identities differ.")
            eligibility = _derive_rebuild_eligibility(source, source_path)
            layout = derive_source_layout(source, source_path, cache_dir=cache_dir,
                                          source_fingerprint=source_file_hash, cancelled=cancelled,
                                          layout_eligibility=eligibility)
        except (OSError, ValueError, TypeError, KeyError):
            layout = _review_layout(target, "layout_source_evidence_unavailable")
        if cancelled and cancelled():
            result["cancelled"] = True
            break
        # Also supersede stale prior proof on a failed/missing-source rebuild.
        # This is a format derivative, never part of the committed text bundle.
        if eligibility is not None or page_path.with_suffix(".layout_eligibility.json").exists():
            write_json_atomic(page_path.with_suffix(".layout_eligibility.json"), {
                "version": 1, "translation_sha256": target.translation_sha256,
                "eligibility": eligibility,
            })
        write_json_atomic(page_path.with_suffix(".layout.json"), {
            "version": 1, "derivation_version": LAYOUT_DERIVATION_VERSION,
            "translation_sha256": target.translation_sha256,
            "source_file_sha256": target.source_file_sha256, "layout": layout,
        })
        result["prepared_pages"].append(number)
        if layout.get("review_required"):
            result["review_required_pages"].append(number)
    return result


def _review_files(pages_dir: Path, page_numbers: Sequence[int] | None) -> dict[int, Path]:
    if page_numbers is None:
        return {int(path.stem.split("_")[1]): path for path in pages_dir.glob("page_*.txt")
                if _PAGE_FILE.fullmatch(path.name)}
    numbers = tuple(page_numbers)
    if (any(type(number) is not int or number < 1 for number in numbers)
            or tuple(sorted(set(numbers))) != numbers):
        raise ValueError("Layout review needs an ordered, unique source-page selection.")
    # Missing selected TXT is still a required page, not silently omitted.
    return {number: pages_dir / f"page_{number:04d}.txt" for number in numbers}


def _bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Layout evidence exceeds the local bound.")
    return raw


def _reviewed_map_pages(output_docx: Path, map_bytes: bytes, payload: dict,
                        files: dict[int, Path], projection, *, expected_reviewer_kind="ai_test_review") -> None:
    """Check the actual package, then bind its selected pages to retained text.

    The ordinary adapter supplies its freshly validated projection. This check
    does not manufacture source-image/reviewer authority or render acceptance.
    """
    from .reviewed_formatting_writer import MAX_PACKAGE_BYTES, validate_reviewed_docx

    docx_bytes = _bounded_bytes(output_docx, MAX_PACKAGE_BYTES)
    validate_reviewed_docx(docx_bytes, map_bytes, projection=projection,
                           expected_reviewer_kind=expected_reviewer_kind)
    numbers = tuple(sorted(files))
    if (tuple(page.page_number for page in projection.pages) != numbers
            or tuple(row["page_number"] for row in payload["pages"]) != numbers):
        raise ValueError("Reviewed layout map has a different source-page selection.")
    for page in projection.pages:
        path = files[page.page_number]
        target = json.loads(page.target_structure_json)
        text_bytes = _bounded_bytes(path, _MAX_SIDECAR_BYTES)
        text = text_bytes.decode("utf-8")
        expected = page.original_parent_separator.join(block["text"] for block in target["blocks"])
        if text != expected or digest_text(text) != target.get("translation_sha256"):
            raise ValueError("Reviewed layout map belongs to different saved text.")
        for suffix, expected_hash in ((".source_structure.json", page.source_structure_sha256),
                                       (".structure.json", page.target_structure_sha256)):
            if fingerprint(_read_json(path.with_suffix(suffix))) != expected_hash:
                raise ValueError("Reviewed layout map belongs to different retained source or target.")
    if (_file_hash(output_docx) != hashlib.sha256(docx_bytes).hexdigest()
            or _bounded_bytes(output_docx.with_suffix(".source_map.json"), _MAX_SIDECAR_BYTES) != map_bytes):
        raise ValueError("Reviewed layout output changed during inspection.")


def collect_docx_layout_review(output_docx: Path, pages_dir: Path, preparation: dict, *,
        page_numbers: Sequence[int] | None = None, reviewed_projection=None,
        expected_reviewer_kind: str = "ai_test_review") -> dict[int, list[str]]:
    """Read a DOCX- and TXT-bound map; never equate layout with fidelity.

    ``page_numbers`` is the caller's actual DONE-page assembly selection. When
    omitted, the existing integer-v1 collector still covers every saved TXT.
    Reviewed map versions require the adapter's validated projection and the
    actual package checker; a recognized version string alone is insufficient.
    Reviewer context comes from the caller's explicit profile, never map labels.
    """
    files = _review_files(pages_dir, page_numbers)
    reasons: dict[int, set[str]] = {number: set() for number in files}
    try:
        map_bytes = _bounded_bytes(output_docx.with_suffix(".source_map.json"), _MAX_SIDECAR_BYTES)
        payload = json.loads(map_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Layout evidence must be an object.")
        rows = payload.get("pages")
        version = payload.get("version")
        reviewed = version in ("reviewed_formatting_source_map_v1", "reviewed_region_source_map_v1")
        if ((not reviewed and (type(version) is not int or version != 1))
                or payload.get("docx_sha256") != _file_hash(output_docx)
                or not isinstance(rows, list) or len(rows) != len(files)):
            raise ValueError("DOCX layout map is missing or stale.")
        if reviewed:
            _reviewed_map_pages(output_docx, map_bytes, payload, files, reviewed_projection,
                                expected_reviewer_kind=expected_reviewer_kind)
            for codes in reasons.values():
                codes.add("layout_review_required")
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid layout map page.")
            number = row.get("page_number" if reviewed else "source_page_number")
            if type(number) is not int or number not in files or number in seen:
                raise ValueError("Invalid layout map coverage.")
            seen.add(number)
            if reviewed:
                continue  # Exact package/projection/TXT check above owns this schema.
            if row.get("translation_sha256") != digest_text(files[number].read_text(encoding="utf-8")):
                raise ValueError("Layout map belongs to different saved text.")
            if row.get("structure_status") != "validated":
                reasons[number].add("source_block_layout_unavailable")
            if row.get("layout_review_required") is True:
                reasons[number].add("layout_review_required")
                # Keep specific canonicalisation visible without copying arbitrary
                # sidecar strings (which may contain private source text).
                warnings = row.get("layout_warnings")
                if isinstance(warnings, list) and "section_furniture_target_variant_standardized" in warnings:
                    reasons[number].add("section_furniture_target_variant_standardized")
        if seen != set(files):
            raise ValueError("Incomplete layout map.")
    except (OSError, ValueError, TypeError, KeyError):
        for codes in reasons.values():
            codes.add("layout_mapping_unavailable")
    for key, code in (("legacy_pages", "source_block_layout_unavailable"),
                      ("review_required_pages", "layout_review_required")):
        values = preparation.get(key, [])
        if isinstance(values, list):
            for number in values:
                if type(number) is int and number in reasons:
                    reasons[number].add(code)
    return {number: sorted(codes) for number, codes in reasons.items() if codes}


def merge_layout_review_queue(payload: dict, page_records: dict) -> None:
    """Add sticky layout notices to the existing queue, not to semantic scores.

    Historical usage, model identity, semantic findings and unrelated fields are
    deliberately left alone. A rebuild is not a fresh translation/review run.
    """
    additions = []
    allowed = {"layout_mapping_unavailable", "source_block_layout_unavailable",
               "layout_review_required", "section_furniture_target_variant_standardized"} | REVIEWED_PROFILE_NOTICE_CODES
    for key, page in page_records.items():
        if not isinstance(page, dict) or not page.get("layout_review_required"):
            continue
        try:
            number = int(key)
        except (ValueError, TypeError):
            continue
        if number <= 0:
            continue
        codes = page.get("layout_review_reasons")
        codes = sorted({item for item in codes if isinstance(item, str) and item in allowed}) if isinstance(codes, list) else []
        additions.append((number, page, codes or ["layout_review_required"]))
    if not additions:
        return
    previous = payload.get("review_queue")
    if previous is not None and not isinstance(previous, list):
        raise ValueError("Historical review queue is malformed; preserve its evidence.")
    from copy import deepcopy
    queue = deepcopy(previous) if isinstance(previous, list) else []
    for number, page, codes in sorted(additions, key=lambda item: item[0]):
        existing = next((item for item in queue if isinstance(item, dict)
                         and item.get("page_number") == number), None)
        if existing is None:
            existing = {"page_number": number, "score": 0.0, "status": page.get("status", "unknown"),
                        "reasons": [], "recommended_action": "manual_review",
                        "retry_reason": page.get("retry_reason", ""),
                        "transport_retries_count": page.get("transport_retries_count", 0),
                        "rate_limit_hit": bool(page.get("rate_limit_hit", False)),
                        "ocr_used": bool(page.get("ocr_used", False)),
                        "image_used": bool(page.get("image_used", False))}
            queue.append(existing)
        old = existing.get("reasons")
        if old is not None and not isinstance(old, list):
            raise ValueError("Historical review reasons are malformed; preserve their evidence.")
        old = list(old) if isinstance(old, list) else []
        existing["reasons"] = old + [code for code in codes if code not in old]
        if existing.get("recommended_action") in (None, "", "spot_check"):
            existing["recommended_action"] = "manual_review"
    payload["review_queue"] = queue
    payload["review_queue_count"] = len(queue)
