"""Browser-generated PDF page-image bundles for browser-first workflows."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable

_BUNDLE_SUFFIX = ".browser_pdf_bundle"
_MANIFEST_NAME = "manifest.json"
_PAGES_SUBDIR = "pages"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def browser_pdf_bundle_dir(source_path: Path) -> Path:
    resolved = source_path.expanduser().resolve()
    return resolved.with_name(f"{resolved.name}{_BUNDLE_SUFFIX}")


def browser_pdf_bundle_manifest_path(source_path: Path) -> Path:
    return browser_pdf_bundle_dir(source_path) / _MANIFEST_NAME


def clear_browser_pdf_bundle(source_path: Path) -> None:
    bundle_dir = browser_pdf_bundle_dir(source_path)
    if not bundle_dir.exists():
        return
    for path in sorted(bundle_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue
    try:
        bundle_dir.rmdir()
    except OSError:
        pass


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_browser_pdf_bundle(source_path: Path) -> dict[str, Any] | None:
    resolved = source_path.expanduser().resolve()
    manifest_path = browser_pdf_bundle_manifest_path(resolved)
    if not manifest_path.exists():
        return None
    payload = _load_manifest(manifest_path)
    if not payload:
        return None
    expected_source_path = str(payload.get("source_path", "") or "").strip()
    if expected_source_path and expected_source_path != str(resolved):
        return None
    source_stat = resolved.stat() if resolved.exists() else None
    expected_size = int(payload.get("source_size_bytes", 0) or 0)
    expected_mtime_ns = int(payload.get("source_mtime_ns", 0) or 0)
    if source_stat is not None:
        if expected_size > 0 and int(source_stat.st_size) != expected_size:
            return None
        if expected_mtime_ns > 0 and int(source_stat.st_mtime_ns) != expected_mtime_ns:
            return None
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        return None
    return payload


def browser_pdf_bundle_page_count(source_path: Path) -> int | None:
    payload = load_browser_pdf_bundle(source_path)
    if payload is None:
        return None
    try:
        page_count = int(payload.get("page_count", 0) or 0)
    except (TypeError, ValueError):
        return None
    return page_count if page_count > 0 else None


def browser_pdf_bundle_page_image_path(source_path: Path, page_number: int) -> Path | None:
    payload = load_browser_pdf_bundle(source_path)
    if payload is None:
        return None
    try:
        target_page = int(page_number)
    except (TypeError, ValueError):
        return None
    bundle_dir = browser_pdf_bundle_dir(source_path)
    for item in payload.get("pages", []):
        if not isinstance(item, dict):
            continue
        try:
            item_page = int(item.get("page_number", 0) or 0)
        except (TypeError, ValueError):
            continue
        if item_page != target_page:
            continue
        rel_path = str(item.get("image_path", "") or "").strip()
        if not rel_path:
            return None
        page_path = (bundle_dir / rel_path).expanduser().resolve()
        return page_path if page_path.exists() else None
    return None


def write_browser_pdf_bundle(
    *,
    source_path: Path,
    page_count: int,
    pages: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    resolved = source_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Source file must exist before bundling: {resolved}")
    if int(page_count) <= 0:
        raise ValueError("Browser PDF bundle page_count must be >= 1.")

    bundle_dir = browser_pdf_bundle_dir(resolved)
    pages_dir = bundle_dir / _PAGES_SUBDIR
    bundle_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    written_pages: list[dict[str, Any]] = []
    seen_page_numbers: set[int] = set()
    for item in pages:
        if not isinstance(item, dict):
            raise ValueError("Browser PDF bundle page descriptors must be objects.")
        try:
            page_number = int(item.get("page_number", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("Browser PDF bundle page number must be an integer.") from exc
        if page_number <= 0:
            raise ValueError("Browser PDF bundle page number must be >= 1.")
        if page_number in seen_page_numbers:
            raise ValueError(f"Duplicate browser PDF bundle page number: {page_number}")
        image_bytes = item.get("image_bytes")
        if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
            raise ValueError(f"Browser PDF bundle page {page_number} is missing image bytes.")
        mime_type = str(item.get("mime_type", "") or "").strip().lower() or "image/png"
        suffix = ".png" if mime_type == "image/png" else ".jpg" if mime_type in {"image/jpeg", "image/jpg"} else ".bin"
        page_path = pages_dir / f"page_{page_number:04d}{suffix}"
        page_path.write_bytes(bytes(image_bytes))
        written_pages.append(
            {
                "page_number": page_number,
                "image_path": str(page_path.relative_to(bundle_dir)).replace("\\", "/"),
                "mime_type": mime_type,
                "width_px": int(item.get("width_px", 0) or 0),
                "height_px": int(item.get("height_px", 0) or 0),
                "size_bytes": int(page_path.stat().st_size),
            }
        )
        seen_page_numbers.add(page_number)

    if len(written_pages) != int(page_count):
        raise ValueError(
            f"Browser PDF bundle expected {int(page_count)} pages but received {len(written_pages)}."
        )
    written_pages.sort(key=lambda item: int(item["page_number"]))

    source_stat = resolved.stat()
    manifest = {
        "version": 1,
        "created_at": _utc_now_iso(),
        "source_path": str(resolved),
        "source_name": resolved.name,
        "source_size_bytes": int(source_stat.st_size),
        "source_mtime_ns": int(source_stat.st_mtime_ns),
        "page_count": int(page_count),
        "pages": written_pages,
    }
    manifest_path = browser_pdf_bundle_manifest_path(resolved)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


__all__ = [
    "browser_pdf_bundle_dir",
    "browser_pdf_bundle_manifest_path",
    "browser_pdf_bundle_page_count",
    "browser_pdf_bundle_page_image_path",
    "clear_browser_pdf_bundle",
    "load_browser_pdf_bundle",
    "write_browser_pdf_bundle",
]
