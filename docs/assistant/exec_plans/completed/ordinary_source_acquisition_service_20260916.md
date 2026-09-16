# Public ordinary source review acquisition

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 48 ordinary source-service tests passed in F3, covering retained acquisition, explicit review and immutable accepted evidence.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Scope and provenance

Author only in `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, base HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`. Root owns current R integration and testing; no imports, execution, native/OCR/provider calls or R edits. Exact R OCR/types baselines and W beforeimages are recorded in `ordinary_source_service_bases.json` and `ordinary_source_service_beforeimages_20260916_01`. Previous context/transport work remains separately pinned.

## Goal

Provide a callable run-bound source review service for complete browser-image PDFs. Retain real selected local OCR TXT/TSV bytes before temporary cleanup. Derive source variants, candidate/hash bindings and review envelopes in production code. Only explicit operator actions and completion decisions can create an accepted source revision. No UI/routes, auto-review, private acceptance/tooling imports, saved preference changes or paid OCR fallback.

## API and persistence

`OrdinarySourceReviewService(config)` copies the supplied saved RunConfig and derives its deterministic run owner. `prepare()` returns a draft view or a content-free decline. `read(draft_id)`, `save_page(draft_id, expected_generation=..., page_number=..., decision=...)`, `submit(draft_id, expected_generation=..., reviewer=..., accept_source=...)` and `load_context(revision_id)` use the same cross-process run lock as translation. Page decisions have explicit typed action IDs/kinds, baseline IDs, operator text/regions/rationale, order, boundary and findings; callers never supply hashes, raw variants or acceptance envelopes. Initial decisions are absent, not pre-approved.

Content-addressed evidence objects and numbered draft generations are immutable. Saved-generation checks reject stale writes; submission freezes its exact draft generation and publishes the immutable revision marker last. No latest-revision inference. File operations reject traversal, links/reparse points/hard links and bound bytes. All operations verify current source/config/run ownership; source guards recheck retained bytes and physical source independently of the context's own verification. Crashes may leave unreferenced immutable objects or an incomplete submission freeze; this is fail-closed publication, not a general filesystem transaction.

## Implementation

1. Promote the exact pure candidate builder into the installed package, retaining tooling behavior unchanged.
2. Add opt-in retained local evidence to OCR results without adding bytes to metadata/report/API serialization. Preserve scoring, selected pass and fallback behavior for existing calls.
3. Author the service and typed public review actions/decisions, source/owner checks, immutable storage and explicit context loader.
4. Author synthetic local OCR plus real transport/SDK Workflow integration tests, candidate compatibility and adversarial generation/source/ownership tests.

## Constraints and acceptance

OCR-off, API-only, missing local baseline/evidence, partial selection and nonbrowser sources decline. LOCAL_THEN_API permits only its local acquisition stage; failure declines without constructing a provider engine or requesting credentials. `page_breaks=False` remains untouched and permits source review/translation. Formatting remains a separate opt-in step with its existing limitations. No retained evidence for the current Arabic acceptance is reacquired.

## Review resolutions and validation handoff

The service preserves the existing target-derived local pass profile (including the Arabic third pass). Optional renderer retention is bounded and omitted from ordinary metadata/report/API serialization. Selected TXT newline normalization applies only to the derived candidate-v1 source variant; original renderer TXT/TSV and engine structure bytes remain unchanged. Repeated-image acquisition and subsequent OCR artifacts are bounded incrementally, including duplicate raster reads.

Worker guards read one coherent checkpoint JSON snapshot and compare immutable owner/settings/context fields, allowing normal atomic progress replacement. They do not acquire the owner thread's run lock. The read-only context loader may recover an abandoned `running` checkpoint only while holding the available OS slot; active runs remain excluded. Draft mutations still require an idle checkpoint. Preparation may create the stable run lock/run directory before a partial-selection or local-evidence decline. No source review tree is published for those declines.

`tests/test_ordinary_source_review_service.py` covers raw selected renderer bytes, actual public decisions through the real Workflow/OpenAIResponsesClient with synthetic SDK/ordinary accounting, exact resume including an abandoned status, CLI draft with unchanged page-break preference, default policy declines, incomplete/operator decisions, stale and submitted generations, source/object/owner tampering, active lock contention, checkpoint progress replacement, repeated-image limits, pass-profile parity and production/tooling candidate compatibility. `tests/test_ordinary_reviewed_source.py` additionally covers transport jitter/reservation/retry rechecks and exact saved-context CLI reconstruction. All tests are authored and unrun.

Status: implementation and static review complete pending independent final review/root execution. No project imports, AST/compile/test/native/provider execution performed. Root owns targeted harvest and runtime validation. UI/routes and visual region acquisition remain outside this implementation.
