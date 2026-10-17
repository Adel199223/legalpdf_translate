# Bounded text-correction opening retry

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
