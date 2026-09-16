# Bound source-review read allocations by the actual file size

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 15 bounded-reader race/identity cases passed in F3. The retained same-node profile measured 94.449 to 32.386 seconds wall time with all 6,317 source reads unchanged. This is one paired observation, not proof of complete-workflow savings.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Root validation checkpoint, 2026-09-16

Root integrated the combined reader/busy correction after independent reviews43ee7c33 and95e09325. The current canonical-interpreter focused run passed89 tests260.19s, including all15 bounded-reader cases and both real contention cases. The same profiled integration node passed1 test31.50s (32.386s wall), versus94.449s wall in the retained initial run. Source reads stayed6317; reader cumulative time fell65.659s to12.705s. Private comparison953365b1 retains single-observation and main-thread limitations. Full repository regression is now running; no further reader optimization is inferred from this result.

## Goal and evidence

The root-owned profile of the genuine browser formatting integration test took about 93 seconds. Source service `_read` ran 6,317 times against a retained set of 12 files totaling 17,150 bytes (maximum 4,068 bytes), but requested as many as 64,000,001 bytes per read. This change reduces that allocation request without caching data or removing any freshness check.

## Scope and coordination

Author in W `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`; root alone integrates and tests in R. Coordinate the shared `ordinary_source_review_service.py` file with the independently authored typed-busy propagation change. Preserve the exact current R file and the frozen W typed-busy file before changing `_read`. Own only the `_read` delta, this new test file and this plan; do not overwrite the other author's import or exception changes.

W is the approved noncanonical concurrent worktree, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`. The parent owns integration through R and eventual canonical `main`; this task neither changes branches nor publishes. The actual source baseline is the preserved current R file, with the independently preserved W typed-busy delta layered on it.

## Implementation

Keep direct-path validation and the complete pre-open, opened, post-read and final-path identity comparisons. Reject a known file size outside zero through the existing maximum. Request that file size plus one sentinel byte, require the returned length to equal the original size, and retain the existing maximum check and caller SHA-256 verification. Empty-file semantics at the reader remain unchanged. No persisted cache, stat-only trust, guard removal, accepted source-data change or other reader optimization is included.

Only the private `_read` implementation changes. Public routes, payloads, source-review identities, accepted data and error vocabulary stay the same. The new test module observes actual read sizes and introduces deterministic mutations around the real reader; the plan and hash manifest describe this scope. Ordinary formatting readers are out of scope.

## Validation

Author deterministic regressions for exact bytes and allocation size, empty and exact-limit files, pre-open oversize rejection, growth/truncation before open and before/after read, same-size/mtime replacement before open and after close, short reads with unchanged identity, and actual source-review rejection of same-size retained-object tampering. Root runs these tests and relevant existing source-review tests, then repeats the same real profiled integration test once. Do not perform a large artificial allocation benchmark. Report performance only from actual root measurements.

## Rollout, risks and assumptions

Root reviews and harvests the combined source once both authors' scopes are independently reviewed. Validation must retain the existing provider/native denial fixtures and file ownership checks. A regression blocks integration; the preserved beforeimages provide exact comparison inputs, without reverting a consumed operation or restoring runtime data. The principal risk is missing a concurrent file change after reducing the requested read size; exact returned length and all four existing identity comparisons remain mandatory. No timing-based speed threshold is an acceptance test, and no measured improvement is claimed before the root-owned profile.

## Status

Authoring complete; independent review and root-owned tests/profile remain pending. The exact R baseline and W typed-busy baseline are preserved under `source_read_allocation_beforeimages_20260916_01`. The combined source keeps the independently authored `RunWorkspaceBusy` import and `_scope` exception branch unchanged. Six new test functions define 15 cases; none have been executed by this author.

No application/helper imports, tests, provider/native calls or R mutations by this author. The English runtime remains under root ownership and this W patch does not change its frozen package. Runtime validation and the single before/after real-profile measurement are required before reporting a performance outcome.
