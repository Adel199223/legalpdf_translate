"""Browser-generated PDF page-image bundles for browser-first workflows."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

_BUNDLE_SUFFIX = ".browser_pdf_bundle"
_MANIFEST_NAME = "manifest.json"
_PAGES_SUBDIR = "pages"
_PAGE_PATH = re.compile(r"(?:pages|generations/[0-9a-f]{32})/page_([0-9]{4})\.(?:png|jpg|bin)")


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
        if browser_pdf_bundle_dir(resolved).exists():
            raise ValueError("Browser PDF bundle manifest is missing.")
        return None
    payload = _load_manifest(manifest_path)
    if not payload:
        raise ValueError("Browser PDF bundle manifest is invalid.")
    if type(payload.get("version")) is not int or payload["version"] not in {1, 2}:
        raise ValueError("Browser PDF bundle version is unsupported.")
    expected_source_path = str(payload.get("source_path", "") or "").strip()
    if expected_source_path and expected_source_path != str(resolved):
        raise ValueError("Browser PDF bundle source path changed.")
    source_stat = resolved.stat() if resolved.exists() else None
    expected_size = int(payload.get("source_size_bytes", 0) or 0)
    expected_mtime_ns = int(payload.get("source_mtime_ns", 0) or 0)
    if source_stat is not None:
        if expected_size > 0 and int(source_stat.st_size) != expected_size:
            raise ValueError("Browser PDF bundle source size changed.")
        if expected_mtime_ns > 0 and int(source_stat.st_mtime_ns) != expected_mtime_ns:
            raise ValueError("Browser PDF bundle source timestamp changed.")
    if payload.get("version") == 2:
        expected_hash = payload.get("source_sha256")
        if (type(expected_hash) is not str or len(expected_hash) != 64 or source_stat is None
                or _file_sha256(resolved) != expected_hash):
            raise ValueError("Browser PDF bundle source hash changed.")
    pages = payload.get("pages")
    page_count = payload.get("page_count")
    if (type(page_count) is not int or not 1 <= page_count <= 500
            or not isinstance(pages, list) or len(pages) != page_count):
        raise ValueError("Browser PDF bundle pages are invalid.")
    owned_pages = [item.get("page_number") if type(item) is dict else None for item in pages]
    if (any(type(number) is not int for number in owned_pages)
            or sorted(owned_pages) != list(range(1, page_count + 1))):
        raise ValueError("Browser PDF bundle page ownership is invalid.")
    return payload


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def browser_pdf_bundle_page_text(source_path: Path, page_number: int) -> dict[str, Any] | None:
    payload = load_browser_pdf_bundle(source_path)
    if payload is None or payload.get("version") == 1:
        return None
    if payload.get("version") != 2:
        raise ValueError("Browser PDF bundle version is unsupported.")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("Browser PDF text page number is invalid.")
    matches = [item for item in payload["pages"] if type(item) is dict and item.get("page_number") == page_number]
    if len(matches) != 1:
        raise ValueError("Browser PDF text page ownership is invalid.")
    item = matches[0]
    expected_hash = item.get("text_sha256")
    image_path = item.get("image_path")
    if type(image_path) is not str or not _PAGE_PATH.fullmatch(image_path):
        raise ValueError("Browser PDF text page image path is invalid.")
    if int(_PAGE_PATH.fullmatch(image_path).group(1)) != page_number:
        raise ValueError("Browser PDF text page ownership is invalid.")
    expected_path = f"{image_path.rsplit('/', 1)[0]}/page_{page_number:04d}.text.json"
    if item.get("text_path") != expected_path or type(expected_hash) is not str or len(expected_hash) != 64:
        raise ValueError("Browser PDF text sidecar is missing.")
    path = browser_pdf_bundle_dir(source_path) / expected_path
    if not path.is_file() or path.stat().st_size > 4_000_000:
        raise ValueError("Browser PDF text sidecar is missing or oversized.")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("Browser PDF text sidecar changed.")
    try:
        evidence = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Browser PDF text sidecar is invalid.") from exc
    from .browser_pdf_text import validate_browser_page_text
    return validate_browser_page_text(evidence, page_number=page_number)


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
        rel_path = item.get("image_path")
        if type(rel_path) is not str or not _PAGE_PATH.fullmatch(rel_path):
            return None
        if int(_PAGE_PATH.fullmatch(rel_path).group(1)) != target_page:
            return None
        page_path = (bundle_dir / rel_path).expanduser().resolve()
        if not page_path.is_file():
            return None
        if payload.get("version") == 2:
            expected_hash = item.get("image_sha256")
            if type(expected_hash) is not str or _file_sha256(page_path) != expected_hash:
                raise ValueError("Browser PDF page image changed.")
        return page_path
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
    if type(page_count) is not int or not 1 <= page_count <= 500:
        raise ValueError("Browser PDF bundle page_count must be between 1 and 500.")

    supplied_pages = list(islice(pages, page_count + 1))
    if len(supplied_pages) != page_count:
        raise ValueError("Browser PDF bundle page count does not match its descriptors.")
    page_numbers: set[int] = set()
    text_presence: list[bool] = []
    prepared: list[tuple[int, bytes, str, int, int, bytes | None]] = []
    for item in supplied_pages:
        if type(item) is not dict or type(item.get("page_number")) is not int:
            raise ValueError("Browser PDF bundle page descriptors require integer page numbers.")
        number = item["page_number"]
        if not 1 <= number <= page_count or number in page_numbers:
            raise ValueError("Browser PDF bundle page ownership is invalid.")
        page_numbers.add(number)
        image = item.get("image_bytes")
        if type(image) not in (bytes, bytearray) or not 0 < len(image) <= 32_000_000:
            raise ValueError("Browser PDF bundle page image is missing or oversized.")
        mime_type = str(item.get("mime_type", "") or "").strip().lower() or "image/png"
        if mime_type not in {"image/png", "image/jpeg", "image/jpg"}:
            raise ValueError("Browser PDF bundle page image type is unsupported.")
        width = item.get("width_px")
        height = item.get("height_px")
        if type(width) is not int or type(height) is not int or not (1 <= width <= 100_000 and 1 <= height <= 100_000):
            raise ValueError("Browser PDF bundle page dimensions are invalid.")
        text_presence.append("text_content" in item)
        raw_text = None
        if "text_content" in item:
            from .browser_pdf_text import validate_browser_page_text
            evidence = validate_browser_page_text(item["text_content"], page_number=number)
            raw_text = json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")
            if len(raw_text) > 4_000_000:
                raise ValueError("Browser PDF text sidecar is oversized.")
        prepared.append((number, bytes(image), mime_type, width, height, raw_text))
    if any(text_presence) and not all(text_presence):
        raise ValueError("Browser PDF text evidence must cover every bundled page.")

    source_stat = resolved.stat()
    source_hash = _file_sha256(resolved) if any(text_presence) else None
    bundle_dir = browser_pdf_bundle_dir(resolved)
    generation = uuid4().hex
    pages_dir = bundle_dir / "generations" / generation
    written_pages: list[dict[str, Any]] = []
    for page_number, image_bytes, mime_type, width, height, raw_text in prepared:
        suffix = ".png" if mime_type == "image/png" else ".jpg"
        image_name = f"page_{page_number:04d}{suffix}"
        written_pages.append(
            {
                "page_number": page_number,
                "image_path": f"generations/{generation}/{image_name}",
                "mime_type": mime_type,
                "width_px": width,
                "height_px": height,
                "size_bytes": len(image_bytes),
            }
        )
        if raw_text is not None:
            written_pages[-1]["image_sha256"] = hashlib.sha256(image_bytes).hexdigest()
            written_pages[-1]["text_path"] = f"generations/{generation}/page_{page_number:04d}.text.json"
            written_pages[-1]["text_sha256"] = hashlib.sha256(raw_text).hexdigest()
    written_pages.sort(key=lambda item: int(item["page_number"]))

    manifest = {
        "version": 2 if any(text_presence) else 1,
        "created_at": _utc_now_iso(),
        "source_path": str(resolved),
        "source_name": resolved.name,
        "source_size_bytes": int(source_stat.st_size),
        "source_mtime_ns": int(source_stat.st_mtime_ns),
        "page_count": int(page_count),
        "pages": written_pages,
    }
    if source_hash is not None:
        manifest["source_sha256"] = source_hash
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    # New data is unreachable until the manifest is replaced. An interrupted upload
    # leaves the prior manifest and all of its generation's files untouched.
    bundle_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=False)
    for page_number, image_bytes, mime_type, _width, _height, raw_text in prepared:
        suffix = ".png" if mime_type == "image/png" else ".jpg"
        (pages_dir / f"page_{page_number:04d}{suffix}").write_bytes(image_bytes)
        if raw_text is not None:
            (pages_dir / f"page_{page_number:04d}.text.json").write_bytes(raw_text)
    fresh_stat = resolved.stat()
    if (fresh_stat.st_size != source_stat.st_size or fresh_stat.st_mtime_ns != source_stat.st_mtime_ns
            or (source_hash is not None and _file_sha256(resolved) != source_hash)):
        raise ValueError("Browser PDF bundle source changed while bundling.")
    manifest_path = browser_pdf_bundle_manifest_path(resolved)
    temporary_manifest = bundle_dir / f".manifest-{generation}.tmp"
    temporary_manifest.write_bytes(manifest_bytes)
    os.replace(temporary_manifest, manifest_path)
    return manifest


__all__ = [
    "browser_pdf_bundle_dir",
    "browser_pdf_bundle_manifest_path",
    "browser_pdf_bundle_page_count",
    "browser_pdf_bundle_page_image_path",
    "browser_pdf_bundle_page_text",
    "clear_browser_pdf_bundle",
    "load_browser_pdf_bundle",
    "write_browser_pdf_bundle",
]
