# Release only a pristine declined source preparation claim

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 44 source API tests passed in F3. The integrated release remains limited to an object-identical new claim, explicit decline and pristine lock-only evidence.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Scope and baseline

W-only follow-up to the frozen browser source route packet. Change only `shadow_web/source_review_api.py`, `tests/test_shadow_web_source_review_api.py` and this new plan/addendum. Preserve all eight original packet files and its manifest under `browser_source_claim_beforeimages_20260916_01/`; hashes are in `browser_source_claim_bases_20260916.json`. The source service/recovery tests, bridge, Workflow and formatting files remain frozen. No imports, tests, application/helper execution, provider/native calls or R writes in this pass.

## Behavior

An explicit source policy decline currently leaves an in-memory claim tied to the original config. Even though no source review was acquired, changing saved OCR/retention settings then preparing the same owned upload fails with `source_review_run_owner_conflict`.

Release only a claim installed by this exact prepare call, after the bridge returns the explicit flat decline contract (`status: "declined"`, nonempty bounded source notice codes, no review handle/extra fields). Hold the API ownership lock and the original run workspace lock, recheck OS lock identity with the existing reentrant context, and require exactly the direct stable lockfile in the run directory. Compare the retained claim by object identity. No directory deletion, lockfile removal, broader registry reset or automatic retry.

Existing claims, changed claim objects, artifact-bearing runs, malformed responses and all exceptions retain ownership. Exceptions do not expose a trustworthy acquisition stage, so they are treated as unknown outcomes. Service policy is not copied into the route; the actual service remains authoritative. A successful acquisition keeps its original exact claim and requires a new explicitly reviewed context for changed settings.

## UI integration note

All route paths, body/response keys, notices and paid-operation nonce semantics remain unchanged. After a pristine explicit decline, users may deliberately correct saved settings and prepare the same owned upload again. Once acquisition has occurred, retain `source_review_run_owner_conflict`; suggested UI copy is: "Settings changed after source review began. Prepare a new source review for the changed settings using a new upload or run." The route never silently switches preferences, reuses accepted evidence under changed settings or retries a paid operation.

## Authored verification

Use actual owned upload/browser bundle/source service for disabled OCR, API-only OCR and retention-off declines followed by explicit saved-setting corrections and same-upload acquisition. Assert no provider clients or automatic requests. Cover artifact-bearing declines, malformed results, exceptions, existing/replaced claims and an occupied run; they must retain ownership. Existing successful-acquisition config-conflict and nonce tests remain unchanged. Parent owns runtime validation.

## Status

Authored and frozen for independent review and parent-owned runtime validation. The production delta adds one private release helper and records whether this prepare call installed the claim. Thirteen new parametrized cases cover three actual policy corrections, eight uncertain/acquired outcomes, an existing claim and an occupied OS run lock. No imports or tests were executed.

The original eight-file route manifest remains immutable. `browser_source_claim_harvest_20260916.json` explicitly supersedes only its API module and new API test file; all other route files and the separately frozen source/context/bridge/formatting packets remain unchanged. The source publication correction was reviewed concurrently under its own exact pins and receipt; it is not part of this route delta.
