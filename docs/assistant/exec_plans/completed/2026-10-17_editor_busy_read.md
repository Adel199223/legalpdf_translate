# Bounded text-correction opening retry

Current status: **Completed with scoped qualifications — October 17, 2026.** Earlier entries below are preserved chronological checkpoints; the final executed outcome at the end owns closeout.

## Goal and scope

Recover a temporary `ordinary_layout_workspace_busy` response during the initial editor GET, and explain exhausted contention. Preserve every other error, lock, route, payload, safe DOM write and explicit mutation. No automatic POST retries, provider/native/Gmail operations or canonical installation belong here.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/worktrees/editor-busy-read-20261017/legalpdf_translate`
- Branch: `feat/editor-busy-read-20261017`
- Base branch: canonical `main`
- Base SHA: `a8863276b5db2cb2def2127d9d04fc33b5157ebd`
- Approved floor `4e9d20e` is an ancestor of the base (verified before edits).
- Integration target: root-owned `feat/order-rerun-20261015`; promotion is outside this subtask.
- Noncanonical authoring checkout only; no UI server is launched.

## Evidence and limits

The historical normal editor GET returned HTTP409 amid native-review polls; its response diagnostic was not captured. Subsequent serialized GETs succeeded. Code supports possible nonblocking job-lock contention, but these facts do not establish the historical error code or cause. Reproduction below is deterministic synthetic busy-response testing only.

## Implementation

1. `text_correction_ui.js`: initial opening may retry only exact diagnostic `ordinary_layout_workspace_busy`, twice after 150/300 ms. Stop after disposal/owner changes. Other reads and POSTs retain single-attempt behavior. Exhausted busy has specific preserved-edits guidance.
2. `test_ordinary_text_correction_browser.py`: mounted-editor probes cover transient recovery, exhaustion, unrelated errors, mutation single dispatch, and obsolete owner/disposal cancellation.

## Validation and acceptance

Use canonical locked `.venv311` with this checkout's `src` first on child-only `PYTHONPATH`; no dependency changes. Retain targeted, Standard and selected Full logs under private `order_rerun_20261015_01/editor_busy_fix_01`. Passing local checks establish implementation behavior only, not historical causality or live acceptance.

Initial validation: 39 targeted cases passed in 3.95 seconds; Standard01 passed 267 cases in 66.45 seconds, with compilation and docs/hygiene passing through the known direct-Dart fallback after AOT-launcher failures. Selected Full01 was intentionally interrupted during formatting, without a terminal Full verdict, to combine the separately reviewed Gmail stage-action repair before one final validation. Its logs remain preserved; all 1,112 frozen paths remained unchanged through interruption. Private `editor_busy_fix_01/interrupted_01.json` records the verified owned runner and descendant shutdown; `interrupted_pin_receipt_01.json` records preservation.

Root authorized this worktree to apply only the independently reviewed stage-action patch, freeze both changes together and run targeted, Standard and selected Full. The new stage-action browser module must be included explicitly in targeted validation; the existing selected Full script does not collect that new module. Root retains canonical, integration, live-app, native and Gmail ownership. Final combined validation is pending; the plan remains active.

## Rollout, fallback and risks

Root reviews the minimal diff and owns integration/rollout. Removing the frontend retry restores prior behavior. Retry is bounded to an already initiated read and retains server-owned consistency checks; owner changes must suppress later requests. The server's existing initial GET preparation semantics remain unchanged.


## Final executed outcome — October 17, 2026

The bounded exact-busy initial GET retry is independently reviewed, committed in D and installed as one of the two static JavaScript changes. Initial targeted 39/Standard 267 and the combined checks below are retained separately; the intentionally interrupted first Full remains interrupted, not passed. The actual original HTTP409 diagnostic/cause remain unproven. Retry stays GET-only at 150/300 ms with owner/disposal cancellation and no mutation retry. Actual final frontend installation and normal finalization passed; that acceptance does not recreate or establish the historical409 cause.

The two frontend repairs are committed as `29d07bc15d2034a55d0fcfaba78d584fb38a3179`. Combined targeted validation passed 55 cases in 13.65 seconds, including the five new mounted stage-action cases; Standard passed 267 in 65.60 seconds. The original combined Full FAILED with 2,152 passes and one Qt sidebar font-metric failure. A paired exact-case probe isolated omission of baseline `QT_QPA_FONTDIR`: zero font families/108-pixel failure when unset, versus 192 families/43-pixel pass with the baseline directory. Root authorized one exact final-group continuation: 579 unique cases passed in 74.90 seconds, plus docs/hygiene exit 0. Qualified selected coverage is 1,574 earlier passes plus 579 continuation cases = 2,153; this is not a single green Full run. All 1,147 frozen paths and 58 package versions stayed exact. The five new stage-action cases are targeted-only, since the unchanged Full selection does not collect that module. Original failures, interrupted runs and causal receipts remain preserved under private `editor_busy_fix_01`; `independent_editor_busy_continuation_review_01/receipt.json` checks the qualification. Known Dart AOT wrapper failures retained their successful direct-Dart fallback.

The consumed rollout08 installed backend/product commit `a8863276b5db2cb2def2127d9d04fc33b5157ebd`. The later static installation fast-forwarded canonical main and disk to `29d07bc15d2034a55d0fcfaba78d584fb38a3179` while preserving that same owned backend process and confirmed session. The browser loaded both exact D JavaScript bodies after cache-bypass verification; the backend's cached build identity remains C. Private `order_rerun_20261015_01/frontend_browser_acceptance_01/installation_and_ui_receipt.json` binds the before/after captures, body proof and actual normal Continue/one Create acceptance. This is a deliberately qualified frontend installation, not a backend restart or confirmed-session recovery import.

Final actual evidence is bound by private `order_rerun_20261015_01/final_root_acceptance_01/combined_verification.private.json` and `final_acceptance_prepared_01/actual_final_report_01.json` (29/29 checks). Scoped preservation covers 85 total rows/all 84 baseline exact, schema, captured settings, sources/archives/old deliveries/accounting and all four prior unsent drafts. Full fee/profile checks and complete MIME-body equality after CRLF normalization are separate from attachment/account/thread checks. No sending, remote publication or hosted CI is claimed. Root confirmed this plan's narrow criteria met and authorized its individual move to completed. Private `order_rerun_20261015_01/final_closeout_01/receipt.json` owns the final local documentation commit and shutdown state. Functional work is complete and its app actions are consumed. Shutdown is requested only if that receipt records an actual operating-system request; physical power-off is not observed.

See the [completed parent](2026-10-15_order_end_to_end_rerun.md) for the complete qualified acceptance.
