# Gmail Preview Panel Presentation

## Provenance
- Branch: `codex/gmail-preview-presentation`
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_preview_presentation`
- Base: `main@430ffe557fefb0408fcee4f63e2246689d80339b`
- Created: 2026-05-09

## Goal
Extract Gmail preview-panel presentation shaping into a pure static module while preserving the existing safe DOM renderer, preview behavior, browser routes, Gmail/native-host contracts, payloads, selectors, and submitted values.

## Implementation Checklist
- [x] Add failing tests in `tests/test_shadow_web_api.py` for `gmail_preview_presentation.js`, preview-panel renderer ownership, ESM preview cases, and static asset serving.
- [x] Verify the targeted preview contract fails before production implementation.
- [x] Create `src/legalpdf_translate/shadow_web/static/gmail_preview_presentation.js` exporting `buildGmailPreviewPanelPresentation(...)`.
- [x] Update `gmail.js` so `renderPreviewPanel()` gathers coordinator state, calls the builder, passes the presentation to `renderGmailPreviewPanelInto(...)`, and keeps PDF canvas rendering gated by `shouldRenderPdfCanvas`.
- [x] Update `gmail_preview_ui.js` so it performs safe DOM writes from the presentation object and no longer derives preview summary/status/control copy.
- [x] Run targeted preview tests, the focused browser/Gmail suite, `scripts/validate_dev.ps1 -Full`, and shadow Browser smoke on port `8888`.
- [x] Move this ExecPlan to `docs/assistant/exec_plans/completed/` before staging.

## Validation Notes
- Use `.\.venv311\Scripts\python.exe` for pytest.
- Use shadow mode only: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.
- Record the known Dart AOT launcher issue only if the validation wrapper reports direct-Dart fallback success.
