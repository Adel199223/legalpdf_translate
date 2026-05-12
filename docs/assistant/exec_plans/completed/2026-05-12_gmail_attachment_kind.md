# Gmail Attachment Kind Classification

## Goal and Non-Goals

Extract duplicated Gmail attachment MIME/PDF/image classification into one pure static module. Preserve all Gmail/browser behavior, routes, payloads, DOM IDs, selectors, native-host contracts, and safe rendering paths.

Non-goals: change attachment filtering, preview loading, start-page editability, Gmail bridge behavior, or any public backend API.

## Scope

In scope:
- Add `gmail_attachment_kind.js` with pure helpers for MIME normalization, PDF/image checks, and `PDF`/`Image`/`Unknown` labels.
- Wire `gmail.js`, `gmail_preview_bundle.js`, `gmail_review_state.js`, and `gmail_attachment_presentation.js` to use the shared helpers.
- Add contract/probe coverage and static asset graph coverage.

Out of scope:
- Live Gmail/OAuth/native-host testing.
- Browser route, payload, selector, or submitted value changes.
- UI redesign.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_attachment_kind`
- Branch name: `codex/gmail-attachment-kind`
- Base branch: `main`
- Base SHA: `96669241411cc5ed47ada34b0d5013e4fdbb4f99`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use shadow browser mode only.

## Interfaces/Types/Contracts Affected

- New internal static browser module: `src/legalpdf_translate/shadow_web/static/gmail_attachment_kind.js`
- Existing internal imports only. No backend routes, request/response payloads, submitted values, selector names, DOM IDs, Gmail/native-host contracts, or extension contracts change.
- Dynamic text continues to flow through existing safe DOM rendering.

## File-by-File Implementation Steps

1. Add tests in `tests/test_shadow_web_api.py` for the new module exports, ESM behavior, purity markers, import wiring, duplicate removal, and static asset serving.
2. Confirm the targeted test fails before implementation.
3. Add `gmail_attachment_kind.js` with pure helpers:
   - `gmailAttachmentMime`
   - `normalizeGmailAttachmentMime`
   - `isGmailPdfMime`
   - `isGmailImageMime`
   - `isGmailPdfAttachment`
   - `isGmailImageAttachment`
   - `deriveGmailAttachmentKindLabel`
   - `deriveGmailAttachmentKindLabelForAttachment`
4. Update existing Gmail modules to import and call the shared helpers while keeping raw MIME display/title behavior unchanged.
5. Run targeted, focused, full validation, and shadow smoke.
6. Mark this plan complete and move it to `completed/` before commit.

## Tests and Acceptance Criteria

- Targeted:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_kind_module_centralizes_mime_classification`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow smoke on port `8888`:
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-attachment-kind-smoke#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, demo attachment load, and normal review/preview interaction without touching live Gmail.

## Rollout and Fallback

Publish via ready PR after validation. If CI fails, conflicts appear, or GitHub auth is unavailable, stop before merge. Fallback is to revert the single shared-module extraction before merge because the change is internal and isolated.

## Risks and Mitigations

- Risk: accidentally changing MIME title display by normalizing values where UI previously showed raw MIME. Mitigation: keep raw display helpers for titles and use shared helpers only for classification labels.
- Risk: changing PDF preview bundling eligibility. Mitigation: preserve exact `application/pdf` normalized check and cover selected PDF/image behavior.
- Risk: static module accidentally reaching DOM or fetch state. Mitigation: contract test blocks DOM, renderer, app state, and diagnostics markers.

## Assumptions/Defaults

- No live Gmail testing is in scope.
- User has authorized PR-first publish/merge flow for the next recommended roadmap slice.
- Record Dart AOT launcher issue only if the validation wrapper reports direct-Dart fallback success.

## Completion Evidence

- RED confirmed: `test_gmail_attachment_kind_module_centralizes_mime_classification` failed before implementation because `gmail_attachment_kind.js` did not exist.
- Targeted contract/probe passed: `1 passed`.
- Static asset graph passed: `1 passed`.
- Focused browser/Gmail suite passed: `218 passed`.
- Full validation passed:
  - wrapper suite: `214 passed`
  - `compileall src tests`: passed
  - `tests/test_gmail_review_state.py`: `2 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - Known Dart AOT launcher issue appeared for both Dart validators; direct-Dart fallback succeeded for agent docs and workspace hygiene.
- Shadow smoke on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-attachment-kind-smoke#gmail-intake` passed with local Playwright fallback after the in-app Browser runtime reported no active Codex browser pane:
  - page identity: `LegalPDF Translate`
  - nonblank Gmail intake content rendered
  - no framework overlay observed
  - console warnings/errors: `0`
  - demo attachment loaded as `demo-gmail-review.pdf` with `PDF` label
  - preview opened and generated `gmail-preview-canvas` with page status
  - no live Gmail, OAuth, native-host, or real drafts touched

Status: complete.
