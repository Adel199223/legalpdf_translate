# Failed-page image rerun guidance

Current status: **Completed with scoped qualifications — October 17, 2026.** Earlier entries below are preserved chronological checkpoints; the final executed outcome at the end owns closeout.

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


## Final executed outcome — October 17, 2026

The reviewed guidance is installed and covered by causal/browser and integrated tests. Suppression requires positive matching evidence that the failed page already used an image; missing, contradictory, text-only and OCR guidance retain their existing paths. No additional live failed/provider attempt was required or claimed to close this advice-only scope.

Integrated validation04 passed focused 125/Standard 267/selected Full 2,144 with 1,211 pins unchanged. Later combined frontend validation is separately qualified in [VALIDATION.md](../../VALIDATION.md); overlapping counts are not additive and its original Full is not a single green run.

Final actual evidence is bound by private `order_rerun_20261015_01/final_root_acceptance_01/combined_verification.private.json` and `final_acceptance_prepared_01/actual_final_report_01.json` (29/29 checks). Scoped preservation covers 85 total rows/all 84 baseline exact, schema, captured settings, sources/archives/old deliveries/accounting and all four prior unsent drafts. Full fee/profile checks and complete MIME-body equality after CRLF normalization are separate from attachment/account/thread checks. No sending, remote publication or hosted CI is claimed. Root confirmed this plan's narrow criteria met and authorized its individual move to completed. Private `order_rerun_20261015_01/final_closeout_01/receipt.json` owns the final local documentation commit and shutdown state. Functional work is complete and its app actions are consumed. Shutdown is requested only if that receipt records an actual operating-system request; physical power-off is not observed.

See the [completed parent](2026-10-15_order_end_to_end_rerun.md) for the complete qualified acceptance.
