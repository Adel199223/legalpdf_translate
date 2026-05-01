# Job Log Output Word Count Fix

## 1) Title
Fix Job Log `Words: 0` by using translated DOCX output as the canonical word-count source.

## 2) Goal and non-goals
- Goal:
  - make Save-to-Job-Log and persisted Job Log rows use translated output word count
  - prefer final DOCX, then partial DOCX, then `pages/page_*.txt`
  - recompute `expected_total` and `profit` from the corrected word count
- Non-goals:
  - no GPT/OpenAI model changes
  - no schema changes
  - no token-based synthetic word estimation

## 3) Scope (in/out)
- In:
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `tests/test_qt_app_state.py`
- Out:
  - workflow/model selection
  - DB schema changes
  - OCR runtime stabilization changes already in progress

## 4) Interfaces/types/contracts affected
- `build_seed_from_run(...)` accepts output artifact paths in addition to `pages_dir`
- `Words` in Job Log means translated output words

## 5) File-by-file implementation steps
- Add DOCX visible-text extraction and word counting helpers in `dialogs.py`
- Update `build_seed_from_run(...)` to use DOCX-first precedence
- Update `_prepare_joblog_seed(...)` in `app_window.py` to pass output and partial DOCX paths
- Add regression tests covering DOCX-first, partial DOCX, and pages-dir fallback behavior

## 6) Tests and acceptance criteria
- Completed OCR-heavy run with no `pages/` directory uses final DOCX word count
- Partial DOCX fallback works
- Pages-dir fallback still works
- Save-to-Job-Log seed recalculates `word_count`, `expected_total`, and `profit`
- `python -m pytest -q tests/test_qt_app_state.py` passes
- `python -m pytest -q` passes

Executed validation:
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> pass (`40 passed`)
- `./.venv311/Scripts/python.exe -m compileall src tests` -> pass
- `./.venv311/Scripts/python.exe -m pytest -q` -> pass (`556 passed`)
- Real-world spot check on `auto (1)_AR_20260306_165834.docx` -> `1666` words via DOCX-first counter

## 7) Rollout and fallback
- Local-only code change on the active OCR stabilization branch
- If DOCX parsing fails, fall back to partial DOCX, then pages-dir, then `0`

## 8) Risks and mitigations
- Risk: DOCX word count may differ slightly from Word because tokenization is not identical
  - Mitigation: accept small differences; eliminate `0` and keep output-based counting deterministic
- Risk: unrelated OCR stabilization WIP is present on branch
  - Mitigation: keep this fix scoped to Job Log seed/counting only

## 9) Assumptions/defaults
- Canonical meaning of `Words` is translated output words
- Final DOCX is the best source when available
- GPT-5.4 unification remains separate from this fix

## 10) Final outcome
- The `Words: 0` bug in Save-to-Job-Log is fixed for successful OCR-heavy runs that produce a final DOCX but no `pages/` text artifacts.
- `Expected total` and `Profit` now recalculate from the corrected translated-output word count.
- Real-world spot check on `auto (1)_AR_20260306_165834.docx` produced `1666` words via the DOCX-first counter, which is close to Microsoft Word's visible count and materially correct for billing.
