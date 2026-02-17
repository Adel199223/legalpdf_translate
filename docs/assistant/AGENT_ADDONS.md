# docs/assistant/AGENT_ADDONS.md — Add-ons (Triggered Checklists)

This file contains targeted checklists to prevent expensive rework. Only apply an add-on when its trigger matches.
If multiple triggers match, apply all relevant add-ons.
In your final report, list which add-ons you applied and the evidence (tests/manual checks).

General rule:
- If a checklist says "must", do it before claiming done.
- If uncertain whether a trigger matches, treat it as matching (cheaper than rework).

----------------------------------------------------------------------
ADD-ON: HIGH_RISK_QT_PERSISTENCE
----------------------------------------------------------------------

Trigger (any):
- settings dialogs, autosave/persistence, config write/read
- Qt tables/delegates/edit lifecycle (QTableWidget/QTableView, setCellWidget, delegates)
- normalize_/coerce_/validate_ pipelines in a save path
- dedup keys/IDs, "visible vs hidden" merges, stale view keys
- cross-language or cross-tab propagation/sync of user-entered data

Mandatory BEFORE coding (must report findings briefly):
1) End-to-end data trace (one concrete example row)
   - user action → Qt edit lifecycle (typing vs commit) → signal(s) → read table rows
   - normalize/coerce/validate → save to disk → load from disk → repopulate UI
   - explicitly identify any "silent drop", overwrite, duplication points
2) Silent-filter audit
   - search for normalize_/coerce_/validate_ functions in the save pipeline
   - explicitly confirm whether empty fields (especially empty translation/target) are dropped
3) Qt lifecycle audit
   - explicitly confirm what happens if the user closes the dialog mid-edit
   - ensure "commit active editor + final save" exists (do not rely only on cellChanged)
4) Idempotence / dedup audit
   - prove repeated autosaves do not create duplicates
   - if keys can change, refresh keys after save or dedup on write

Mandatory acceptance tests (manual; must run and report step-by-step):
A) Draft persistence with empty translation
   - Add row → type ONLY Source phrase → do NOT press Enter/Tab → close dialog immediately → reopen
   - Row must still exist (no silent drop).
B) Mid-edit close persistence
   - Start editing an existing cell (cursor still active) → close dialog → reopen
   - Final text must be saved.
C) Repeat-save idempotence
   - Make two edits that trigger autosave twice → reopen
   - No duplicates; stable counts.
D) Cross-language propagation + restart
   - Add Source phrase in one target language view → switch to other target languages: row exists
   - Restart app: row exists everywhere.

Required commands (PowerShell; adapt patterns to the task):
    rg -n "normalize_|coerce_|validate_|save_gui_settings|load_gui_settings|persist|autosave|glossary" src/legalpdf_translate
    python -m pytest -q
    python -m compileall src tests

Deliverables:
- code changes
- short report covering the 4 investigations + A–D results
- regression test(s) where feasible (pure logic) or a stable manual repro script (UI)

----------------------------------------------------------------------
ADD-ON: DEFERRED_DOCS_NOTES
----------------------------------------------------------------------

Trigger (all):
- you changed anything under src/ or tests/
- user did NOT request "docs refresh / update assistant docs"

Goal:
- capture exactly what would need to be updated later, without spending tokens updating docs now.

Mandatory action:
1) Append an entry to: docs/assistant/DOCS_REFRESH_NOTES.md
2) Do NOT edit other docs/assistant/* yet.

If DOCS_REFRESH_NOTES.md does not exist:
- create it as an empty file, then append the entry.

Entry format (copy this structure exactly; keep it short):
## YYYY-MM-DD — <branch> (<commit if available>)
- Files changed:
  - <path>
  - <path>
- Key symbols / entrypoints changed:
  - <file>::<symbol>
  - <file>::<symbol>
- Behavior changes (user-visible):
  - <bullet>
  - <bullet>
- Tests:
  - python -m pytest -q <optional focused tests>
  - python -m compileall src tests

Required commands:
    git status --short
    git rev-parse --abbrev-ref HEAD
    git rev-parse --short HEAD
    git diff --name-only

Deliverable:
- The notes entry exists and matches the actual diff.

----------------------------------------------------------------------
ADD-ON: COST_CONTROL_API
----------------------------------------------------------------------

Trigger (any):
- app→API prompting, model selection, params, token limits
- caching behavior, retries, chunking, OCR/translation pipeline
- parallel workers / concurrency / rate limit behavior
- anything likely to increase number of API calls or tokens

Mandatory BEFORE coding:
1) Identify where cost is controlled
   - where model/params are selected
   - where caching is applied and cache keys are computed
   - where concurrency/workers are configured
2) Identify worst-case cost increase risk
   - "more calls" (chunking, retries, per-page calls)
   - "more tokens per call" (prompt bloat, glossary injection size)
   - "more parallelism" (rate limits, retries cascade)

Mandatory acceptance evidence (must report):
- Before/after: how many API calls happen in a representative run (or why unchanged)
- Before/after: any change to prompt size limits / max_tokens / chunk sizes / glossary injection size
- Cache: confirm hit/miss behavior on a second run (or why not applicable)
- Concurrency: state the default workers and why it's safe

Recommended commands (adapt to repo; show exact outputs used):
    rg -n "model|max_tokens|temperature|cache|retry|chunk|worker|parallel|rate" src/legalpdf_translate
    python -m pytest -q
    python -m compileall src tests

Deliverables:
- safe defaults (conservative)
- optional "power user" override only if requested
- no secrets printed/logged

----------------------------------------------------------------------
ADD-ON: REGRESSION_TEST_REQUIREMENT
----------------------------------------------------------------------

Trigger (any):
- bug fix or behavior change in a core workflow:
  translation, glossary handling, export, settings persistence, diagnostics, OCR pipeline, UI correctness

Rule:
- Prefer automated tests. If UI makes automation heavy, add a stable manual repro script plus at least one unit test for the underlying logic if possible.

Mandatory:
1) Add at least one regression test OR a focused manual repro script that is deterministic.
2) Test must fail before and pass after (or be clearly explained if not possible).

Required commands:
    python -m pytest -q
    python -m compileall src tests

Deliverables:
- test(s) added/updated OR documented manual repro script
- report includes exactly how to run it

----------------------------------------------------------------------
ADD-ON: UI_LAYOUT_CLIPPING_RESPONSIVENESS
----------------------------------------------------------------------

Trigger (any):
- text clipping ("Exact/Contains/Auto" cut off)
- controls cut off, layout collapses, resizing issues, DPI scaling problems
- alignment/centering/overflow regressions

Mandatory checks:
1) Resize sweep (manual)
   - normal size → smaller than content → larger
   - confirm no unusable 1–2 px collapsed controls
2) Text fit
   - ensure combo/button text fits fully (or control widens)
   - prefer fixing size policies / layouts first; QSS only if necessary and scoped
3) DPI sanity (if feasible)
   - Windows scaling (e.g., 100% vs 125%) basic check

Guidance:
- Prefer layout/sizePolicy/column sizing fixes over hard-coded pixel widths.
- If using QSS, scope by objectName to avoid global regressions.

Deliverables:
- clear before/after description (what clipped, what changed)
- manual steps confirming the UI is usable at small sizes
- tests where feasible (non-UI logic) + validation commands

----------------------------------------------------------------------
ADD-ON: SAFE_ENVIRONMENT_INSPECTION
----------------------------------------------------------------------

Trigger (any):
- packaging/installer issues, missing deps, startup crash
- "works on my machine" differences, environment-specific behavior

Allowed (safe) inspection:
- python version, package versions, platform info
- app logs (with redaction), config files that do not contain secrets
- lockfiles (requirements/pyproject/poetry), build scripts

Forbidden:
- reading/printing `.env` contents
- printing API keys/tokens/headers
- copying large log dumps without redaction

Mandatory:
1) State what you inspected (paths/commands) and what you found.
2) Redact sensitive strings in any shared output.
3) Prefer reproducible diagnostics commands over guesswork.

Suggested commands:
    python --version
    python -c "import sys; print(sys.executable); print(sys.version)"
    python -m pip freeze
    git status --short

Deliverables:
- short diagnosis with evidence
- concrete fix steps
- validation commands run

----------------------------------------------------------------------
END
----------------------------------------------------------------------

Usage reminder:
- Apply only what triggers.
- If you applied HIGH_RISK_QT_PERSISTENCE, you must run and report A–D acceptance tests.
- If you changed src/ or tests/ and docs refresh is deferred, you must append DEFERRED_DOCS_NOTES.
