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
