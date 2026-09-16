# Owned browser formatting review

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 26 formatting-manager and 25 formatting-API tests passed in F3. Rebuild operations bind exact revision/nonces and owned artifact records, including uncertain outcomes.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and non-goals

Expose the existing explicit ordinary formatting service through a completed,
owned reviewed-source job. Preserve saved translation settings and original
outputs. No paid translation, native export, source acquisition, target edits,
automatic acceptance, or fallback assembly belongs to this change.

## Scope

Two new backend modules, a narrow trusted job accessor/artifact registry and app
injection, two focused test modules. Browser UI is authored independently and is
not included in this backend patch. Existing source API tests are excluded.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`
- Branch: `codex/reviewed-regions`
- HEAD/base snapshot: `4780a2e16c32adf7af7479656f0b5fafdff83224`
- Base/target branch: `main`; integration is root-owned in the activation tree.
- Noncanonical author-only worktree; no server or helper is launched here.
- Beforeimages: `browser_formatting_beforeimages_20260916_01/manifest.json`.

## Interfaces and implementation

1. TranslationJobManager returns a backend-only deep-copied config and freshly
   verified exact source context for an explicitly owned completed job. Register
   reviewed artifacts separately from the original selected output.
2. BrowserFormattingReviewManager retains immutable draft ownership/choice and
   exact revision associations in the owned run. Use the existing run OS lock.
   Rebuild intent consumes its nonce before publication. Exact successful retries
   return retained artifacts; an uncertain result never replays automatically.
3. Add `/api/translation/jobs/{job_id}/formatting-reviews` routes for explicit
   prepare/read/image/page/document/submit/revision/rebuild/artifact operations.
   Strict bounded JSON becomes typed decisions, never evidence or caller paths.
4. Source/target spans use Unicode codepoints. Optional column gaps pass the
   current v2 source-support validator. An explicit strict boolean chooses a
   page-matched derivative; original config/state/accounting remain unchanged.

## Tests and acceptance

Author genuine reviewed source -> completed job -> formatting service -> browser
route flows. Cover owner/config/context changes, strict choices, stale generation,
exact revisions, gutters, nonce concurrency/lost response, artifact tampering,
restart with retained trusted job, and no further client/native construction.
Root executes tests. ASGI/TestClient cases use standard synthetic pytest, not an
exception to the isolated runner's socket prohibition.

## Rollout and fallback

Additive routes and injectable disabled manager preserve existing offline service
construction and existing translation/source endpoints. No fallback on declined
or failed formatting. Root reviews a scoped frozen manifest before integration.

## Risks and defaults

Source/target text is private UI content, never diagnostics. Artifact downloads
return verified bytes with fixed kinds and no caller paths. Drafts/operations are
persistent, but a full app restart may lack the in-process trusted job; that is
an explicit unavailable result, not automatic reconstruction or latest selection.

## Browser contract

All routes require an explicit consistent runtime mode/workspace through the
existing source-route headers, query parameters or body fields. Prefix:
`/api/translation/jobs/{job_id}/formatting-reviews`.

| Method and suffix | Body / result |
| --- | --- |
| POST `/prepare` | Strict `page_matched_derivative` boolean; returns a draft or explicit decline |
| GET `/{review_id}` | Exact draft/submitted state, rebuild operations and artifact descriptors |
| GET `/{review_id}/pages/{page_number}/image` | Owned source PNG bytes |
| POST `/{review_id}/pages/{page_number}` | `expected_generation`, typed page `decision` |
| POST `/{review_id}/document` | `expected_generation`, typed document `decision` |
| POST `/{review_id}/submit` | `expected_generation`, `reviewer`, `accept_formatting: true` |
| GET `/{review_id}/revisions/{revision_id}` | Inspect only this draft's exact submitted revision |
| POST `/{review_id}/rebuild` | Exact `revision_id`, 32-lowercase-hex `operation_nonce` |
| GET `/{review_id}/artifacts/{artifact_id}/{artifact_kind}` | Verified bytes for `output_docx`, `source_map`, or `assembly_receipt` |

JSON responses use `normalized_payload.formatting_review` with the existing
status/diagnostics/capability envelope. Views include `review_id`, `job_id`, the
immutable derivative choice and the ordinary service's honest review notices.
They exclude backend paths, config/context objects, raw evidence and image bytes.
Each page exposes image dimensions and source provenance/uncertainty, plus
`parents[{parent_number,source_text,target_text}]` for explicit independent Unicode
codepoint selections. Images are fetched by exact owned page number.

Page decisions contain `fragments`, `header`, `body`, `footer`, nullable
`folio_fragment_number`, two explicit review booleans, reviewer and review note.
Fragments contain a 1-based parent number, independent 0-based half-open source
and target ranges, pixel box, role, alignment, bold/italic booleans and note.
Roles are header/body/signature/footer/folio; alignment is left/right/center/justify.
Body entries are `{fragment_number}` or `{column_widths,rows,column_gaps_px?}`.
Rows contain cells, each a list of 1-based fragment numbers. The optional gap
array must be omitted for v1; explicit arrays select the current v2 validation.
No `null` gap or text replacement field is accepted. Tables retain the service's
four-column/100-row bounds. Document decisions contain explicit start/end-page
groups, all-pages-reviewed, pipe-cell and source-gap choices, reviewer and note.

Rebuild responses include an exact `rebuild_operations` row and matching
`artifacts` descriptor. A pending nonce cannot be bypassed with a new nonce.
Completed requests can restore their job artifact registration from the durable
exact record without rebuilding. Downloads revalidate the original job, accepted
revision, receipt and complete bytes, then return those bytes rather than a path
that could change before FileResponse opens it. The original output selection is
untouched; descriptors live in `job.artifacts.reviewed_formatting`.

The UI must not infer the pending submit request's reviewer from a read-returned
revision. While retaining a pending request, repeat that explicit exact submit
request to prove its association; after reload show an existing submitted result
without inventing acceptance. The ordinary service owns this durable submission
protocol; the browser manager does not add a second acceptance authority.

## Durable records and limits

The owned run contains `browser_formatting_reviews/{review_id}/owner.json` and
`operations/{nonce}/intent.json` plus an exclusive verified `result.json` when
publication completes. Review IDs are the service's opaque draft IDs. Canonical
JSON joins distinguish booleans from integers. All operations use the run OS lock;
cross-thread/process contention fails promptly. There are at most 256 review
folders per run and 256 rebuild operations per review; bounded inventories reject
unexpected entries. JSON records are limited to 8 MiB and request bodies to 2 MiB.
Artifact reads follow current application bounds: DOCX 32 MiB, map 128 MiB,
assembly receipt 8 MiB. Readers reject reparse points, symlinks, hardlinks and
changing file identities. These limits confer no provider or native authority.

Prepare has no paid or DOCX effect. A lost prepare response may leave an orphaned
draft; it is never guessed or selected automatically. A build lacking its complete
manager result remains pending even when partial files exist. No route deletes,
resets or retries that operation. Complete results remain recoverable after a
lost response only with fresh exact ownership and artifact verification.

## Status

Authoring complete; 25 manager cases and 25 API/typed-schema cases are authored.
Only standard-library AST, byte comparison and hash inspection were performed.
No application imports, tests, provider calls or native operations were run by
the author. Runtime validation and integration remain root-owned. Existing source
fixture `test_browser_source_review.py` and source API tests are dependencies only
and excluded from this harvest. Current R validators, including gutter support,
are authoritative; stale W validator copies are not harvested with this patch.
