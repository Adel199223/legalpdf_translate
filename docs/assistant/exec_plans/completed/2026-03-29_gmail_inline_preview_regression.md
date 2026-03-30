# Gmail Inline Preview Regression Repair

## Summary
- Goal: restore inline Gmail attachment preview in the browser app and stop the preview route from behaving like a download endpoint.
- Root cause under investigation: `/api/gmail/attachment/{attachment_id}` currently serves previewable files through `FileResponse(..., filename=path.name)`, which defaults to `Content-Disposition: attachment`.

## Execution Outline
1. Repair the Gmail attachment preview route in `src/legalpdf_translate/shadow_web/app.py`.
   - Keep the current preview URL contract.
   - Return `Content-Disposition: inline` for previewable attachment types used by the Gmail review UI.
   - Leave explicit artifact download routes unchanged.
2. Add regression coverage in `tests/test_shadow_web_api.py`.
   - Assert previewable Gmail attachment responses stay inline for PDF and image attachments.
   - Assert translation artifact routes still return download-oriented headers.
3. Run targeted validation.
   - Focus on Gmail preview route coverage and browser app contract checks.
   - Add one browser-level sanity check if the local runtime state is available.

## Notes
- This worktree is already dirty from recent Gmail/browser changes; patch in place and do not revert unrelated edits.
- The browser review drawer UX is intentionally unchanged in this pass.
