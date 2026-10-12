# Terminal browser recovery across an approved update

## What This Workflow Is For

This bounded local operator workflow preserves terminal translation jobs and prepared, unconfirmed Gmail translation sessions. It does not call providers, Gmail or native Word, edit checkpoints, save cases, generate fees/drafts, accept reviews or join different sessions. Live application and restarting a live server still require the project's approval gates.

## Expected Outputs

- A private hash-pinned capsule, temporary-source backup and unchanged-originals receipt.
- Restored terminal job/session ownership with pending review and unchanged raw accounting.
- Explicit refusal when required evidence is missing or changed.

## When To Use

Use when an explicitly approved app update would otherwise lose retained terminal jobs and unfinished Gmail sessions. Capture and validate while the old server still runs; apply only within the approved live-update scope.

## What Not To Do

Don't use this workflow when work is active or the task is ordinary browser refresh, cross-batch merging or general automatic persistence. Instead use normal retained-job Resume while the original server remains available. Do not replace raw accounting with a selected-delivery overlay, fabricate review acceptance, or replay completed provider work.

## Primary Files

- `src/legalpdf_translate/terminal_recovery.py`
- `src/legalpdf_translate/shadow_web/server.py`
- `tests/test_terminal_recovery.py`

## Minimal Commands

### Capture before stopping the old server

Privately retain each workspace's `translation/bootstrap`, separate job GET, Gmail bootstrap and Gmail current responses. Raw jobs come exclusively from `translation/bootstrap.normalized_payload.active_jobs`; job GET may contain selected-delivery costs and must never be used as the raw completion.

Create a private JSON specification with `version: "terminal_recovery_v1"`, the old server's exact forty-character `base_sha`, and `targets`. Each target contains:

- `mode`, original `workspace_id`, original absolute `settings_path`, and the ordinary-layout storage `layout_root` (normally live app-data directory).
- `raw_job_paths`: local translation bootstrap capture paths; `job_ids`: exact terminal jobs to retain.
- `overlay_paths`: separate job GET captures for those IDs.
- `gmail_bootstrap_path` and `gmail_current_path`: local capture paths for the same prepared session.

Optional `extra_files` and `extra_directories` pin other private journals/history evidence. Avoid volatile SQLite files while another process is writing. The defaults pin unchanged settings, sources, retained runs/checkpoints/raw baselines and the owned ordinary/saved review histories. No capture belongs in git.

```powershell
.\.venv311\Scripts\python.exe -m legalpdf_translate.terminal_recovery --capture PRIVATE_SPEC.json --capsule PRIVATE_CAPSULE.json
.\.venv311\Scripts\python.exe -m legalpdf_translate.terminal_recovery --validate PRIVATE_CAPSULE.json --sha256 PRINTED_SHA256
```

Capture prints the capsule SHA256; record it independently. Capture creates a new manifest and, where relevant, an adjacent `PRIVATE_CAPSULE.json.sources` directory containing exact hash-pinned copies of owned `legalpdf_gmail_batch_*` system-temp download trees. Existing capsule/backup paths are not overwritten. Keep both together. This is a recovery evidence capsule, not a complete app-data backup.

### Approved startup

After explicit update/restart approval, use the usual canonical server entry point with:

```powershell
.\.venv311\Scripts\python.exe -m legalpdf_translate.shadow_web.server --port 8877 --recovery-capsule PRIVATE_CAPSULE.json --recovery-sha256 PRINTED_SHA256 --recovery-restore-missing-sources
```

The source-restoration flag is an explicit filesystem action. It can recreate only missing files under the original owned Gmail temp directories from the pinned sidecar. It rejects changed existing files, additional files, invalid paths, symlinks/reparse points, missing non-source evidence and backup tampering. It never overwrites files or relocates sources. Omit the flag when all original source paths remain available. Normal import and `--validate` remain read-only except for temporary in-memory registries and OS locking of existing initialized lock files.

Startup checks settings/layout ownership against the new app before source restoration, validates the complete capsule, reconstructs config from checkpoint and unchanged settings, resolves trusted ordinary-layout bytes locally and verifies persisted ownership manifests. It compares selected delivery and correction history/costs against the separate GET overlay, preserving raw completion accounting and pending output review. It installs both registries only after all validation passes. An invalid import prevents serving. Repeat import of the same capsule into those same registries is a no-op; a conflicting/nonempty registry is refused.

## Targeted Tests

PowerShell:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_terminal_recovery.py
```

POSIX syntax for an existing compatible isolated environment:

```bash
.venv311/bin/python -m pytest -q tests/test_terminal_recovery.py
```

Live Gmail rollout uses the canonical Windows installation. The test syntax does not authorize another host or feature-worktree live operation.

## Failure Modes and Fallback Steps

Any missing or changed pinned evidence blocks import. Preserve the old process until preflight succeeds. If approved shutdown removed only the owned temporary sources, use the explicit verified restore-missing flag. Do not overwrite conflicts, edit checkpoints, clear uncertain charges or reinterpret missing evidence as acceptance.

## Handoff Checklist

1. Retain raw bootstrap, separate GET overlays and Gmail captures privately; pin the capsule SHA independently.
2. Verify original-source backup and read-only import before requesting live application approval.
3. After approved startup, verify canonical identity, original jobs/workspaces, selected corrected bytes, raw costs and pending review.
4. Resume only unfinished work through normal controls; manually review final files before Save or Gmail finalization.
5. Preserve original failures, charges, sources and capsule evidence; record limits separately from document acceptance.

## Limits and acceptance

Only retained terminal translate/rebuild jobs and prepared, unconfirmed translation sessions with the original local paths are supported. Active work, reviewed-source provenance requiring in-memory handles, confirmed/finalized sessions and unavailable originals fail explicitly. No cross-session adoption or batch merging is performed.

The old completed accounting object is not reconstructed: paid layout actions on a restored completed job can remain unavailable. Existing local correction, selected download and failed translation Resume retain their normal controls. Import never clears an uncertain charge, creates a reservation, accepts a native review or declares legal/content acceptance. Manually review the actual final output before Save/Gmail finalization.

Fictional adversarial coverage is in `tests/test_terminal_recovery.py`. The parent workflow owns integrated Standard/Full validation and approval; a local dry run is evidence of bounded restoration, not live workflow acceptance.
