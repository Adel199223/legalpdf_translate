# Bind UI recovery to server operations and compare canonical decisions

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 10 source browser-state tests passed in F3, with actual synthetic browser recovery 9d2109be. A restored operation requires the exact current server association; semantic object comparison preserves array order and values.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Scope and provenance

W-only correction to the first frozen source UI packet. Preserve its seven files and immutable `browser_source_ui_harvest_20260916.json` in `browser_source_ui_recovery_beforeimages_20260916_01/`; record exact bases in `browser_source_ui_recovery_bases_20260916.json`. Only the controller, editor and their new test file change. The initial UI plan, translation/template/style hooks, all backend scopes and R stay untouched. Author only: no imports, test/Node/Python execution, provider/native calls or R writes.

## Findings and changes

1. Local session storage is not evidence of a dispatched operation. A restored nonce must match an exact server-returned `translation_operations` entry with the same nonce and selected revision before recovery can POST. A missing association remains read-only/unknown. The original live page can retry its same intended nonce only with its original unchanged setup; restoring or invalidating that setup cannot use an arbitrary stored nonce to bypass the requirement.
2. Canonical source storage sorts object keys. Comparing `JSON.stringify` results falsely treats a genuine saved decision as changed. Export one recursive object-key-stable comparison for both controller lost-save recovery and editor reconciliation; preserve all array ordering, exact strings and primitive values. Ignore only the expected server `reviewer_kind` decoration when comparing a typed decision.

## Authored verification

The nine-test UI file now includes two new regression functions and an extended real-flow test:

- Restored valid review/revision with a missing, different, mismatched or duplicate operation association sends no POST. Both the public controller and visible recovery button require the exact server association. A later read without that association clears permission even when the display view still contains earlier metadata.
- Nested object-key permutations compare equal; reordered arrays, changed Unicode text, changed primitive types and added keys do not. A lost-save response followed by canonical read clears both controller pending state and the editor's dirty state, allowing a later saved generation to refresh the visible reviewer.
- The DOM-to-public-service-to-Workflow test now reads the actual canonical saved page over GET, then supplies that genuine response to the lost-save controller probe. The old string comparison is explicitly shown to differ while the semantic decision remains equal. No accepted source or translation commit fixture replaces the real service flow.

Ordinary translate, saved preferences, explicit decisions and all backend routes remain unchanged. These tests are authored, not executed. The parent will run the existing Node browser ESM probes outside the subprocess-forbidding offline harness; that harness is unchanged.

## Provenance, interfaces and integration

This is an additive correction to `browser_source_review_ui_20260916.md`, with the same approved isolated worktree and integration target: W `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`; parent integration R `feat/structured-translation-activation`. W is an authoring tree, not the canonical live build. The original UI plan/manifest retain their historical pins.

`source_review.js` adds exported `sourceDecisionsEqual` and private, non-persisted `operationAssociated` state. `source_review_ui.js` uses those existing-controller capabilities. `tests/test_source_review_browser_state.py` owns the focused probes. No route, request body, session-storage schema, supplied select value or backend acceptance interface changes.

## Risks, defaults and rollout

The server is still the review and operation authority; session storage never proves dispatch. Original-page same-nonce retries retain their unchanged-setup guard. Reloads cannot invent a new start when the server has no exact recorded association. A server restart still makes browser handles unavailable; no persisted-owner restore behavior is added. Decision equality is limited to JSON values and ignores only the existing server reviewer-kind decoration.

Parent review and runtime validation precede harvest. Harvest the three corrected files and this plan from the new correction manifest while keeping the original four UI files and eight backend pins unchanged. Do not roll back an already integrated backend to W's older unrelated files.

## Status

Authoring frozen for independent static review; parent-owned runtime validation remains pending. No application imports, tests, Node/Python execution, provider/native operations or R writes were performed in this correction.
