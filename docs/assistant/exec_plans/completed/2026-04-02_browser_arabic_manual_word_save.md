# Switch Browser Arabic Review to Manual Word Save

## Goal

- Make the browser Arabic DOCX review gate behave like the Qt manual review path:
  - auto-open the durable DOCX in Word once
  - let the operator align/edit manually
  - continue when a manual save is detected
- Remove the browser-visible `Align Right + Save` action so the browser flow never mutates the Word document automatically.

## Scope

In:
- Browser Arabic review manager status/copy updates.
- Browser translation completion drawer UI changes for the Arabic review card.
- Focused regression updates for the shell template and Arabic review manager.

Out:
- No change to the underlying server review route surface.
- No Gmail batch/finalization behavior change beyond the existing review gate semantics.
- No change to the failed-run recovery flow.

## Files expected

- `src/legalpdf_translate/browser_arabic_review.py`
- `src/legalpdf_translate/shadow_web/static/translation.js`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `tests/test_browser_arabic_review.py`
- `tests/test_shadow_web_api.py`

## Acceptance checks

- Browser Arabic review card shows `Open in Word`, `Continue now`, and `Continue without changes`.
- Browser Arabic review card does not expose `Align Right + Save`.
- Review copy tells the operator to align/edit manually in Word and save.
- Successful Arabic review still auto-opens Word once and resolves on manual save detection.
- Save-to-Job-Log and Gmail confirmation remain blocked until the review gate resolves.
