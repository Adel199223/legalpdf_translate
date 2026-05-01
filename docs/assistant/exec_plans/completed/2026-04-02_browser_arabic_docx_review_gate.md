# Restore the Arabic Word Review Gate in the Browser Translation/Gmail Flow

## Goal and non-goals

Goal:
- Re-establish the Qt-matched Arabic DOCX review pause in the browser translation flow before Save-to-Job-Log or Gmail batch confirmation can continue.
- Use the durable translated DOCX from the completed translation run as the only review source of truth.
- Keep the gate state durable inside the running browser-app process so the same pending review can resume after drawer close/reopen or browser refresh.

Non-goals:
- Do not modify the unrelated `feat/lichtfeld-wsl-setup` worktree.
- Do not loosen the Arabic review requirement into a reminder-only browser flow.
- Do not change Gmail batch finalization semantics beyond ensuring the reviewed durable DOCX remains the artifact carried forward.

## Scope (in/out)

In:
- Backend Arabic review session state keyed by runtime/workspace/completion key.
- New browser APIs for Arabic review state/open/align-save/continue actions.
- Translation completion drawer UI for the Arabic review gate.
- Gmail confirm-step gating so unresolved Arabic review blocks confirmation.
- Focused API/UI regressions plus targeted live validation.

Out:
- Non-Arabic translation flows.
- Gmail draft/finalization architecture changes outside the review gate dependency.
- Qt review-dialog behavior changes.

## Worktree provenance

- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_pdf_worker_fix`
- branch name: `codex/gmail-pdf-worker-fix`
- base branch: `main`
- base SHA: `ab70a47`
- target integration branch: `main`
- canonical build status: noncanonical isolated implementation worktree; this slice exists to restore browser parity before later canonical integration

## Interfaces/types/contracts affected

- New browser API family under `/api/translation/arabic-review/*`.
- Translation UI snapshot gains additive Arabic review fields consumed by Gmail UI hooks.
- Existing translation save and Gmail confirm routes gain additive validation against unresolved Arabic review state when a current browser translation job is present.

## File-by-file implementation steps

1. Add a small backend Arabic review session helper beside `word_automation.py` with Qt-matched fingerprint polling and manual-continue semantics.
2. Register the helper in `shadow_web/app.py` and expose `state`, `open`, `align-right-save`, and `continue` routes.
3. Restore pending Arabic review sessions after browser refresh by allowing the client to query the workspace-scoped unresolved review state and reload the matching completed translation job.
4. Add an Arabic DOCX Review card to the Finish Translation drawer and block Save-to-Job-Log until the gate resolves.
5. Extend Gmail translation-step gating so `Confirm Current Translation Row` is disabled and server-guarded while Arabic review is unresolved.
6. Add focused API, HTML-shell, and Gmail/translation gating regressions, then run targeted validation.

## Tests and acceptance criteria

- Arabic review state is required only for completed `AR` translation jobs with an existing durable DOCX from `save_seed.output_docx`.
- `open` uses Word automation first and falls back to the Windows default handler when automation fails.
- `align-right-save` resolves the gate immediately on success.
- Fingerprint polling resolves only after a save change plus the quiet-period contract.
- `Save Translation Row` and `Confirm Current Translation Row` stay blocked until Arabic review resolves.
- Browser refresh can recover the same pending Arabic review session for the current workspace/completion key.

## Rollout and fallback

- Preferred path: land the browser review gate in this isolated worktree, validate the Arabic Gmail browser flow locally, then merge into canonical `main`.
- Fallback: if Windows Word automation proves environment-specific, keep the review gate functional through the default-handler fallback and manual continue actions instead of silently skipping the gate.

## Risks and mitigations

- Risk: browser review gating could accidentally block saved-row edit flows.
  - Mitigation: scope the gate to current completed translation jobs and keep loaded saved rows outside the review-session API.
- Risk: refresh recovery could reopen or relaunch the wrong completed job.
  - Mitigation: key sessions by runtime/workspace/completion key and restore only the unresolved session explicitly tracked by the server.
- Risk: Gmail confirm could still bypass the gate through stale UI state.
  - Mitigation: disable the client button and re-check server-side before the confirm route proceeds.

## Assumptions/defaults

- The durable DOCX referenced by `save_seed.output_docx` is the canonical artifact to review and later attach.
- The browser flow should mirror the documented Qt Arabic review contract, including auto-open, align-right-save, manual continue, and quiet-period save detection.
- Closing the browser drawer should leave the review gate pending rather than cancelling the translation or Gmail batch session.

## Executed validations and outcomes

- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m py_compile src\legalpdf_translate\browser_arabic_review.py src\legalpdf_translate\shadow_web\app.py`
  - passed
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests\test_browser_arabic_review.py tests\test_shadow_web_api.py tests\test_gmail_review_state.py`
  - passed, `40 passed`
