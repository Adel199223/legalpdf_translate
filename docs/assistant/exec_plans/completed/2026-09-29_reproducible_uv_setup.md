# Reproducible Python setup with uv

## Goal and non-goals

Recreate the translator's tested Python/package combination from tracked inputs, fail visibly on installer errors, and use the same setup locally and in Windows CI. Preserve the existing canonical `.venv311`, application code, private settings/data, and live services. No provider/native/Gmail operation or VS Code change is part of this task. Initial local delivery excluded publication; the subsequent user request on 2026-09-29 authorizes the standard commit/push, PR, green-CI, merge and cleanup lifecycle.

## Scope

In: Python/tool/build pins, seeded uv lock, Windows setup and CI, behavioral setup tests, scoped setup/validation docs. Out: translation/UI contracts, dependency upgrades, release changes, historical ignored snapshots, live environment replacement.

## Worktree provenance

- Worktree: `C:/Users/FA507/Documents/Codex/2026-09-29/i-would-like-you-to-go/work/legalpdf-uv`
- Branch: `feat/uv-python-setup-20260929`
- Base/target integration branch: `main`
- Base SHA: `3bbff4b9f0748262c120d51ed8d8deffed3b2932`, containing approved floor `4e9d20e`.
- Noncanonical tooling checkout; daily live use remains canonical main.
- Managed creation was attempted but is unavailable in this projectless chat; native Git created this isolated checkout. Existing checkouts were left intact.

## Interfaces and contracts

Keep default `.venv311`, optional environment selection, and `-Recreate`. Recreate preserves a backup and restores it on failure rather than deleting the old environment. Validate environment paths and all native exit codes. Preserve Windows CI job names, exhaustive shards and evidence reconciliation. Python 3.11.9 and uv 0.12.20 are the observed baseline.

## Implementation steps

1. Snapshot normalized versions from the existing environment without changing it.
2. Add `.python-version`, pin editable build tooling, seed `uv.lock` with existing versions, then remove temporary constraints and verify lock freshness.
3. Replace unlocked pip setup with checked uv commands; preserve extras and restore process environment variables.
4. Update Windows CI to pinned uv/locked setup and explicit project Python.
5. Add real PowerShell subprocess regressions using fake uv for failure propagation, invalid paths, backup recovery and success.
6. Update README, agent/setup guidance, current handoff/validation and external source registry.

## Tests and acceptance criteria

Lock checks without modification; fresh isolated `.venv311` builds through the actual script; installed Windows versions match the normalized baseline. Behavioral regressions and existing Quick/required selected Full pass, plus docs/hygiene and whitespace. Canonical environment and application source remain intact throughout.

## Rollout and fallback

Do not run setup against the working canonical environment. Stage only reviewed tooling/docs changes for local use after testing. Existing explicit Python launchers continue to work. The 2026-09-29 follow-up supplies publication authority; use the standard branch/PR/check/merge/cleanup workflow. Keep the old ignored snapshot as historical evidence; the tracked lock is the recreation input.

## Risks and mitigations

Test reconstruction separately. Use inexact sync to preserve extras in established environments. Require a `.venv` leaf under this checkout, reject reparse points, and restore previous environments after failed recreation. No global Python/PATH/config changes are needed.

## Assumptions and progress

2026-09-29: user authorized implementation. Baseline Python 3.11.9, uv 0.12.20; original metadata fingerprint `082c17227d27cd511bb083e565b29829256fe876f81ba3326153a3d4e2beddf9` includes duplicated editable metadata. Compare normalized package identities. Implementation and local validation complete.

## Executed validations and outcome

- Fresh reconstruction through the actual setup script uses Python 3.11.9 and matches all 57 normalized baseline package versions. Repeated setup, lock freshness, dependency compatibility and application imports pass.
- All 22 Windows setup subprocess cases pass. Quick passes 93 cases/two expected deselections. Required selected Full exits 0: 1,389 selected executions/nine expected intake deselections, including 191 formatting cases. These counts are separate tiers and do not establish complete-repository coverage.
- Compilation, scoped docs and workspace hygiene pass. The installed Dart wrapper retains its known AOT snapshot failure; validation succeeds using the existing direct-SDK fallback. Original logs remain in `tmp/uv-setup/` and formatting worker receipts in `tmp/validation/` in this worktree.
- The Windows workflow parses and preserves all required jobs and four exhaustive shards. Hosted CI had not run at initial local delivery. The later user-authorized publication requires its own successful exact-head workflow receipt.
- Tested tooling/docs are copied into canonical main as local uncommitted changes only after base/path/environment guards. Exact original files are retained under the task's `work/uv-adoption-before/`, and application hashes are recorded in `work/uv-adoption-receipt.json`. The user-facing summary and exported patch are under the task's `outputs/`.
- The canonical interpreter, package versions, app source and private settings/data remain preserved. No live service or provider/Gmail operation is invoked. No commit or push was made during initial local delivery. Publication is now authorized by the subsequent user request. The isolated checkout is retained for review and evidence.

## Authorized publication closeout

On 2026-09-29, the user asked to commit and push if useful. This preserves the tested setup and exercises the updated hosted workflow. The existing implementation and selected Full remain valid: publication edits are scoped documentation only, and implementation/test/lock hashes must remain identical.

1. Commit the coherent tooling, regression tests and supporting documentation on the existing isolated feature branch, based on current main and containing floor `4e9d20e`.
2. Push without rewriting history, create the PR against main and verify its reviewed head.
3. Require all hosted Windows contracts, four exhaustive shards, Linux docs/tooling and aggregate `test (3.11)` to pass. Preserve any original failure and use a bounded retry only when justified.
4. Merge only with a correct base, clean lineage and no unresolved blocking reviews. Preserve the already-adopted local edits before fast-forwarding canonical main; verify source/package versions remain intact.
5. Remove the merged feature branch when safe; retain the checkout and ignored test evidence for recovery/review. Record actual commits, PR/check/merge/application and cleanup in the chat task's `work/uv-publication-01/publication_receipt.json` and user-facing output report. Do not infer terminal success from this plan.
