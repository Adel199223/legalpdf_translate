# Browser Test Portability and Upload Race Hardening

## Goal and non-goals
- Goal: make the browser-module Node probe tests portable across normal Node environments without relying on repo-global ESM defaults.
- Goal: harden local source upload transactions so stale or out-of-order upload results cannot overwrite the visible `#new-job` source/action state.
- Goal: keep the beginner-facing browser `ui=qt` `#new-job` surface visually unchanged except for necessary pending-upload helper/disable behavior.
- Non-goal: redesign Gmail intake, interpretation, completion surfaces, or the broader browser shell.
- Non-goal: change backend translation APIs, route contracts, or `ui=legacy`.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/shadow_web/static/translation.js`
  - one shared Python test helper under `tests/`
  - `tests/test_translation_browser_state.py`
  - `tests/test_shadow_web_route_state.py`
  - `tests/test_gmail_review_state.py`
- Out of scope:
  - production `package.json`
  - other Node-backed browser-module tests outside the requested trio
  - Gmail intake UX redesign
  - backend translation/job API changes

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- base SHA: `f70d65c92df8`
- target integration branch: `main`
- canonical build status: canonical worktree on top of approved base floor `4e9d20e`

## Interfaces/types/contracts affected
- Preserve:
  - `?mode=live|shadow`
  - `?workspace=<id>`
  - `#new-job`
  - `#gmail-intake`
  - `ui=legacy`
  - `/api/translation/upload-source`
  - existing prepared Gmail launch payloads and translation field names
- Add only:
  - a shared Python-side Node probe helper for temporary ESM module workspaces
  - internal browser-side guards around the existing source upload transaction model

## File-by-file implementation steps
1. Add a shared Node probe helper under `tests/`:
   - copy `src/legalpdf_translate/shadow_web/static/` into a temp workspace
   - write temp `package.json` with `{ "type": "module" }`
   - expose temp module URLs and a shared `subprocess.run` wrapper with timeout plus stdout/stderr-rich failures
2. Refactor the requested Node-backed tests:
   - `tests/test_translation_browser_state.py`
   - `tests/test_shadow_web_route_state.py`
   - `tests/test_gmail_review_state.py`
   - keep Node-missing skip behavior unchanged
3. Update `translation.js`:
   - require an active transaction-token/file-key match before any upload commit or rollback mutates visible/manual/prepared state
   - ignore stale success/failure completions entirely
   - block visible picker/card/drop interactions while `manual-uploading`
   - keep same-file upload caching and active Gmail rollback behavior intact
4. Expand translation-browser race coverage:
   - stale success after newer success
   - stale failure after newer success
   - stale success while newer upload is still pending
   - prepared Gmail plus stale failed replacement
   - blocked visible pick behavior while pending

## Tests and acceptance criteria
- Validation target:
  - `python -m pytest -q tests/test_translation_browser_state.py`
  - `python -m pytest -q tests/test_shadow_web_route_state.py`
  - `python -m pytest -q tests/test_gmail_review_state.py`
  - `python -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - `python -m compileall src tests`
  - `dart run tooling/validate_agent_docs.dart` if ExecPlan/docs are touched
  - `dart run tooling/validate_workspace_hygiene.dart` if available
  - if `dart run` fails with the known AOT snapshot issue, rerun both with the direct Dart executable and report both commands clearly
- Acceptance:
  - the three requested Node-backed tests no longer depend on environment-specific ESM defaults
  - stale upload results cannot change the visible source/action state
  - prepared Gmail rollback still works for the active failed replacement only
  - the `#new-job` screen stays visually stable except for blocked pending-upload interactions and helper copy

## Rollout and fallback
- Keep all browser behavior changes internal to the existing source upload flow.
- If stale-upload suppression conflicts with prepared Gmail rollback, prefer preserving the currently visible prepared/manual source over surfacing stale diagnostics or state.
- Leave other Node probe tests untouched in this pass and record them as a later portability sweep candidate if needed.

## Risks and mitigations
- Risk: test helper drift if each test keeps embedding its own Node harness assumptions.
  - Mitigation: centralize temp-module workspace setup and Node subprocess execution in one helper.
- Risk: stale upload completions still mutate shared cache fields indirectly.
  - Mitigation: guard every async success/failure path before cache/path/manual/prepared mutations.
- Risk: blocking visible picks during upload could strand the browse button in a confusing state.
  - Mitigation: pair the disabled/ignored interactions with explicit helper copy that the document is still being checked.

## Assumptions/defaults
- Use a copied temp `static/` tree, not symlinks, for the Node ESM workspace.
- Scope the portability helper to the three requested tests only in this pass.
- Block visible new picks while upload is pending instead of allowing visible supersession.
- Local `.env`, generated DOCX files, run folders, `.pytest_cache`, `requirements_freeze.txt`, `rg_*` scratch files, and build artifacts are ignored and must not be relied upon.

## Outcome
- Added `tests/browser_esm_probe.py` so the three requested Node-backed browser-module tests run from a temp ESM workspace with copied browser static assets, a temp `package.json`, explicit timeouts, and stdout/stderr-rich failures.
- Refactored `tests/test_translation_browser_state.py`, `tests/test_shadow_web_route_state.py`, and `tests/test_gmail_review_state.py` to use that shared helper.
- Hardened `translation.js` so only the active source-upload transaction may commit or roll back visible state; stale success/failure completions now no-op.
- Blocked visible source-card click, browse-button click, and drag/drop actions during `manual-uploading` while still allowing programmatic/test-driven input changes to exercise race safety.
- Left the broader browser UI, backend APIs, Gmail intake routing, interpretation flow, and other direct Node ESM tests untouched.

## Validation Notes
- Plain `python -m pytest ...` commands on this machine resolved to `C:\Python314\python.exe`, which does not have `pytest` installed; the requested pytest coverage was therefore validated with `.\.venv311\Scripts\python.exe -m pytest ...`.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py` -> `5 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> `3 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> `1 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py` -> `54 passed`
- `python -m compileall src tests` -> succeeded
- `dart run tooling/validate_agent_docs.dart` -> failed in this environment with `Unable to find AOT snapshot for dartdev`
- `dart run tooling/validate_workspace_hygiene.dart` -> failed in this environment with `Unable to find AOT snapshot for dartdev`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> `PASS`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> `PASS`
