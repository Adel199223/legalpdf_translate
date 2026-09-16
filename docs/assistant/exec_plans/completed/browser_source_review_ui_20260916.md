# Explicit ordinary source review in the browser

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 10 source browser-state tests passed in F3. Actual combined synthetic browser smoke 9d2109be completed source acceptance, translation and exact same-job/reload recovery with one synthetic SDK response and saved page-break False.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and non-goals

Let a user review a staged manual PDF using its actual full-page image, retained local OCR text and word evidence, save explicit page decisions, accept the complete source and start one exact reviewed translation. Keep ordinary Start Translate, saved preferences, existing routes/payloads and Gmail behavior unchanged. No formatting review or server-restart restore in this scope.

## Scope and provenance

Author only in `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`. Parent integrates into `feat/structured-translation-activation` in R. This is a noncanonical authoring tree, not a running UI handoff. Preserve W beforeimages and copy only exact current R `translation.js`, `index.html` and `style.css`; `browser_source_ui_bases_20260916.json` records all pins. Frozen backend/source/bridge/workflow/formatting packets remain untouched.

## Interfaces and implementation

1. New `static/source_review.js`: scope-bound controller, exact draft generations and explicit source submission, code-only feedback, stable paid-operation nonce, bounded session recovery metadata. Use the existing six dedicated source-review endpoints without new payload keys or routes.
2. New `static/source_review_ui.js`: safe DOM page editor with image, baseline text/blocks and word-box evidence; explicit Retain/Replace/Omit/Transcribe actions, pixel region selection, reading order, findings, reviewer and unchecked completion/acceptance controls. The browser generates opaque action/finding IDs; it never asks the operator to type hashes, paths or JSON.
3. Narrow `translation.js` hooks: reuse manual-source readiness, `ensureUploadedSource`, unchanged setup collector and normal job rendering/polling. A separate review action leaves ordinary Start Translate unchanged. Source/setup/scope changes invalidate selection for new reviewed starts.
4. `index.html` adds one review button and panel anchor; `style.css` adds namespaced responsive/RTL-safe review styles. Existing route IDs and submitted select values are preserved.
5. New `tests/test_source_review_browser_state.py`: existing Node ESM/DOM probe style, synthetic transport boundaries and a controller-generated decision/selection chain through actual public acquisition/routes/Workflow with synthetic local OCR and SDK.

## State and recovery

Each request captures immutable mode/workspace and the current local review session. At most one mutation is active. Stale responses never replace a newer source/scope. Preparing captures exact current setup in memory; server normalization/saved-generation guards remain authoritative. Source/setup changes block new reviewed starts and do not rewrite preferences or the accepted context.

The page editor offers fit/full-resolution viewing, selected genuine word-box overlays and either drawn or explicitly adopted keyboard rectangles. Unfinished action/finding input blocks page save. Any edit clears both visible completion checks. Other dirty pages remain dirty after one page saves. When a read proves a saved generation differs from an uncertain page-save request, an explicit local-discard control loads the current saved page without a mutation or automatic overwrite.

The operator must save every page with full-page and reading-order review complete, resolve findings and choose page boundaries. Editing a saved decision clears completion checks and whole-source acceptance. Source submission is a separate explicit unchecked acceptance. No action, region adoption, boundary decision, completion or acceptance is preapproved.

Generate a cryptographic 32-lowercase-hex operation nonce once on explicit reviewed start and persist the opaque scope/review/revision/nonce association before dispatch. A lost response retains that nonce. Read association metadata and explicitly retry only the exact operation; never select latest or generate a replacement nonce. Persist no source text, evidence, reviewer, filesystem paths or setup values in browser storage.

Restored identifiers are unverified UI metadata until an owned backend read joins the exact selected revision to the returned revision list. Recovery cannot dispatch before that read. Retained source views are deeply frozen and shared by controller snapshots to avoid cloning every page's evidence on every input. The renderer copies only editable decisions and uses safe DOM text/value insertion.

After a full browser reload, show recovery-only mode. Existing exact pending operations/jobs can be recovered while the same backend process retains the handle. A new paid start stays disabled because the existing view does not expose the original trusted setup summary. A backend restart cannot restore these handles: say so plainly; do not promise saved drafts survive a server restart or invent a raw-path restore route. Source submission recovery uses the exact original generation/reviewer or the service's exact pending/completed submission metadata, requiring an explicit same-submit action. Read never accepts source.

## Tests and acceptance criteria

Author tests for blank decisions, no provider calls during review, safe dynamic text/textarea insertion, RTL and astral text preservation, pixel scaling/explicit region adoption, block coverage/order, dirty-check reset, generation conflicts, exact revision and nonce reuse across lost responses/reload, scope/source/setup drift, conservative disabled/unsupported notices and original Start Translate separation. Include real public service actions to ordinary context/Workflow commits, without fabricated accepted reviews or commits. Parent owns all execution and runtime review; no imports, tests, Node/Python/helper execution, provider/native calls or R writes in this pass.

## Risks, defaults and follow-ups

The actual backend remains the authority for source/geometry/ownership validity; client hints do not certify OCR geometry. Saved OCR/retention policy is never changed automatically. Unsupported partial/non-browser/API-only/disabled-local cases display an honest decline. `page_breaks=False` remains supported for source review/translation.

Visual formatting remains separate: a later explicit page-matched derivative choice must preserve the original `page_breaks=False` config, and genuine reviewed gutters need optional `column_gaps_px` for the new region-layout version. Do not copy old W validators over R or infer gutter acceptance.

## Status

Authored and frozen for independent review and parent-owned execution. Seven test functions cover controller recovery and drift, dirty-page accounting and storage failure, genuine DOM operator actions through the public source service to real Workflow commits with synthetic OCR/SDK, Unicode/RTL text safety and coordinate scaling, explicit page-conflict recovery, and preservation of the ordinary translation request. The workflow case checks the actual owned image endpoint, exact source revision, ordinary accounting begin/finish events and unchanged saved page-break preference. No acceptance envelope or commit fixture is injected into that case.

Only the approved six application/test files and this plan are in the UI harvest packet; baseline metadata is included separately. No backend files changed. No Node/Python imports, tests, native/provider actions or R mutations were executed. Parent must execute browser ESM probes outside the generic offline harness that prohibits subprocesses; the tests do not alter that harness or relax its restrictions.

Concurrency audit: all eight source/route/Workflow bystanders match the prior frozen packet. Parent independently advanced the formatting service to `5300c75be3090cc72d7d55c2bcf1fccfd7a7f7b7d503bfef8ab6975cad234e70` during this authoring pass. This UI neither changes nor imports that service; its separate packet remains parent-owned.
