# App Audit And Optimization Pass

## 1. Title
Broad audit and optimization pass for the latest-feature build, with emphasis on recent interpretation notice autofill, OCR diagnostics/defaults, Gmail interpretation reporting, and honorarios PDF export behavior.

## 2. Goal and Non-Goals
- Goal:
  - Verify that the newer feature worktree behaves correctly across the app, especially in the recently modified interpretation/OCR/export flows.
  - Identify correctness gaps, regression risks, stale defaults, UX/reporting inconsistencies, and obvious optimization opportunities.
  - Implement concrete fixes discovered during the audit and add targeted coverage where practical.
- Non-goals:
  - No release/publish/deploy work.
  - No unrelated large-scale visual redesign.
  - No destructive cleanup of unrelated pending local changes.

## 3. Scope (In/Out)
- In scope:
  - Recent interpretation notice metadata extraction and OCR fallback behavior.
  - OCR settings defaults, diagnostics, effective key resolution, and related tooling consistency.
  - Honorarios DOCX/PDF export behavior, retry flow, local-only handoff UX, and Gmail draft gating/reporting.
  - Adjacent app paths that touch those newer flows, including Job Log, Gmail intake/finalization, and targeted runtime/tooling/test consistency.
- Out of scope:
  - Unrelated translation pipeline redesign.
  - Commit/push/merge work unless explicitly requested.
  - Blanket docs rewrite during the audit itself.

## 4. Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical audit worktree; canonical build remains `C:\Users\FA507\.codex\legalpdf_translate` on `main`
- Current HEAD at audit start: `5c9842e3fbec1ca2351507f1f31bbf8b5b7ffa02`

## 5. Interfaces/Types/Contracts Affected
- Interpretation notice metadata extraction result/diagnostics contracts.
- OCR effective credential/default resolution and provider/env fallback behavior.
- Gmail interpretation session report payload sections for metadata extraction and PDF export.
- Honorarios export dialog/result behavior around retry, local-only continuation, and draft gating.
- Job Log and Save/Edit Job Log autofill UX contract for interpretation vs translation.

## 6. File-by-File Implementation Steps
- Review and harden:
  - `src/legalpdf_translate/metadata_autofill.py`
  - `src/legalpdf_translate/ocr_engine.py`
  - `src/legalpdf_translate/user_settings.py`
  - `src/legalpdf_translate/workflow.py`
  - `src/legalpdf_translate/gmail_batch.py`
  - `src/legalpdf_translate/word_automation.py`
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/worker.py`
  - `tooling/ocr_preflight.py`
  - `tooling/ocr_translation_probe.py`
- Audit supporting tests and extend them where they can pin down discovered regressions:
  - `tests/test_metadata_autofill_header.py`
  - `tests/test_qt_app_state.py`
  - `tests/test_honorarios_docx.py`
  - `tests/test_user_settings_schema.py`
  - `tests/test_ocr_preflight.py`
  - `tests/test_ocr_translation_probe.py`
- Inspect adjacent runtime/docs knowledge only as needed to validate assumptions or identify stale behavioral descriptions.

## 7. Tests and Acceptance Criteria
- Acceptance criteria:
  - No newly discovered correctness bug in the recent interpretation/OCR/export flow remains unfixed if it can be resolved locally in this pass.
  - OCR defaults are consistent across runtime and tooling, with legacy compatibility preserved intentionally.
  - Interpretation metadata extraction and honorarios export state/reporting are coherent across manual and Gmail-driven flows.
  - Any discovered regressions or residual risks are documented explicitly if they cannot be fixed in this pass.
- Validation targets:
  - Targeted unit tests where runnable.
  - `py_compile` / syntax validation over changed source and tests.
  - `git diff --check`.
  - Additional focused inspection and static review when the environment blocks full runtime tests.

## 8. Rollout and Fallback
- Make small, reviewable fixes in the current feature worktree.
- Prefer additive, backward-compatible changes for diagnostics/report payloads.
- If a broader environment issue blocks runtime validation, preserve safe behavior and record the blocker explicitly.

## 9. Risks and Mitigations
- Risk: environment/tooling limitations may prevent full pytest or manual end-to-end verification.
  - Mitigation: maximize static validation, targeted tests, and code-path inspection; report the exact blocker.
- Risk: broad audit could drift into unrelated cleanup.
  - Mitigation: keep implementation scoped to correctness, regression prevention, and clear optimization wins.
- Risk: stale docs may lag behavior after the audit.
  - Mitigation: flag docs-sync need separately after implementation changes settle.

## 10. Assumptions/Defaults
- The latest-feature worktree is the correct implementation target for this audit.
- Existing unrelated local changes, including `docs/assistant/SESSION_RESUME.md`, must remain untouched.
- Sub-agents may be used for bounded parallel audit passes, but the main thread remains responsible for integration decisions and edits.

## 11. Executed Validations and Outcomes
- Code-path audit completed across the recent interpretation/OCR/export changes plus adjacent direct honorarios entry points.
- Concrete fixes applied during the audit:
  - Honorarios PDF export retry now uses the same longer timeout budget for Word preflight as for export execution.
  - Manual/direct honorarios entry points now show the explicit local-only ready handoff after `Continue local-only`.
  - Translation Job Log rows without a source PDF no longer inherit the interpretation-only manual PDF picker fallback.
- Validation outcomes:
  - `py_compile` passed for touched source and test files.
  - `git diff --check` passed.
  - Targeted `pytest` re-run remained blocked by the broken local Python 3.11 runtime (`ModuleNotFoundError: No module named '_socket'`) before test collection.

## Execution Notes / Outcomes
- Concrete issues fixed during this audit pass:
  - `tooling/ocr_translation_probe.py` now passes the effective `OCR_API_KEY_ENV_NAME` into `run_ocr_preflight(...)`, so probe preflight reflects the same OCR credential source the app/runtime will actually use.
  - `tooling/ocr_preflight.py` now falls back to the configured app OCR env name when no explicit `OCR_API_KEY_ENV_NAME` override is provided, so the standalone preflight tool also stays aligned with app settings.
  - `tests/test_honorarios_docx.py` was updated so its `_begin_pdf_export` monkeypatches match the current `timeout_seconds` signature introduced by the retryable PDF export flow.
  - Added targeted probe/preflight coverage for effective OCR env propagation and settings fallback in `tests/test_ocr_translation_probe.py` and `tests/test_ocr_preflight.py`.
- Validation executed:
  - `py_compile` over the touched source/tooling/tests -> pass.
  - `python -m compileall src tooling tests` using `C:\Python314\python.exe` -> pass.
  - `git diff --check` -> pass.
  - `C:\Python314\python.exe -m pytest --version` -> failed because that interpreter does not have `pytest` installed.
  - The existing project Python 3.11 runtime remains blocked earlier in startup by the machine-level `_socket` issue, so full pytest execution is still not available from the intended environment.
