"""Local, fail-closed staging for the app's generated honorarios DOCX exports.

This module does not start Word, alter document contents, or establish trust in
an arbitrary uploaded document. Callers must use app-generated DOCX inputs and
keep the renderer's security protections enabled. A staged source has exactly
the original bytes, including relationships and security-related metadata.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


_DOCX_MAIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_HYPERLINK_RELATIONSHIPS = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/hyperlink",
}
_EXTERNAL_FIELD = re.compile(r"^\s*(?:INCLUDETEXT|INCLUDEPICTURE|DDEAUTO|DDE|LINK|DATABASE|RD)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _FileSnapshot:
    identity: tuple[int, int, int, int, int]
    digest: bytes


def _reject_link(path: Path, label: str) -> None:
    """Reject file links without resolving them to an unintended target."""
    try:
        details = path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise ValueError(f"Cannot inspect {label} file.") from None
    if stat.S_ISLNK(details.st_mode) or (
        getattr(details, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    ):
        raise ValueError(f"The {label} file must not be a link or reparse point.")
    if not stat.S_ISREG(details.st_mode):
        raise ValueError(f"The {label} must be a regular file.")


def _identity(details: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        details.st_dev,
        details.st_ino,
        details.st_size,
        details.st_mtime_ns,
        details.st_ctime_ns,
    )


def _read_snapshot(path: Path, label: str) -> tuple[_FileSnapshot, bytes]:
    _reject_link(path, label)
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(f"The {label} must be a regular file.")
            data = handle.read()
            after = os.fstat(handle.fileno())
        current = path.stat()
    except OSError:
        raise ValueError(f"Cannot read {label} file; it may be missing or locked.") from None
    if _identity(before) != _identity(after) or _identity(after) != _identity(current):
        raise ValueError(f"The {label} file changed while being read.")
    return _FileSnapshot(_identity(after), hashlib.sha256(data).digest()), data


def _optional_snapshot(path: Path) -> _FileSnapshot | None:
    _reject_link(path, "destination PDF")
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise ValueError("Cannot inspect destination PDF file.") from None
    return _read_snapshot(path, "destination PDF")[0]


def _reject_origin_mark(path: Path) -> None:
    """Never remove Windows origin protection by copying a marked document.

    An app-generated honorarios document does not need a Zone.Identifier. We
    conservatively reject any such stream, even empty/local-zone metadata, and
    fail closed if its presence cannot be checked. No metadata is removed or
    rewritten, and its potentially private referrer values are never read.
    """
    if os.name != "nt":
        return
    try:
        with Path(str(path) + ":Zone.Identifier").open("rb"):
            pass
    except FileNotFoundError:
        return
    except OSError:
        raise ValueError("Cannot verify source DOCX origin security; export was not started.") from None
    raise ValueError("The source DOCX has origin security metadata and cannot be staged for unattended export.")


def _validate_relationships(root: ElementTree.Element) -> None:
    for relation in root:
        target = relation.attrib.get("Target", "").strip()
        external = (
            relation.attrib.get("TargetMode", "").casefold() == "external"
            or bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target))
            or target.startswith(("\\", "//"))
        )
        if external and relation.attrib.get("Type") not in _HYPERLINK_RELATIONSHIPS:
            raise ValueError("The source DOCX references external content; unattended export was not started.")


def _validate_field_instructions(root: ElementTree.Element) -> None:
    """Reject file/network-loading field codes, including split Word runs."""
    def check(instruction: str) -> None:
        if _EXTERNAL_FIELD.search(instruction):
            raise ValueError("The source DOCX references external content; unattended export was not started.")

    fields: list[tuple[list[str], bool]] = []
    for element in root.iter():
        if element.tag == f"{{{_WORD_NAMESPACE}}}fldSimple":
            check(element.attrib.get(f"{{{_WORD_NAMESPACE}}}instr", ""))
        elif element.tag == f"{{{_WORD_NAMESPACE}}}fldChar":
            kind = element.attrib.get(f"{{{_WORD_NAMESPACE}}}fldCharType", "")
            if kind == "begin":
                fields.append(([], True))
            elif kind == "separate" and fields:
                parts, _ = fields[-1]
                check("".join(parts))
                fields[-1] = (parts, False)
            elif kind == "end" and fields:
                check("".join(fields.pop()[0]))
        elif element.tag == f"{{{_WORD_NAMESPACE}}}instrText":
            if fields and fields[-1][1]:
                fields[-1][0].append(element.text or "")
            else:
                check(element.text or "")
    for remaining, _ in fields:
        check("".join(remaining))


def _validate_docx(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as package:
            entries = package.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)):
                raise ValueError("The source DOCX contains duplicate package entries.")
            if any(entry.flag_bits & 1 for entry in entries):
                raise ValueError("The source DOCX must not be encrypted.")
            if any("vba" in name.casefold() for name in names):
                raise ValueError("The source DOCX must not contain macros.")
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise ValueError("The source is not a supported DOCX document package.")
            content_types = ElementTree.fromstring(package.read("[Content_Types].xml"))
            main_types = [
                item.attrib.get("ContentType", "")
                for item in content_types.findall(f"{{{_CONTENT_TYPES_NAMESPACE}}}Override")
                if item.attrib.get("PartName") == "/word/document.xml"
            ]
            if main_types != [_DOCX_MAIN_CONTENT_TYPE] or any(
                "macroenabled" in item.attrib.get("ContentType", "").casefold()
                or "vba" in item.attrib.get("ContentType", "").casefold()
                for item in content_types
            ):
                raise ValueError("The source must be a non-macro DOCX document.")
            if package.testzip() is not None:
                raise ValueError("The source DOCX package is corrupt.")
            document = ElementTree.fromstring(package.read("word/document.xml"))
            if document.tag != f"{{{_WORD_NAMESPACE}}}document":
                raise ValueError("The source DOCX document structure is invalid.")
            for name in names:
                if name.endswith(".rels"):
                    _validate_relationships(ElementTree.fromstring(package.read(name)))
                elif name.endswith(".xml"):
                    _validate_field_instructions(ElementTree.fromstring(package.read(name)))
    except (OSError, zipfile.BadZipFile, RuntimeError, ElementTree.ParseError, KeyError, zlib.error):
        raise ValueError("The source DOCX package is invalid, corrupt, or encrypted.") from None


def _normalise_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def validate_pdf(path: str | Path, *, expected_text: str | None = None) -> None:
    """Require a complete, unencrypted PDF whose pages can all be read.

    Word's output must not need MuPDF repair. Optional expected text is useful
    for a synthetic export canary; its content is never included in errors.
    Validation is local and has no persistent MuPDF configuration side effects.
    """
    import fitz

    _, data = _read_snapshot(Path(path), "PDF")
    if not data:
        raise ValueError("The exported PDF is empty.")
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise ValueError("The exported PDF is invalid or truncated.")
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise ValueError("The exported PDF is corrupt or unreadable.") from None
    try:
        if not document.is_pdf or document.is_repaired:
            raise ValueError("The exported PDF is corrupt or requires repair.")
        if document.is_encrypted or document.needs_pass or document.metadata.get("encryption"):
            raise ValueError("The exported PDF must not be encrypted.")
        if document.page_count < 1:
            raise ValueError("The exported PDF contains no pages.")
        page_text: list[str] = []
        for page_number in range(document.page_count):
            try:
                page = document.load_page(page_number)
                dimensions_valid = not page.rect.is_empty and not page.rect.is_infinite
                text = page.get_text()
            except Exception:
                raise ValueError("The exported PDF contains unreadable pages.") from None
            if not dimensions_valid:
                raise ValueError("The exported PDF has invalid page dimensions.")
            page_text.append(text)
        if expected_text and _normalise_text(expected_text) not in _normalise_text("\n".join(page_text)):
            raise ValueError("The exported PDF is missing the expected text.")
    except ValueError:
        raise
    except Exception:
        raise ValueError("The exported PDF contains unreadable pages.") from None
    finally:
        document.close()


@contextmanager
def staged_pdf_export(
    docx_path: str | Path,
    pdf_path: str | Path,
    *,
    expected_text: str | None = None,
) -> Iterator[tuple[Path, Path]]:
    """Yield unique DOCX/PDF paths and publish only on a successful exit.

    The renderer must finish and close its staged files before exiting the
    context. Raise on renderer failure, including ambiguous timeouts. An old
    destination cannot stand in for the missing new output. Existing targets
    and original DOCX bytes remain intact on validation/publication failures.

    Callers serialize their exports; source/destination snapshots also detect
    outside edits immediately before the atomic replacement. Portable filesystems
    do not expose a compare-and-swap replacement against arbitrary outside editors.
    """
    source = Path(docx_path).absolute()
    destination = Path(pdf_path).absolute()
    if source.suffix.casefold() != ".docx":
        raise ValueError("The source must have a DOCX extension.")
    if destination.suffix.casefold() != ".pdf":
        raise ValueError("The destination must have a PDF extension.")
    if ":" in source.name or ":" in destination.name:
        raise ValueError("DOCX and PDF paths must identify files, not alternate data streams.")
    _reject_link(source, "source DOCX")
    _reject_link(destination, "destination PDF")
    _reject_origin_mark(source)
    try:
        if source.resolve() == destination.resolve() or (
            destination.exists() and source.samefile(destination)
        ):
            raise ValueError("The source DOCX and destination PDF must not be the same file.")
        if not destination.parent.is_dir():
            raise ValueError("The destination PDF directory does not exist.")
        parent_identity = destination.parent.stat()
    except OSError:
        raise ValueError("Cannot inspect the source DOCX or destination PDF paths.") from None

    source_snapshot, source_bytes = _read_snapshot(source, "source DOCX")
    destination_snapshot = _optional_snapshot(destination)
    try:
        staging = tempfile.TemporaryDirectory(
            prefix=".honorarios-pdf-", dir=destination.parent, ignore_cleanup_errors=True
        )
    except OSError:
        raise ValueError("Cannot create the PDF export staging directory.") from None
    with staging as staging_name:
        staged_source = Path(staging_name) / "source.docx"
        staged_output = Path(staging_name) / "output.pdf"
        try:
            staged_source.write_bytes(source_bytes)
        except OSError:
            raise ValueError("Cannot stage the source DOCX for PDF export.") from None
        _validate_docx(staged_source)
        _reject_origin_mark(source)
        yield staged_source, staged_output
        candidate_snapshot = _read_snapshot(staged_output, "staged PDF")[0]
        validate_pdf(staged_output, expected_text=expected_text)
        try:
            current_parent = destination.parent.stat()
            if (current_parent.st_dev, current_parent.st_ino) != (
                parent_identity.st_dev,
                parent_identity.st_ino,
            ):
                raise ValueError("The destination PDF directory changed during export.")
            _reject_origin_mark(source)
            if _read_snapshot(source, "source DOCX")[0] != source_snapshot:
                raise ValueError("The source DOCX changed during PDF export; no PDF was replaced.")
            if _read_snapshot(staged_source, "staged DOCX")[0].digest != source_snapshot.digest:
                raise ValueError("The staged DOCX changed during PDF export; no PDF was replaced.")
            if _optional_snapshot(destination) != destination_snapshot:
                raise ValueError("The destination PDF changed during export; it was not replaced.")
            if _read_snapshot(staged_output, "staged PDF")[0] != candidate_snapshot:
                raise ValueError("The staged PDF changed after validation; no PDF was replaced.")
            os.replace(staged_output, destination)
        except OSError:
            raise ValueError("Cannot publish the verified PDF; the destination may be locked.") from None
