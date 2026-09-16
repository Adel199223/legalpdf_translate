# Explicit visual formatting review in the browser

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 11 formatting DOM/public-flow tests passed in F3. Actual combined synthetic smoke 9d2109be completed explicit review/build/download and exact recovery while preserving saved page-break False.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and scope

Let an operator review a completed ordinary reviewed-source translation against its original page images, select source and target text independently, describe paragraph/table ownership and document groups, then accept one exact formatting revision and build/download its DOCX. Use Agent5's dedicated job-owned formatting routes. No target text editing, source acquisition, automatic layout acceptance, provider/native calls, or changes to ordinary Translate/Rebuild, saved preferences or Gmail contracts.

## Worktree provenance

Author only in W `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`. Parent integrates into R `feat/structured-translation-activation`; W is not the canonical live build. Root confirmed source UI harvest receipt `8c1330b45a3ebfd0d1137dfe19140a12bdb23293914340355e37cf4a332e446a` before the shared-hook changes. `browser_formatting_ui_bases_20260916.json` binds the exact beforeimages of translation/template/style and unchanged source modules/manifests. First reviewed drafts are retained in `browser_formatting_ui_review_beforeimages_20260916_01/`. All backend and source review modules remain untouched by this scope.

## Interfaces and implementation

Use `/api/translation/jobs/{job_id}/formatting-reviews`: POST prepare with explicit `page_matched_derivative`; GET exact review; GET page image; POST page/document decisions with generation; POST explicit submit; GET exact revision; POST rebuild with exact revision and stable 32-hex nonce; GET artifact using owned opaque artifact ID and kind. Bodies and returned views follow Agent5's manager/API contract. No client-authored hashes, filesystem paths, manifests or revision IDs.

- `static/formatting_review.js`: scope/job-bound state, frozen server views, semantic decision comparison, exact generation reconciliation and explicit revision/build recovery. Browser storage retains only opaque owner/review/revision/operation identifiers. Server reads recover associations; no newest revision or automatic replacement build.
- `static/formatting_review_ui.js`: safe DOM image and independent read-only source/target selections. Convert browser UTF-16 offsets to codepoints, rejecting a split surrogate pair. Backend validates grapheme/literal boundaries and complete source/target coverage. Explicit fragment region/role/alignment/emphasis, ownership, editable paragraph/table rows/cells/order/widths/measured gutters, local folio, document groups and unchecked completion/acceptance controls. All visible table/source-gap labels use plain language.
- `tests/test_formatting_review_browser_state.py`: eleven existing-style browser ESM/DOM tests, including actual job-owned public service flow with synthetic OCR/SDK boundaries. Cover Unicode, table ownership, invalidation, stale generation, exact revision/build recovery and safe rendering.
- Narrow hooks in translation.js/index.html/style.css: separate completed-job action and panel, eligibility from `job.actions.formatting_review`, namespaced responsive styles, no ordinary action changes. Root's confirmed source UI snapshot was preserved first. Controls have explicit ID/label associations and exact plain accessible labels; table-cell pickers have distinct per-cell labels.

## Interaction and authority

Before prepare, require an explicit saved-page-breaks versus page-matched-derivative choice; explain that saved settings remain unchanged. Start with no fragments, ownership, document groups or completed review assertions. Operators select each source/target span, adopt each independently, and supply a region and style before adding a fragment. Editing decisions clears page/mapping/document completion and final acceptance. Textareas remain read-only and dynamic text uses textContent/value.

Page decisions reference 1-based fragment numbers; removal/reordering must remap every owner and folio reference consistently. Tables have 1–4 explicit column widths totalling100, editable rows and ordered fragment ownership per cell. Gutters are optional explicitly reviewed pixel measurements, never inferred. All tables need explicit gaps when that page uses the gap option. Each fragment must have one owner. Document groups cover all pages contiguously; selecting a folio identifies existing immutable text.

Read-only metadata never authorizes a new build. A fresh explicit build creates one nonce and persists it before POST. An uncertain result retains it; after reload, only an exact server-associated nonce/revision can POST for recovery. No automatic new nonce, latest selection, target edit or acceptance on read. A server restart cannot restore browser review handles through these routes. Current server-owned draft read can restore editable decisions when no submission/build is pending.

An uncertain in-memory submission retains its exact generation/reviewer until an explicit same-request retry proves acceptance through the service. A read-returned existing revision does not prove the original reviewer; reload can display it honestly as an existing result, with no invented acceptance. Failed revision checks or rebuilds remove verified download permission until a new successful server read. Artifact selection joins the exact build nonce, revision and owned artifact descriptor.

Independent review found and corrected three draft interactions: unfinished fragment edits now disable reordering; vertical-spacing labels describe capped versus full measured source gaps while retaining complete text coverage in both choices; and a new server generation with document_decision:null clears local whole-document completion and final acceptance while preserving unsaved choices. Deterministic DOM regressions cover each behavior. Same-generation rerenders do not clear a newly explicit checkbox.

## Tests and acceptance criteria

Authored synthetic tests cover surrogate pairs, combining/RTL strings and exact ranges; independent source/target selection; table/cell numbering and reordering; explicit widths/gutters; blank acceptance and edit invalidation; canonical lost-save recovery; stale page/document saves; scope/job changes and stale responses; exact submitted revision; stale revision/build failures; lost build response, reload association and owned download. The real-flow test uses Agent5's `formatting_api_case` and `completed_reviewed_job`, then actual DOM-generated page/document/accept/build bodies against public routes. It checks original run files, accounting, original DOCX and settings byte-for-byte unchanged during formatting, and only the one earlier synthetic translation SDK response. No accepted review or committed page fixture is injected.

The backend contract is pinned by `browser_formatting_review_harvest_20260916.json` (`c1b87cbe41820ec5b4f313194698fe18cba949e1a76fbb785eda40d57f015744`). Parent corrected and synced the shared synthetic multiline source fixture to `tests/test_browser_source_review.py` SHA `c769a219cae66f749660d437e721fde0f432623c6f03bac0cb9c4a0b5524dcc5`; this UI scope does not edit it. R's current validators/writer remain explicit runtime dependencies; older W copies are not included in this packet.

Tests run only later under parent control with the existing mandated Python/Node runner, outside subprocess-forbidding offline harnesses. No boundary weakening.

## Risks and rollout

The backend remains authoritative for geometry, literal/grapheme boundaries, complete source/target mappings and package bindings. UI shows geometry/rendered layout still unverified, and an exported DOCX needs visual review. Partial/nonbrowser/unsupported protocol or bidi-preservation settings may decline honestly. Page-matched derivative is explicit and does not change saved page_breaks=False. No old W validator is copied over current R.

Parent reviews/harvests the exact seven-file UI packet and runs browser/backend tests. Shared hooks are already authored from their preserved source UI snapshot. Keep unrelated source/backend packets untouched. Rollback is limited to this isolated UI feature.

## Status

Authoring frozen for final independent static review and parent-owned runtime validation. No imports, Node/Python execution, tests, provider/native operations or R writes were performed. Source review modules and backend files were not edited by this scope.
