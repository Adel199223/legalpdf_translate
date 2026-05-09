# Gmail Attachment Presentation

## Provenance
- Branch: `codex/gmail-attachment-presentation`
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_attachment_presentation`
- Base: `main@29ecf6b1657de04ab87a3ca9bfc06bdf6c521fe4`
- Created: 2026-05-09

## Goal
Extract Gmail attachment list/detail presentation shaping into a pure static module while preserving the existing safe DOM renderer, Gmail review selectors, submitted payloads, routes, and Gmail/native-host behavior.

## Implementation Checklist
- [x] Add failing tests in `tests/test_shadow_web_api.py` for `gmail_attachment_presentation.js`, attachment renderer ownership, ESM list/detail cases, and static asset serving.
- [x] Verify targeted attachment presentation tests fail before production implementation.
- [x] Create `src/legalpdf_translate/shadow_web/static/gmail_attachment_presentation.js` exporting `buildGmailAttachmentListPresentation(...)` and `buildGmailReviewDetailPresentation(...)`.
- [x] Update `gmail.js` so attachment list/detail wrappers gather coordinator state, call the builders, and pass presentation objects to `gmail_attachment_ui.js`.
- [x] Update `gmail_attachment_ui.js` so it performs safe DOM writes from presentation objects and no longer derives attachment labels/meta/help text.
- [x] Run targeted tests, focused browser/Gmail tests, `scripts/validate_dev.ps1 -Full`, and shadow Browser smoke on port `8888`.
- [x] Move this ExecPlan to `docs/assistant/exec_plans/completed/` before staging.

## Validation Notes
- Use `.\.venv311\Scripts\python.exe` for pytest.
- Shadow smoke target: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.
- Do not touch live Gmail, OAuth, native-host, draft creation, backend route contracts, submitted values, or selector/dataset names.
- Red test confirmed before implementation with targeted attachment presentation/static-route failures.
- Targeted attachment presentation tests passed: 3 passed.
- Focused browser/Gmail suite passed: 191 passed.
- `scripts/validate_dev.ps1 -Full` passed; `dart run` hit the known AOT snapshot launcher issue and the direct-Dart fallback succeeded for agent docs and workspace hygiene.
- Browser shadow smoke passed on port `8888`; a fresh isolated shadow workspace loaded demo attachments, selected `demo-gmail-review.pdf`, enabled continue, opened PDF preview, verified `gmail-preview-canvas`, and kept the preview href under `/api/gmail/attachment/demo-gmail-review-pdf?mode=shadow&workspace=gmail-attachment-smoke#page=1`.
- Smoke screenshot: `C:\Users\FA507\AppData\Local\Temp\gmail-attachment-smoke-preview.png`.
