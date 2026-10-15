# Failed-page image rerun guidance

## Goal and scope
Avoid an actionable image-setting escalation when the failed page already used an image. Preserve OCR guidance and conservative image guidance for missing, different-page or contradictory evidence. No payload, route, provider, validation or billing changes.

## Worktree provenance
Isolated `C:/Users/FA507/.codex/worktrees/image-rerun-guidance-oct15/legalpdf_translate`, branch `codex/image-rerun-guidance-20261015`, based on canonical main `e892bb9`. Parent owns integration and live acceptance. This worktree is noncanonical.

## Implementation and contracts
Use existing failure request type and matching failed-page progress in `translation_result_presentation.js`. Exercise the actual `translation.js` recovery export and result-card presenter in sanitized browser probes in `test_translation_recovery_state.py`. Returned shapes and action values stay unchanged.

## Validation and acceptance
First reproduce the observed auto/image-backed case. Cover text-only, unknown, other-page and contradictory evidence, plus independent OCR escalation. Run focused recovery/presentation/browser tests and docs/hygiene checks; parent owns one integrated Full run. Current output remains unaccepted.

## Risks, rollout and fallback
Only positive, page-bound, noncontradictory image evidence suppresses image escalation. Leave general analyze/run-summary advisor recommendations intact. No runtime or canonical edits, provider calls, publication or commit in this scope. If evidence is ambiguous, retain existing guidance.

## Results
The sanitized observed case failed before the fix: the actual browser recovery export recommended Images always despite matching image-backed failure/progress evidence. The fix suppresses only that ineffective escalation and replaces its setup-change instruction with validation-review guidance. Missing, different-page and conflicting evidence retain image guidance; independent OCR escalation remains intact. Final focused suite: 43 passed in 3.97 seconds across recovery, result presentation, browser state and run-status presentation. Direct-Dart agent docs and workspace hygiene validators passed. Parent owns integrated Standard/Full and live acceptance; no current output is accepted here.
