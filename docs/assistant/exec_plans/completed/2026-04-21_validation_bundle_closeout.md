# Validation Wrapper and Review Bundle Closeout

## Goal and non-goals
- Goal: make beginner-safe validation and clean review-bundle creation easier and more reliable on Windows.
- Goal: remove duplicate baseline validation from `scripts/validate_dev.ps1 -Full`.
- Goal: add a reusable `scripts/create_review_bundle.ps1` workflow that writes a clean source ZIP to Downloads.
- Goal: produce new Downloads deliverables for this tooling pass only: implementation summary, validation summary, and clean ZIP.
- Non-goal: change production app behavior, browser UI behavior, backend APIs, Gmail flows, translation behavior, or route contracts.

## Scope (in/out)
- In:
  - `scripts/validate_dev.ps1`
  - new `scripts/create_review_bundle.ps1`
  - beginner-facing validation/bundle docs in `README.md` and `APP_KNOWLEDGE.md`
  - Downloads deliverables for this pass
  - ExecPlan lifecycle and validation outcome recording
- Out:
  - application/runtime behavior
  - backend/browser/Gmail contracts
  - unrelated dirty worktree files from previous passes
  - bare/global Python installation or dependency mutation

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- target integration branch: `main`
- canonical build status or intended noncanonical override: noncanonical feature-branch worktree used for local tooling/docs work only; no app-runtime contract change intended

## Interfaces/types/contracts affected
- Existing developer-facing entrypoints retained:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- New developer-facing helper:
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- No production app/backend/Gmail/translation/interpretation/route contract changes.

## File-by-file implementation steps
- `scripts/validate_dev.ps1`
  - keep `.venv311` enforcement, fail-fast logging, docs-trigger detection, and Dart fallback
  - split command groups into baseline and full-only extras so `-Full` no longer reruns baseline pytest/compileall
- `scripts/create_review_bundle.ps1`
  - resolve repo root and Downloads path
  - prefer `git ls-files --cached --others --exclude-standard`
  - fall back to directory walk with explicit exclusions
  - preserve `.env.example`
  - exclude local env files, caches, `*.egg-info`, temp run folders, generated DOCX/PDF outputs, scratch files, and generated build/dist output
  - write a `legalpdf_translate/`-rooted ZIP and report excluded generated DOCX/PDF files
- `README.md`
  - keep beginner-safe validation instructions
  - add beginner-friendly review-bundle workflow
  - explicitly steer users away from bare/global Python for normal dev validation
- `APP_KNOWLEDGE.md`
  - add the same validation/bundle workflow guidance in the canonical app/dev knowledge surface

## Tests and acceptance criteria
- Run:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- Confirm:
  - both validation runs use `.\.venv311\Scripts\python.exe`
  - `-Full` runs baseline once, then only the Gmail extra checks
  - docs validation runs because this pass touches docs/ExecPlans
  - workspace hygiene runs if available
  - Dart falls back to direct executable only for the known `dartdev` AOT issue
  - clean ZIP lands in Downloads with root `legalpdf_translate/`
  - ZIP excludes `.env`, `.git`, `.venv*`, caches, `*.egg-info`, generated DOCX/PDF outputs, and specifically `6a330e92-744d-4579-847b-6bace4fa38d2_temp_FR_20260211_000727.docx`
  - `.env.example` remains included

## Rollout and fallback
- Keep validation behavior explicit and fail-fast.
- If validation fails but the worktree remains coherent, still create the validation summary and clean ZIP.
- Use the new bundle script itself for the final ZIP deliverable rather than an ad hoc command path.

## Risks and mitigations
- Risk: bundle exclusions accidentally drop important review files.
  - Mitigation: prefer Git-tracked/untracked file enumeration and preserve normal project files while excluding only clearly local/generated outputs.
- Risk: `-Full` command refactor changes validation coverage unintentionally.
  - Mitigation: keep the same baseline and extra Gmail checks, but remove only the duplicated baseline rerun.
- Risk: Dart fallback handling regresses while refactoring.
  - Mitigation: keep the current known-working fallback logic intact and validate both normal and `-Full` runs.

## Assumptions/defaults
- This pass is tooling/docs only; app behavior remains unchanged.
- The repo currently has no tracked `.docx` or `.pdf` fixtures, so excluding discovered generated DOCX/PDF review outputs is safe for this pass.
- Use `workingtree` in the ZIP filename only if Git is unavailable for hash discovery.

## Validation results
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - passed
  - baseline pytest group: `55 passed in 127.29s (0:02:07)`
  - compileall: passed
  - `dart run tooling/validate_agent_docs.dart` hit the known `Unable to find AOT snapshot for dartdev` issue, then passed via `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe`
  - `dart run tooling/validate_workspace_hygiene.dart` hit the same known issue, then passed via direct Dart fallback
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - passed
  - baseline pytest group ran once: `55 passed in 132.93s (0:02:12)`
  - compileall ran once: passed
  - Gmail extras:
    - `tests/test_gmail_review_state.py` -> `1 passed in 0.20s`
    - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"` -> `5 passed, 9 deselected in 0.52s`
  - docs and workspace hygiene validators used the same direct Dart fallback path after the known `dartdev` AOT issue
- `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
  - initial run failed because the script had not yet loaded `System.IO.Compression` for `ZipArchiveMode`
  - after the script fix, rerun passed and created a clean Downloads ZIP
  - final bundle report confirmed generated DOCX/PDF exclusions, including `6a330e92-744d-4579-847b-6bace4fa38d2_temp_FR_20260211_000727.docx`
- Direct archive inspection of the final validation ZIP confirmed:
  - root `legalpdf_translate/`
  - includes `scripts/validate_dev.ps1`, `scripts/create_review_bundle.ps1`, `README.md`, `APP_KNOWLEDGE.md`, and `.env.example`
  - excludes `.env`, `.git`, `.venv*`, caches, `*.egg-info`, the generated root DOCX, and all DOCX/PDF outputs
