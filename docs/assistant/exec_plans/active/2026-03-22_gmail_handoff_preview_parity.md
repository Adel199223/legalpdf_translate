# Gmail Handoff Speed and Qt-Style Preview Parity

## Title
Speed up Gmail browser handoff and replace raw attachment downloads with a Qt-style preview workflow in the browser app.

## Goal and non-goals
- Goal:
  - make Gmail extension clicks feel faster on the browser-first flow
  - make Gmail PDF preview behave like the Qt preview dialog: inline, page-aware, and start-page-driven
- Non-goals:
  - no resident tray/helper process
  - no Gmail bridge ownership change
  - no popup-window workflow
  - no Qt preview redesign in this pass

## Scope
- In:
  - Gmail extension hot-path focus/open behavior
  - browser Gmail attachment preview bootstrap/render flow
  - browser preview drawer interaction model for PDFs and images
  - focused Gmail/browser acceptance coverage
- Out:
  - persistent warm-launch helper
  - broader Gmail/session UX redesign outside handoff and preview
  - unrelated browser-shell polish

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_handoff_preview`
- Branch name: `codex/gmail-handoff-preview-parity`
- Base branch: `main`
- Base SHA: `97387493eb6a449a5b47005123b95ab91882cf0c`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree carrying the approved `main` floor

## Interfaces/types/contracts affected
- `extensions/gmail_intake/background.js`
  - hot-path browser open/focus ordering and exact-match tab handling
- `shadow_web` Gmail preview contract
  - keep `/api/gmail/preview-attachment` as bootstrap
  - add one page-render endpoint for cached Gmail attachment preview pages
- Browser Gmail preview state helpers
  - evolve from single-page raw-file preview into lazy multi-page rendered preview state
- No Gmail token, port, or ownership contract changes

## File-by-file implementation steps
- `extensions/gmail_intake/background.js`
  - focus existing exact-match browser tabs without forced reload
  - open/focus the browser app immediately after successful native prepare on the browser-app path
  - keep the localhost POST and banner/fallback semantics intact
- `src/legalpdf_translate/shadow_web/app.py`
  - add a Gmail preview page-render endpoint backed by cached downloaded attachments
- `src/legalpdf_translate/gmail_browser_service.py`
  - expose cached preview-path/page-count bootstrap data needed by the render endpoint
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - add browser preview-page state helpers for jump, scroll, cache, and request suppression
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - replace raw PDF iframe-style preview behavior with lazy rendered page cards
  - keep image preview fixed to page `1`
  - keep `Open in new tab` as fallback only
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - update the preview drawer structure for Qt-style multi-page review
- `src/legalpdf_translate/shadow_web/static/style.css`
  - style the preview cards and preview navigation affordances
- Tests:
  - extend Gmail extension tests
  - extend Gmail review-state tests
  - add/update shadow web API/runtime tests for preview rendering and cached-page behavior

## Tests and acceptance criteria
- Static checks:
  - JS syntax validation for touched browser modules
- Focused automated coverage:
  - extension hot-path tests for no forced reload on exact-match tabs
  - preview-state tests for jump/apply/suppression behavior
  - shadow-web API tests for preview bootstrap and page rendering
- Acceptance:
  - Gmail click with an already-running browser app focuses or reuses the right workspace without visible reload churn
  - PDF preview shows inline page content in the drawer and no longer triggers download-per-page behavior
  - the user can jump to any page and set that as the start page
  - image attachments stay fixed to page `1`
  - translation and interpretation bounded continuation flows still work after the hot-path change

## Implementation status
- Completed:
  - removed exact-match browser tab reloads from the Gmail extension hot path
  - moved browser-app open/focus ahead of the slower localhost POST after successful native prepare
  - added cached Gmail preview page metadata (`page_sizes`) and a unique preview filename strategy for browser downloads
  - added `/api/gmail/preview-attachment/{attachment_id}/pages/{page_number}` for rendered preview pages
  - replaced raw PDF iframe preview with an inline multi-page browser drawer using page cards, jump/go controls, per-page `Start from this page`, and page-aware start-page application
- Verified locally:
  - JS syntax checks passed for touched browser modules
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_intake.py tests/test_gmail_browser_service.py tests/test_shadow_web_api.py` -> `35 passed`
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_gmail_bridge.py tests/test_gmail_focus_host.py tests/test_gmail_review_state.py tests/test_shadow_web_server.py` -> `33 passed`
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m compileall src tests` passed
  - `dart run tooling/validate_agent_docs.dart` passed
  - `dart run tooling/validate_workspace_hygiene.dart` passed
- Still pending before publish:
  - live manual confirmation with the installed Edge extension against a real Gmail message to measure hot-path feel and confirm the inline preview no longer falls back to raw per-page PDF downloads

## Rollout and fallback
- Keep the current browser-first Gmail contract and launch path.
- If preview rendering regresses, keep the bootstrap cache and fallback link but revert only the new rendered-page drawer behavior.
- If hot-path open ordering causes regressions, revert to the prior ordering while preserving the exact-match no-reload change.

## Risks and mitigations
- Risk: rendered preview pages could create too many browser requests or sluggish scrolling.
  - Mitigation: mirror Qt’s lazy visible-page rendering, prefetch buffer, and duplicate-request suppression.
- Risk: focusing the browser app before POST completion could expose stale UI for a moment.
  - Mitigation: keep the POST immediate and ensure the Gmail workspace auto-refresh path remains intact.
- Risk: cached attachment preview paths might drift from the active workspace.
  - Mitigation: keep preview rendering scoped by runtime mode, workspace, and attachment id.

## Assumptions/defaults
- The Qt Gmail preview dialog is the behavioral authority for page navigation and start-page selection.
- Same-tab drawers remain the correct browser adaptation.
- A persistent warm-launch helper is intentionally deferred unless this pass still leaves cold-start latency unacceptable.
