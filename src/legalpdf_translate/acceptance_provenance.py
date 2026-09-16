"""Read-only physical evidence verification for separately approved acceptance.

This module never creates approvals, discovers credentials, or opens a transport.
Paths are explicit private inputs; exceptions expose labels, never document text.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from .budget_reservations import BudgetError, fingerprint


class AcceptanceProvenanceError(BudgetError):
    """The approved bytes do not describe the current dispatch environment."""


_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def canonical_run_config(config: Any) -> dict[str, Any]:
    """Bind every effective RunConfig field except the operational resume flag.

    Resume changes only restart orchestration; all translation, formatting,
    source and output configuration remains part of the approval identity.
    """
    value = asdict(config) if is_dataclass(config) and not isinstance(config, type) else config
    if not isinstance(value, Mapping):
        raise AcceptanceProvenanceError("Effective runtime configuration must be a mapping or dataclass.")

    def convert(item: Any) -> Any:
        if isinstance(item, Enum):
            return convert(item.value)
        if isinstance(item, Path):
            return str(item)
        if isinstance(item, Mapping):
            return {str(key): convert(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [convert(child) for child in item]
        return item

    result = {key: convert(item) for key, item in value.items() if key != "resume"}
    try:
        return json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise AcceptanceProvenanceError("Effective runtime configuration is not finite JSON.") from exc


def request_fingerprint(request: Mapping[str, Any]) -> str:
    """Match the transport identity; timeout is local and not API semantics."""
    try:
        return fingerprint({key: value for key, value in request.items() if key != "timeout"})
    except (TypeError, ValueError) as exc:
        raise AcceptanceProvenanceError("Final request must contain finite JSON values.") from exc


def _verified_file(value: Any, label: str, expected: str | None = None) -> bytes:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        raise AcceptanceProvenanceError(f"{label} requires an exact path and SHA-256.")
    digest = value["sha256"]
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest) or (expected and digest != expected):
        raise AcceptanceProvenanceError(f"{label} digest does not match the approved identity.")
    path = Path(str(value["path"]))
    if not path.is_absolute():
        raise AcceptanceProvenanceError(f"{label} requires an absolute physical path.")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AcceptanceProvenanceError(f"{label} is unavailable.") from exc
    if hashlib.sha256(raw).hexdigest() != digest:
        raise AcceptanceProvenanceError(f"{label} bytes changed after approval.")
    return raw


def verify_physical_provenance(
    provenance: Mapping[str, Any], *, source_sha256: str, execution_identity: Mapping[str, Any]
) -> None:
    """Rehash source, preference bytes and every file in both approved manifests."""
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "source", "code_manifest", "config_manifest", "preferences"
    }:
        raise AcceptanceProvenanceError("Complete physical acceptance provenance is required.")
    _verified_file(provenance["source"], "source", source_sha256)
    _verified_file(provenance["preferences"], "preferences", execution_identity["preferences_sha256"])
    for label in ("code_manifest", "config_manifest"):
        raw = _verified_file(provenance[label], label, execution_identity[f"{label}_sha256"])
        try:
            manifest = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise AcceptanceProvenanceError(f"{label} is not a valid file manifest.") from exc
        expected_fields = {"files"} if label == "code_manifest" else {"files", "runtime_config_sha256"}
        if not isinstance(manifest, dict) or set(manifest) != expected_fields:
            raise AcceptanceProvenanceError(f"{label} requires an explicit files list.")
        if label == "config_manifest" and (not isinstance(manifest["runtime_config_sha256"], str)
                or not _SHA256.fullmatch(manifest["runtime_config_sha256"])):
            raise AcceptanceProvenanceError("Config manifest requires an effective runtime configuration digest.")
        entries = manifest["files"]
        if not isinstance(entries, list) or not entries or len(entries) > 10000:
            raise AcceptanceProvenanceError(f"{label} files list is empty or invalid.")
        paths: set[Path] = set()
        for entry in entries:
            _verified_file(entry, f"{label} member")
            resolved = Path(entry["path"]).resolve()
            if resolved in paths:
                raise AcceptanceProvenanceError(f"{label} contains a duplicate file.")
            paths.add(resolved)
        if label == "code_manifest":
            _verify_executing_package_membership(paths)


def _verify_executing_package_membership(manifest_paths: set[Path]) -> None:
    """The caller cannot substitute an arbitrary root for the executing package."""
    package_root = Path(__file__).resolve().parent
    actual_paths: set[Path] = set()
    for path in package_root.rglob("*.py"):
        resolved = path.resolve()
        if not resolved.is_relative_to(package_root):
            raise AcceptanceProvenanceError("Executing package contains a path escaping its physical root.")
        # Reparse/symlink indirection below the executing root is not a frozen
        # source member even when it currently resolves back into the package.
        for component in (path, *path.parents):
            if component == package_root:
                break
            if component.is_symlink() or getattr(component.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                raise AcceptanceProvenanceError("Executing package contains an indirect source path.")
        actual_paths.add(resolved)
    approved_package_paths = {path for path in manifest_paths if path.is_relative_to(package_root)}
    if not actual_paths or approved_package_paths != actual_paths:
        raise AcceptanceProvenanceError("Code manifest must include the exact executing package Python-file closure.")
    # Additional explicitly pinned tooling/test files are permitted, but an
    # alternate LegalPDF package cannot stand in for or supplement runtime code.
    for path in manifest_paths - approved_package_paths:
        if "legalpdf_translate" in path.parts:
            raise AcceptanceProvenanceError("Code manifest contains another LegalPDF package root.")


def verify_runtime_context(
    provenance: Mapping[str, Any], *,
    config: Mapping[str, Any] | Callable[[], Mapping[str, Any]],
    preferences: Mapping[str, Any] | Callable[[], Mapping[str, Any]],
) -> None:
    """Reevaluate actual in-memory values, not only caller-declared file hashes."""
    actual_config = config() if callable(config) else config
    actual_preferences = preferences() if callable(preferences) else preferences
    if not isinstance(actual_config, Mapping) or not isinstance(actual_preferences, Mapping):
        raise AcceptanceProvenanceError("Effective runtime configuration and preferences must be objects.")
    try:
        manifest = json.loads(_verified_file(provenance["config_manifest"], "config_manifest"))
        saved_preferences = json.loads(_verified_file(provenance["preferences"], "preferences"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AcceptanceProvenanceError("Runtime configuration or preferences evidence is invalid.") from exc
    if not isinstance(saved_preferences, dict):
        raise AcceptanceProvenanceError("Approved preferences must decode to an object.")
    if fingerprint(canonical_run_config(actual_config)) != manifest.get("runtime_config_sha256"):
        raise AcceptanceProvenanceError("Effective runtime configuration differs from approval.")
    try:
        preferences_match = fingerprint(dict(actual_preferences)) == fingerprint(saved_preferences)
    except (TypeError, ValueError) as exc:
        raise AcceptanceProvenanceError("Effective preferences are not finite JSON.") from exc
    if not preferences_match:
        raise AcceptanceProvenanceError("Effective runtime preferences differ from approval.")


def verify_pending_correction(entry: Mapping[str, Any], expected_fingerprint: str) -> None:
    """A correction approval binds both physical bytes and the durable envelope."""
    raw = _verified_file(entry, "pending correction")
    try:
        envelope = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AcceptanceProvenanceError("Pending correction is not a valid envelope.") from exc
    if (not isinstance(envelope, dict) or envelope.get("sha256") != expected_fingerprint
            or fingerprint({key: value for key, value in envelope.items() if key != "sha256"}) != expected_fingerprint):
        raise AcceptanceProvenanceError("Pending correction envelope differs from approval.")
