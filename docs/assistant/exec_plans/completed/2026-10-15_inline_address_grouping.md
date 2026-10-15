# Inline Arabic address wrapper equivalence

## Goal and non-goals
Prevent a source-exact inline street/house-number literal from failing because a model groups its required number inside the whole protected address, then a correction splits that same literal. Preserve visible characters, occurrence multiplicity/order, exact ownership and all existing protocol contracts. Do not accept missing, mutated, duplicated or reordered source literals.

## Scope and provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/gmail-manual-context-20261015/legalpdf_translate`
- Branch: `feat/gmail-manual-context-20261015`
- Base/integration floor: `main` at `a69a2dcc811d5b220729e28265fb2f76bcc36a19`, containing approved floor `4e9d20e`.
- Parent target: `feat/email-retest-20261015`; existing manual-intake/progress patches stay intact.
- Offline implementation only. No live source/evidence changes, provider/native/Gmail calls, dependency installation or publication.

## Evidence and interfaces
Independent retained-output diagnosis confirms identical visible address text in both attempts: the first wraps a full inline address, the second separates prefix and required house number. Current source-field detection owns labelled address lines/postal chains but excludes inline street spans. Existing complete-field canonicalization already checks exact source characters, source order, occurrence multiplicity and crossing wrappers. Preserve routes, saved protocol, API shapes and extension/native contracts.

## Implementation sequence
1. Lock a sanitized structural reproduction, keeping private wording out of tests/docs.
2. Add bounded inline street plus explicit house-number source recognition; reuse existing field canonicalization only when full source ownership is proven.
3. Cover initial/correction evaluation, missing/duplicated/reordered/mutated literals, ambiguous boundaries, overlapping fields and crossing wrappers. Reject unsupported shapes rather than guessing.
4. Run focused Arabic preprocessing/fidelity/evaluation suites; parent owns integrated Standard/Full and rollout.

## Acceptance, rollout and risks
Both source-exact wrapper arrangements must validate with unchanged visible text and stable source expected-token ownership. Adversarial cases must reject. Deliver only the new scoped diff to parent, with test outcomes and any limitations; no commit. Broad address/prose recognition risks accidental new Latin locking, so keep the inline recognizer bounded to explicit street/house-number syntax and exact source proof.

## Results
Implemented a wrapper-equivalence-only inline recognizer. Source pretokenization and saved expected-token shapes stay unchanged. The bounded form requires a recognized street name, an explicit house-number marker, exact characters and optional source-proven locality. Existing complete line/postal ownership takes priority. Canonicalization retains exact field occurrence count/order and crossing-wrapper checks; standalone constituent tokens outside the claimed fields must retain the remaining source multiplicity.

The new sanitized baseline suite reproduced five failures, including the whole-address first response and wrapper-only correction. Final focused validation passed **279 cases in 4.80 seconds**, exit 0: inline/source-address/literal fidelity, preprocessing, Arabic validation, output normalization, workflow token locking, translation structure and structured literal contracts. Thirty-nine new parameterized cases include altered/missing/repeated/reordered addresses, duplicated numeric constituents, independent repeated source numbers, nested street words, hard boundaries, malformed wrappers and preservation of an adjacent complete address/locality field. `git diff --check` passes.

Independent `workflow_audit` review found no actionable boundary/multiplicity issue. Its pure read-only retained-input reproduction accepted both actual failed response bodies against all 11 unchanged expected source tokens, including the correction with the original primary literal guard input. Both retained failure files remained hash-identical. This establishes the local validation mechanism; it does not approve other translation wording, signature metadata, complete source coverage or a new paid/provider run. Parent integration owns Standard/Full validation, continuity docs and any separately authorized rollout.

## Integrated closeout

Implementation and independent review are complete. Final frozen validation: The broader repair passed 371 focused cases; the final badge delta passed 30 affected cases, and the subsequent test-only ZIP fixture delta passed all 33 module cases. These overlapping runs are not additive. Standard03 passed 267 tests, exit 0 in 51.063 seconds (pytest 45.69 seconds). Full03 passed 2,144 selected case executions, including all 191 formatting cases; nine intake cases were intentionally deselected. It exited 0 in 2,648.000 seconds. All 1,196 captured source/test/documentation paths stayed unchanged through final Standard and Full; package versions remained unchanged. Subsequent closeout edits are documentation-only and receive separate validators. The final Full log SHA256 is `4b674a51c7f3021c4101d3f822b465cffcf5b404fe6e0c6e3948d3fcc10a867a`. Both wrappers retained the known dartdev AOT-launcher failure and succeeded through their direct-Dart fallback; agent-doc and workspace-hygiene validation passed. These are selected local checks, not an additive unique total or hosted CI.

Visible isolated shadow acceptance passed selected-generation changes, independent full-output/Arabic review gates, warning badges, explicit zero-cost retention and final Save availability. Its fixture was retired. Private `email_retest_20261015_01/completion_review_shadow/final_acceptance_receipt.json` owns that synthetic UI evidence; it is not another provider, native Word, Gmail or live extension run.

Private `email_retest_20261015_01/rollout_capture_01/final_postflight_01/receipt.json` owns the exact locally installed Git SHA, served runtime/asset identity, restored failed-job/session ownership and rollout preservation checks. An absent or failed receipt means local application is still pending; a source commit or passing local tests alone is not installation. No remote publication, hosted CI success or email sending is claimed. See the [email retest closeout](2026-10-15_email_retest_and_repairs.md) for qualified manual delivery, historical accounting and preservation scope.
