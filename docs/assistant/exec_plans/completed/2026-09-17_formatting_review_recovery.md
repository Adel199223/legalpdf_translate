# Formatting review recovery after a rejected submission

## Local completion — 2026-09-24

The scoped implementation is independently reviewed and integrated in the unpublished acceptance worktree. All four independently reviewed UI fixes are integrated only in the unpublished acceptance worktree. The final affected suites passed 39 tests; the combined Full wrapper passed 639 selected tests plus compilation and docs/hygiene checks, using the documented direct-Dart fallback. Full is not the complete repository pytest collection. Post-edit closeout docs validation is recorded separately. Desktop and narrow normal-click partial downloads passed using fictional loopback bytes; the actual French download used its observed artifact URL before the UI fix. No paid translation was replayed. The implementation scope is complete; publication is separate. Parent testing is concluded with its documented French failure, deferred optional Arabic formatting and qualified Gmail recovery. Earlier pending-status entries below are retained execution history.

## Goal and non-goals

Allow an explicitly and successfully submitted new formatting revision to make its first normal DOCX build after a browser-restored draft. Recover editing after a rejected submission only when a fresh authoritative read proves the same generation remains an unpublished draft. Preserve uncertainty for lost responses, published revisions and unknown build operations. Do not change translation, strict formatting validation, paid execution, native export or saved defaults.

## Scope

Controller/UI recovery state and focused offline browser probes. The running multilingual acceptance worktree and its retained real evidence are immutable for this task. No browser/server launch, provider/native/ledger operation, publication or actual acceptance replay is authorized here.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_formatting_recovery`
- Branch: `feat/formatting-recovery-20260917`
- Base/target integration branch: `main`
- Base SHA: `7a86cd07a28496eecfbe3cc7e69398a611242184`
- Approved floor `4e9d20e` is an ancestor of the base.
- Noncanonical isolated regression work; no live server or served asset claim.

## Interfaces and contracts

Keep HTTP routes/payloads, immutable revision and nonce ownership, private browser-storage shape, exact retry identity, safe text rendering and strict source-role validation unchanged. Existing server `draft` status means no submission intent; `submission_pending` preserves uncertainty.

## Implementation steps

1. Capture the actual failure chain as qualified private evidence references: an invalid manual header assertion was rejected, normal reload restored the draft, a corrected explicit submit succeeded, but stale `restored` state disabled its first build.
2. Add offline red regressions for restored-draft successful submit and conservative rejected-submit recovery, plus lost-response and reload-negative cases.
3. Scope fresh-submit state transition to a server-confirmed submitted revision with no prior revision/build identity. Do not grant first-build permission merely from a read or restored published revision.
4. Offer explicit dismissal of an uncommitted pending submit only after a matching authoritative draft read, preserving all publication/build uncertainty cases.
5. Run focused affected browser tests and required validation; record synthetic scope separately from any later real verification.

## Tests and acceptance criteria

Successful explicit new submission from a restored draft enables one nonce-persisted first build. Reads/reloads of existing revisions cannot mint replacement builds. Failed/declined/mismatched submit responses cannot grant build authority. A lost response that may have published retains exact-request recovery and cannot unlock editing. A confirmed same-generation unpublished draft permits an explicit abandon-pending action with zero network request from that action. Changed owner/generation and pending publication remain locked. Safe DOM rendering and no fresh images during busy actions remain covered.

## Rollout and fallback

Root reviews and integrates after the current matrix. This branch is regression-only until an independently authorized real workflow verifies it. No current server hot reload or acceptance evidence substitution. Preserve all earlier drafts/revisions/failures.

## Risks and mitigations

Clearing recovery state too broadly could authorize a second build or abandon an uncertain publication. Require exact owner/review/generation and authoritative status, then an explicit operator action. Keep unknown operations and restored published revisions fail-closed. The earlier signature-stamp rejection was valid and does not justify weakening the validator.

## Assumptions and status

Root explicitly authorized this isolated fix and normal non-paid actual recovery independently. Plan recorded before production edits. Actual case evidence stays private under `application_multilingual_gmail_acceptance_20260917_01/cases/en_short_01`.

Implementation checkpoint: two new behavior probes failed against the original controller/UI, reproducing the disabled first-build control and absent explicit rejected-submit recovery. Two negative probes already passed. The first red invocation also exposed a checkbox-selector mistake in the new test fixture; that fixture was corrected before the retained second red run. No production fix was used in either red run. The first complete focused batch passed 17 tests. Two additional uncertainty/owner tests and a known-build inventory guard then passed with all six new cases. Complete final affected controller/API validation is running. A mistaken test filename caused an earlier invocation to run zero tests; the corrected invocation is distinct retained evidence.

Root explicitly deferred a standalone Full wrapper before it started, to run one required Full validation after this patch and the other campaign changes are integrated. This branch therefore must not claim Full completion or current real-browser verification. Direct Dart docs/hygiene checks have passed at the implementation checkpoint; they will be repeated after final plan results are recorded.

The implemented discard permission is transient, not persisted: every request clears it, and only a successful same-generation `draft` read with no revision and empty operation/artifact lists restores it. The operator must explicitly discard the unsubmitted request, which sends no request and resets acceptance in the UI. A `submission_pending`/published/changed-generation/read-failure state cannot supply this permission. A successful explicit submission that began on a draft clears the restored-only first-build restriction only if no known build/artifact inventory exists. An existing restored published revision and any uncertain build retain the previous restriction.

## Final isolated implementation result

The affected controller/browser-manager/API batch passed 70 tests in 395.01 seconds. That batch began before the final conservative observation guard. The final controller/UI file suite then passed all 20 tests in 27.19 seconds on the frozen production bytes; the backend/API files did not change. These batches overlap and must not be reported as 90 distinct tests. The final guard preserves an in-memory observation of `submission_pending` or a valid published revision across exact retries, so a contradictory later draft cannot authorize discard. Its new negative regression was first observed failing before the guard; the exact-acknowledgement positive paths still pass. This is defensive uncertainty preservation, not an observed healthy-backend reversal.

Independent static review approved the final controller, UI and tests with no actionable findings. Private evidence, red logs, actual-case provenance and final patch/inventory are retained under `application_multilingual_gmail_acceptance_20260917_01/formatting_recovery_patch_01`. The actual successful new-draft DOCX build in the English case used the existing pinned acceptance build, not this patch, and does not verify the patch. No actual provider, native Word, ledger, browser or server operation was executed by this isolated fix task. The existing `.venv311` runtime is referenced through a worktree-local junction only.

Implementation is ready for root review and later integration. Full validation remains explicitly deferred to the combined campaign patch, and no publication or real verification is claimed here. Keep this plan active until that integration and validation are resolved.
