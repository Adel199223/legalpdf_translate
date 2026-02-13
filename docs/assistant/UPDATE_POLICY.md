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
