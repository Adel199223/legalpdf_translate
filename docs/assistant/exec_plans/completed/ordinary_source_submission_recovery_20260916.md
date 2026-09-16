# Exact ordinary source submission recovery

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 48 ordinary source-service tests passed in F3. The integrated durable intent and fresh draft/generation checks retain exact submission recovery and publication ownership.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Scope and baseline

W-only authoring of `ordinary_source_review_service.py`, its existing synthetic test file, and this new plan/addendum. Preserve the original source plan/harvest manifest and the frozen route, browser bridge, Workflow, context and formatting files. Beforeimages and hashes are recorded in `ordinary_source_submission_bases_20260916.json` and `ordinary_source_submission_beforeimages_20260916_01/`. No imports, tests, application/helper execution, provider/native calls or R writes are authorized in this pass.

## Problem and intended behavior

The prior service writes `drafts/<id>/submitted.json` before `revisions/<id>.json`. A local failure between these writes leaves an uneditable draft without a loadable revision. Retrying must complete the same explicit acceptance, with the same revision ID, generation, source/evidence and reviewer. It must never choose a newest revision, regenerate acceptance evidence with a new timestamp, or overwrite an inconsistent record.

## Durable intent and publication

After full source/candidate/context validation and immutable output-object retention, publish one `submit_intent.json` in the exact draft directory. Bind owner, generation and draft bytes, explicit reviewer/acceptance, selected revision ID and complete canonical revision bytes/hash. New submission records and output objects use the existing production `structured_artifacts._publish_file_exclusive`: flushed sibling temporary, non-replacing Windows rename or exclusive POSIX link, cleanup of only that helper's temporary. W and R helper SHA256 is `6e331ff2ed84f1ce646c3b038bde2e33d8408233db7093f1fd54f08488b81e5f`. No `os.replace`, existence-check/overwrite fallback or application helper edits.

All recovery holds the existing run lock. A durable intent freezes editing. Explicit repeated submit validates the exact same generation/reviewer/acceptance and current retained source/evidence, then publishes only missing exact records. Existing records must match their expected bytes. Validation and repeated publication never manufacture a replacement revision ID or timestamp. Failures before durable intent cannot publish either accepted record. Legacy completed records remain loadable; legacy orphan markers are not migrated or guessed.

New internal revision records add `submission_version: "ordinary_source_submission_v1"`, requiring their intent during read and context loading. Deleting an intent cannot silently select legacy behavior. This does not alter the source acceptance envelope, candidate format, context identity shape, settings, reviewer kind or public submit arguments/result. Existing records without that field are verified as complete legacy records; no new intent is written for them. The new intent pins the canonical complete revision and its hash; the revision's candidate/manifest/decision/envelope hashes are independently joined to the exact current draft and operator decisions. Integer generations and explicit booleans are checked without truthy coercion.

Read remains non-publishing: it reports `submission` metadata only after binding the intent or exact legacy completed marker/revision. Pending intent does not imply accepted completion. A complete source submission can be reported idempotently and explicit repeated submit returns the same existing result. The unchanged browser bridge can associate a service-recovered revision through an explicit same-submit retry; automatic read-only association recovery in the bridge remains a separate future hook. No new nonce, API route or job selection is introduced.

For a bound intent or completed legacy record, the existing source read view gains `submission: {status: "pending" | "completed", revision_id, generation, reviewer}`. `submitted` is true only when both exact publications exist and verify; a pending intent returns false and blocks page edits. Reading creates no records. Repeating `submit(draft_id, expected_generation=..., reviewer=..., accept_source=True)` with those exact explicit acceptance inputs completes only missing pinned records or returns the unchanged successful result. A different reviewer/generation, altered source/evidence, conflicting target or missing required intent raises a content-free error. The frozen browser route/schema packet stays unchanged; its earlier source-publication limitation is superseded only when the parent explicitly harvests this new source-service revision.

## Validation to author

Use genuine synthetic local acquisition and explicit operator decisions. Inject failures after intent, after each accepted record, and after completed publication before return. Restart the service and repeat the exact request: one intent/revision, unchanged bytes and exact context identity. Read of pending work creates no records. Test reviewer/generation/source/evidence/intent tamper, bool-as-generation rejection, immutable drafts once intent exists, exact complete legacy reads and orphan rejection. Prove a publication target collision is not overwritten by the trusted helper. Recover a submission into an actual ordinary Workflow with synthetic SDK and real commits/accounting. Existing unrelated tests and frozen artifacts remain unchanged.

## Limits

This is recovery of a pinned local submission, not a multi-file filesystem transaction or a guarantee against hardware/power-loss durability failures. Truncated or inconsistent preexisting records fail closed. The helper's temporary-file cleanup and filesystem hard-link/rename support retain their existing platform assumptions. No repair of old partial generations or objects is added. No paid request, native process, preference mutation or browser owner restore is part of recovery.

## Independent review correction: exact current draft

Agent1 identified that the first frozen recovery (`8a577ce...`, manifest `18925f8e...`) validated publication against entry-call draft bytes without rereading the selected generation. A changed selected file or newly appended generation after intent creation could therefore be published from cached bytes. Preserve that packet as history in `ordinary_source_submission_guard_beforeimages_20260916_01/` and its original manifest; the correction has a separate manifest.

`_fresh_submission_draft` now rereads the actual latest generation through `_draft` and requires exact raw bytes, draft ID and integer generation to match the pinned submission. Fresh identity/size data is supplied to publication validation. Recheck before the durable intent, before each accepted record and immediately before final success, including another freshness check after potentially substantial validation I/O. Deterministic selected-file and newer-generation mutations cover all four boundaries: before intent, after intent, between accepted records and after the final record. A final-record mutation returns failure; it cannot undo an already published record and is not represented as a transaction rollback.

## Status

Initial recovery authoring is preserved in `ordinary_source_submission_harvest_20260916.json`. The reviewed correction is frozen in `ordinary_source_submission_guard_harvest_20260916.json`; Agent1 verified the concrete draft-freshness gap is closed with no further blocker in that correction. The service delta remains bounded to exact submission publication/recovery and required context/read joins; existing acquisition generation writing is unchanged. All eight frozen route packet files remain unchanged at this freeze; the pristine-claim follow-up paused before production/test edits. No imports, tests, application/helper execution, provider/native calls or R writes occurred in this pass. Parent owns harvest and all runtime validation.
