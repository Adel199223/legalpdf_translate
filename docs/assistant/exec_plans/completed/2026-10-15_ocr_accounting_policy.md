# Future scanned translation accounting policy

## Goal and non-goals
Allow future default OpenAI OCR calls with complete supported billing evidence to contribute their real token cost to ordinary translation and layout accounting. Preserve unknown historical calls, immutable saved policies, and the layout accounting gate. No provider calls, live repair, schema changes or publication.

## Scope and provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/email-save-cost-oct15/legalpdf_translate`
- Branch: `feat/email-save-cost-20261015`
- Base branch: `main`; base SHA: `a69a2dcc811d5b220729e28265fb2f76bcc36a19`
- Integration: parent `feat/email-retest-20261015`, then separately approved canonical publication.
- This checkout is noncanonical. The earlier cost-input repair remains a separate uncommitted change in this worktree.

## Contracts and implementation
Preserve all API contracts, accounting identity checks, hard-budget reservations and `_source` completeness enforcement. Extend only the future ordinary policy with an exact OCR alias/snapshot allowlist, default-tier public USD prices and approved public endpoint binding. Retain omitted request tier/output controls for ordinary uncapped calls. Refresh the combined future catalog date after verifying both affected models; saved runs restore their original catalog and limits.

Files: `accounting_policy.py` contains the policy; `test_ordinary_accounting_policy.py` exercises real OCR transport/accounting, exclusions, historical preservation and combined prior-call budget attribution. The layout-manager fixture date and three ordinary caller/workflow test clocks follow the new catalog date; the caller's catalog identity assertion follows its new name. Add a scoped reference-registry block with official URLs and verification date.

## Tests and acceptance
Fictional OCR success must settle actual alias/tier/usage and allow the ordinary layout accounting boundary to include OCR, translation and correction spend exactly once. Wrong model, unsupported or absent tier, and untrusted endpoints remain unknown and block layout. Unsupported hard-budget OCR must stop before dispatch; no guessed image bound or auto-tier guarantee. Existing saved unknown OCR receipts remain byte-identical after policy refresh. Run focused policy, transport, accounting and layout suites; parent runs integrated Standard and Full.

## Rollout and fallback
Parent reviews and copies the bounded changes for integration. Canonical runtime remains unchanged. Historical OCR remains unknown; a future policy fix does not silently reprice it. If validation fails, retain the completed translation and stop before paid layout rather than bypassing the gate.

## Risks and assumptions
Public token prices are attribution rather than invoice reconciliation. Only the documented GPT-4o Mini snapshot and actual default tier at the verified public endpoint are supported. Policy expiry remains local and finite. No general OCR-provider promotion or hard-budget image allowance is implied.

## Progress
Read-only diagnosis established complete OCR response metadata but missing policy alias, prices and endpoint/scope attribution. Official model and pricing references verified 2026-10-15. The bounded future-run policy is implemented; the shared transport and accounting gate require no change.

Validation: the initial accounting run passed 69 cases and failed one new test comparing equivalent Decimal zero strings; the assertion now compares numeric values. A broader run passed 195 and failed eight existing checks because their fake clocks preceded the new verified catalog date. Only the ordinary policy clocks were updated; the separate layout catalog and historical recovery dates remain unchanged. The follow-up broad run passed 208 of 219, with 11 caller cases still executing the old catalog-name assertion loaded before its correction. The complete final policy/caller rerun passed all 40 cases in 7.12 seconds. Together these runs verify all 219 targeted cases on final applicable code; no single all-green combined run is claimed. Direct-Dart agent-doc and workspace-hygiene checks and `git diff --check` passed. Parent integration owns Standard, Full and runtime acceptance.

The exact fictional success probe fails against unchanged canonical policy with incomplete coverage and unknown cost, establishing the regression. Existing live OCR receipts remain unknown and untouched. Their model, tier, endpoint and token evidence is retained, but there is no existing supported retrospective reconciliation operation; no manual journal rewrite or guessed zero is used.

## Integrated closeout

Implementation and independent review are complete. Final frozen validation: The broader repair passed 371 focused cases; the final badge delta passed 30 affected cases, and the subsequent test-only ZIP fixture delta passed all 33 module cases. These overlapping runs are not additive. Standard03 passed 267 tests, exit 0 in 51.063 seconds (pytest 45.69 seconds). Full03 passed 2,144 selected case executions, including all 191 formatting cases; nine intake cases were intentionally deselected. It exited 0 in 2,648.000 seconds. All 1,196 captured source/test/documentation paths stayed unchanged through final Standard and Full; package versions remained unchanged. Subsequent closeout edits are documentation-only and receive separate validators. The final Full log SHA256 is `4b674a51c7f3021c4101d3f822b465cffcf5b404fe6e0c6e3948d3fcc10a867a`. Both wrappers retained the known dartdev AOT-launcher failure and succeeded through their direct-Dart fallback; agent-doc and workspace-hygiene validation passed. These are selected local checks, not an additive unique total or hosted CI.

Visible isolated shadow acceptance passed selected-generation changes, independent full-output/Arabic review gates, warning badges, explicit zero-cost retention and final Save availability. Its fixture was retired. Private `email_retest_20261015_01/completion_review_shadow/final_acceptance_receipt.json` owns that synthetic UI evidence; it is not another provider, native Word, Gmail or live extension run.

Private `email_retest_20261015_01/rollout_capture_01/final_postflight_01/receipt.json` owns the exact locally installed Git SHA, served runtime/asset identity, restored failed-job/session ownership and rollout preservation checks. An absent or failed receipt means local application is still pending; a source commit or passing local tests alone is not installation. No remote publication, hosted CI success or email sending is claimed. See the [email retest closeout](2026-10-15_email_retest_and_repairs.md) for qualified manual delivery, historical accounting and preservation scope.
