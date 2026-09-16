# APP_KNOWLEDGE

This file is canonical for app-level architecture and status. Source code is final truth when documentation conflicts. Read this overview first; consult a specific module, user guide or current plan next instead of loading the historical acceptance corpus.

## Current build and status

- **Daily-use build:** canonical `C:/Users/FA507/.codex/legalpdf_translate`, branch `main`. PR #296 merged at `068e4312269106e26677185ae33bc1b556e3c073`; canonical verification confirmed `068e4312269106e26677185ae33bc1b556e3c073` on `2026-09-16T22:23:49.151967+00:00`. Recheck actual Git/process state before work.
- **Reviewed implementation:** reviewed-source, accounting, formatting and browser changes are available in builds containing that merge. See the [publication closeout](docs/assistant/exec_plans/completed/2026-09-16_reviewed_candidate_publication.md) for exact CI and canonical-build evidence. Integration-worktree disposition: retained for scoped documentation closeout from the merged main revision; the fully merged feature branch was removed locally and remotely. Recheck actual Git state before new work; retained private/ignored evidence is not disposable.
- **Authoring worktree:** `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`. Harvest exact reviewed scopes; never overwrite a newer integration snapshot wholesale.
- Current acceptance and validation results live in the [ordinary browser integration plan](docs/assistant/exec_plans/completed/2026-09-16_ordinary_browser_integration.md) and [Arabic rendered-correction plan](docs/assistant/exec_plans/completed/2026-09-16_arabic_render_corrections.md). Completed private derivatives, synthetic browser evidence and real ordinary-workflow acceptance are distinct.
- No global translation model/protocol promotion is implied. The user's Astra Ultra preference concerns the assistant's Codex task. Terra evaluation concerns the app's translation provider. Saved app preferences and explicit per-run selections remain authoritative.

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
