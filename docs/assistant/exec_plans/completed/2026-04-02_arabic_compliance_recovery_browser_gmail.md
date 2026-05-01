# Harden Arabic Compliance Recovery Without Changing the Success-Only Word Review Gate

## Goal and non-goals

Goal:
- Keep Arabic Word review limited to completed runs with a durable translated DOCX.
- Reduce flaky Arabic locked-token retry failures by strengthening the retry prompt and keeping retry effort aligned with the first attempt.
- Make browser and Gmail recovery behavior explicit when the current Gmail attachment fails before confirmation.

Non-goals:
- Do not add partial-DOCX Word review or failed-run Gmail confirmation.
- Do not add a third model attempt for Arabic token correction.
- Do not change the existing success-path Arabic review gate or Gmail finalization semantics.

## Scope (in/out)

In:
- Arabic retry prompt shape and retry-effort policy.
- Failure-context enrichment for Arabic token mismatch diagnostics.
- Browser translation failed-run recovery messaging.
- Gmail stage/CTA semantics for failed current translation jobs.
- Focused workflow/browser/Gmail regressions.

Out:
- PDF worker/runtime provenance work already covered by the existing active plan.
- Qt behavior changes.
- Broader OCR advisor redesign outside the failed Arabic recovery path.

## Worktree provenance

- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_pdf_worker_fix`
- branch name: `codex/gmail-pdf-worker-fix`
- base branch: `main`
- base SHA: `ab70a47`
- target integration branch: `main`
- canonical build status: noncanonical isolated worktree for focused browser/Gmail recovery implementation

## Interfaces/types/contracts affected

- `build_ar_token_retry_prompt(...)` gains additive source/mismatch inputs for richer correction prompts.
- Browser translation job result payload gains additive advisor and Arabic token-mismatch diagnostics.
- Translation UI snapshot gains additive failed-run recovery fields.
- Gmail browser stage model gains additive `translation_recovery`.

## File-by-file implementation steps

1. Expand the Arabic retry prompt builder to include the source page block plus mismatch diagnostics, while preserving the existing locked-token and prior-output blocks.
2. Keep Arabic token-correction retries at the first-attempt effort floor and surface richer missing/unexpected token details in failure context/result payloads.
3. Add browser-side failed-run recovery derivation so the translation workspace shows targeted recovery guidance and advisor-based rerun hints.
4. Add Gmail `translation_recovery` stage/CTA wiring so failed current attachments route back to the translation recovery surface instead of appearing merely in progress.
5. Add focused tests for retry prompt structure, retry effort, failure metadata, browser recovery derivation, and Gmail stage semantics.

## Tests and acceptance criteria

- Arabic retry prompt includes source, locked-token, mismatch-summary, and prior-output blocks.
- Arabic token-correction retries no longer downgrade from `high`/`xhigh` to `medium`.
- Failed Arabic runs expose missing/unexpected token samples in failure context.
- Translation failed-run recovery copy distinguishes Resume vs Start Translate vs Rebuild DOCX.
- Gmail active translation batches with failed current jobs derive stage `translation_recovery`.
- Successful reruns still flow into the existing success-only Arabic Word review gate.

## Rollout and fallback

- Preferred path: land this together with the earlier browser PDF and Arabic review work on the same isolated branch, then retest the Gmail Arabic attachment flow end to end.
- Fallback: if the stronger retry still fails on the same source, keep the improved diagnostics and failed-run recovery guidance so the operator can rerun with advisor-recommended settings without ambiguity.

## Risks and mitigations

- Risk: richer retry prompts could over-constrain successful Arabic retries.
  - Mitigation: keep the correction scope narrow and do not fabricate missing tokens; only add source/mismatch context.
- Risk: Gmail recovery staging could misclassify the current attachment state.
  - Mitigation: derive `translation_recovery` only for active translation sessions whose current browser translation job is failed or cancelled before confirmation.
- Risk: additive failure diagnostics could break existing consumers.
  - Mitigation: keep all new fields additive and preserve current top-level keys.

## Assumptions/defaults

- The correct product policy is to keep Arabic Word review success-only.
- Failed Arabic Gmail attachments should remain recoverable in-place through rerun/resume/rebuild, without allowing premature Gmail confirmation.
- Advisor recommendations should be shown only when they are stronger than the failed run's actual OCR/image settings.
