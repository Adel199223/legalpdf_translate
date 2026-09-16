# Ordinary reviewed-source context

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 25 ordinary reviewed-source context tests passed in F3, including actual identity propagation and guarded dispatch behavior.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and scope

Author a public immutable reviewed-source context and ordinary Workflow/structured-translation integration. Consume genuine separately reviewed image-source evidence, preserve reviewer identity, bind exact source revision into checkpoint settings and protocol identity, and retain ordinary accounting. No source acquisition, UI/routes, global protocol/default changes, private acceptance authority changes, provider/native operations or execution in this task.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`.
- Worktree HEAD/base SHA: `4780a2e16c32adf7af7479656f0b5fafdff83224`.
- Current integration baseline: read-only `legalpdf_translate_structured_activation`, branch `feat/structured-translation-activation`; root owns integration and canonical activation.
- Noncanonical authoring only. Exact prior W files retained under `ordinary_source_context_beforeimages_20260915_01`; only workflow/new_translation_blocks/checkpoint synced from R. Hashes recorded in `ordinary_source_context_bases.json`.

## Public interface and identity

`OrdinaryReviewedSourceContext` accepts an explicit revision ID, explicit reviewer kind (`operator_review` or `ai_test_review`), source-review envelope bytes, immutable `ReviewedSourceEvidence`, separate decision evidence bytes and a caller source guard. The guard is a recheck notification/failure hook, never proof of acceptance: the context independently validates evidence bytes, physical page identities and all source decisions. Every page review and envelope must match the caller's explicit reviewer kind.

`TranslationWorkflow(reviewed_source_context=context)` explicitly selects `legal_blocks_v2` for that workflow, rejects an explicit conflicting protocol and any acceptance continuation, and never mutates RunConfig/global preferences. The revision's content identity is added only for this context to checkpoint settings and structured extraction identity. Resume requires exactly the same context; omitting it, changing revision ID/content/kind, or changing source bytes fails before accounting/authentication. Full browser-image page inventory and retained intermediates are initially required. No OCR/extraction is performed in reviewed dispatch. Source/translation provenance remains uncertain and not legally certified.

The future public acquisition service owns revision storage, complete immutable source evidence and safe file guards. It creates this context from an explicitly selected accepted revision and reconstructs that exact selection for resume. It must not use an acceptance campaign/authorizer, latest-revision inference or regenerated OCR evidence. Formatting rebuild continues to validate retained commits independently.

## Implementation steps

1. Add pure context module with bounded immutable bytes and deterministic identity; preserve all review evidence.
2. Add optional checkpoint settings identity parameters without changing default settings/schema behavior.
3. Wire Workflow selection, early context/checkpoint validation and ordinary accounting boundary; keep existing acceptance path intact.
4. Wire NewTranslationBlocks reviewed source selection, repeated verification and source/provenance metadata through the public context.
5. Author synthetic context/ordinary-run/resume/tamper/role tests. Root executes after Arabic runtime freeze.

## Acceptance and tests

- Both explicit reviewer kinds retain distinct provenance; mismatched inner/outer kinds fail.
- Byte/path/source-guard failure, incomplete source selection and stale/missing resume context fail before accounting/auth/dispatch.
- A synthetic ordinary run produces real structured commits without acceptance continuation, private journals or authorization; ordinary accounting remains active.
- Context mutation and changed returned source dictionaries cannot change the frozen binding.
- No-context and strict private acceptance behavior remains unchanged; existing tests remain required.

## Rollout, risks and status

Opt-in only; existing callers remain unchanged. Repeated complete source verification favors integrity over speed. Caller guards may close over mutable storage, so immutable evidence and physical-source verification remain independent requirements. Full browser source inventory is intentionally narrower than all ordinary input formats. Root reviews/harvests changes and runs targeted offline tests; no imports/tests are executed in W. Status: authoring and static diff review complete; runtime validation pending root's post-freeze review. `git diff --check` passed for the tracked implementation files. No AST compilation, application imports or test execution was performed.

## Next source service: design only

### Independent review follow-up, 2026-09-16

Prior frozen files are preserved in `ordinary_source_context_transport_beforeimages_20260916_01`. The ordinary-only transport cancellation/deadline callback now independently rechecks source evidence during jitter/backoff and after reservation, before every SDK send. Private acceptance keeps its existing callback. Content-free context failures suppress the original exception chain. New authored tests use the real OpenAIResponsesClient with a synthetic SDK and actual ordinary DispatchAccounting to check no dispatch during source mutation at jitter, reservation or transport retry, and settled not-dispatched reservations. No execution/imports performed; root owns validation.

The formatting CLI now reconstructs the explicitly known ordinary source identity, validates its exact schema/source binding against real saved commits and reviewer provenance, and rejects unknown identity/settings fields in this opt-in branch. Existing no-context reconstruction remains unchanged. Its exact R base is `2e52b383e0c5ae2f365772a9475135a7a4880802e14cdec58a2ed70656624042`; beforeimage is retained beside the transport beforeimages. Context-produced and acquisition-service-produced runs have authored CLI draft regressions, retaining the honest `page_breaks=False` formatting decline.

Smallest callable interface for a future ordinary acquisition service:

```text
prepare_source_review(config, *, reviewer_kind, review_owner) -> DraftOrDecline
read_source_review(draft_id) -> SourceReviewView
save_source_review_page(draft_id, *, expected_generation, page_number,
                       actions, reading_order, boundary, findings) -> Draft
submit_source_review(draft_id, *, expected_generation, reviewer) -> Revision
load_reviewed_source_context(revision_id) -> OrdinaryReviewedSourceContext
```

`review_owner` is a server-resolved ordinary run/workspace, never an arbitrary browser path. Each operation takes its shared run lock, validates saved source/config identity and uses immutable artifact files plus a commit-last draft/revision marker. No lock is held while the person reviews a page. A draft generation detects stale tabs; a submitted revision is immutable. No latest-revision selection is inferred.

Preparation consumes the existing browser PDF bundle and the exact saved OCR policy. Retain real selected local-pass TXT/TSV/raw structure and image bytes before the existing OCR temporary directory closes, through a narrow optional evidence-retention result/sink. Preserve the actual recognition output, confidence, engine/pass identity and selected-text binding. Never regenerate TSV from word metadata. Initial v1 declines OCR-off, API-only/missing local baseline or unavailable local evidence rather than changing OCR settings, inventing geometry or buying an unsupported fallback. The service does not change `page_breaks=False`; source review/translation remains possible with it, and formatting can report its current separate limitation.

The view provides original image assets and baseline text with opaque stable IDs. Page actions are typed UI choices: retain/replace/omit/transcribe, existing baseline IDs, operator text, confirmed/drawn source region and rationale. Before-text, all hashes, inventory, action ownership and page-plan JSON are derived internally from the frozen draft. Full-page, order and boundary review start incomplete. Submission requires explicit completed decisions for every page, builds the unaccepted candidate record, validates it using the existing adapter, then creates the separately recorded source decision envelope. The caller's explicit reviewer kind must match every page; no AI-to-operator relabelling.

The returned revision retains source envelope, candidate, manifest, original evidence and separate decision bytes. `load_reviewed_source_context` pins those exact bytes and installs a read-only physical-file recheck closure; the context still independently verifies them. An explicitly selected revision starts ordinary structured translation. The future visual region service consumes the resulting committed parents and existing formatting APIs; source actions never guess target cuts or certify translation/layout fidelity.

This is an interface sketch only. The raw OCR retention hook, candidate builder exposure, source service persistence and UI are not implemented in this bounded change.
