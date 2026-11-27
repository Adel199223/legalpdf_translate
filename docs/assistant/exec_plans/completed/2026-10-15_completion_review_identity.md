# Completion review follows selected delivery

## Goal and scope
Keep completion UI readiness bound to the latest selected delivery and its independent Arabic Word/full-output review gates. Preserve backend guards, safe text rendering and cost-dirty fixes. No route/payload/provider/Gmail contract changes or live actions.

## Worktree provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/gmail-manual-context-20261015/legalpdf_translate`
- Branch/base: `feat/gmail-manual-context-20261015`, `main` at `a69a2dcc811d5b220729e28265fb2f76bcc36a19`.
- Integration target: parent `feat/email-retest-20261015`.
- Before authoring, overlapping `translation.js` and `test_translation_browser_state.py` were copied from parent integration to retain its cost-dirty changes. Other earlier patches remain intact.

## Implementation and interfaces
1. Bind Arabic review request ownership to selected-delivery identity and immediately invalidate readiness when that identity changes.
2. Refresh latest Arabic review after selected delivery changes and ignore old asynchronous responses for earlier selections of the same job.
3. Gate Save and delivery confirmation independently on full-output review for text corrections, including non-Arabic jobs; notify on same-selection output-review state transitions.
4. Add initialized UI causal regressions for the transitions, stale responses and preserved cost edits.
5. Prepare private synthetic shadow acceptance harness only after code passes: offline service bundle, no live Gmail bridge, strict route allowlist/tripwires, no product edits for harness.

## Acceptance, rollout and risks
Previously resolved gen1 review cannot authorize gen2; gen2 stays blocked until its own Arabic review resolves and full-output review passes. Late gen1 replies cannot update gen2. Output-review completion with unchanged selection ID updates readiness. EN/FR full-output review blocks Save too. Backend guards remain unchanged. Parent owns integrated Standard/Full and separately authorized rollout. Private harness has no provider/native/Gmail capability.

## Results
Implemented selected-delivery ownership for Arabic review, request deduplication, fail-closed refresh errors, and independent full-output review gating. Same-selection output-review transitions notify completion UI without resetting cost edits. Metrics discovery of a changed selected revision requests its current Arabic review. Backend contracts and guards unchanged.

Affected validation: 57 passed in 4.36s across translation browser state, ordinary layout browser state, completion presentation, text correction browser, and completion metrics. Initialized-control scenarios cover AR/EN/FR correction approval, immediate blocking, late older success/rejection, latest GET failure, output approval with unchanged selection ID, and subsequent current Arabic resolution. Existing cost-dirty/race cases remain green. Private synthetic harness preparation follows; parent owns integrated full validation.

Visible synthetic browser acceptance confirmed both independent gates and final Save availability. It additionally exposed a misleading Ready result badge while Arabic review was pending. The parent stopped Full before the bounded presentation-only correction, retained the interruption, and changed the badge to Review required with warning tone. Thirty presentation/browser checks passed afterward. Final visible confirmation and resumed frozen validation own closeout.

## Integrated closeout

Implementation and independent review are complete. Final frozen validation: The broader repair passed 371 focused cases; the final badge delta passed 30 affected cases, and the subsequent test-only ZIP fixture delta passed all 33 module cases. These overlapping runs are not additive. Standard03 passed 267 tests, exit 0 in 51.063 seconds (pytest 45.69 seconds). Full03 passed 2,144 selected case executions, including all 191 formatting cases; nine intake cases were intentionally deselected. It exited 0 in 2,648.000 seconds. All 1,196 captured source/test/documentation paths stayed unchanged through final Standard and Full; package versions remained unchanged. Subsequent closeout edits are documentation-only and receive separate validators. The final Full log SHA256 is `4b674a51c7f3021c4101d3f822b465cffcf5b404fe6e0c6e3948d3fcc10a867a`. Both wrappers retained the known dartdev AOT-launcher failure and succeeded through their direct-Dart fallback; agent-doc and workspace-hygiene validation passed. These are selected local checks, not an additive unique total or hosted CI.

Visible isolated shadow acceptance passed selected-generation changes, independent full-output/Arabic review gates, warning badges, explicit zero-cost retention and final Save availability. Its fixture was retired. Private `email_retest_20261015_01/completion_review_shadow/final_acceptance_receipt.json` owns that synthetic UI evidence; it is not another provider, native Word, Gmail or live extension run.

Private `email_retest_20261015_01/rollout_capture_01/final_postflight_01/receipt.json` owns the exact locally installed Git SHA, served runtime/asset identity, restored failed-job/session ownership and rollout preservation checks. An absent or failed receipt means local application is still pending; a source commit or passing local tests alone is not installation. No remote publication, hosted CI success or email sending is claimed. See the [email retest closeout](2026-10-15_email_retest_and_repairs.md) for qualified manual delivery, historical accounting and preservation scope.
