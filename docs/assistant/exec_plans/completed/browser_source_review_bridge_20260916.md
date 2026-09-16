# Browser source review service bridge

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 19 bridge tests passed in F3. Reviewed translation preserves scope/configuration and recovers only the exact associated operation.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Scope and provenance

Author only in W `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, base HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`. Frozen source/context/OCR/CLI files remain untouched. Only current R `translation_service.py` is synced, with old W beforeimage and exact R pin in `browser_source_bridge_bases.json`. No app.py, static, route, submitted-value or existing payload changes. No imports, execution, tests, provider/native activity or R edits.

## Interface and ownership

`BrowserSourceReviewManager` accepts an existing TranslationJobManager. A trusted backend resolves the existing `_active_target` mode/workspace and settings path and builds the saved RunConfig through a public wrapper over the existing form parser. `prepare(runtime_mode, workspace_id, config, settings_path)` creates an opaque review ID and owns the copied config, settings path and source service. Each read/image/save/submit/start/resume operation requires that ID plus the exact nonempty mode/workspace. Browser decisions are typed source actions only; no evidence/config paths or hash bindings are submitted.

`restore(..., config, settings_path, revision_id)` explicitly registers an existing immutable revision using trusted backend-resolved config. It never infers latest or changes source/checkpoints. Registry handles are in memory, like current translation jobs; persisted source revisions remain usable through explicit restore after restart.

The dedicated `TranslationJobManager.start_reviewed_translate` retains the exact reviewed context and loader privately and forwards them to a Workflow before lazy authentication/client creation. Background start/resume reloads and validates the exact selected revision against the original context identity. Existing start/analyze/rebuild payloads/defaults remain unchanged. Existing resume carries its private source context and rejects a different settings owner. Additive routes and existing route workspace authorization remain root's integration responsibility; the bridge performs strict owner checks for all its operations.

## Steps and tests

1. Add public normal form-parser wrapper and minimal private job context/loader fields and explicit reviewed-start hook.
2. Add browser_source_review.py registry, safe JSON views and separate owned image accessor, exact restore/selection/resume.
3. Author synthetic ownership/policy/decision/start/resume/context-reload tests using service and Workflow/SDK where feasible, with no live execution.

## Constraints

Saved OCR policy, page breaks, source selection and normal defaults stay authoritative. Missing local source evidence, OCR-off/API-only and partial/nonbrowser profiles retain the source service's explicit decline codes. Source review does not call providers. Source views contain private text for safe UI text insertion, never logs. Frozen context's per-send guard and shared run locks remain authoritative during translation. No preaccepted actions, hidden selection, private acceptance helpers, credential serialization, checkpoint edits or manufactured commits.

## Integration handoff

`prepare`, `restore`, `read`, `image`, `save_page`, `submit`, `start_translate` and `resume` are the bridge methods. Draft/submitted responses include `review_id`; internal source-service `draft_id` and image bytes are removed. `image(...)` returns owned PNG bytes for a separate future asset endpoint. Existing translation job snapshots are returned unchanged from start/resume and contain no private context/loader. Typed page decisions use the frozen source-service dataclasses.

Root should construct one bridge with the same `TranslationJobManager` used by `ShadowWebContext`, injectable via a dedicated BrowserAppServices factory. Future routes resolve `_active_target` and pass its exact mode/workspace/settings. Initial `prepare` and `restore` accept trusted backend config only; routing must resolve existing uploaded-source/run ownership before calling them. The persistent source service binds run/source/language, not a browser workspace, so this bridge does not claim to authenticate arbitrary client-supplied config. Subsequent opaque handles are strictly owner-checked. Existing job routes also need target ownership checks at integration; their current contracts have no manager-level caller workspace argument.

Restored handles select only the operational `resume=True` flag; no source/content preferences change. Manager-owned reviewed resume/rebuild validates the original settings path and reloads the same revision before background execution. The Workflow receives the context before constructing its own lazy client under source verification and the run lock. Ordinary nonreviewed client creation and existing request/response shapes remain unchanged.

`tests/test_browser_source_review.py` covers saved form defaults, JSON-safe views and owned image access, cross-mode/workspace rejection, explicit submission/revision requirements, policy declines, real source-service -> managed background job -> Workflow/SDK failure and resume with actual commits, tampering after queueing before client construction, explicit restore without OCR reacquisition, and context retention through unchanged resume/rebuild methods. No tests/imports/execution were performed. Static R-to-W diff reviewed; frozen prior source manifest hashes rechecked unchanged. Status: authoring complete, independent static review and root runtime validation pending.

## Saved transport policy correction

The independent bridge review found that deferring construction with `client=None` lost the browser's saved retry/backoff options. Root authorized reopening only W Workflow's lazy construction and these bridge tests/docs. Beforeimages and exact prior hashes are retained in `browser_source_bridge_transport_beforeimages_20260916_01`; the earlier source/context review remains historical evidence.

The ordinary reviewed-context branch now passes the already loaded GUI retry/backoff options at both lazy default-client construction sites, using the same conversions/defaults as the existing browser constructor. No-context and private acceptance paths receive no additional options. Credential resolution remains after source verification and run locking. No new factory, public payload or route contract is introduced.

New regressions leave the real Workflow's `client=None` path intact and replace only its SDK boundary. They assert nondefault saved retry/backoff policy, an actual structured commit, and no client/SDK construction after source mutation either while queued or after initial source validation before authentication. The correction author performed only stdlib syntax/diff/hash inspection; root still owns runtime tests and independent validation of the correction.
