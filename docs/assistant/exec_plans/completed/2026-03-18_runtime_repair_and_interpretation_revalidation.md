# Restore Real OCR Runtime and Re-validate Interpretation Honorarios Flow

## Goal and non-goals
- Goal: restore a normal Python 3.11 + `.venv311` runtime so the latest-feature build launches without a compatibility stub, then re-run the interpretation notification PDF -> honorarios flow and fix only any remaining real app bugs.
- Non-goals: keep the temporary launcher as the accepted path, add local Tesseract as the first-line fix, or make unrelated product changes outside launcher/runtime health and the interpretation repro path.

## Scope (in/out)
- In scope:
  - repair or replace the broken machine Python 3.11 runtime
  - rebuild `C:\Users\FA507\.codex\legalpdf_translate\.venv311`
  - add launcher preflight / degraded-session messaging
  - re-test notification OCR autofill and interpretation honorarios generation in the latest-feature build
  - patch remaining interpretation/OCR/export logic only if still broken in the healthy runtime
- Out of scope:
  - DB/schema changes
  - broad UI redesign
  - local Tesseract installation unless API OCR remains unavailable after runtime repair

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree using `--allow-noncanonical`

## Interfaces/types/contracts affected
- Launcher runtime validation contract in `tooling/launch_qt_build.py`
- User-facing launch failure/degraded-session messaging
- Interpretation notification OCR/autofill flow only if healthy-runtime repro still exposes app-code issues

## File-by-file implementation steps
- `tooling/launch_qt_build.py`
  - add preflight checks for critical runtime imports
  - fail fast on unhealthy runtimes
  - make degraded compatibility launches explicit if retained
- runtime environment
  - restore a healthy machine Python 3.11
  - recreate canonical `.venv311` from `pyproject.toml`
  - validate core imports before app launch
- latest-feature interpretation flow
  - relaunch via the normal launcher
  - re-run notification PDF autofill and interpretation honorarios export
  - patch `src/legalpdf_translate/metadata_autofill.py` / `src/legalpdf_translate/qt_gui/dialogs.py` / related runtime surfaces only if a real app bug remains

## Tests and acceptance criteria
- Python 3.11 imports `ctypes`, `socket`, `ssl`, `sqlite3`
- canonical `.venv311` imports `PySide6.QtCore`, `openai`, `fitz`, `lxml.etree`, `PIL._imaging`
- latest-feature build launches normally through `tooling/launch_qt_build.py`
- Settings OpenAI/OCR tests run against the real client
- scanned notification PDF autofills through OCR in the healthy runtime
- interpretation honorarios DOCX + PDF export succeeds, or the intended local-only recovery dialog appears

## Rollout and fallback
- Preferred path: repaired runtime + normal launcher
- Fallback: explicit degraded-session warning only for temporary troubleshooting, not as final acceptance

## Risks and mitigations
- Risk: Python 3.11 repair requires reinstall and venv recreation
  - Mitigation: validate base runtime imports before rebuilding the venv
- Risk: existing feature changes in the worktree are unrelated
  - Mitigation: keep edits scoped and do not revert unrelated modifications
- Risk: healthy runtime reveals a remaining app bug
  - Mitigation: patch only the repro path after the runtime is known-good

## Assumptions/defaults
- `OPENAI_API_KEY` is the intended OCR credential on this machine
- legacy `DEEPSEEK_API_KEY` remains compatibility-only
- final acceptance requires a normal latest-feature launch, not the temporary compatibility session
