"""Source-only visual and first-mention guidance for an ordinary primary page."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
import re

from .browser_pdf_bundle import (
    browser_pdf_bundle_manifest_path, browser_pdf_bundle_page_text, load_browser_pdf_bundle,
)


_VISUAL_GUIDANCE = (
    "The page image and the extracted text describe the same printed page. Match each field or "
    "passage to its printed location before translating. When extraction lists a field at a "
    "different position from its visible row, write it once at the visible row, without also "
    "copying it at the extraction position. Count actual printed occurrences. Preserve every "
    "genuinely repeated row, and both endpoints of an interval even when their dates are equal. "
    "An amount in figures followed by words in parentheses contains two source expressions. "
    "Translate the words and preserve the printed parentheses and punctuation. "
    "Apply approved terminology and the existing acronym convention across the selected "
    "document, including first-mention glosses. Preserve an expansion printed in the source. "
    "Do not guess a meaning or an occurrence that the available source does not establish."
)

_MAX_PDF_BYTES = 16 * 1024 * 1024
_MAX_MANIFEST_BYTES = 512 * 1024
_MAX_SELECTED_PAGES = 12
_MAX_PAGE_CHARS = 32_000
_MAX_HINTS = 12
_UPPERCASE = re.compile(r"(?<![\w./-])[A-Z]{2,12}(?![\w/-])")


def _uppercase_groups(text: str) -> Iterator[str]:
    if len(text) <= _MAX_PAGE_CHARS and "\ufffd" not in text and "\x00" not in text:
        yield from (match.group() for match in _UPPERCASE.finditer(text))


def _earlier_texts(pdf_path: Path, prior: Sequence[int], last_page: int) -> Iterator[str]:
    manifest = browser_pdf_bundle_manifest_path(pdf_path)
    if manifest.parent.exists():
        # The normal authenticated reader checks the PDF identity and text-sidecar hash.
        from .browser_pdf_text import ordered_browser_page_text

        if not manifest.is_file() or manifest.stat().st_size > _MAX_MANIFEST_BYTES:
            return
        bundle = load_browser_pdf_bundle(pdf_path)
        if bundle is None or bundle["version"] != 2 or last_page > bundle["page_count"]:
            return
        for number in prior:
            evidence = browser_pdf_bundle_page_text(pdf_path, number)
            if evidence is None:
                return
            items = evidence["items"]
            if len(items) > 2_000 or sum(len(item["text"]) for item in items) > _MAX_PAGE_CHARS:
                continue
            page = ordered_browser_page_text(evidence)
            if not page.extraction_failed and not page.fragmented:
                yield page.text
        return

    import fitz

    with fitz.open(pdf_path) as document:
        if (
            not document.is_pdf or document.needs_pass or document.is_repaired
            or last_page > len(document) or document.xref_length() > 16_000
        ):
            return
        for number in prior:
            page = document.load_page(number - 1)
            # Stay in the text layer. No rendering, OCR, images or model calls.
            if any(entry[0] == "ignore-text" for entry in page.get_bboxlog()):
                continue
            yield page.get_text("text", flags=fitz.TEXTFLAGS_TEXT)


def primary_visual_guidance(
    pdf_path: Path, page_number: int, selected_pages: Sequence[int], current_source_text: str
) -> str:
    """Supplement a primary image request. An unavailable hint never blocks translation."""
    if (
        type(page_number) is not int
        or type(current_source_text) is not str
        or not isinstance(selected_pages, Sequence)
        or isinstance(selected_pages, (str, bytes))
        or not 1 <= len(selected_pages) <= _MAX_SELECTED_PAGES
        or any(type(number) is not int or number < 1 for number in selected_pages)
        or len(set(selected_pages)) != len(selected_pages)
        or page_number not in selected_pages
    ):
        return _VISUAL_GUIDANCE
    prior = selected_pages[:selected_pages.index(page_number)]
    current = set(_uppercase_groups(current_source_text))
    if not prior or not current:
        return _VISUAL_GUIDANCE

    found: dict[str, None] = {}
    try:
        path = Path(pdf_path)
        if path.suffix.lower() != ".pdf" or not path.is_file() or path.stat().st_size > _MAX_PDF_BYTES:
            return _VISUAL_GUIDANCE
        for text in _earlier_texts(path, prior, max(selected_pages)):
            for group in _uppercase_groups(text):
                if group in current:
                    found[group] = None
                    if len(found) == _MAX_HINTS:
                        break
            if len(found) == _MAX_HINTS or len(found) == len(current):
                break
    except (OSError, RuntimeError, ValueError, TypeError, IndexError, ImportError):
        return _VISUAL_GUIDANCE
    if not found:
        return _VISUAL_GUIDANCE
    return (
        _VISUAL_GUIDANCE + "\nEarlier selected source text contains these exact uppercase strings "
        "also found on this page: " + ", ".join(found) + ". Treat them only as prior-mention "
        "hints. If the same acronym is confirmed in context, avoid a repeated discretionary "
        "first-use gloss. Other uppercase strings may be names or identifiers. An unlisted "
        "string has no first-use determination here. Follow explicit approved terminology."
    )
