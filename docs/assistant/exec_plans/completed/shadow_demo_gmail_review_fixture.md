# Shadow Demo Gmail Review Fixture

## Goal and non-goals
- Add a shadow-only demo Gmail review fixture so the Review Attachments and Preview persistence UX can be manually tested before merge.
- Do not change live Gmail handoff behavior, extension/native-host contracts, route payload shapes used by live Gmail, safe rendering, draft sending, app data, or translation behavior.

## Scope
- In scope: a shadow-only internal demo route, synthetic Gmail review state, one local demo PDF preview cache, a visible shadow test button, and focused tests.
- Out of scope: live Gmail testing, real Gmail/native-host access, OpenAI translation auth, and draft creation.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_persistence`
- Branch name: `codex/gmail-review-preview-persistence`
- Base branch: `origin/main`
- Base SHA: `77204f82e7992b00237fb218426c4ba0578cd8f3`
- Target integration branch: `main`

## Interfaces/types/contracts affected
- Adds internal shadow-only route `POST /api/gmail/demo-review`.
- Public live Gmail/native-host/extension contracts: none.

## Implementation steps
- Add a `GmailBrowserSessionManager.load_demo_review(...)` helper that rejects non-shadow mode and seeds a safe fake loaded Gmail message plus cached local PDF.
- Add the `/api/gmail/demo-review` route and keep it blocked in live mode.
- Add a shadow-only `Load demo attachments` button to the Gmail intake workspace and wire it to the demo route.
- Keep Review Attachments disabled until a real or demo loaded Gmail message exists.

## Tests and acceptance criteria
- Demo route works in shadow mode and seeds at least one PDF attachment.
- Demo route is blocked in live mode.
- Existing preview route returns inline PDF content for the demo attachment.
- Template exposes the shadow demo button.
- Existing Gmail route and persistence tests continue to pass.

## Rollout and fallback
- Validate with targeted Gmail/browser route tests and `scripts/validate_dev.ps1`.
- Restart only the `8888` shadow test server after validation so the user can test.
- If validation fails, keep changes local and do not promote.

## Risks and mitigations
- Risk: demo path leaks into live mode. Mitigation: service and route reject non-shadow mode; tests cover the live block.
- Risk: fake state diverges from real UI path. Mitigation: seed the existing session manager and preview cache, then use normal Review/Preview routes.

## Executed validation
- `git diff --check` passed.
- `Get-Content src\legalpdf_translate\shadow_web\static\gmail.js -Raw | node --input-type=module --check -` passed.
- `.\.venv311\Scripts\python.exe -m py_compile src\legalpdf_translate\gmail_browser_service.py src\legalpdf_translate\shadow_web\app.py` passed.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py tests/test_translation_browser_state.py tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py` passed: 63 passed.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` passed: wrapper pytest 62 passed, compileall passed, agent docs validation passed via direct-Dart fallback, and workspace hygiene validation passed via direct-Dart fallback.
