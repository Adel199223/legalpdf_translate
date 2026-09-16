# Preserve typed formatting run contention

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

The focused combined pass covered 89 cases, and F3 passed the contention/service regressions. Only the existing typed RunWorkspaceBusy condition is propagated to the existing browser busy response.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Root validation checkpoint, 2026-09-16

Root integrated typed RunWorkspaceBusy propagation together with the independently reviewed bounded source reader. Current focused tests passed89 in260.19s, including the unchanged concurrent nonce test and new real retained-loader contention test. All generic/private errors remain sanitized; no new dispatch or artifact is created on contention. Earlier formatting61 suite60pass/1fail1188.14s remains the preserved pre-fix result.

## Goal and non-goals

Preserve `RunWorkspaceBusy` through source-context loading and trusted-job resolution so the existing formatting manager emits its existing `run_busy` error. Do not change locks, ownership, source verification, timeouts, route shapes or general content-free errors.

## Scope and provenance

- Authoring only in `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions` (W), branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`.
- Exact selected baselines come from current R `C:/Users/FA507/.codex/legalpdf_translate_structured_activation`, target branch `feat/structured-translation-activation`. W is a noncanonical authoring worktree, not a runtime launch target.
- Four necessary files were preserved under `browser_formatting_busy_beforeimages_20260916_01` and synced byte-for-byte from R. Their W/R base pins matched; `browser_formatting_busy_bases_20260916.json` records them. No wholesale sync or R mutation.
- Root holds R stable for the EN acceptance window. Source `_read` optimization belongs separately to Agent5 and must build on the frozen typed-busy source-file pin, preserving a new beforeimage.

## Interfaces and implementation

1. `ordinary_source_review_service.py`: import the existing run-lock error and rethrow that typed error from `_scope` before generic translation. Other source failures remain unchanged.
2. `translation_service.py`: preserve the same typed error from `trusted_formatting_job`. The existing browser formatting `_scope` already translates it to its public `run_busy` category.
3. `test_browser_formatting_review.py`: exercise the real source loader and trusted job under another thread's real run lock; assert exact typed propagation, no second dispatch or formatting publication, and unchanged existing source-bridge generic containment.
4. `test_ordinary_source_review_service.py`: tighten the existing actual held-lock context-load assertion to the now-preserved type. Existing end-to-end concurrent rebuild test remains unchanged, including its 10-second waits.

## Evidence and tests

Root-authorized diagnostics at `P/application_formatting_profile_20260916_01` reproduced the runtime chain `RunWorkspaceBusy -> source_review_operation_failed -> formatting_job_unavailable -> browser_formatting_review_operation_failed`. The existing test failed its expected busy-category assertion, not its entered wait. The private exception-chain observation is diagnostic only; production must not parse strings or suppressed traceback contexts.

Review the exact code/test delta, then root runs the focused source and formatting contention tests after harvest. Include real source API/bridge regression checks: the source bridge still catches generic exceptions and returns its existing fixed errors, and the source API's generic handler still returns fixed status-422 diagnostics. No new raw exception message reaches an API response.

## Risks, rollout and defaults

Direct service callers can now distinguish actual contention from other failures. `RunWorkspaceBusy` remains a `ValueError`. Source browser wrappers retain their current generic public categories. All immutable source/context/ownership checks and same-thread reentrancy remain intact. No cache, retry, timeout, acceptance, default-setting or route change is included. Root reviews and harvests the bounded packet; rollback is the exact beforeimage.

## Status

Authoring frozen, root review/runtime validation pending. The typed source-service snapshot is retained as `browser_formatting_busy_beforeimages_20260916_01/source_service_typed_busy.py` (SHA256 `88cdf4a9cd47c84b40f93d52350304ef231c9eb53423eb8fbbe892703ca15317`). Agent5 may now supersede the live W source file with the separate measured-read correction; this packet's exact typed-only delta uses the immutable snapshot, not a moving W file. Root must integrate the combined reviewed source file deliberately.

The new real-loader test holds the actual run slot on one thread, calls the completed job's original context loader and formatting prepare from another, and checks typed busy/public busy classification without a new draft, source changes or second dispatch. It also checks the original source bridge's fixed image error, context reuse after release and content-free generic handling for an unrelated loader error. The existing source-service held-lock test now expects the preserved type. The original concurrent-nonce test and both 10-second waits are unchanged.

Static caller review: `browser_source_review.py` retains its method-specific `except Exception` wrappers; `shadow_web/source_review_api.py:265–271` retains fixed error envelopes and status 422. No route or payload change is needed. No imports, tests, provider/native operations or R writes were performed for this implementation. Prior diagnostics executed against unchanged R are separate evidence, not validation of this patch.
