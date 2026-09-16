# Ordinary visual formatting review service

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 33 ordinary formatting-service tests passed in F3, covering explicit page/document decisions, submitted revision ownership and separate reviewed artifacts.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and non-goals

Expose explicit operator source/target region decisions through a public callable service, using the existing ordinary reviewed DOCX adapter. The backend owns all paths, hashes, IDs and immutable source evidence. No routes, browser rendering, provider/native execution, automatic approvals, preference changes or private acceptance helpers are in scope.

## Worktree provenance

- Authoring: `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`.
- Current integration: `C:/Users/FA507/.codex/legalpdf_translate_structured_activation`, `feat/structured-translation-activation`, same HEAD with separately frozen changes.
- Noncanonical authoring only. Root owns harvest, integration and validation. No imports, tests or execution are authorized in this pass.
- At scope start `reviewed_formatting.py`, `run_docx_formatting.py` and `reviewed_formatting_writer.py` matched integration byte for byte. Root subsequently authored the separate R-only footer validator correction (`d2208efc...`); W keeps its earlier validator (`c5c8dc2d...`) and root will integrate/test the service against the newer floor. No baseline synchronization or existing-file edits are made here. Source/context/browser bridge scopes remain untouched by this author; Agent1 separately owns the root-authorized lazy-transport correction.

## Interfaces and contracts

`OrdinaryFormattingReviewService(config, source_context)` accepts only trusted backend-resolved saved configuration and the exact immutable ordinary source context. Operations: `prepare`, `read`, `image`, `save_page`, `save_document`, `submit`, `inspect`, and `rebuild`. All operations own the existing run OS lock. Config/checkpoint/context identity, actual commit/TXT/image binding and retained original source evidence are rechecked.

Typed page decisions provide independent source and target Unicode codepoint ranges, a one-based parent number, explicit pixel boxes, role/alignment/style, paragraph/table ownership through one-based fragment numbers, and an explicit local folio selection (including absence). Document decisions provide explicit contiguous groups, optional reviewed pipe-cell cuts and optional source-gap spacing. No range, box, container, folio or approval is preselected. Final submit requires every page's full-page and mapping completion assertions plus a separately explicit final acceptance. These declarations retain `operator_review`, `geometry_status=not_verified`, and rendered layout acceptance `not_evaluated`.

The service derives the existing strict manifest from these actions and invokes the unchanged public validator and normal run adapter. It saves bounded exclusive draft generations, with immutable original parent text/binding snapshots, then publishes the adapter's accepted revision and a service-owned selection receipt. Existing adapter defaults remain `strict_ai_test_v1`; this service explicitly selects `ordinary_operator_browser_v1`.

A durable submission intent fixes the exact draft/generation/context/reviewer/evidence before adapter publication and freezes further draft edits. Recovery searches the bounded owned revision inventory for exactly one completed matching evidence publication, validates it through public prepare, and finishes missing receipts idempotently. A lost successful response is recoverable through `read(draft_id)` or exact repeated submit. Changed acceptance inputs and ambiguous matches fail. Read never creates a new adapter revision. Once adapter execution began, an uncertain attempt with no completed matching publication remains pending and cannot be blindly retried; incomplete files stay available for explicit backend diagnosis.

## File-by-file steps

1. New `src/legalpdf_translate/ordinary_formatting_review_service.py`: typed decisions, bounded direct-path storage, generation and source guards, explicit acceptance, exact revision inspection/rebuild.
2. New `tests/test_ordinary_formatting_review_service.py`: genuine public source acquisition and synthetic local OCR/SDK ordinary Workflow commits, followed by formatting decisions and strict package validation; negative stale/tamper/ownership/generation/policy cases.
3. Record dependency and final file pins in a new small JSON manifest. No wholesale copies.

## Tests and acceptance criteria

Root will execute focused tests and ordinary regressions with the mandated project Python after freeze/harvest. Author tests for EN/FR/AR independent ranges and literal preservation, editable paragraph/table and local folio grouping, no inferred decisions, strict reviewer provenance, stale TXT/source/context/config rejection, generation conflicts and active run exclusion. Failure injection covers loss after adapter publication, each service receipt, a successful response, and an uncertain incomplete publication. Rebuild must retain source commits, ordinary accounting and preferences, and make zero SDK/OCR calls. Invalid mappings must not invoke the ordinary fallback writer. Cross-process lock behavior is covered separately by existing lock tests.

## Rollout and fallback

Unsupported partial, non-browser, non-operator, unstructured, page-breaks-disabled or bidi-stripping-disabled profiles return explicit notices. Source or target tampering remains an error or explicit stale decline, never permission to reuse a mapping. The explicit service rebuild uses public prepare/build APIs directly; no ordinary fallback is called. It publishes a separate non-overwriting DOCX/map/assembly receipt and does not rewrite checkpoint selection, accounting, existing DOCX or normal run reports. Later UI wiring must register this returned artifact explicitly. Failed publication can leave incomplete immutable files; this is not an all-or-nothing filesystem transaction.

## Risks and mitigations

- Browser JavaScript uses UTF-16 indices: future UI must convert selections to Unicode codepoint offsets against the exact displayed parent string, including bidi/literal wrappers. The service never converts or guesses them.
- Source geometry remains operator-observed and unverified. A4 remains the existing assumed frame. A rendered Word/PDF review is still required separately.
- Run locks serialize cooperating translation/review work. Direct-path checks reject symlinks/reparse points/hardlinks, bounded reads and recapture detect stale inputs; local filesystem control is not reviewer authentication or an adversarial-user security boundary.
- Draft reads may create the existing stable `.run_workspace.lock` if absent. A retained lock file is not activity; prepare does not create missing run folders or provider artifacts.
- Complete-only profile may honestly decline OCR/digital/partial runs and current `page_breaks=False` defaults. Ordinary source review/translation remains usable independently. A later explicit profile/settings choice is required before a new run to request source-page-matched formatting; do not silently change saved preferences or retrofit checkpoint settings.
- No browser routes/payloads are changed. A future owned mode/workspace bridge must resolve config/context and expose opaque IDs, safe text/image rendering and explicit submission. Persistent revisions require exact ID selection; no auto-latest marker is introduced.

## Status

Authoring complete and frozen for root harvest. Independent static review found and resolved submission recovery and exact intent-to-revision binding gaps; root also requested strict integer types for persisted generations. Synthetic tests cover the corrections. No imports, execution, provider/native calls or tests ran in this author-only pass. Root owns runtime validation against its newer footer-validator floor and separately revised browser bridge.
