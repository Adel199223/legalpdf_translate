# Gmail Attachment Metadata Helpers

## Goal and Non-Goals

Extract repeated Gmail attachment metadata/display helpers into one pure static module. Preserve all existing Gmail/browser behavior, routes, payloads, DOM IDs, selectors, submitted values, native-host contracts, and safe rendering paths.

Non-goals: change attachment filtering, MIME classification semantics, PDF preview behavior, start-page editability, report payload fields, or any public backend API.

## Scope

In scope:
- Add `gmail_attachment_metadata.js` with pure helpers for attachment id, filename fallback, raw display MIME, size labels, by-id reads, and attachment-list normalization.
- Wire `gmail_attachment_presentation.js`, `gmail_preview_presentation.js`, `gmail_review_state.js`, and `gmail_report_context.js` to use the shared helpers.
- Add contract/probe coverage and static asset graph coverage.

Out of scope:
- Live Gmail/OAuth/native-host testing.
- UI redesign.
- Backend route or payload changes.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_attachment_metadata`
- Branch name: `codex/gmail-attachment-metadata`
- Base branch: `main`
- Base SHA: `6fb34a3d845f1158a938f789dc4ddaf3bbec1054`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use shadow browser mode only.

## Interfaces/Types/Contracts Affected

- New internal static browser module: `src/legalpdf_translate/shadow_web/static/gmail_attachment_metadata.js`
- Existing internal imports only. No backend routes, request/response payloads, submitted values, selector names, DOM IDs, Gmail/native-host contracts, or extension contracts change.
- Dynamic text remains plain data consumed by existing safe DOM renderers.

## File-by-File Implementation Steps

1. Add a focused contract/probe test in `tests/test_shadow_web_api.py`, then confirm RED before production code.
2. Add `gmail_attachment_metadata.js` with pure exports:
   - `normalizeGmailAttachmentList`
   - `gmailAttachmentId`
   - `gmailAttachmentFilename`
   - `gmailAttachmentDisplayMime`
   - `readGmailAttachmentValueById`
   - `formatGmailAttachmentSizeLabel`
3. Update `gmail_attachment_presentation.js`, `gmail_preview_presentation.js`, `gmail_review_state.js`, and `gmail_report_context.js` to import and use the helpers.
4. Update static asset graph coverage for `gmail_attachment_metadata.js`.
5. Run targeted, focused, full validation, and shadow smoke.
6. Mark complete and move this plan to `completed/` before commit.

## Tests and Acceptance Criteria

- Targeted:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_metadata_module_centralizes_display_helpers`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow smoke on port `8888`:
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-attachment-metadata-smoke#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, demo attachment load, PDF label/size text, Preview action, and generated preview canvas. Do not touch live Gmail.

## Rollout and Fallback

Publish via ready PR after validation. If CI fails, conflicts appear, or GitHub auth is unavailable, stop before merge. Fallback is to revert this internal helper extraction before merge.

## Risks and Mitigations

- Risk: changing raw MIME title display by normalizing too much. Mitigation: keep `gmailAttachmentDisplayMime` raw-with-fallback and test malicious/raw text preservation.
- Risk: changing inherited object-key behavior in by-id reads. Mitigation: helper uses own-property checks and tests inherited fallback.
- Risk: accidentally moving rendering or fetch behavior. Mitigation: contract test forbids DOM, `innerHTML`, renderers, `fetchJson`, `setDiagnostics`, and app state markers in the helper module.

## Assumptions/Defaults

- No live Gmail testing is in scope.
- User authorized PR-first publish/merge flow for the next recommended roadmap slice.
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

## Completion Evidence

- RED confirmed: `test_gmail_attachment_metadata_module_centralizes_display_helpers` failed before implementation because `gmail_attachment_metadata.js` did not exist.
- Targeted metadata contract/probe passed: `1 passed`.
- Static asset graph passed: `1 passed`.
- Focused browser/Gmail suite passed: `219 passed`.
- Full validation passed:
  - wrapper suite: `215 passed`
  - `compileall src tests`: passed
  - `tests/test_gmail_review_state.py`: `2 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - Known Dart AOT launcher issue appeared for both Dart validators; direct-Dart fallback succeeded for agent docs and workspace hygiene.
- Shadow smoke on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-attachment-metadata-smoke#gmail-intake` passed with local Playwright fallback after the in-app Browser runtime reported no active Codex browser pane:
  - page identity: `LegalPDF Translate`
  - nonblank Gmail intake content rendered
  - no framework overlay observed
  - console warnings/errors: `0`
  - demo attachment loaded as `demo-gmail-review.pdf` with `PDF` label and `661 B` size
  - preview opened and generated `gmail-preview-canvas`
  - no live Gmail, OAuth, native-host, or real drafts touched

Status: complete.
