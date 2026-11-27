"""Explicit, local recovery of pinned terminal browser work; no network or replay.

The capsule is an evidence manifest, not a backup: original absolute paths must
remain present. Its SHA256 is supplied independently at import. HTTP delivery
overlays are retained for comparison and never replace raw completion accounting.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from contextlib import ExitStack
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .checkpoint import load_run_state, settings_fingerprint, sha256_of_text
from .ordinary_layout_contracts import decode, encode, identifier, job_identity
from .run_workspace_lock import run_workspace_slot
from .translation_service import TranslationJobManager, _ManagedTranslationJob
from .types import RunConfig, TargetLang

VERSION = "terminal_recovery_v1"
MAX_FILES = 10000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
TERMINAL = {"completed", "failed", "cancelled"}


class RecoveryError(ValueError):
    """A safe code only: never include private paths or captured content."""


def _fail(code):
    raise RecoveryError("terminal_recovery_" + code) from None


def _direct(value, *, directory=False):
    if type(value) is not str or not value or "\x00" in value:
        _fail("invalid_path")
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//"))
            or any(":" in part for part in path.parts[1:])):
        _fail("invalid_path")
    try:
        for item in (path, *path.parents):
            info = item.lstat()
            if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                _fail("linked_path")
            expected = stat.S_ISDIR if item != path or directory else stat.S_ISREG
            if not expected(info.st_mode) or (item == path and not directory and info.st_nlink != 1):
                _fail("invalid_path")
        if path.resolve(strict=True) != path:
            _fail("invalid_path")
    except OSError:
        _fail("missing_path")
    return path


def _bytes(path):
    path = _direct(str(path))
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError:
        _fail("unreadable_file")
    if len(raw) > MAX_FILE_BYTES:
        _fail("file_limit")
    return raw


def _json(path):
    try:
        result = decode(_bytes(path).decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        _fail("invalid_json")
    if not isinstance(result, dict):
        _fail("invalid_json")
    return result


def _payload(path):
    value = _json(path)
    if "normalized_payload" in value:
        if value.get("status") != "ok" or not isinstance(value["normalized_payload"], dict):
            _fail("capture_failed")
        value = value["normalized_payload"]
    return value


def _scope(target):
    mode, workspace = target.get("mode"), target.get("workspace_id")
    if mode not in {"live", "shadow"} or type(workspace) is not str or re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?", workspace) is None:
        _fail("invalid_owner")
    return mode, workspace


def _raw_capture(path, target, base_sha):
    payload = _payload(path)
    runtime = payload.get("runtime")
    observed_sha = runtime.get("build_sha", "") if isinstance(runtime, dict) else ""
    if (not isinstance(runtime, dict) or type(base_sha) is not str
            or re.fullmatch(r"[a-f0-9]{40}", base_sha) is None
            or type(observed_sha) is not str or re.fullmatch(r"[a-f0-9]{7,40}", observed_sha) is None
            or not base_sha.startswith(observed_sha)
            or (runtime.get("runtime_mode"), runtime.get("workspace_id")) != _scope(target)
            or runtime.get("settings_path") != target["settings_path"]):
        _fail("capture_build_mismatch")
    if not isinstance(payload.get("active_jobs"), list):
        _fail("raw_jobs_invalid")
    return payload


def _tree(path):
    root = _direct(str(path), directory=True)
    result = []
    # Inspect directories too, so an empty linked directory cannot hide evidence.
    for parent, directories, filenames in os.walk(root, followlinks=False):
        for name in directories:
            _direct(str(Path(parent) / name), directory=True)
        for name in filenames:
            file = _direct(str(Path(parent) / name))
            if name != ".run_workspace.lock":
                result.append(str(file))
            if len(result) > MAX_FILES:
                _fail("file_limit")
    return sorted(result)


def _temp_source_root(value):
    path = Path(value)
    system_temp = _direct(str(Path(tempfile.gettempdir()).resolve()), directory=True)
    if (not path.is_absolute() or path.parent != system_temp
            or re.fullmatch(r"legalpdf_gmail_batch_[A-Za-z0-9_-]+", path.name) is None):
        _fail("source_backup_owner_invalid")
    return path


def _backup_sources(capsule, destination):
    """Backup only owned Gmail batch temp trees, never unrelated artifacts."""
    downloads = set()
    for target in capsule["capture"]["targets"]:
        session = _payload(Path(target["gmail_current_path"]))["active_session"]
        root = Path(session["download_dir"])
        if root.parent == Path(tempfile.gettempdir()).resolve() and root.name.startswith("legalpdf_gmail_batch_"):
            downloads.add(str(_temp_source_root(str(root))))
    if not downloads:
        return []
    backup_root = destination.with_name(destination.name + ".sources")
    _direct(str(backup_root.parent), directory=True)
    backup_root.mkdir(exist_ok=False)
    backups = []
    for directory in sorted(downloads):
        root = _direct(directory, directory=True)
        token = hashlib.sha256(directory.encode("utf-8")).hexdigest()
        folder = backup_root / token
        folder.mkdir()
        rows = {}
        for original in _tree(root):
            relative = str(Path(original).relative_to(root))
            raw = _bytes(original)
            pin = capsule["files"].get(original)
            if pin != {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}:
                _fail("source_backup_unpinned")
            backup = folder / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb") as handle:
                handle.write(raw)
            rows[relative] = {"backup_path": str(backup), **pin}
        backups.append({"directory": directory, "files": rows})
    return backups


def create_capsule(spec_path: Path, destination: Path) -> str:
    """Pin captured JSON and all retained local evidence; create a new file only."""
    spec = _json(spec_path)
    if spec.get("version") != VERSION or not re.fullmatch(r"[a-f0-9]{40}", spec.get("base_sha", "")):
        _fail("invalid_capture")
    targets = spec.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
        _fail("target_limit")
    files = {str(_direct(str(spec_path)))}
    trees = set()
    scopes, jobs = set(), set()
    for target in targets:
        scope = _scope(target)
        if scope in scopes:
            _fail("duplicate_owner")
        scopes.add(scope)
        files.add(str(_direct(target["settings_path"])))
        _direct(target["layout_root"], directory=True)
        requested = target.get("job_ids", [])
        if not isinstance(requested, list) or not 1 <= len(requested) <= 20 or len(set(requested)) != len(requested):
            _fail("job_limit")
        raw_jobs = []
        for name in target.get("raw_job_paths", []):
            files.add(str(_direct(name)))
            raw_jobs.extend(_raw_capture(Path(name), target, spec["base_sha"])["active_jobs"])
        selected = [job for job in raw_jobs if job.get("job_id") in requested]
        if len(selected) != len(requested) or {job["job_id"] for job in selected} != set(requested):
            _fail("raw_job_missing")
        for job in selected:
            identifier(job["job_id"])
            if job["job_id"] in jobs or job.get("status") not in TERMINAL:
                _fail("active_or_duplicate_job")
            jobs.add(job["job_id"])
            if (job.get("runtime_mode"), job.get("workspace_id")) != scope:
                _fail("job_owner_mismatch")
            source = _direct(job["config"]["source_path"])
            files.add(str(source))
            _direct(job["config"]["output_dir"], directory=True)
            run = _direct(job["result"]["run_dir"], directory=True)
            trees.add(str(run))
            for name in ("context_file", "glossary_file"):
                if job["config"].get(name):
                    files.add(str(_direct(job["config"][name])))
            for name in ("ordinary_layout", "saved_docx_layout"):
                root = Path(target["layout_root"]) / name / scope[1]
                if root.exists():
                    trees.add(str(_direct(str(root), directory=True)))
            for name, value in job.get("artifacts", {}).items():
                if value and name != "run_dir" and isinstance(value, str) and Path(value).is_absolute():
                    artifact = Path(value)
                    if artifact.is_dir():
                        _direct(value, directory=True)
                        if not artifact.is_relative_to(run):
                            _fail("artifact_owner_mismatch")
                    else:
                        files.add(str(_direct(value)))
        for name in target.get("overlay_paths", []):
            files.add(str(_direct(name)))
        for key in ("gmail_bootstrap_path", "gmail_current_path"):
            files.add(str(_direct(target[key])))
        gmail = _payload(Path(target["gmail_current_path"]))
        session = gmail.get("active_session")
        if not isinstance(session, dict):
            _fail("session_missing")
        for attachment in session.get("attachments", []):
            files.add(str(_direct(attachment["saved_path"])))
        if session.get("session_report_path"):
            files.add(str(_direct(session["session_report_path"])))
        if session.get("download_dir"):
            root = _direct(session["download_dir"], directory=True)
            if root.parent == Path(tempfile.gettempdir()).resolve() and root.name.startswith("legalpdf_gmail_batch_"):
                trees.add(str(_temp_source_root(str(root))))
    for name in spec.get("extra_files", []):
        files.add(str(_direct(name)))
    for name in spec.get("extra_directories", []):
        trees.add(str(_direct(name, directory=True)))
    directory_index = {name: _tree(name) for name in sorted(trees)}
    for names in directory_index.values():
        files.update(names)
    if len(files) > MAX_FILES:
        _fail("file_limit")
    index, total = {}, 0
    for name in sorted(files):
        raw = _bytes(name)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            _fail("total_limit")
        index[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    capsule = {"version": VERSION, "capture": spec, "files": index, "trees": directory_index}
    # Stage the complete import before writing the new private manifest.
    _stage(capsule)
    destination = Path(destination).absolute()
    _direct(str(destination.parent), directory=True)
    if destination.exists() or destination.is_symlink():
        _fail("destination_exists")
    capsule["source_backups"] = _backup_sources(capsule, destination)
    raw = encode(capsule)
    try:
        with destination.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        _fail("destination_exists")
    return hashlib.sha256(raw).hexdigest()


def restore_missing_sources(path: Path, expected_sha256: str) -> dict:
    """Explicit rollout step: restore missing owned temp sources, never overwrite.

    The default importer remains read-only. A separate flag is required for this
    bounded filesystem action after the approved old-server shutdown.
    """
    path = _direct(str(path))
    raw = _bytes(path)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("capsule_hash_mismatch")
    capsule = decode(raw)
    if capsule.get("version") != VERSION:
        _fail("version_mismatch")
    backups = capsule.get("source_backups", [])
    if not isinstance(backups, list) or len(backups) > 10:
        _fail("source_backup_limit")
    backup_root = path.with_name(path.name + ".sources")
    planned, roots, total = [], [], 0
    for row in backups:
        root = _temp_source_root(row["directory"])
        if root in roots:
            _fail("duplicate_source_backup")
        roots.append(root)
        expected = set()
        if root.exists() or root.is_symlink():
            _direct(str(root), directory=True)
        for relative, pin in row["files"].items():
            rel = Path(relative)
            if (rel.is_absolute() or rel.drive or not rel.parts
                    or any(part in {"..", "."} or ":" in part for part in rel.parts)):
                _fail("source_backup_escape")
            original = root / rel
            if not original.is_relative_to(root):
                _fail("source_backup_escape")
            expected.add(str(original))
            backup = Path(pin["backup_path"])
            token = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
            if backup != backup_root / token / rel:
                _fail("source_backup_escape")
            content = _bytes(backup)
            total += len(content)
            file_pin = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            if (total > MAX_TOTAL_BYTES or len(planned) >= MAX_FILES or file_pin != capsule["files"].get(str(original))
                    or pin.get("sha256") != file_pin["sha256"] or pin.get("bytes") != file_pin["bytes"]):
                _fail("source_backup_changed")
            for parent in original.parents:
                if parent.exists() or parent.is_symlink():
                    _direct(str(parent), directory=True)
            if original.exists() or original.is_symlink():
                if _bytes(original) != content:
                    _fail("existing_source_changed")
            else:
                planned.append((original, content))
        if root.exists() and not set(_tree(root)) <= expected:
            _fail("existing_source_tree_changed")
        captured = capsule["trees"].get(str(root))
        if captured is None or set(captured) != expected:
            _fail("source_backup_incomplete")
    # All paths and backup hashes have passed before the first filesystem write.
    _verify(capsule, missing_sources={str(original) for original, _ in planned},
        source_roots={str(root) for root in roots})
    for original, content in planned:
        original.parent.mkdir(parents=True, exist_ok=True)
        _direct(str(original.parent), directory=True)
        descriptor = os.open(original, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        if _bytes(original) != content:
            _fail("source_restore_changed")
    return {"status": "sources_restored" if planned else "sources_unchanged", "restored_files": len(planned),
        "source_directories": len(roots)}


def _verify(capsule, *, missing_sources=frozenset(), source_roots=frozenset()):
    if capsule.get("version") != VERSION or capsule.get("capture", {}).get("version") != VERSION:
        _fail("version_mismatch")
    index = capsule.get("files")
    if not isinstance(index, dict) or not 1 <= len(index) <= MAX_FILES:
        _fail("file_limit")
    total = 0
    for name, pin in index.items():
        if name in missing_sources:
            continue
        raw = _bytes(name)
        total += len(raw)
        if len(raw) != pin.get("bytes") or hashlib.sha256(raw).hexdigest() != pin.get("sha256"):
            _fail("evidence_changed")
        if total > MAX_TOTAL_BYTES:
            _fail("total_limit")
    for name, expected in capsule.get("trees", {}).items():
        if name in source_roots and not Path(name).exists():
            if not set(expected) <= missing_sources:
                _fail("source_backup_incomplete")
            continue
        actual = _tree(name)
        if actual != [path for path in expected if path not in missing_sources] or any(path not in index for path in actual):
            _fail("tree_changed")
    for backup in capsule.get("source_backups", []):
        for pin in backup["files"].values():
            raw = _bytes(pin["backup_path"])
            if len(raw) != pin["bytes"] or hashlib.sha256(raw).hexdigest() != pin["sha256"]:
                _fail("source_backup_changed")


def _pinned(capsule, path, *, directory=False):
    path = _direct(str(path), directory=directory)
    collection = capsule["trees"] if directory else capsule["files"]
    if str(path) not in collection:
        _fail("unpinned_evidence")
    return path


def _existing_lock(directory):
    """Never let the normal lock helper create/initialize retained evidence."""
    lock = _direct(str(Path(directory) / ".run_workspace.lock"))
    if not lock.stat().st_size:
        _fail("lock_uninitialized")
    return run_workspace_slot(Path(directory))


def _config(raw, target, capsule):
    from .user_settings import load_gui_settings_from_path
    run = _pinned(capsule, raw["result"]["run_dir"], directory=True)
    state_path = _pinned(capsule, run / "run_state.json")
    state = load_run_state(state_path)
    if state is None or state.run_status in {"running", "queued", "formatting"}:
        _fail("checkpoint_active_or_invalid")
    form = deepcopy(raw["config"])
    source = _pinned(capsule, form["source_path"])
    output = _direct(form["output_dir"], directory=True)
    source_hash = hashlib.sha256(_bytes(source)).hexdigest()
    if (state.pdf_fingerprint != source_hash or raw["result"].get("source_sha256") != source_hash
            or Path(state.pdf_path) != source or Path(state.run_dir_abs) != run
            or Path(state.frozen_outdir_abs) != output or state.lang != form["target_lang"]
            or not run.is_relative_to(output)):
        _fail("checkpoint_identity_mismatch")
    settings_path = _pinned(capsule, target["settings_path"])
    # The existing form builder probes writability. Recovery must never write
    # to the output directory, so build its defaults against the settings only.
    defaults = load_gui_settings_from_path(settings_path)
    from .types import (ReasoningEffort, EffortPolicy, ImageMode, OcrMode,
                        OcrEnginePolicy, OcrApiProvider)
    config = RunConfig(pdf_path=source, output_dir=output, target_lang=TargetLang(form["target_lang"]))
    enums = {"effort": ReasoningEffort, "effort_policy": EffortPolicy, "image_mode": ImageMode,
        "ocr_mode": OcrMode, "ocr_engine": OcrEnginePolicy, "ocr_api_provider": OcrApiProvider}
    for field in fields(config):
        name = field.name
        if name in {"pdf_path", "output_dir", "target_lang"}:
            continue
        value = form.get(name, getattr(config, name))
        if name in {"ocr_api_provider", "ocr_api_base_url", "ocr_api_model", "ocr_api_key_env_name"}:
            value = defaults.get(name, value)
        if name == "ocr_api_provider":
            value = defaults.get(name, defaults.get("ocr_api_provider_default", value))
        if name in state.settings:
            pinned_value = state.settings[name]
            if name in form and form[name] != pinned_value:
                _fail("config_mismatch")
            value = pinned_value
        if name in enums:
            value = enums[name](value)
        elif name in {"context_file", "glossary_file"}:
            if name == "glossary_file":
                value = state.settings.get("glossary_file_path", value)
            value = _pinned(capsule, value) if value else None
        elif name in {"ocr_api_base_url", "ocr_api_model", "context_text"}:
            value = value or None
        setattr(config, name, value)
    fingerprint = settings_fingerprint(config,
        ordinary_source_review=state.settings.get("ordinary_source_review"),
        ordinary_auto_layout_policy=state.settings.get("ordinary_auto_layout_policy"),
        primary_recipe=state.settings.get("primary_assembly_recipe"))
    if fingerprint != state.settings or state.settings.get("ordinary_source_review"):
        _fail("config_fingerprint_mismatch")
    context_hash = (hashlib.sha256(_bytes(config.context_file)).hexdigest() if config.context_file
        else sha256_of_text(config.context_text))
    if context_hash != state.context_hash:
        _fail("context_mismatch")
    if config.keep_intermediates:
        for number, page in state.pages.items():
            if page.get("status") == "done":
                _pinned(capsule, run / "pages" / f"page_{int(number):04d}.txt")
    return config, state


def _restore_accountant(raw, config, state, capsule):
    """Recover frozen soft accounting without writing or authorizing dispatch."""
    from .usage_accounting import DispatchAccounting, DispatchAccountingError
    from .types import BudgetExceedPolicy
    reference = state.dispatch_accounting
    if not reference:
        return None  # Historical evidence never proves zero spend.
    if not isinstance(reference, dict):
        _fail("accounting_identity_mismatch")
    if type(reference.get("historical_incomplete", False)) is not bool:
        _fail("accounting_identity_mismatch")
    accounting_id = reference.get("id")
    if type(accounting_id) is not str or not re.fullmatch(r"[a-f0-9]{32}", accounting_id):
        _fail("accounting_identity_mismatch")
    path = _pinned(capsule, Path(raw["result"]["run_dir"]) / "accounting" / accounting_id / "dispatch_accounting.json")
    saved = _json(path)
    identity = saved.get("run_identity")
    events = saved.get("events")
    if not isinstance(identity, dict) or not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        _fail("accounting_identity_mismatch")
    model = identity.get("model")
    expected = {"accounting_id": accounting_id, "source_sha256": state.pdf_fingerprint,
        "context_hash": state.context_hash, "language": state.lang,
        "protocol": state.protocol_identity.get("protocol", "legacy_text_v1"),
        "model": model, "protocol_identity": dict(state.protocol_identity),
        "selection": [state.selection_start_page, state.selection_end_page],
        "run_started_at": state.run_started_at}
    if (identity != expected or type(model) is not str or not model.strip()
            or state.protocol_identity.get("model", model) != model
            or any(event.get("requested_model") != model for event in events
                if event.get("event") == "begin" and event.get("purpose") in {"translation", "correction"})):
        _fail("accounting_identity_mismatch")
    # A persistent cap must never be silently replaced by a soft accountant.
    # Unsupported hard budgets stay visible but unavailable for new layout work.
    if (not isinstance(saved.get("dispatch_limits"), dict)
            or any(not isinstance(value, dict) for value in saved["dispatch_limits"].values())):
        _fail("accounting_evidence_invalid")
    if (saved.get("budget_context") != {"hard": False}
            or config.budget_cap_usd is not None and config.budget_on_exceed == BudgetExceedPolicy.BLOCK
            or saved.get("pricing_catalog") is None):
        return None
    try:
        return DispatchAccounting(path.parent, run_identity=expected,
            historical_incomplete=bool(reference.get("historical_incomplete", False)),
            _existing_journal_sha256=capsule["files"][str(path)]["sha256"])
    except (DispatchAccountingError, ValueError, TypeError, KeyError):
        _fail("accounting_evidence_invalid")


def _restore_job(raw, target, capsule, jobs):
    if any(key in raw for key in ("delivery", "ordinary_layout", "layout_costs", "text_correction")):
        _fail("raw_job_is_delivery_overlay")
    if raw.get("result", {}).get("selected_text_review"):
        _fail("raw_job_is_delivery_overlay")
    if raw.get("status") not in TERMINAL or raw.get("job_kind") not in {"translate", "rebuild"}:
        _fail("active_or_invalid_job")
    if (raw.get("runtime_mode"), raw.get("workspace_id")) != _scope(target):
        _fail("job_owner_mismatch")
    identifier(raw["job_id"])
    if raw["job_id"] in jobs._jobs:
        _fail("duplicate_job")
    config, state = _config(raw, target, capsule)
    job = _ManagedTranslationJob(job_id=raw["job_id"], job_kind=raw["job_kind"],
        runtime_mode=raw["runtime_mode"], workspace_id=raw["workspace_id"], created_at=raw["created_at"],
        updated_at=raw["updated_at"], status=raw["status"], status_text=raw["status_text"],
        config_payload=deepcopy(raw["config"]), progress_payload=deepcopy(raw["progress"]),
        diagnostics_payload=deepcopy(raw["diagnostics"]), log_tail=list(raw["logs"]),
        result_payload=deepcopy(raw["result"]), artifacts_payload=deepcopy(raw["artifacts"]), _config=config,
        _ordinary_auto_layout_policy=state.settings.get("ordinary_auto_layout_policy"))
    job._completed_accountant = _restore_accountant(raw, config, state, capsule)
    jobs._jobs[job.job_id] = job
    return job


def _restore_layout(job, target, capsule, jobs, overlay):
    from .ordinary_layout_service import OrdinaryLayoutService
    from .ordinary_layout_integration import delivery_job_snapshot
    from .ordinary_layout_manager import OrdinaryLayoutManager
    run = Path(job.result_payload["run_dir"])
    retained = run / "ordinary_layout_originals" / job.job_id
    original = _pinned(capsule, retained / "provider.docx")
    mapping_path = _pinned(capsule, retained / "provider.source_map.json")
    mapping_raw = _bytes(mapping_path)
    mapping = decode(mapping_raw) if mapping_raw else {}
    original_hash = hashlib.sha256(_bytes(original)).hexdigest()
    pages = tuple(range(job._config.start_page, (job._config.end_page or
        load_run_state(run / "run_state.json").selection_end_page) + 1))
    if job._config.max_pages is not None:
        pages = pages[:job._config.max_pages]
    service = OrdinaryLayoutService(Path(target["layout_root"]), mode=job.runtime_mode,
        workspace_id=job.workspace_id)
    folder = service.root / job.job_id
    reviewed = original
    if folder.exists():
        with _existing_lock(folder), service.scope(job.job_id) as owned:
            baseline, manifest = service._baseline(owned)
            # Source/original copies and their manifest are independently pinned.
            for name in ("manifest.json", "source.pdf", "provider.docx", "reviewed.docx"):
                _pinned(capsule, baseline / name)
            reviewed = baseline / "reviewed.docx"
            if manifest["identity"]["original_sha256"] != original_hash:
                _fail("baseline_original_mismatch")
    job._ordinary_baseline = {"source_path": str(job._config.pdf_path),
        "source_sha256": hashlib.sha256(_bytes(job._config.pdf_path)).hexdigest(),
        "original_path": str(original), "original_sha256": original_hash,
        "output_path": str(reviewed), "selected_pages": pages, "mapping": mapping,
        "mapping_path": str(mapping_path),
        "mapping_sha256": hashlib.sha256(mapping_raw).hexdigest() if mapping_raw else ""}
    trusted = jobs.trusted_ordinary_layout_job(job.job_id, runtime_mode=job.runtime_mode,
        workspace_id=job.workspace_id)
    job_identity(trusted, job.runtime_mode, job.workspace_id)
    if folder.exists():
        with _existing_lock(folder):
            service.assert_current(trusted)
            manager = OrdinaryLayoutManager(Path(target["layout_root"]), mode=job.runtime_mode,
                workspace_id=job.workspace_id, job_resolver=lambda _: trusted)
            selected, artifact = delivery_job_snapshot(manager, jobs.get_job(job.job_id))
        if overlay is None:
            _fail("delivery_overlay_missing")
        if selected.get("delivery") != overlay.get("delivery"):
            _fail("delivery_overlay_mismatch")
        for key in ("api_cost", "estimated_api_cost", "output_docx", "word_count", "run_id"):
            if selected["result"]["save_seed"].get(key) != overlay["result"]["save_seed"].get(key):
                _fail("delivery_accounting_mismatch")
        if selected.get("text_correction") != overlay.get("text_correction"):
            _fail("correction_history_mismatch")
        if artifact is not None:
            _pinned(capsule, artifact.path)


def _restore_gmail(target, capsule, jobs):
    from .gmail_browser_service import _WorkspaceState, _preferred_reply_email_from_load_result
    from .gmail_batch import (FetchedGmailMessage, GmailAttachmentCandidate, DownloadedGmailAttachment,
        GmailMessageLoadResult, GmailBatchSession)
    from .gmail_intake import InboundMailContext
    for key in ("gmail_bootstrap_path", "gmail_current_path"):
        _pinned(capsule, target[key])
    bootstrap = _payload(Path(target["gmail_bootstrap_path"]))
    payload = _payload(Path(target["gmail_current_path"]))
    session, loaded = payload.get("active_session"), payload.get("load_result")
    if not isinstance(session, dict) or not isinstance(loaded, dict) or not loaded.get("ok"):
        _fail("session_missing")
    if bootstrap.get("active_session") != session or bootstrap.get("load_result") != loaded:
        _fail("session_capture_mismatch")
    if (session.get("kind") != "translation" or session.get("status") != "prepared"
            or session.get("confirmed_items") or session.get("draft_created")
            or session.get("finalization_state") or session.get("actual_honorarios_path")
            or session.get("actual_honorarios_pdf_path") or session.get("consistency_signature")
            or session.get("final_attachment_basenames")):
        _fail("session_out_of_scope")
    context = InboundMailContext.from_payload(loaded["intake_context"])
    message_payload = loaded["message"]
    candidates = tuple(GmailAttachmentCandidate(**row) for row in message_payload["attachments"])
    message = FetchedGmailMessage(**{**message_payload, "attachments": candidates})
    if (session["message"] != message_payload or context.message_id != message.message_id
            or context.thread_id != message.thread_id or loaded["account_email"] != message.account_email):
        _fail("message_mismatch")
    downloaded = []
    for row in session["attachments"]:
        candidate = GmailAttachmentCandidate(**row["attachment"])
        path = _pinned(capsule, row["saved_path"])
        if candidate not in candidates or candidate.source_message_id != message.message_id:
            _fail("attachment_mismatch")
        if type(row["start_page"]) is not int or row["start_page"] < 1 or type(row["page_count"]) is not int or row["page_count"] < 1:
            _fail("attachment_selection_invalid")
        downloaded.append(DownloadedGmailAttachment(candidate, path, row["start_page"], row["page_count"]))
    index = session["current_index"]
    if not downloaded or type(index) is not int or not 0 <= index < len(downloaded):
        _fail("session_index_invalid")
    if session["current_attachment"] != session["attachments"][index] or session["total_items"] != len(downloaded):
        _fail("session_index_mismatch")
    output = _direct(session["effective_output_dir"], directory=True)
    report = _pinned(capsule, session["session_report_path"]) if session.get("session_report_path") else None
    if report is not None:
        report_payload = _json(report)
        if report_payload.get("session_id") != session["session_id"]:
            _fail("session_report_mismatch")
    batch = GmailBatchSession(intake_context=context, message=message, gog_path=Path(loaded["gog_path"]),
        account_email=loaded["account_email"], downloaded_attachments=tuple(downloaded),
        download_dir=_direct(session["download_dir"], directory=True), effective_output_dir=output,
        selected_target_lang=session["selected_target_lang"], session_id=session["session_id"],
        started_at=session["started_at"], status=session["status"], halt_reason=session["halt_reason"],
        session_report_path=report, session_report_dir=report.parent if report else None,
        finalization_report_context=deepcopy(session.get("finalization_report_context", {})))
    state = _WorkspaceState(loaded_result=GmailMessageLoadResult(ok=True, classification=loaded["classification"],
        status_message=loaded["status_message"], intake_context=context, gog_path=batch.gog_path,
        account_email=batch.account_email, accounts=tuple(loaded["accounts"]), message=message,
        stdout=loaded.get("stdout", ""), stderr=loaded.get("stderr", "")), batch_session=batch,
        current_batch_index=index, review_event_id=payload["review_event_id"],
        message_signature=payload["message_signature"],
        current_handoff_context=deepcopy(payload["current_handoff_context"]),
        pending_status=payload["pending_status"], pending_intake_context=deepcopy(payload["pending_intake_context"]),
        pending_review_open=payload["pending_review_open"], allow_report_restore=False)
    state.preferred_reply_email = _preferred_reply_email_from_load_result(state.loaded_result)
    for job in jobs._jobs.values():
        if (job.runtime_mode, job.workspace_id) != _scope(target):
            continue
        binding = job._config.gmail_batch_context
        attachment = downloaded[index]
        if (not isinstance(binding, dict) or binding.get("session_id") != batch.session_id
                or binding.get("message_id") != message.message_id or binding.get("thread_id") != message.thread_id
                or binding.get("attachment_id") != attachment.candidate.attachment_id
                or job._config.pdf_path != attachment.saved_path or job._config.output_dir != output
                or job._config.start_page != attachment.start_page
                or job._config.target_lang.value != batch.selected_target_lang):
            _fail("gmail_job_binding_mismatch")
    return state


def _stage(capsule):
    _verify(capsule)
    jobs, workspaces = TranslationJobManager(), {}
    targets = capsule["capture"]["targets"]
    if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
        _fail("target_limit")
    for target in targets:
        scope = _scope(target)
        if scope in workspaces:
            _fail("duplicate_owner")
        raw_jobs = []
        for name in target["raw_job_paths"]:
            _pinned(capsule, name)
            raw_jobs.extend(_raw_capture(Path(name), target, capsule["capture"]["base_sha"])["active_jobs"])
        requested = target["job_ids"]
        selected = [raw for raw in raw_jobs if raw["job_id"] in requested]
        if len(selected) != len(requested) or not 1 <= len(selected) <= 20:
            _fail("raw_job_missing")
        overlays = {}
        for name in target["overlay_paths"]:
            _pinned(capsule, name)
            overlay = _payload(Path(name))
            overlay = overlay.get("job", overlay)
            if overlay["job_id"] in overlays:
                _fail("duplicate_overlay")
            overlays[overlay["job_id"]] = overlay
        for raw in selected:
            job = _restore_job(raw, target, capsule, jobs)
            overlay = overlays.get(job.job_id)
            if (overlay is None or overlay.get("status") != job.status
                    or (overlay.get("runtime_mode"), overlay.get("workspace_id")) != scope):
                _fail("job_overlay_mismatch")
            if job.status == "completed":
                _restore_layout(job, target, capsule, jobs, overlay)
        workspaces[scope] = _restore_gmail(target, capsule, jobs)
    _verify(capsule)
    return jobs, workspaces


def import_capsule(path: Path, expected_sha256: str, *, translation_jobs, gmail_sessions,
                   expected_targets: list[dict]) -> dict:
    """Validate and atomically install into empty registries. Same import is a no-op."""
    raw = _bytes(path)
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256 or "") or hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("capsule_hash_mismatch")
    try:
        capsule = decode(raw)
        actual_targets = [{key: target[key] for key in ("mode", "workspace_id", "settings_path", "layout_root")}
            for target in capsule["capture"]["targets"]]
        if actual_targets != expected_targets:
            _fail("target_mismatch")
        with translation_jobs._lock, gmail_sessions._lock:
            if (getattr(translation_jobs, "_terminal_recovery_sha256", None) == expected_sha256
                    and getattr(gmail_sessions, "_terminal_recovery_sha256", None) == expected_sha256):
                return {"status": "already_imported", "jobs": len(translation_jobs._jobs),
                    "workspaces": len(gmail_sessions._workspaces)}
            if translation_jobs._jobs or translation_jobs._reservations or gmail_sessions._workspaces:
                _fail("registry_not_empty")
            with ExitStack() as stack:
                directories = {str(Path(raw["result"]["run_dir"]))
                    for target in capsule["capture"]["targets"]
                    for name in target["raw_job_paths"]
                    for raw in _payload(Path(name))["active_jobs"] if raw["job_id"] in target["job_ids"]}
                for directory in sorted(directories):
                    stack.enter_context(_existing_lock(directory))
                staged, workspaces = _stage(capsule)
                translation_jobs._jobs.update(staged._jobs)
                gmail_sessions._workspaces.update(workspaces)
                translation_jobs._terminal_recovery_sha256 = expected_sha256
                gmail_sessions._terminal_recovery_sha256 = expected_sha256
            return {"status": "imported", "jobs": len(staged._jobs), "workspaces": len(workspaces)}
    except RecoveryError:
        raise
    except Exception:
        _fail("invalid_evidence")


def validate_capsule(path: Path, expected_sha256: str) -> dict:
    """Offline dry run using temporary registries; does not launch a server."""
    raw = _bytes(path)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("capsule_hash_mismatch")
    from .gmail_browser_service import GmailBrowserSessionManager
    capsule = decode(raw)
    targets = [{key: target[key] for key in ("mode", "workspace_id", "settings_path", "layout_root")}
        for target in capsule["capture"]["targets"]]
    return import_capsule(path, expected_sha256, translation_jobs=TranslationJobManager(),
        gmail_sessions=GmailBrowserSessionManager(), expected_targets=targets)


def restore_app(app, path: Path, expected_sha256: str, *, restore_sources=False):
    """Startup-only adapter. Resolve settings/layout ownership from the new app."""
    context = app.state.shadow_context
    # Read only after checking the externally supplied pin.
    raw = _bytes(path)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("capsule_hash_mismatch")
    targets = []
    for target in decode(raw)["capture"]["targets"]:
        mode, workspace = _scope(target)
        data = context.services.detect_data_paths(mode=mode, repo=context.repo_root, identity=context.build_identity)
        root_factory = context.services.ordinary_layout_root or context.services.saved_docx_layout_root
        if not callable(root_factory):
            _fail("layout_disabled")
        root = root_factory(mode=mode, repo=context.repo_root, identity=context.build_identity)
        targets.append({"mode": mode, "workspace_id": workspace, "settings_path": str(data.settings_path),
            "layout_root": str(root)})
    captured_targets = [{key: target[key] for key in ("mode", "workspace_id", "settings_path", "layout_root")}
        for target in decode(raw)["capture"]["targets"]]
    if captured_targets != targets:
        _fail("target_mismatch")
    if restore_sources:
        restore_missing_sources(path, expected_sha256)
    return import_capsule(path, expected_sha256, translation_jobs=context.translation_jobs,
        gmail_sessions=context.gmail_sessions, expected_targets=targets)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a private terminal recovery evidence capsule.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--capture", type=Path, help="Local capture specification JSON.")
    operation.add_argument("--validate", type=Path, help="Offline read-only capsule dry run.")
    parser.add_argument("--capsule", type=Path, help="New private manifest path for capture.")
    parser.add_argument("--sha256", help="Independent capsule SHA256 for validation.")
    args = parser.parse_args(argv)
    if args.capture and (not args.capsule or args.sha256):
        parser.error("Capture requires --capsule and does not use --sha256.")
    if args.validate and (not args.sha256 or args.capsule):
        parser.error("Validation requires --sha256 and does not use --capsule.")
    try:
        if args.capture:
            print(create_capsule(args.capture, args.capsule))
        else:
            print(json.dumps(validate_capsule(args.validate, args.sha256)))
        return 0
    except Exception as exc:
        print(str(exc) if isinstance(exc, RecoveryError) else "terminal_recovery_invalid_evidence")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
