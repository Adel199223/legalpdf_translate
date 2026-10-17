# Preserve available Gmail stage actions beside disabled controls

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
