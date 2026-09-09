"""Hash-bound structured page publication; the commit manifest is written last.

TXT remains compatible with the accepted writer. The caller owns the run and
checkpoint lock, validates source/protocol policy before dispatch, and marks
DONE only after publication succeeds. This module neither calls providers nor
deletes old evidence. Privacy cleanup is a separate, explicitly recorded step.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any

from .document_structure import PageStructure, StructureBlock, text_sha256, validate_page_structure

_HASH = re.compile(r"[a-f0-9]{64}\Z")
_PROTOCOL = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
_MAX_COMMIT_BYTES = 64 * 1024
_VERSION = 2


class StructuredArtifactError(ValueError):
    """Incomplete or incompatible local evidence, with content-free diagnostics."""


class StructuredArtifactCancelled(StructuredArtifactError):
    """Publication stopped before its logical completion marker."""


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise StructuredArtifactError("invalid_structured_json") from exc


def _hash_value(value: Any) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def normalize_protocol_identity(value: Mapping[str, Any] | None) -> dict[str, str]:
    """Empty identity means historical TXT; nonempty identities must be explicit."""
    if value is None or value == {}:
        return {}
    if (not isinstance(value, Mapping) or set(value) != {"protocol", "fingerprint"}
            or not isinstance(value["protocol"], str) or not _PROTOCOL.fullmatch(value["protocol"])
            or value["protocol"] == "legacy_text_v1" or not _hash_value(value["fingerprint"])):
        raise StructuredArtifactError("invalid_protocol_identity")
    return dict(value)


def _names(number: int) -> dict[str, str]:
    if type(number) is not int or number < 1:
        raise StructuredArtifactError("invalid_artifact_page")
    stem = f"page_{number:04d}"
    return {"text": stem + ".txt", "source": stem + ".source_structure.json",
            "target": stem + ".structure.json", "commit": stem + ".commit.json"}


def _duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StructuredArtifactError("duplicate_artifact_json_key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise StructuredArtifactError("nonfinite_artifact_json")


def _decode(content: bytes) -> Any:
    try:
        return json.loads(content.decode("utf-8"), object_pairs_hook=_duplicates,
                          parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise StructuredArtifactError("invalid_artifact_json") from exc


def _page(value: Any) -> dict:
    raw = value.to_dict() if isinstance(value, PageStructure) else deepcopy(value)
    if (not isinstance(raw, dict) or set(raw) - set(PageStructure.__dataclass_fields__)
            or not isinstance(raw.get("blocks"), list)
            or any(not isinstance(row, dict) or set(row) - set(StructureBlock.__dataclass_fields__)
                   for row in raw["blocks"])):
        # Do not silently discard a new schema field and certify reduced proof.
        raise StructuredArtifactError("unsupported_structure_fields")
    try:
        return validate_page_structure(raw).to_dict()
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise StructuredArtifactError("invalid_structure_evidence") from exc


def _validated_pair(source_structure, translated_structure, translated_text: str) -> tuple[dict, dict]:
    source, target = _page(source_structure), _page(translated_structure)
    source_text = "\n".join(row["text"] for row in source["blocks"])
    target_text = "\n".join(row["text"] for row in target["blocks"])
    try:
        source_hash, target_hash = text_sha256(source_text), text_sha256(target_text)
    except UnicodeError as exc:
        raise StructuredArtifactError("invalid_structure_text_encoding") from exc
    if (not isinstance(translated_text, str) or source["translation_sha256"] is not None
            or not _hash_value(source["source_file_sha256"])
            or source["source_sha256"] != source_hash
            or source["source_text_sha256"] != source["source_sha256"]
            or target_text != translated_text or target["translation_sha256"] != target_hash):
        raise StructuredArtifactError("source_target_text_binding_failed")
    exempt = {"blocks", "translation_sha256", "metadata"}
    if ({key: value for key, value in source.items() if key not in exempt}
            != {key: value for key, value in target.items() if key not in exempt}
            or len(source["blocks"]) != len(target["blocks"])):
        raise StructuredArtifactError("source_target_identity_mismatch")
    for left, right in zip(source["blocks"], target["blocks"]):
        if ({key: value for key, value in left.items() if key != "text"}
                != {key: value for key, value in right.items() if key != "text"}
                or bool(left["text"].strip()) != bool(right["text"].strip())):
            raise StructuredArtifactError("source_target_block_mismatch")
    if any(key not in target["metadata"] or target["metadata"][key] != value
           for key, value in source["metadata"].items()):
        raise StructuredArtifactError("source_metadata_binding_failed")
    return source, target


def _page_result(value: Any) -> dict | None:
    """Retain the already-paid outcome so a commit-before-DONE crash is recoverable.

    No provider is consulted here. The workflow supplies its existing diagnostic
    metadata, never raw responses or document text. None keeps old callers
    compatible but cannot authorize automatic orphan-commit recovery.
    """
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {"usage", "image_used", "retry_used", "metadata"}
            or type(value["image_used"]) is not bool or type(value["retry_used"]) is not bool
            or not isinstance(value["usage"], dict) or not isinstance(value["metadata"], dict)):
        raise StructuredArtifactError("invalid_committed_page_result")
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 32 or count > 10000:
            raise StructuredArtifactError("oversized_committed_page_result")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise StructuredArtifactError("invalid_committed_page_result")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in (str, bool, int, float):
            raise StructuredArtifactError("invalid_committed_page_result")
    if len(_json(value)) > _MAX_COMMIT_BYTES // 2:
        raise StructuredArtifactError("oversized_committed_page_result")
    return deepcopy(value)


def validate_commit_record(record: Any, *, page_number: int | None = None,
                           protocol_identity: Mapping[str, Any] | None = None,
                           page_fingerprint: str | None = None) -> dict:
    """Validate content-free checkpoint evidence, not existence of its artifacts."""
    keys = {"version", "page_number", "protocol_identity", "page_fingerprint", "source_file_sha256",
            "source_sha256", "translation_sha256", "artifacts", "bundle_sha256"}
    if isinstance(record, dict) and record.get("version") == _VERSION:
        keys.add("page_result")
    if (not isinstance(record, dict) or set(record) != keys
            or type(record["version"]) is not int or record["version"] not in (1, _VERSION)):
        raise StructuredArtifactError("invalid_structured_commit")
    if record["version"] == _VERSION:
        _page_result(record["page_result"])
    names = _names(record["page_number"])
    identity = normalize_protocol_identity(record["protocol_identity"])
    if (not identity or any(not _hash_value(record[key]) for key in
            ("page_fingerprint", "source_file_sha256", "source_sha256", "translation_sha256", "bundle_sha256"))
            or not isinstance(record["artifacts"], dict) or set(record["artifacts"]) != {"text", "source", "target"}):
        raise StructuredArtifactError("invalid_structured_commit")
    for kind, item in record["artifacts"].items():
        if (not isinstance(item, dict) or set(item) != {"name", "sha256", "bytes"}
                or item["name"] != names[kind] or not _hash_value(item["sha256"])
                or type(item["bytes"]) is not int or not 0 <= item["bytes"] <= _MAX_ARTIFACT_BYTES):
            raise StructuredArtifactError("invalid_commit_artifact")
    if _hash(_json({key: value for key, value in record.items() if key != "bundle_sha256"})) != record["bundle_sha256"]:
        raise StructuredArtifactError("invalid_commit_digest")
    if (page_number is not None and record["page_number"] != page_number
            or protocol_identity is not None and identity != normalize_protocol_identity(protocol_identity)
            or page_fingerprint is not None and record["page_fingerprint"] != page_fingerprint):
        raise StructuredArtifactError("structured_commit_identity_mismatch")
    return deepcopy(record)


def _read_file(path: Path, *, maximum: int = _MAX_ARTIFACT_BYTES) -> bytes:
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400
                or before.st_size > maximum):
            raise StructuredArtifactError("unsafe_or_oversized_artifact")
        with path.open("rb") as handle:
            content = handle.read(maximum + 1)
            after = os.fstat(handle.fileno())
        final = path.lstat()
        snapshot = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        if len(content) > maximum or snapshot(before) != snapshot(after) or snapshot(before) != snapshot(final):
            raise StructuredArtifactError("artifact_changed_during_read")
        return content
    except OSError as exc:
        raise StructuredArtifactError("structured_artifact_unavailable") from exc


def _validate_files(folder: Path, record: dict) -> None:
    contents = {}
    for kind, item in record["artifacts"].items():
        content = _read_file(folder / item["name"])
        if len(content) != item["bytes"] or _hash(content) != item["sha256"]:
            raise StructuredArtifactError("structured_artifact_hash_mismatch")
        contents[kind] = content
    try:
        text = contents["text"].decode("utf-8")
    except UnicodeError as exc:
        raise StructuredArtifactError("invalid_translation_encoding") from exc
    source, target = _validated_pair(_decode(contents["source"]), _decode(contents["target"]), text)
    if (source["page_number"] != record["page_number"] or source["source_file_sha256"] != record["source_file_sha256"]
            or source["source_sha256"] != record["source_sha256"] or target["translation_sha256"] != record["translation_sha256"]):
        raise StructuredArtifactError("commit_source_binding_mismatch")


def validate_structured_page(pages_dir: Path, page_number: int, *,
                             protocol_identity: Mapping[str, Any] | None = None,
                             page_fingerprint: str | None = None,
                             expected_commit: dict | None = None) -> dict:
    """Read-only DONE/resume proof; a lone TXT or deliberately purged page fails."""
    path = Path(pages_dir) / _names(page_number)["commit"]
    content = _read_file(path, maximum=_MAX_COMMIT_BYTES)
    record = validate_commit_record(_decode(content), page_number=page_number,
        protocol_identity=protocol_identity, page_fingerprint=page_fingerprint)
    if expected_commit is not None:
        expected = validate_commit_record(expected_commit, page_number=page_number,
            protocol_identity=protocol_identity, page_fingerprint=page_fingerprint)
        if record != expected:
            raise StructuredArtifactError("checkpoint_commit_mismatch")
    _validate_files(Path(pages_dir), record)
    if _read_file(path, maximum=_MAX_COMMIT_BYTES) != content:
        raise StructuredArtifactError("commit_changed_during_read")
    return record


def validate_structured_rebuild_page(pages_dir: Path, page_number: int, *,
                                     expected_commit: dict,
                                     protocol_identity: Mapping[str, Any] | None = None,
                                     page_fingerprint: str | None = None) -> tuple[dict, bool]:
    """Allow only a changed TXT in an explicitly requested local rebuild.

    The caller whitelists DONE checkpoint pages and supplies their original
    commit. Source, target and commit remain exact, including the original TXT
    proof reconstructed from the target blocks. The returned flag requires a
    manual-edit/layout review warning; it does not rebind or certify edited text.
    Resume and DONE use validate_structured_page, never this exception.
    """
    folder = Path(pages_dir)
    path = folder / _names(page_number)["commit"]
    expected = validate_commit_record(expected_commit, page_number=page_number,
        protocol_identity=protocol_identity, page_fingerprint=page_fingerprint)
    content = _read_file(path, maximum=_MAX_COMMIT_BYTES)
    record = validate_commit_record(_decode(content), page_number=page_number,
        protocol_identity=protocol_identity, page_fingerprint=page_fingerprint)
    if record != expected:
        raise StructuredArtifactError("checkpoint_commit_mismatch")
    contents = {}
    for kind, item in record["artifacts"].items():
        value = _read_file(folder / item["name"])
        if kind != "text" and (len(value) != item["bytes"] or _hash(value) != item["sha256"]):
            raise StructuredArtifactError("structured_artifact_hash_mismatch")
        contents[kind] = value
    try:
        contents["text"].decode("utf-8")
    except UnicodeError as exc:
        raise StructuredArtifactError("invalid_translation_encoding") from exc
    target_payload = _page(_decode(contents["target"]))
    original_text = "\n".join(block["text"] for block in target_payload["blocks"])
    source, target = _validated_pair(_decode(contents["source"]), target_payload, original_text)
    original_bytes = original_text.encode("utf-8")
    text_record = record["artifacts"]["text"]
    if (len(original_bytes) != text_record["bytes"] or _hash(original_bytes) != text_record["sha256"]
            or source["page_number"] != record["page_number"]
            or source["source_file_sha256"] != record["source_file_sha256"]
            or source["source_sha256"] != record["source_sha256"]
            or target["translation_sha256"] != record["translation_sha256"]):
        raise StructuredArtifactError("commit_source_binding_mismatch")
    if _read_file(path, maximum=_MAX_COMMIT_BYTES) != content:
        raise StructuredArtifactError("commit_changed_during_read")
    return record, contents["text"] != original_bytes


def _publish_file_exclusive(path: Path, content: bytes) -> None:
    """Publish a flushed sibling without replacing pre-existing user evidence.

    Windows rename fails if its target exists and needs no hard-link support.
    On POSIX, where rename replaces its target, use an exclusive same-directory
    link instead. Never fall back to an unsafe exists + replace race.
    """
    descriptor, temporary = tempfile.mkstemp(prefix=".structured-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            os.rename(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def publish_structured_page(pages_dir: Path, *, source_structure, translated_structure,
                            translated_text: str, protocol_identity: Mapping[str, Any],
                            page_fingerprint: str, cancelled: Callable[[], bool] | None = None,
                            evidence_guard: Callable[[], None] | None = None,
                            page_result: dict | None = None) -> dict:
    """Commit one validated page last; never overwrite partial/stale old files.

    Keep these artifacts available through assembly even when retention is off.
    After successful final assembly the caller records purged evidence and owns
    the privacy cleanup. Rebuild and this helper never recreate missing proof.
    """
    def check_cancelled():
        if cancelled is not None and cancelled():
            raise StructuredArtifactCancelled("structured_publication_cancelled")

    check_cancelled()
    if evidence_guard is not None:
        evidence_guard()
    identity = normalize_protocol_identity(protocol_identity)
    if not identity or not _hash_value(page_fingerprint):
        raise StructuredArtifactError("invalid_structured_publication_identity")
    source, target = _validated_pair(source_structure, translated_structure, translated_text)
    names = _names(source["page_number"])
    contents = {"text": translated_text.encode("utf-8"), "source": _json(source), "target": _json(target)}
    if any(len(content) > _MAX_ARTIFACT_BYTES for content in contents.values()):
        raise StructuredArtifactError("structured_artifact_too_large")
    record = {"version": _VERSION, "page_number": source["page_number"], "protocol_identity": identity,
              "page_result": _page_result(page_result),
              "page_fingerprint": page_fingerprint, "source_file_sha256": source["source_file_sha256"],
              "source_sha256": source["source_sha256"], "translation_sha256": target["translation_sha256"],
              "artifacts": {kind: {"name": names[kind], "sha256": _hash(content), "bytes": len(content)}
                            for kind, content in contents.items()}}
    record["bundle_sha256"] = _hash(_json(record))
    validate_commit_record(record)
    folder = Path(pages_dir)
    if any((folder / name).exists() or (folder / name).is_symlink() for name in names.values()):
        # Idempotent replay of the exact bundle is safe; differing or partial
        # prior artifacts are not authorization to erase earlier legal work.
        return validate_structured_page(folder, source["page_number"], protocol_identity=identity,
                                        page_fingerprint=page_fingerprint, expected_commit=record)
    check_cancelled()
    folder.mkdir(parents=True, exist_ok=True)
    for kind, content in contents.items():
        check_cancelled()
        _publish_file_exclusive(folder / names[kind], content)
    _validate_files(folder, record)
    check_cancelled()
    if evidence_guard is not None:
        evidence_guard()
    _publish_file_exclusive(folder / names["commit"], _json(record))
    return validate_structured_page(folder, source["page_number"], protocol_identity=identity,
                                    page_fingerprint=page_fingerprint, expected_commit=record)
