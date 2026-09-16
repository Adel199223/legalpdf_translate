# Include ordinary review regressions in Full validation

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

Actual Standard Full SF2 passed its explicit source and formatting groups on the recorded snapshot. Separate complete F3 also passed 6,477 cases; these are distinct validation commands and neither is presented as the other.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and scope

Append source-review and formatting-review pytest groups to the existing `scripts/validate_dev.ps1 -Full` extras. Baseline validation, existing Gmail groups and filters, failure handling, docs trigger, Dart fallback and workspace hygiene remain unchanged. No backend/UI/default changes, test edits or new command-line switches.

## Provenance

Authoring W is `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`, noncanonical authoring only. Current R `C:/Users/FA507/.codex/legalpdf_translate_structured_activation` on `feat/structured-translation-activation` supplies the exact baseline.

W/R script SHA256 both `852ad9c45c8be059f69dd263afa49045c8508812dbc35c211404affe828cad32`. Preserve it at `review_validation_full_beforeimages_20260916_01/validate_dev.ps1`, then copy exact R baseline to W before editing. No R mutation or wholesale synchronization.

## Implementation and contracts

Append two entries to `$fullExtraCommands` after the existing Gmail entries. Both use the existing `$venvPython` and `-m pytest -q` invocation through the unchanged logging/failure wrapper.

Source group: `test_source_review_candidate.py`, `test_ordinary_reviewed_source.py`, `test_ordinary_source_review_service.py`, `test_ordinary_source_bounded_reads.py`, `test_browser_source_review.py`, `test_shadow_web_source_review_api.py`, `test_source_review_browser_state.py` (all under `tests/`). This is the six-file source assessment plus the newly requested bounded-reader suite.

Formatting group: `test_ordinary_formatting_review_service.py`, `test_ordinary_formatting_options.py`, `test_browser_formatting_review.py`, `test_shadow_web_formatting_review_api.py`, `test_formatting_review_browser_state.py`, `test_formatting_review_cli.py` (all under `tests/`).

These explicit groups extend the existing Full check. They do not redefine it as a complete repository pytest collection; separate repository-wide pytest remains required where applicable. Existing synthetic fixtures, native/credential guards and Node-backed browser state tests execute as already authored. No test filtering or offline-boundary exception is added.

## Validation, rollout and risks

Statically verify that the exact diff contains only the two entries, every listed test file exists in the current R target or a separately reviewed pending W packet, and baseline/Gmail/docs/Dart blocks are byte-identical. W does not contain the existing R `test_source_review_candidate.py`; it is an authoring checkout, so no unrelated test synchronization is needed. The new bounded-reader suite must be harvested with its separate source patch before Full validation. Root reviews and harvests after the current EN window and runs validation. No script import, execution, test or R edit occurs during this authoring task. Root owns runtime validation and interpretation of Node/tool availability or pre-existing failures.

The change increases Full runtime by the explicit review groups. Any group failure retains the existing stop-on-failure behavior. Rollback is the exact retained script baseline. No timeout, retry, interpretation of failure, or user preference changes are introduced.

## Status

Authoring frozen; root review and validation pending.
