# Browser Translation Finish and Gmail Finalization Beginner Qt Polish

## Goal and non-goals
- Goal: make the browser `ui=qt` translation finish/save/finalization surfaces feel beginner-friendly and Qt-like while preserving translation, Arabic review, Gmail save/finalization, and report behavior.
- Goal: clarify the main next steps after completion: review the result, download the translated DOCX, save the case record, save the current Gmail attachment, and create the Gmail reply.
- Non-goal: change backend APIs, translation semantics, Gmail session progression, Arabic review mechanics, interpretation behavior, or route contracts.
- Non-goal: remove reports, diagnostics, or operator-only information.

## Scope (in/out)
- In:
  - browser completion drawer copy and action grouping
  - translation save form labels and helper text
  - Arabic review card wording
  - Gmail current-attachment save card wording
  - Gmail batch finalization drawer wording
  - focused browser markup/state tests for those surfaces
- Out:
  - backend service behavior
  - Gmail/Arabic review APIs
  - interpretation review/finalization redesign
  - `ui=legacy` and route-contract changes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-new-job-qt-polish`
- Base branch: `main`
- Base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- Target integration branch: `main`
- Canonical build status or intended noncanonical override: noncanonical feature branch used for browser UX iteration only; no runtime contract changes.

## Interfaces/types/contracts affected
- No backend, route, query-param, Gmail, Arabic-review, or translation API contract changes.
- Add one additive browser-only display helper in `translation.js` for finish-surface presentation.
- Keep all existing DOM IDs, button IDs, field IDs, and download/report endpoints intact.

## File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - rewrite beginner-visible completion/save/finalization copy
  - regroup completion downloads into primary actions plus one compact secondary collapsible
  - de-emphasize technical report/download language without removing actions
- `src/legalpdf_translate/shadow_web/static/translation.js`
  - add one pure finish-surface presentation helper
  - route completion/save/Arabic/Gmail current-attachment copy through that helper
  - keep all action/state behavior intact
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - rewrite beginner-visible Gmail batch finalization status/result/button copy only
- `src/legalpdf_translate/shadow_web/static/style.css`
  - support the promoted primary actions and secondary collapsible grouping in the completion drawer
- Tests
  - update `tests/test_shadow_web_api.py`
  - extend `tests/test_translation_browser_state.py`
  - touch Gmail tests only if finalization beginner-copy assertions require it

## Tests and acceptance criteria
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
- `.\.venv311\Scripts\python.exe -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart` if docs are touched; use direct Dart executable if `dartdev` AOT is broken.
- `dart run tooling/validate_workspace_hygiene.dart` if available; same fallback rule.
- Acceptance: the finish drawer reads like a normal app finish screen, primary next-step actions are obvious, technical reports/diagnostics are secondary, and existing translation/Gmail/Arabic-review behavior is unchanged.

## Rollout and fallback
- Keep the current drawer IDs, action handlers, and download/report endpoints untouched so the pass remains a presentation refactor only.
- If a wording/grouping change risks breaking Arabic review or Gmail continuation, preserve the current behavior and narrow the copy-only portion.

## Risks and mitigations
- Risk: completion copy becomes inconsistent across completed/analyze/loaded-row/Gmail cases.
  - Mitigation: centralize beginner wording in one pure helper instead of spreading string changes across renderers.
- Risk: de-emphasizing report actions hides needed outputs.
  - Mitigation: keep them reachable through one compact secondary collapsible and preserve all existing IDs.
- Risk: Arabic review and Gmail confirm blockers become unclear.
  - Mitigation: keep blocker logic unchanged and only rewrite the helper text into plain language.

## Assumptions/defaults
- Keep `Finish Translation` as the drawer title.
- Use one compact secondary collapsible for extra downloads/options rather than removing or renaming any report endpoints.
- Move only `Run ID` into a collapsed details area; keep `Target language` visible in the main save form.
- APP_KNOWLEDGE and user guides remain unchanged unless this pass creates an immediate docs mismatch beyond the ExecPlan lifecycle update.

## Validation results
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections` -> `1 passed in 1.48s`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py` -> `6 passed in 0.34s`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> `1 passed in 0.24s`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"` -> `5 passed, 9 deselected in 0.62s`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py` -> `55 passed in 130.17s (0:02:10)`
- `.\.venv311\Scripts\python.exe -m compileall src tests` -> succeeded
- `dart run tooling/validate_agent_docs.dart` -> failed with `Unable to find AOT snapshot for dartdev`
- `dart run tooling/validate_workspace_hygiene.dart` -> failed with `Unable to find AOT snapshot for dartdev`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> `PASS: agent docs validation succeeded.`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> `PASS: workspace hygiene validation succeeded.`
