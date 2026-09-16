# Docket fields in pipe-delimited metadata

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

The baseline red proof was retained, followed by 305 focused passes and F3. Actual EN02 native/coverage evidence completed the intended metadata/folio case without changing retained source or target text.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Root validation checkpoint, 2026-09-16

Root integrated the exact reviewed folio correction ead4a462 and tests f29ad544. Red run d531b3 reproduced4 intended failures against prior production code; current folio/cell/v2 suites passed305 tests2.79s (e41e95). The subsequent actual English preparation/build and sole native export completed successfully. No source/target text, artifact or saved preference was changed by the classifier correction.

## Goal and non-goals

Correct the EN V2 preflight false positive for a complete top-quarter docket field followed by pipe-delimited metadata. Preserve all original source/target text, fragment ranges, regions and layout declarations. Do not broaden bare numeric ratios into docket exceptions or hide a separate folio field.

## Scope

Only reviewed_folios.py, its exact current test file, this plan and isolated authoring receipts. No routes/UI/defaults, private formatter packet, R source, native/provider operations or tests executed by this author.

## Worktree provenance

W: C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions, codex/reviewed-regions, HEAD 4780a2e16c32adf7af7479656f0b5fafdff83224. Root-owned integration is R/feat/structured-translation-activation. Noncanonical authoring only. Exact current R module cda277eb8c49bc44ac8f928ae40e309f874f685da59b29a982264232932301ac and tests ba13df2338bd9c84ffaba71917ed6fe1c80b5948b42494fbb8fb6d2691336686 are the baselines. Differing old W module and absent W test are recorded under folio_pipe_metadata_beforeimages_20260916_01.

## Interfaces and implementation

1. Preserve existing whole-line docket grammar and existing source/target/top-quarter role evidence requirements.
2. Admit a complete first docket field in a closed 2–4-field metadata row, with nonempty fields and ASCII horizontal whitespace around each literal pipe. Mask only the docket field for folio classification, preserving all coordinates and line breaks.
3. Scan remaining raw pipe fields independently, including malformed delimiter spacing, so a real/malformed worded folio or bare slash ratio cannot hide behind metadata. No rendered text or stored hash changes.
4. Add public folio-validator tests covering PT/EN and wrapped docket retention, exact docket/reference preservation, appended/buried folios, malformed/ambiguous identifiers, geometry/role limits and ordinary embedded citation prose.

## Tests and acceptance criteria

Root owns focused regression execution, red baseline confirmation, current actual EN manifest validation and integration. Author performs only stdlib AST/hash/diff inspection. Acceptance requires the real unchanged EN manifest to pass with unchanged source/target/layout bytes and all negative cases to retain rejection. Existing Arabic sad-abbreviation, inline-cell, docket and document-local folio behavior remains tested.

## Rollout and fallback

Freeze a scoped manifest and exact diff for independent review before root tests or harvest. EN current closure will require explicit new binding after any integration. Retain the unconsumed failure and all old packet receipts. No fallback assembly or preflight replay by this author.

## Risks and mitigations

A mask must never cover other pipe fields. Scan each field using original offsets; require the target to retain the source-proven docket and bracketed reference exactly. Nonclosed delimiters, empty fields, excessive metadata fields, unknown/bare ratios and docket-like fragments outside reviewed top-quarter body/header ownership do not gain an exemption. This is classification metadata, not source or translation approval.

## Status

Authoring frozen for independent review. Seven new test functions provide 60 parameterized cases. Existing test function ASTs are unchanged from the exact current R baseline. Only stdlib AST/hash/diff checks were performed; no application import, tests, modes, native/provider calls or R writes.
