# Preserve a confirmed source-review job through upload handoff

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 10 source browser-state tests passed in F3 and the combined actual synthetic browser smoke 9d2109be completed the expected handoff without creating another job.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Root validation checkpoint, 2026-09-16

Root harvested four files (receipt62408478) after independent review371e2232. All10 source UI tests passed18.33s in the valid second run; the earlier absent-output-parent setup failure is retained. Combined actual browser smoke then confirmed the correct accepted-source message and exact source/translation/formatting recovery with one synthetic SDK call (receipt9d2109be).

## Goal and evidence

Root's actual synthetic browser smoke completed translation, DOCX download and exact reload recovery. The normal onJob hook calls renderTranslationJob, which clears temporary manual-upload state. The unchanged form then incorrectly reports source/setup drift. Root also observed that the nested source field label includes select-option text in an exact accessible-name query.

## Scope and provenance

W-only authoring in `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`. Parent integrates into R `feat/structured-translation-activation`. Preserve source controller f138fb15, editor93f6e2d and testsff63b832 plus the original recovery manifest in `browser_source_ui_handoff_beforeimages_20260916_01/`; exact pins are recorded in `browser_source_ui_handoff_bases_20260916.json`.

Only those three files and this plan change. No formatting UI packet, shared translation/template/style hook, backend, provider/native operation, test/import execution or R mutation. R's smoke/evidence and the EN package remain under root ownership.

## Implementation and authority

- Source controller: a private, nonpersisted upload-handoff marker is set only after validating an actual server job response. It suppresses only sync's manualReady-loss warning after expected cleanup. Continue comparing the exact original setup regardless; reset/scope changes clear the marker. No approval is inferred from a stored job ID.
- During read, reviewVerified and operationAssociated are still cleared before GET exactly as before. The separate UI marker survives that read await, but never bypasses dispatch checks. A failed/mismatched read leaves operationAssociated false. checkSetup remains byte-for-byte unchanged, so new/unassociated sends still require the original manual-ready setup. Root explicitly chose this separation after reviewing the initial proposed approach.
- Source field helper: give each control the plain field label through aria-label. Keep nested wrappers, text insertion and submitted values unchanged.

## Tests and integration

The ten-test source UI file now includes a regression that runs explicit prepare/accept/translate and simulates onJob clearing manualReady then synchronizing, followed by read and same-operation recovery. It checks verification/association are both false during the awaited GET, failed and mismatched reads cannot dispatch, actual setup changes still invalidate, scope changes discard the old owner, loss before a confirmed job blocks first dispatch, and a stored nonce/job without a server association cannot dispatch after reload. The actual DOM probe now asserts exact plain names for all labelled controls, including the Action select. These tests are authored, not executed.

Parent owns runtime validation and harvest. Preserve the original manifests as history and publish a new three-file correction diff/manifest plus this plan. The formatted UI's dependency pins referring to the earlier source files are historical; its seven code/plan files stay byte-identical during this correction.

## Status

Authoring frozen for independent static review and parent-owned runtime validation. No imports, tests, provider/native calls or R writes performed.
