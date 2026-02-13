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
