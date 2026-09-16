# Preserve real client class identity in legacy formatting tests

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

The affected fixture suites passed 23, 17 and 10 cases in F3. Real class identity is preserved while forbidden-construction callbacks and original assertions remain active; production behavior is unchanged.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Scope and provenance

This test-only correction is authored in `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, base `4780a2e16c32adf7af7479656f0b5fafdff83224`. The integration target is the existing `feat/structured-translation-activation` worktree. No production code or canonical/live build is changed.

Root's focused reproduction identified fifteen legacy formatting failures at `TranslationWorkflow.__init__`: the old fixtures replaced `OpenAIResponsesClient` with a function, so the real constructor's `isinstance(client, OpenAIResponsesClient)` raised `TypeError` before rebuilding. Root identified a sixteenth matching case in `test_output_handling.py` from the still-running full collection; its fixture has the same replacement. Preserve every existing output, accounting, sticky-warning and no-provider assertion.

## Implementation

- Copy only the exact current R versions of `tests/test_formatting_workflow.py`, `tests/test_formatting_policy_isolation.py` and `tests/test_output_handling.py` into W after preserving both R and W beforeimages under `legacy_client_fixture_beforeimages_20260916_01`.
- Patch the original client class's `__init__` with the existing forbidden callback instead of replacing the class. The callback still fails immediately on attempted construction, while `isinstance` receives the real type. This matches the existing `test_docx_clock_rebuild.py` fixture.
- Keep the scope local to the existing fixture or test. Do not broaden the patch to `no_external_work`, because that fixture also supports a separate synthetic SDK client-construction contract test.
- Leave every assertion, parameter, saved checkpoint, provider/auth/extraction/OCR denial and timeout unchanged. No route, payload, preference or production behavior changes.

## Validation and status

Authoring is frozen and statically checked against the exact R beforeimages. No application imports, pytest invocation, provider/native operation or R write occurred in this scope. Root owns harvest and runtime validation after the running full-suite snapshot ends. Run the three affected modules with the canonical `.venv311` interpreter, then include the corrected fixtures in the final full repository regression; this document does not claim they pass yet.

The full run's other failures and any later failures remain separate. Do not weaken production checkpoint gates or provider boundaries to make legacy tests pass. Rollback, if needed, uses the exact retained beforeimages only after root authorizes it. No commit or publication is performed by this scope.
