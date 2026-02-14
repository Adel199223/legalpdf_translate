# UPDATE_POLICY

## Mandatory Policy
Any task that changes files under `src/` or `tests/` must also update relevant documentation under `docs/assistant/*` in the same task. This keeps the ChatGPT Project knowledge pack accurate.

## Doc-Update Checklist
When code changes, update the matching documentation sections:
- Architecture map updates:
  - New/removed/renamed modules, classes, functions, entrypoints.
- Pipeline updates:
  - Stage order, routing decisions, retry behavior, output flow.
- Knobs/flags/settings updates:
  - New defaults, renamed settings keys, changed CLI flags.
- Diagnostics/report artifacts:
  - Added/removed fields, files, run-folder outputs, export paths.
- Prompt factory updates:
  - Add/adjust examples that reflect new real paths and tests.
- API prompt catalog updates:
  - If prompt templates, system instructions, prompt builder logic, retry prompt wrappers, or API payload shape changes, update `docs/assistant/API_PROMPTS.md` (sections B-H).
- Uncertainty notes refresh:
  - Remove stale `Uncertain` notes when verified, or add new ones with commands.

## Required Verification on Doc Updates
Run and capture results when docs are updated after code changes:
```powershell
git status --short
git diff --name-only
python -m pytest -q
python -m compileall src tests
```

## Docs Refresh Workflow (Manual, Repeatable)
When code changes, run a docs-only Codex refresh task that updates `docs/assistant/*` from current repo state.
- Refresh `APP_KNOWLEDGE.md`, `CODEX_PROMPT_FACTORY.md`, and `UPDATE_POLICY.md` (and `PROJECT_INSTRUCTIONS.txt` if guidance changed).
- In that refresh task, do not modify `src/` or `tests/`.

## Mini Changelog (Append-Only)
Append an entry for each update using this format:

```text
Date: YYYY-MM-DD
Code change summary:
- <brief bullets>

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: <...>)
- docs/assistant/PROJECT_INSTRUCTIONS.txt (sections: <...>)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: <...>)
- docs/assistant/UPDATE_POLICY.md (sections: <...>)

Verification commands/results:
- python -m pytest -q -> <result>
- python -m compileall src tests -> <result>
- git status --short -- src tests -> <result>
```

## Ownership Rule
If a task owner is unsure whether docs need updates, default to updating docs and citing exact changed paths/symbols.

Date: 2026-02-13
Code change summary:
- Finalized Arabic DOCX RTL output handling in `src/legalpdf_translate/docx_writer.py` with run-level directional segmentation, RTL paragraph defaults, and placeholder cleanup before write.
- Added regression coverage for mixed RTL/LTR output and isolate-control stripping in `tests/test_docx_writer_rtl.py`.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, I, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - added Example 9)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 121 passed in 5.24s
- python -m compileall src tests -> success
- git status --short -- src tests -> M src/legalpdf_translate/docx_writer.py; ?? tests/test_docx_writer_rtl.py

Date: 2026-02-13
Code change summary:
- Added minimal glossary enforcement for AR legal phrasing with file-based JSON rules and built-in defaults (`src/legalpdf_translate/glossary.py`).
- Integrated glossary loading/application into workflow output finalization and added config wiring across Qt settings, CLI, and checkpoint fingerprinting.
- Added regression coverage for glossary behavior, workflow integration, CLI precedence, settings defaults, and resume compatibility.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 132 passed in 6.88s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added per-language glossary table support with normalization helpers and prompt formatting in `src/legalpdf_translate/glossary.py`.
- Added settings schema support for `glossaries_by_lang` + one-time AR seed tracking in `src/legalpdf_translate/user_settings.py`.
- Added a dedicated Glossary tab in Qt Settings with language selector and editable source/target/match rows in `src/legalpdf_translate/qt_gui/dialogs.py`.
- Added workflow glossary prompt injection via `src/legalpdf_translate/workflow.py::_append_glossary_prompt` while keeping legacy deterministic fallback behavior.
- Added regression tests for glossary normalization, settings migration/roundtrip, prompt injection, and glossary-table UI logic.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 156 passed in 5.99s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Updated glossary entry schema to source-keyed canonical fields with per-row source language (`source_text`, `preferred_translation`, `match_mode`, `source_lang`) in `src/legalpdf_translate/glossary.py`.
- Switched workflow glossary enforcement to prompt-only guidance and added source-language detection/filtering in `src/legalpdf_translate/workflow.py` (`_append_glossary_prompt` path); removed blind post-output glossary rewriting from `_evaluate_output`.
- Updated Qt Settings Glossary tab table to include `Source lang` and renamed source column to `Source phrase (PDF text)` in `src/legalpdf_translate/qt_gui/dialogs.py`.
- Updated settings normalization/seeding compatibility for the new schema and seed versioning in `src/legalpdf_translate/user_settings.py`.
- Extended glossary/settings/workflow/Qt-table tests for source-language-aware behavior and backward-compatible migration.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 160 passed in 4.86s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added tiered glossary entries (`tier` 1..6), per-target active tiers, tier-aware prompt filtering/sorting/capping, and backward-compatible tier migration defaults.
- Added searchable glossary UI with `Ctrl+F`, tier selector view, active tier checkboxes, tier counts, and non-blocking glossary hygiene warnings in Settings.
- Added workflow tier-aware token-efficient glossary injection (active tiers only, sorted, capped at 50 entries / 6000 chars).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 173 passed in 5.09s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added learning-only Study Glossary core logic in `src/legalpdf_translate/study_glossary.py` (term mining, scoring, 20-80 coverage selection, merge helpers, language expansion, review-date helpers, translation fill helper).
- Added Study Glossary settings schema + normalization in `src/legalpdf_translate/user_settings.py` (`study_glossary_entries`, snippets/corpus/coverage keys).
- Added a dedicated Study Glossary settings tab in `src/legalpdf_translate/qt_gui/dialogs.py` with run-folder builder, search/filters, suggestions table, review statuses, and translation refresh/quiz actions.
- Added regression tests for Study Glossary algorithm/settings/prompt isolation and Qt method-level table behaviors.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/PROJECT_INSTRUCTIONS.txt (routing rule for Study Glossary)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 194 passed in 5.20s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Hardened Study Glossary coverage to use non-overlapping longest-match assignment (`tri->bi->uni`) in `src/legalpdf_translate/study_glossary.py` (`tokenize_pt`, `build_ngram_index`, `count_non_overlapping_matches`, `compute_non_overlapping_tier_assignment`).
- Added subsumption suppression for noisy short suggestions (`apply_subsumption_suppression`) and wired deterministic coverage+tiering in Study Glossary candidate finalization path (`src/legalpdf_translate/qt_gui/dialogs.py::_on_study_candidate_finished`).
- Added content-only Markdown export for consistency glossary in Qt settings (`src/legalpdf_translate/qt_gui/dialogs.py::_export_consistency_glossary_markdown`, `src/legalpdf_translate/glossary.py::build_consistency_glossary_markdown`).
- Kept consistency glossary dynamic language expansion robust by making `serialize_glossaries(...)` accept caller-provided supported languages and using that in `src/legalpdf_translate/user_settings.py::load_gui_settings`.
- Added regression coverage for non-overlapping coverage behavior, subsumption demotion, consistency export format, future-language glossary expansion, and prompt-isolation lock tests.

Docs updated:
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 205 passed in 5.10s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added Study Glossary corpus source modes in Qt settings (`run_folders`, `current_pdf`, `select_pdfs`, `joblog_runs` unavailable) with persisted settings keys and UI state/validation paths.
- Wired active main-window PDF into settings dialog (`src/legalpdf_translate/qt_gui/app_window.py::_open_settings_dialog`) for `Current PDF only` Study corpus mode.
- Extended Study candidate worker inputs in `src/legalpdf_translate/qt_gui/dialogs.py::_StudyCandidateWorker` to support direct PDF sources while preserving streaming/cancel behavior and keeping Study prompt-isolated.
- Added optional manual `Copy selected to AI Glossary...` action in Study tab with explicit confirmation, defaults (`exact`, `PT`, `tier 2`), duplicate-skip behavior, and conflict skip/replace prompt.
- Added regression tests for new study settings keys/normalization, corpus source input resolution, and Study-to-AI merge semantics.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: F)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 211 passed in 5.37s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added integrated consistency Glossary Builder and Calibration Audit backends:
  - `src/legalpdf_translate/glossary_builder.py` (frequency mining, thresholds, deterministic suggestions, markdown/json rendering).
  - `src/legalpdf_translate/calibration_audit.py` (deterministic sampling, forced OCR comparison path, verifier JSON retry handling, audit artifacts).
- Added project+personal consistency glossary scope support and merge helpers in `src/legalpdf_translate/glossary.py` (`load_project_glossaries`, `merge_glossary_scopes`, `save_project_glossaries`) and wired runtime merge in `src/legalpdf_translate/workflow.py::TranslationWorkflow.run`.
- Added optional per-language prompt addendum path (`prompt_addendum_by_lang`) with deterministic append marker block in `src/legalpdf_translate/workflow.py::_append_prompt_addendum`.
- Added Qt actions/dialogs for both tools in:
  - `src/legalpdf_translate/qt_gui/app_window.py` (`Glossary Builder...`, `Calibration Audit...`)
  - `src/legalpdf_translate/qt_gui/tools_dialogs.py` (`QtGlossaryBuilderDialog`, `QtCalibrationAuditDialog`, worker/cancel/progress/apply flows).
- Kept Study Glossary prompt-isolated and consistency prompt injection path unchanged (`_append_glossary_prompt` still consumes only consistency glossary source).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (builder/audit architecture + settings/scope merge + addendum + navigation entries)
- docs/assistant/API_PROMPTS.md (addendum insertion + calibration verifier prompt/retry templates)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 218 passed in 5.79s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified/untracked files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Implemented OCR auto-mode quality routing in `src/legalpdf_translate/workflow.py` with `classify_extracted_text_quality(...)`, explicit `ocr_request_reason` (`required|helpful|not_requested`), and conservative signal-based helpful detection.
- Switched OCR initialization to lazy on-demand preflight (no run-start preflight), added `ocr_preflight_checked` tracking, and added explicit events `ocr_preflight_checked`, `ocr_required_but_unavailable`, `ocr_helpful_but_unavailable`.
- Enforced cost guardrail for helpful OCR: local-only attempts in auto mode; if unavailable, direct-text fallback with info-only event and `ocr_failed_reason="helpful_unavailable"`.
- Extended summary/report payloads in `src/legalpdf_translate/workflow.py` and `src/legalpdf_translate/run_report.py` with additive OCR fields (`ocr_required_pages`, `ocr_helpful_pages`, `ocr_preflight_checked`) and non-misleading warning semantics.
- Added deterministic OCR routing coverage in `tests/test_workflow_ocr_routing.py` and expanded `tests/test_run_report.py` for required-vs-helpful unavailable reporting behavior.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: D, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - added Example 12)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 232 passed in 5.50s
- python -m compileall src tests -> success
- git status --short -- src tests -> M src/legalpdf_translate/ocr_engine.py; M src/legalpdf_translate/run_report.py; M src/legalpdf_translate/workflow.py; M tests/test_run_report.py; ?? tests/test_workflow_ocr_routing.py

Date: 2026-02-13
Code change summary:
- Hardened Arabic sensitive-value locking in `src/legalpdf_translate/arabic_pre_tokenize.py` by tokenizing full `Nome`/`Morada`/`IBAN`/case-value spans as single `[[...]]` tokens and adding `extract_locked_tokens(...)`.
- Extended Arabic normalization in `src/legalpdf_translate/output_normalize.py` with deterministic expected-token auto-fix before isolate wrapping (`normalize_output_text_with_stats`, `autofix_expected_ar_tokens`).
- Extended `src/legalpdf_translate/validators.py::validate_ar` to accept `expected_tokens` and fail on locked-token mismatch with count diagnostics (`missing_count`, `altered_count`, `unexpected_count`).
- Wired expected-token enforcement through `src/legalpdf_translate/workflow.py` for both initial and retry evaluation, with diagnostics-only events `ar_locked_token_autofix_applied` and `ar_locked_token_violation`.
- Hardened Arabic system prompt constraints in `resources/system_instructions_ar.txt` with explicit label-value preservation examples and anti-splitting guidance for Word-stable LTR runs.
- Added/updated regression coverage for pretokenization locks, normalize/validator enforcement, workflow auto-fix/fail behavior, and RTL DOCX mixed-direction stability.

Docs updated:
- docs/assistant/API_PROMPTS.md (sections: A, E)
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - added Example 13)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 243 passed in 5.72s
- python -m compileall src tests -> success
- git status --short -- src tests -> M src/legalpdf_translate/arabic_pre_tokenize.py; M src/legalpdf_translate/output_normalize.py; M src/legalpdf_translate/validators.py; M src/legalpdf_translate/workflow.py; M tests/test_docx_writer_rtl.py; M tests/test_output_normalize.py; M tests/test_validators_ar.py; ?? tests/test_arabic_pre_tokenize.py; ?? tests/test_workflow_ar_token_lock.py

Date: 2026-02-13
Code change summary:
- Split shared EN/FR system instructions into language-specific resources:
  - `resources/system_instructions_en.txt` (new)
  - `resources/system_instructions_fr.txt` (new)
- Updated `src/legalpdf_translate/resources_loader.py::load_system_instructions` routing:
  - EN -> `system_instructions_en.txt`
  - FR -> `system_instructions_fr.txt`
  - AR unchanged -> `system_instructions_ar.txt`
- Updated `src/legalpdf_translate/prompt_builder.py::build_retry_prompt` to include language-specific retry compliance hints for EN/FR while keeping wrapper markers and payload shape unchanged.
- Added/updated tests:
  - `tests/test_resources_loader.py` (new)
  - `tests/test_resource_path_resolution.py`
  - `tests/test_prompt_builder.py`
- Updated prompt-contract docs/pointers:
  - `docs/assistant/API_PROMPTS.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/CODEX_PROMPT_FACTORY.md` (added worked EN/FR hardening example)

Verification commands/results:
- python -m pytest -q tests/test_resource_path_resolution.py tests/test_resources_loader.py tests/test_prompt_builder.py -> 9 passed in 0.08s
- python -m pytest -q -> 252 passed in 5.71s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Added Portuguese month-date token classifier `is_portuguese_month_date_token(...)` in `src/legalpdf_translate/arabic_pre_tokenize.py`.
- Updated Arabic workflow enforcement in `src/legalpdf_translate/workflow.py::_process_page` to keep strict token-lock for sensitive values while excluding Portuguese month-name date tokens from strict expected-token matching.
- Added deterministic AR date normalization in `src/legalpdf_translate/output_normalize.py`:
  - recognized month-name dates (`[[10 de fevereiro de 2026]]` or plain `10 de fevereiro de 2026`) normalize to `[[10]] فبراير [[2026]]`,
  - uncertain month parsing falls back to one protected token `[[...]]`,
  - slash dates remain single-token style.
- Updated Arabic instruction contract in `resources/system_instructions_ar.txt` to remove date-rule contradiction and define month-name date behavior + fallback.
- Added/updated tests for month-date classification, AR date normalization/fallback, workflow token-lock compatibility for month-date transformation, and DOCX mixed-direction date stability.

Docs updated:
- docs/assistant/API_PROMPTS.md (sections: A, E)
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - updated Example 13)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_arabic_pre_tokenize.py tests/test_output_normalize.py tests/test_workflow_ar_token_lock.py tests/test_docx_writer_rtl.py -> 24 passed in 1.07s
- python -m pytest -q -> 259 passed in 6.89s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Fixed EN/FR Portuguese month-date leakage by extending `src/legalpdf_translate/output_normalize.py` normalization:
  - Added deterministic PT month-name date conversion for EN (`10 February 2026`) and FR (`10 février 2026`) in `normalize_output_text_with_stats`.
  - Kept slash numeric dates unchanged.
  - Kept unknown/typo month names unchanged (non-fatal).
- Kept AR/RTL behavior unchanged; AR date/token-lock path remains isolated.
- Updated EN/FR system instruction contracts:
  - `resources/system_instructions_en.txt`: removed dates from verbatim-only list and added explicit month-name date translation rule + example.
  - `resources/system_instructions_fr.txt`: removed dates from verbatim-only list and added explicit month-name date translation rule + example.
- Added/updated regression tests:
  - `tests/test_output_normalize.py` for EN/FR month-date conversion, slash-date unchanged, unknown-month unchanged.
  - `tests/test_resources_loader.py` assertions for updated EN/FR instruction content.

Docs updated:
- docs/assistant/API_PROMPTS.md (section: E normalization contract)
- docs/assistant/APP_KNOWLEDGE.md (section: D pipeline normalization notes)
- docs/assistant/CODEX_PROMPT_FACTORY.md (section: 2 - added Example 15)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_output_normalize.py tests/test_resources_loader.py tests/test_prompt_builder.py -> 24 passed in 0.09s
- python -m pytest -q -> 263 passed in 6.02s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Extended EN/FR date normalization in `src/legalpdf_translate/output_normalize.py` from year-only month-name dates to both forms:
  - `DD de <PT_MONTH> de YYYY`
  - `DD de <PT_MONTH>`
  with deterministic conversion to EN (`DD Month [YYYY]`) and FR (`DD mois [YYYY]`), while preserving slash numeric dates.
- Kept AR date/token-lock behavior unchanged and isolated.
- Extended `src/legalpdf_translate/validators.py::validate_enfr` to support `lang`-aware month-date leak checks after normalization, with address-context exemptions to avoid false positives (e.g., `Rua 1.º de Dezembro`).
- Wired EN/FR validator language context through:
  - `src/legalpdf_translate/workflow.py::_evaluate_output`
  - `src/legalpdf_translate/calibration_audit.py`
  - `src/legalpdf_translate/study_glossary.py`
- Updated EN/FR system instructions to:
  - translate institution/court names when stable equivalents exist,
  - keep originals only when uncertain/no stable equivalent,
  - allow dual form only for acronyms (first mention),
  - include anti-calque guidance (`illustre défenseur`, `office de notification`).
- Added/updated tests:
  - `tests/test_output_normalize.py` (no-year month-date conversion + address no-rewrite)
  - `tests/test_validators_enfr.py` (leak rejection + address exemption + legacy no-lang behavior)
  - `tests/test_retry_reason_mapping.py` (workflow evaluate pass/fail for EN/FR month-date guardrail)
  - `tests/test_resources_loader.py` (new EN/FR instruction policy assertions)

Docs updated:
- docs/assistant/API_PROMPTS.md (section: E validator + normalization contract)
- docs/assistant/APP_KNOWLEDGE.md (section: D pipeline validation/normalization notes)
- docs/assistant/CODEX_PROMPT_FACTORY.md (section: 2 - updated Example 15 acceptance criteria)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_output_normalize.py tests/test_validators_enfr.py tests/test_resources_loader.py tests/test_prompt_builder.py -> 33 passed in 0.11s
- python -m pytest -q -> 271 passed in 6.02s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Aligned Arabic prompt contract in `resources/system_instructions_ar.txt` for institution/court/prosecution naming:
  - translate full names to Arabic when a stable equivalent exists (default),
  - keep Portuguese full names only when uncertain/no stable equivalent,
  - allow dual form only for acronyms on first mention,
  - removed deprecated forced full-name bilingual template rule.
- Extended AR resource contract test in `tests/test_resources_loader.py` to assert the new naming-policy text and absence of the old mandatory dual template line.
- Updated prompt/docs references for this AR naming policy:
  - `docs/assistant/API_PROMPTS.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/CODEX_PROMPT_FACTORY.md` (added Example 16)

Verification commands/results:
- python -m pytest -q tests/test_resources_loader.py tests/test_prompt_builder.py -> 8 passed in 0.05s
- python -m pytest -q -> 271 passed in 5.81s
- python -m compileall src tests -> success
