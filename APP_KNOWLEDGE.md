# APP_KNOWLEDGE

This file is canonical for app-level architecture and status. Source code is final truth when documentation conflicts. Read this overview first; consult a specific module, user guide or current plan next instead of loading the historical acceptance corpus.

## Current build and status

PR #306 is published and applied to clean canonical main at `b35be1c3ad401ba70ca3dc4464f09bf64782958b`, including the EN post-save Arabic-review guard. [HANDOFF.md](docs/assistant/HANDOFF.md) routes to the completed publication and account-permission receipts and the completed test-performance implementation.

Test-infrastructure implementation and local validation are complete; the user approved publication and canonical application on 2026-09-26. The complete baseline passed 6,717 tests in 1,835.010 seconds; Quick passed 87 tests in 10.72 seconds (16.202-second wrapper), and selected Full retained 659 passing tests in 838.559 seconds. Quick excludes only two DOM integration cases, both retained in Full/complete coverage. The complete four-worker run passed 6,754 tests in 537.941 seconds: exact ordered coverage of all 6,717 baseline cases plus 37 runner regressions, 3.411x faster (70.685% shorter wall time) in one local comparison. The baseline overlapped short Quick/tool checks; this is not a hosted-CI guarantee. [VALIDATION.md](docs/assistant/VALIDATION.md) records snapshot boundaries, preservation checks and the local CI rerun design; later artifact-selector validation remains separate from the measured complete run.

Canonical daily use remains `C:/Users/FA507/.codex/legalpdf_translate`, branch `main`. Earlier PR #304 merged at `1d6fdb3e7bfdd0c60ef74f8b9f5f2d3a977c5a46`, with entire-tree equality to reviewed `11beb6c5c296c4087e3455aa176e3de70f158722`. Its shared Word startup deadline passed 91 targeted tests, fresh Full with 655 selected passes/nine expected deselections and all four exact-head CI jobs; both Windows runs passed 6,713 tests with one dependency warning. The earlier PR #303 accounting, absent-settings ownership, formatting-save recovery and stale-warning fixes remain published. [HANDOFF.md](docs/assistant/HANDOFF.md) records current runtime and evidence limits.

Actual Gmail05 acceptance used docs-only PR #305 checkpoint `a8f795098f15685b106d4c354be6f7d531635b2d` with PR #304 product source. The completed PR #306 publication/application is recorded separately by the receipt routed from HANDOFF. The user-authorized [Gmail/formatting task](docs/assistant/exec_plans/completed/2026-09-24_gmail_formatting_readiness.md) has qualified complete English and Arabic formatting evidence: EN03's three native pages and AR02's one native page, exact DOCX mappings, editable tables, retained pipes and full spacing. AR01's partial failure remains preserved. Gmail05 completed genuine extension intake, one image-only English translation, an exact normal download, qualified source/Word review and confirmed row 91 without a duplicate. Finalization generated fee DOCX/PDF, but its single draft attempt returned Google 403 for insufficient permissions; no draft or send succeeded in that operation. Fee-page review and 28 finalization checks passed; the runtime stopped normally. The [closeout plan](docs/assistant/exec_plans/completed/2026-09-26_gmail_finalization_and_arabic_closeout.md) records completed scoped implementation/qualified acceptance and publication provenance for source commit `24f7ecb`; the receipt routed from HANDOFF confirms completed publication/application. The guard passed 20 no-provider tests and clear independent semantic review, preserving completed-Arabic and no-current-job restoration. All659 selected Full tests/nine deselections and compile passed; the wrapper exited1 at docs-only AD046 failures, then exact marker repair and direct docs/hygiene passed. The wrapper failure remains preserved. Independent terminal cleanup passed28/28 with owned processes absent. These bounded cases do not certify all documents or legal accuracy.

A separate user-approved connection follow-up resolved the current Gmail account-permission limitation: one harmless recipient-free/attachment-free draft and its readback succeeded, as did reading that new message. The same configured account requested readonly plus compose access; actual operations, rather than stored requested-scope metadata alone, establish the exercised permissions. No email was sent, Gmail05 was not replayed, and its historical 403 remains unchanged. All 68 protected files/settings/budgets/outputs were preserved; HANDOFF owns the bounded completion-receipt route.

After the preserved automatic Word startup failure, the [completed startup deadline plan](docs/assistant/exec_plans/completed/2026-09-25_word_startup_readiness_deadline.md) published a shared 45-second readiness allowance, retaining the separate canary deadline and ownership/cleanup gates. One actual canonical default-readiness aggregate then passed both stages in 27.673 seconds, with confirmed cleanup and protected/source/tool preservation. Publication, canonical application and this native check are complete; `word_startup_publication_01/final_application_receipt.json` indexes the evidence. The historical delay's cause remains unknown. This synthetic canary is separate from legal-document quality, Gmail finalization and another server process's cache; earlier owned browser runtimes remain stopped; current runtime state belongs in HANDOFF.

Saved translation defaults remain unchanged. Normal Gmail metadata confirmation added only `court_emails_by_city`; the original whole-settings-byte baseline remains false, with exact beforeimages and a narrow reviewed continuation amendment. Preserve the original USD 10 limit, shared phase ledger, FRlong01's USD 0.119 unknown hold/block and five-page partial. The [FRlong reconciliation](docs/assistant/exec_plans/completed/2026-09-24_frlong_readonly_reconciliation.md) remains shelved unless a failure recurs; its old private campaign block is not a global app lock.

[VALIDATION.md](docs/assistant/VALIDATION.md) distinguishes local tests, exact-head CI, actual output/native review and publication. Earlier [PR302](docs/assistant/exec_plans/completed/2026-09-24_everyday_app_update_publication.md), [multilingual](docs/assistant/exec_plans/completed/2026-09-17_multilingual_gmail_acceptance.md) and [Arabic](docs/assistant/exec_plans/completed/2026-09-17_arabic_normal_browser_acceptance.md) results retain their qualifications. Exact status beforeimages for this closeout are privately preserved under `gmail_formatting_readiness_20260924_01/docs_sync_ar02_gmail_closeout_01/`; earlier snapshots remain preserved. This status sync does not alter the architecture below.

## Product surfaces

The primary product is a **local browser app**, producing editable DOCX translations from Portuguese into EN, FR or AR. Translation PDFs/PNGs are internal review evidence. Honorários generation and its Word-to-PDF export are a separate feature.

| Surface | Ownership and purpose |
| --- | --- |
| Browser `live`, port 8877 | Real settings, profiles, job log, outputs and authorized Gmail workflows on canonical main. |
| Browser `shadow` | Isolated development/test state. Verify the actual build and owned data roots; the word shadow is not by itself a network/native safety boundary. |
| Gmail bridge, port 8765 | Exact-message extension handoff, canonical live owner only. No live Gmail actions without explicit scope. |
| Qt | Supported secondary desktop shell/fallback; use the existing build-identity launcher when reviewing Qt. |
| CLI and queue | Existing translation, resume, rebuild and sequential queue entry points. |

Browser navigation keeps `New Job`, `Recent Jobs`, conditional `Gmail` and `More` as the main surface. `#new-job` and `#gmail-intake` retain their existing meanings. Mode/workspace ownership applies to jobs, actions, uploads and artifacts. Static assets form a versioned startup snapshot; a reload of an old server does not prove new CSS/JS was served.

## Translation and review data flow

1. The form/CLI builds a `RunConfig` from explicit input and saved settings. Source selection, OCR policy, retention, output formatting and costs must not be changed silently.
2. `TranslationWorkflow` serializes operations on the actual run directory, binds checkpoint/resume identity and accounts for provider dispatches. The ordinary path and private acceptance continuation have distinct authority.
3. The optional public source-review service retains genuine local TXT/TSV/image evidence and explicit decisions. `OrdinaryReviewedSourceContext` binds the immutable revision to the per-run structured protocol. It verifies source identity before dispatch, on transport retries and before publication.
4. Structured page artifacts bind source/target IDs, protocol identity and commits. Missing or changed evidence fails or declines explicitly; it is not reconstructed into accepted provenance.
5. Ordinary export/rebuild collects source layout evidence and preserves historical findings/accounting. An explicitly selected reviewed revision can produce a separate validated editable DOCX derivative. Unsupported profiles use the documented decline/fallback path.
6. Browser source/formatting managers expose owned review handles and exact operation associations. The UI collects decisions; it never supplies authoritative hashes or evidence paths. A reload can recover only a server-associated operation; process-owned handles are not restored automatically after server restart.

## Runtime map

| Responsibility | Main files under `src/legalpdf_translate/` |
| --- | --- |
| Form/jobs/browser API | `translation_service.py`, `shadow_web/app.py`, `shadow_web/source_review_api.py`, `shadow_web/formatting_review_api.py` |
| Translation orchestration/resume | `workflow.py`, `checkpoint.py`, `new_translation_blocks.py`, `run_workspace_lock.py` |
| Protocol and faithful literals | `translation_structure.py`, `structured_artifacts.py`, `structured_arabic_literals.py`, `structured_arabic_entities.py`, `structured_glossary.py` |
| Source/OCR policy and review | `ocr_engine.py`, `source_readiness.py`, `reviewed_source.py`, `source_review_candidate.py`, `ordinary_source_review_service.py`, `ordinary_reviewed_source.py` |
| Every-call cost and limits | `openai_client.py`, `usage_accounting.py`, `accounting_policy.py`, `budget_reservations.py`, `cost_guardrails.py` |
| Editable DOCX and mappings | `docx_writer.py`, `layout_integration.py`, `run_docx_formatting.py`, `ordinary_formatting_review_service.py`, `reviewed_formatting.py`, `reviewed_regions.py` and their writers |
| Owned browser review | `browser_source_review.py`, `browser_formatting_review.py`, `shadow_web/static/source_review*.js`, `shadow_web/static/formatting_review*.js` |
| Summaries and user review | `run_report.py`, `translation_diagnostics.py`, `review_export.py`, `workflow_components/` |
| Persistence and queues | `user_settings.py`, `joblog_db.py`, `queue_runner.py` |
| Gmail and interpretation | `gmail_intake.py`, `gmail_batch.py`, `gmail_draft.py`, `interpretation_google_photos.py` |
| Native honorários export | `word_automation.py`, `word_process_start.py`, `word_pdf_control.py`, `word_pdf_artifacts.py` |

Private acceptance modules/tooling enforce their own declared provenance, budget and consumed-operation contracts. They are not a shortcut for ordinary user review. The original lifetime acceptance ledger and Word journal must be preserved, never reset or replaced to bypass a failed operation.

## Reviewed formatting limits

The current ordinary browser review requires a genuine complete browser-image source profile and explicit source/target mappings. Local source acquisition preserves OCR policy and requires retained local evidence. Digital/OCR-only provenance, partial selections and incompatible preferences can decline honestly. A page-matched derivative is an explicit choice that preserves original `page_breaks=False`; it is not a global preference change. Source-supported gutters, measured vertical spacing, table-cell ownership, document groups and local folios require review. Geometry uncertainty and unassessed rendered layout stay visible.

Final delivery must preserve legal meaning and complete content. Do not shorten text or shrink fonts to meet a page target. Review the actual output before delivery; a valid package or completed model response is not legal certification.

## Where to go next

- In the dormant roadmap state, [SESSION_RESUME](docs/assistant/SESSION_RESUME.md) identifies any active roadmap tracker and otherwise routes normal ExecPlan work. Issue memory remains a reusable repeated-issue registry, not the current task ledger.
- Follow [harness isolation and diagnostics](docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md) for localhost listeners, browser/app bridges and handoff/run/finalization boundaries.
- [Fresh-session handoff](docs/assistant/HANDOFF.md) and [dormant roadmap anchor](docs/assistant/SESSION_RESUME.md).
- [App user guide](docs/assistant/features/APP_USER_GUIDE.md), [PDF translation guide](docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md), [reviewed-source and DOCX guide](docs/assistant/features/REVIEWED_SOURCE_AND_DOCX_USER_GUIDE.md).
- [Validation tiers and commands](docs/assistant/VALIDATION.md), [workflow index](docs/assistant/INDEX.md), [machine routing manifest](docs/assistant/manifest.json).
- [Historical front-door snapshots](docs/assistant/history/2026-09-16_front_doors/README.md). These preserve the former detailed architecture and dated operations; their old gates, budgets and status are not current instructions.
