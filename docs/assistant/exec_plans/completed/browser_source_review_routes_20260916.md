# Browser source review routes and ownership

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 44 source API tests passed in F3, including owned upload/run resolution and unchanged ordinary route contracts.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and scope

Expose the frozen public source-review bridge through additive local browser APIs. Preserve existing routes, submitted form values, Gmail/native contracts and normal translation behavior. No UI, restart restore endpoint, source/formatting core changes, provider/native execution, imports or tests in this author-only pass.

## Worktree provenance

- W: `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`.
- R: `C:/Users/FA507/.codex/legalpdf_translate_structured_activation`, `feat/structured-translation-activation`, root-owned frozen integration runtime.
- Narrow exact copies: R `shadow_web/app.py`, `tests/test_shadow_web_api.py`, `tests/test_shadow_web_isolated_services.py`. W lacked the last file. Existing beforeimages and exact hashes are in `browser_source_routes_bases_20260916.json` and `browser_source_routes_beforeimages_20260916_01/`.
- Keep current W `translation_service.py` reviewed-job hooks; preserve its beforeimage and change only optional workspace filtering in `list_jobs`. All frozen source/context/formatting/bridge files, including Agent1 Workflow, remain untouched.

## Interfaces and ownership

Add an optional source-review factory to BrowserAppServices and pass the identical TranslationJobManager instance to it. Missing/injected offline factories disable the feature; construction and bootstrap perform no review acquisition. Install a separate `shadow_web/source_review_api.py` with prepare/read/image/save-page/submit/translate endpoints. No raw-path restore endpoint exists.

New routes require explicit conflict-free mode/workspace values across headers, query and body. Reject invalid or missing scope before legacy normalization. Bound JSON bytes before parsing, reject duplicate/unknown fields, enforce exact typed decision keys/enums/finite boxes and integer generation/page values. The client never supplies evidence files, hashes, reviewer-kind authority or source envelopes. Source text stays in private normalized UI views; diagnostics contain fixed codes only. Blocking operations run through a bounded threadpool seam.

Prepare first resolves an exact direct regular file in this mode/workspace's manual upload folder. It then delegates the existing public form parser to preserve user settings and custom output directories. This release declines Gmail form context for review preparation. A run/config claim is owned by the API instance and serialized with the actual run lock. An unclaimed nonempty saved run is declined until a trusted persisted browser owner record exists; no source path or checkpoint is treated as proof of restart ownership. A claim cannot be reassigned to another mode/workspace/source/config.

The existing browser-PDF bundle endpoint preserves its multipart/request/response shape. Before reading page uploads or writing a bundle it requires either the owned manual upload, or exact equality with the backend `current_attachment_file` resolved for the supplied attachment ID and current target. Client Gmail fields grant no authority.

All existing translation job reads/actions/artifacts, supplied save-row/Gmail-confirm job IDs, and Arabic-review job helpers require immutable snapshot mode/workspace equality. Foreign and unknown jobs use the same not-found response. Bootstrap/history pass an optional workspace filter into TranslationJobManager before sorting/limiting. No production snapshot is repaired using the requester's scope.

## File-by-file implementation

1. New API module: strict scope/JSON/typed-decision adapter, disabled source service, owned source check, owned run claims and additive route registration.
2. `shadow_web/app.py`: injection/context/registration, shared owned-job access, workspace list filter, PDF bundle ownership precheck.
3. `translation_service.py`: optional workspace list filter only.
4. New API tests using actual public source service and real Workflow with synthetic local OCR/SDK, plus ownership/scope/size/decision/recovery matrices.
5. Existing API fixtures: explicit legitimate job and attachment ownership for same-owner requests. Isolated-service test: new disabled routes and factory identity without live probes.

## Tests and acceptance criteria

Root will execute focused API/service regressions and required broader checks after harvest. Tests must prove route→bridge→real source actions→context→real commits, same-operation nonce recovery without repeat dispatch, saved settings and lazy transport retention, workspace filtering before limit, foreign job denial before actions/artifact resolution, and owned manual/Gmail bundle validation before writes. Source review mutations and offline bootstrap must not create provider clients or invoke native probes.

## Rollout and limitations

Only additive source-review endpoints use strict scope parsing; legacy defaults remain unchanged. Existing owned-job restrictions intentionally reject previously unscoped foreign snapshots. This is workspace isolation, not local-user authentication. UI and persisted restart ownership remain separate work. No automatic source acceptance, source rewrite, profile switch, provider fallback, hidden latest revision or paid retry is added. Source/formatting services keep their existing limitations and genuine operator provenance.

Preparation validates the raw existing local output directory and rejects symlink/reparse ancestors before invoking the unchanged normal form parser. It also rejects an existing `.write_test.tmp` object. The parser still briefly writes/deletes its ordinary writable-folder probe; source preparation is not a read-only request. Preparation then creates the run directory and retained stable `.run_workspace.lock` before policy declines or owner rejection; the lockfile is not an activity marker. Claims are held in this API instance, including after a decline, and bind the exact original config. The first release does not permit silently changing that config under a claimed run. A new server cannot reopen preexisting source drafts through a raw path; a trusted persisted browser owner mechanism remains future work. These checks assume trusted local filesystem state between path validation and opening; they are not a sandbox against a separate local process replacing directory objects concurrently.

Completed submit response loss can be recovered by reading the same in-memory review handle. This does not claim filesystem-transaction or crash recovery: the frozen source service currently writes its submitted marker before its revision record, so a local publication failure between those writes can leave a submitted draft without a completed revision. That independent core persistence gap must remain an explicit failure until addressed in a bounded follow-up. The route cannot invent a revision, retry an uncertain paid operation or infer the newest record.

### Exact additive route and body contract

All routes below require an explicit mode (`live` or `shadow`) and nonempty existing normalized workspace ID. Send `X-LegalPDF-Runtime-Mode` and `X-LegalPDF-Workspace-Id` headers. Query `mode`, `workspace`/`workspace_id`, and optional POST top-level `mode`/`workspace_id` are also accepted, but every supplied value must agree. Workspace IDs are at most 128 characters, preserved exactly by existing normalization, and cannot start/end with `.`, `_` or `-`. Existing routes retain their older scope parsing. The source APIs do not create browser workspace IDs.

Base path: `/api/translation/source-reviews`. All JSON POST bodies are at most 2 MiB UTF-8, must be an object, and reject duplicate and unknown top-level keys and nonfinite constants. Optional top-level scope keys are the only additions to the exact bodies listed here. IDs for reviews, revisions and operation nonces are 32 lowercase hexadecimal characters.

| Method and suffix | Exact JSON body | Success payload |
| --- | --- | --- |
| POST `/prepare` | `{ "form_values": { ...existing translation form fields... } }` | `normalized_payload.source_review` draft or honest decline |
| GET `/{review_id}` | No body | `normalized_payload.source_review` draft, submitted view or exact operation associations |
| GET `/{review_id}/pages/{page_number}/image` | No body | PNG bytes; page number 1–5000 |
| POST `/{review_id}/pages/{page_number}` | `{ "expected_generation": integer, "decision": { ...below... } }` | Updated `normalized_payload.source_review` generation |
| POST `/{review_id}/submit` | `{ "expected_generation": integer, "reviewer": string, "accept_source": true }` | Exact submitted `revision_id` in `normalized_payload.source_review` |
| POST `/{review_id}/translate` | `{ "revision_id": string, "operation_nonce": string }` | Existing unchanged job snapshot in `normalized_payload.job` |

`prepare.form_values` delegates the existing `build_translation_config` form parser and saved settings. `source_path` must equal the returned path of an owned manual `/api/translation/upload-source` upload in the same mode/workspace; `output_dir` remains the user's normal selected output folder. The source file must have its complete browser-rendered bundle acquired through the existing `/api/browser-pdf/bundle` multipart endpoint. The browser submits neither evidence paths nor hashes. Truthy `gmail_batch_context` is declined by this first review release. No OCR, image, page-break, target-language or retained-intermediate preference is silently changed. Missing local baseline, disabled/API-only OCR, incomplete page selection or missing retained evidence remain honest service declines.

Draft views include `review_id`, `generation`, `reviewer_kind: "operator_review"`, `notice_codes`, and `pages`. Each page has `page_number`, `image_size_px: [width,height]`, `baseline_text`, `baseline_blocks`, genuine `word_evidence`, `selected_pass`, `decision` (initially null), and `image_available`. Fetch image bytes by the owned image route. Source text and decisions are private UI content: use safe text insertion, never diagnostic logs or HTML interpolation. Baseline block IDs and word evidence come from the server; no review decision is preaccepted. Returned saved decisions additionally have read-only `reviewer_kind`; clients must send only the exact editable decision keys below.

`decision` exact keys:

```json
{
  "actions": [],
  "reading_order": [],
  "full_page_review_completed": false,
  "reading_order_reviewed": false,
  "boundary_decision": "unresolved",
  "boundary_rationale": "Operator-entered explanation",
  "findings": [],
  "reviewer": "Operator-entered name or label"
}
```

This is a schema illustration, not a valid completed review or preset approval. Actions/findings each allow at most 5000 objects. Each action has exactly `id`, `kind`, `baseline_block_ids`, `after_text`, `region_px`, `rationale`. Action IDs and referenced IDs use `[A-Za-z0-9][A-Za-z0-9_-]{0,99}`. `kind` is `retain`, `replace`, `omit_nontext` or `transcribe`. `baseline_block_ids` is an array of server baseline block IDs; `after_text` is at most 100000 Unicode codepoints; `region_px` is `[left,top,right,bottom]`, finite integer/float coordinates within the displayed image with positive width/height. No guessed region is generated by the API. `rationale` must contain nonwhitespace text and be at most 1000 codepoints. Source-service validation requires exact baseline coverage, matching retained/omitted text rules, evidence references and nonoverlapping new transcriptions; the API does not bypass those checks.

`reading_order` is an explicit ordered array of action IDs. Completion fields are JSON booleans, never numeric truthy values. `boundary_decision` is `start`, `continuation` or `unresolved`; `boundary_rationale` and `reviewer` are nonblank strings of at most 1000 codepoints. Each finding has exactly `id`, `category`, `status`, `action_ids`, `rationale`. Categories are `identifier`, `citation`, `omission`, `invention`, `reading_order`, `boundary`, `other`; status is `resolved` or `unresolved`. The server derives and verifies all source hashes, evidence bindings, immutable revisions and reviewer provenance. The client cannot submit reviewer-kind authority.

Save each page with the current positive integer generation (booleans rejected); use the returned generation for the next mutation. Submit requires explicit final `accept_source: true` and all page/source/boundary requirements satisfied. Saved `page_breaks=false` remains supported for source review and ordinary reviewed translation; the separate visual formatting profile may honestly decline it.

After a successful submit whose response was lost, GET the same handle. A completed submitted view reports `submitted:true` and `revision_ids`; there is no automatic selected revision. Once translation is requested, GET also returns `translation_operations` (`operation_nonce`, `revision_id`, `status`, `job_id`) and `translation_jobs` (`job_id`, `revision_id`) without re-reading locked source artifacts. This association-only recovery is available while the job owns the run lock; it does not certify current source content. The translation worker independently reloads/verifies the exact context before auth, each send/retry and publication.

Generate one new nonce for one explicit Translate action and retain it across request retries. An exact known nonce returns its exact original job; a different revision for that nonce fails. An uncertain operation reports an error and is never redispatched. Do not generate a fresh nonce to automatically retry an uncertain action. Poll and use existing owned job routes for status/resume/rebuild/artifacts, with the same mode/workspace headers. Existing resume/rebuild receive the private retained context loader; no source selection marker or changed existing payload is required.

JSON responses retain the four keys `status`, `normalized_payload`, `diagnostics`, `capability_flags`. Success is HTTP 200 with `status:"ok"`; a decline is a successful review operation with inner `status:"declined"` and `notice_codes`. Errors use fixed code-only `diagnostics.error`, empty normalized payload, usually HTTP 422, HTTP 413 for oversized input, or HTTP 409 for injected disabled service. `capability_flags.source_review.status` is `available` or `disabled`; it describes route availability, not OCR/provider readiness. All new responses use `Cache-Control:no-store` and `X-Content-Type-Options:nosniff`. No global capability/credential/native probes or private review text enter diagnostics. There is no restore endpoint in this patch.

## Status

Authoring complete and frozen for parent review/harvest. Exact file and unchanged-dependency pins are in `browser_source_routes_harvest_20260916.json`; narrow beforeimages are in the bases manifest. Independent review identified the raw-output normalization gap; the authored correction and link/probe tests are included, with final independent receipt and all runtime validation still pending. Root owns tests and integration. No imports, application/helper execution, tests, provider/native calls or R writes occurred in this pass.
