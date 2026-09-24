# APP_KNOWLEDGE

This file is canonical for app-level architecture and status. Source code is final truth when documentation conflicts. Read this overview first; consult a specific module, user guide or current plan next instead of loading the historical acceptance corpus.

## Current build and status

Canonical daily use remains `C:/Users/FA507/.codex/legalpdf_translate`, branch `main`. The published base is PR #303 merge `ca395d601efe4e00aad3458526b7d961d3cf5f0c`, matching the reviewed `dad5ea1` tree. The caller-owned accounting, absent-settings ownership, explicit formatting-save recovery and stale-warning fixes are published. Full_04 passed 655 selected tests with nine expected deselections and 486 matching source pins; all four required exact-head CI jobs passed. [HANDOFF.md](docs/assistant/HANDOFF.md) records the current runtime and evidence limits.

The user-authorized [Gmail/formatting readiness task](docs/assistant/exec_plans/active/2026-09-24_gmail_formatting_readiness.md) remains active. EN03's three-page reviewed DOCX/native output covers the qualified English formatting matrix. Genuine Gmail03 image-only/OCR-off output passed qualified review and normal Save/Confirm, producing row 90 with all 63 prior rows preserved. These outcomes do not certify all documents or establish an email draft/send. AR01 remains a preserved partial compliance failure; AR02 still needs reviewed inline-pipe, full-spacing and RTL output evidence and currently awaits a browser local-file access setting.

A later automatic canonical Word startup failed before ownership was established. Separate exact-process cleanup and one fresh supported 45-second preflight succeeded with confirmed cleanup; the old cause remains unknown. This revision adds a shared 45-second startup allowance across the app's readiness checks, preserving separate canary deadlines and ownership/cleanup gates. The [startup deadline plan](docs/assistant/exec_plans/active/2026-09-25_word_startup_readiness_deadline.md) and bounded actual receipts in HANDOFF distinguish the 91-test regression pass, required Full/CI, canonical application and the separate native readiness check. Both earlier owned browser runtimes are stopped; no native acceptance is inferred merely from publication.

Saved translation defaults remain unchanged. Normal Gmail metadata confirmation added only `court_emails_by_city`; the original whole-settings-byte baseline remains false, with exact beforeimages and a narrow reviewed continuation amendment. Preserve the original USD 10 limit, shared phase ledger, FRlong01's USD 0.119 unknown hold/block and five-page partial. The [FRlong reconciliation](docs/assistant/exec_plans/completed/2026-09-24_frlong_readonly_reconciliation.md) remains shelved unless a failure recurs; its old private campaign block is not a global app lock.

[VALIDATION.md](docs/assistant/VALIDATION.md) distinguishes local tests, exact-head CI, actual output/native review and publication. Earlier [PR302](docs/assistant/exec_plans/completed/2026-09-24_everyday_app_update_publication.md), [multilingual](docs/assistant/exec_plans/completed/2026-09-17_multilingual_gmail_acceptance.md) and [Arabic](docs/assistant/exec_plans/completed/2026-09-17_arabic_normal_browser_acceptance.md) results retain their qualifications. Exact superseded status text is privately preserved under `gmail_formatting_readiness_20260924_01/docs_sync_word_startup_01/beforeimages/`. This status sync does not alter the architecture below.

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
