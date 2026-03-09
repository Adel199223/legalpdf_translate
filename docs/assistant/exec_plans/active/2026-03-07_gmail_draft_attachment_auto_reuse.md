## 1. Title
Gmail Draft Attachment Auto-Reuse for Honorarios Exports

## 2. Goal and non-goals
- Goal: stop asking the user to reselect the translated DOCX for Gmail draft creation when the app already knows or can persist that path.
- Non-goals:
  - no Gmail body/subject changes
  - no OCR or translation behavior changes
  - no heuristic file guessing from filenames or directories
  - no schema backfill for old rows beyond lazy healing on successful manual selection

## 3. Scope (in/out)
- In scope:
  - additive Job Log columns for final/partial DOCX paths
  - persistence of those paths from current-run Save-to-Job-Log
  - automatic reuse of stored paths in historical Job Log Gmail draft flow
  - legacy fallback picker and row healing
  - focused regression tests
- Out of scope:
  - changing Gmail transport semantics
  - changing honorarios template content
  - broad docs sync beyond this feature unless requested later

## 4. Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/ai-docs-bootstrap`
- base branch: `feat/ai-docs-bootstrap`
- base SHA: `fae5c051011b19141f94a4f94dd03c3c014ed2d2`
- target integration branch: `feat/ai-docs-bootstrap`
- canonical build status: canonical repo-root build

## 5. Interfaces/types/contracts affected
- Job Log DB schema:
  - additive columns `output_docx_path`
  - additive columns `partial_docx_path`
- Save-to-Job-Log payload now persists translation artifact paths
- Historical Gmail draft flow contract:
  - prefer stored final DOCX
  - then stored partial DOCX
  - only then prompt for manual `.docx`
  - successful manual selection heals the row for future reuse

## 6. File-by-file implementation steps
1. Update `src/legalpdf_translate/joblog_db.py`
   - add schema columns
   - extend migration
   - return the new columns from row reads
   - add a helper to update stored output paths for existing rows
2. Update `src/legalpdf_translate/qt_gui/dialogs.py`
   - persist current-run DOCX paths in Save-to-Job-Log
   - auto-resolve current-run Gmail attachment from final/partial DOCX
   - auto-resolve historical Gmail attachment from stored row paths
   - add legacy fallback picker and row-healing behavior
3. Update `tests/test_db_migration_joblog_v2.py`
   - verify additive columns and backward compatibility
4. Update `tests/test_honorarios_docx.py`
   - cover current-run partial fallback
   - cover historical stored final/partial path reuse
   - cover legacy picker healing

## 7. Tests and acceptance criteria
- Focused tests:
  - `tests/test_db_migration_joblog_v2.py`
  - `tests/test_honorarios_docx.py`
- Acceptance criteria:
  - Save-to-Job-Log Gmail flow does not prompt for translated DOCX when current-run paths are known
  - Historical Job Log Gmail flow auto-uses stored final or partial DOCX when valid
  - Legacy historical rows prompt only when stored paths and exact `run_id` recovery both fail, then persist the selected translated DOCX
  - Cancelling the legacy picker aborts draft creation without affecting honorarios export

## 8. Rollout and fallback
- Rollout is additive and backward compatible.
- Old rows remain valid with blank path fields.
- If a stored path is stale or missing, the user still gets a manual picker fallback.

## 9. Risks and mitigations
- Risk: stale stored paths point to deleted files.
  - Mitigation: validate existence before reuse and fall back to manual picker.
- Risk: legacy rows never gain paths unless the user retries Gmail draft.
  - Mitigation: lazy healing persists the path the first time the user selects it successfully.
- Risk: mixed row payloads may drop hidden DB fields.
  - Mitigation: Job Log row refresh now preserves all row keys, not only visible columns.

## 10. Assumptions/defaults
- Final translated DOCX is the preferred Gmail attachment, with partial DOCX as a backup.
- Storing artifact paths in Job Log is acceptable and lower risk than filename inference.
- This work should remain within the canonical repo-root build and branch.

## 11. Outcome
- Implemented in the canonical repo-root build.
- Historical Gmail draft attachment reuse now resolves in this order:
  1. stored `output_docx_path`
  2. stored `partial_docx_path`
  3. exact `run_id` recovery in normal output locations
  4. manual picker only if no unique valid match exists
- Successful exact recovery or one-time manual selection heals the Job Log row by persisting the translated DOCX path for future reuse.
- Validation:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_db_migration_joblog_v2.py`
  - `./.venv311/Scripts/python.exe -m compileall src tests`
