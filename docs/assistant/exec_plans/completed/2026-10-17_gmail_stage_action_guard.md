# Preserve available Gmail stage actions beside disabled controls

Current status: **Completed with scoped qualifications — October 17, 2026.** Earlier entries below are preserved chronological checkpoints; the final executed outcome at the end owns closeout.

## Goal and scope
Repair the observed post-Save finalize controls silently doing nothing. The completed translation session has no suggested launch, so its hidden launch control is correctly disabled. That unrelated control must not veto an enabled finalize action. Preserve disabled-trigger eligibility and cross-control in-flight protection. No routes, payloads, Save/finalization mutation guards or provider/native/Gmail behavior changes.

## Worktree provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/gmail-stage-action-guard-20261017/legalpdf_translate`.
- Branch: `feat/gmail-stage-action-guard-20261017`.
- Base: canonical `main`, exact commit `a8863276b5db2cb2def2127d9d04fc33b5157ebd`, containing approved floor `4e9d20e`.
- Integration target: root-owned `feat/order-rerun-20261015`. This is a noncanonical authoring checkout; no server is launched.
- Separate `feat/editor-busy-read-20261017` owns the independent initial-editor GET retry and combined frozen validation after both patches are reviewed.

## Evidence and implementation
The actual captured bootstrap retains translation kind, confirmed status, completed=true and ready-to-finalize state, with no suggested launch. `runStageAction` gives the shared busy runner three controls and no distinct initiating guard; its default rejects the entire action when any member is disabled. Both visible finalize controls therefore silently return before opening the drawer. Private captured evidence remains under `order_rerun_20261015_01/post_save_capture_01` and `finalize_reopen_diagnosis_01`; no message/recipient/source content belongs in this plan.

1. `gmail.js`: pass the clicked trigger from all three existing stage handlers; reject an absent/disabled trigger, retain one shared in-flight latch, and mark only currently enabled stage controls busy. The drawer opener returns its existing caught preflight promise, and the stage plan awaits it so that the latch spans the initial preflight. Other callers may still ignore that returned promise. Preserve single failure feedback, the existing action plan, error runner and mutation checks.
2. `tests/test_gmail_stage_action_browser.py`: mount actual initialization/bootstrap/events and drawer chrome with fictional DOM/session/fetch. Cover both completed-session CTA paths, unrelated disabled launch preservation, disabled initiating control, cross-trigger duplicate prevention while recovery/preflight await despite rehydration, and error release without automatic retry.

## Tests and acceptance
First retain the causal failing mounted completed-session regression on the unchanged base. Then run the targeted browser tests with canonical locked Python and child-only isolated app data/environment, with no real network. The editor-retry agent owns combined targeted/Standard/Full after reviewed exact patch handoff. Actual current-session reopening, fee review and unsent draft creation remain root-owned and are not inferred from fixture success.

## Rollout, fallback and risks
Freeze the minimal three-file patch, source pins and targeted receipt privately for independent review before integration. Reverting this scoped event/guard change restores previous behavior. The explicit shared latch must prevent a different stage control from starting an overlapping action; unavailable controls must stay disabled. No automatic mutation retry, Save replay or draft creation belongs here.

## Status
The unchanged product base reproduced both completed-session CTA failures at the hidden-drawer assertion (two failed cases, one deselected). Final targeted validation passed 16 cases in 11.36 seconds: five new mounted-flow cases, five existing confirmation guards, the fee-options case and five shared runner/action-plan/chrome/session cases. Exact source/test hashes remained unchanged through that run. Earlier three- and fifteen-case passes are overlapping intermediate evidence, not additional unique totals.

Independent review of the first freeze found its latch ended before the drawer's fire-and-forget preflight. A held-preflight mounted regression failed on that frozen product at the prematurely released-busy assertion. The narrow successor returns and awaits the existing caught promise; the original freeze, review finding and red result remain preserved. The final held-preflight case proves that another CTA cannot start a duplicate request even after bootstrap re-enables its DOM control.

Receipts, JUnit and logs remain under private `order_rerun_20261015_01/gmail_stage_guard_01/{red_01,green_01,targeted_01,preflight_red_01,targeted_02}`. All probes used fictional data, mounted modules and local fake fetch with canonical locked Python and isolated app-data/temp paths; no real browser, app/API, Gmail, provider or native action occurred. Final frozen independent review and the editor agent's combined targeted/Standard/Full checks remain pending. All existing real Save/adoption steps remain consumed; root owns live continuation and final acceptance. This plan remains active.


## Final executed outcome — October 17, 2026

The final narrow guard and awaited existing caught preflight promise are independently reviewed, committed in D and installed. Both original completed-session CTA regressions and the first-freeze held-preflight failure remain red history; final 16 targeted cases passed. Five new mounted cases are included in the combined 55 targeted result and remain targeted-only. Actual normal Continue opened the finalization path and one Create succeeded from the preserved confirmed session; no Save or draft replay occurred. Eligibility, cross-trigger latch, mutation checks and safe DOM patterns remain intact.

The two frontend repairs are committed as `29d07bc15d2034a55d0fcfaba78d584fb38a3179`. Combined targeted validation passed 55 cases in 13.65 seconds, including the five new mounted stage-action cases; Standard passed 267 in 65.60 seconds. The original combined Full FAILED with 2,152 passes and one Qt sidebar font-metric failure. A paired exact-case probe isolated omission of baseline `QT_QPA_FONTDIR`: zero font families/108-pixel failure when unset, versus 192 families/43-pixel pass with the baseline directory. Root authorized one exact final-group continuation: 579 unique cases passed in 74.90 seconds, plus docs/hygiene exit 0. Qualified selected coverage is 1,574 earlier passes plus 579 continuation cases = 2,153; this is not a single green Full run. All 1,147 frozen paths and 58 package versions stayed exact. The five new stage-action cases are targeted-only, since the unchanged Full selection does not collect that module. Original failures, interrupted runs and causal receipts remain preserved under private `editor_busy_fix_01`; `independent_editor_busy_continuation_review_01/receipt.json` checks the qualification. Known Dart AOT wrapper failures retained their successful direct-Dart fallback.

The consumed rollout08 installed backend/product commit `a8863276b5db2cb2def2127d9d04fc33b5157ebd`. The later static installation fast-forwarded canonical main and disk to `29d07bc15d2034a55d0fcfaba78d584fb38a3179` while preserving that same owned backend process and confirmed session. The browser loaded both exact D JavaScript bodies after cache-bypass verification; the backend's cached build identity remains C. Private `order_rerun_20261015_01/frontend_browser_acceptance_01/installation_and_ui_receipt.json` binds the before/after captures, body proof and actual normal Continue/one Create acceptance. This is a deliberately qualified frontend installation, not a backend restart or confirmed-session recovery import.

Final actual evidence is bound by private `order_rerun_20261015_01/final_root_acceptance_01/combined_verification.private.json` and `final_acceptance_prepared_01/actual_final_report_01.json` (29/29 checks). Scoped preservation covers 85 total rows/all 84 baseline exact, schema, captured settings, sources/archives/old deliveries/accounting and all four prior unsent drafts. Full fee/profile checks and complete MIME-body equality after CRLF normalization are separate from attachment/account/thread checks. No sending, remote publication or hosted CI is claimed. Root confirmed this plan's narrow criteria met and authorized its individual move to completed. Private `order_rerun_20261015_01/final_closeout_01/receipt.json` owns the final local documentation commit and shutdown state. Functional work is complete and its app actions are consumed. Shutdown is requested only if that receipt records an actual operating-system request; physical power-off is not observed.

See the [completed parent](2026-10-15_order_end_to_end_rerun.md) for the complete qualified acceptance.
