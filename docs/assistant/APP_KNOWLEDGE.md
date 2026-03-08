# APP_KNOWLEDGE (Bridge)

This bridge is intentionally shorter than `APP_KNOWLEDGE.md`.

## Bridge Purpose
Use this file to route quickly to canonical and workflow docs. Do not treat this file as the canonical architecture source.

## Canonical Deference
- Canonical app architecture/status lives in `APP_KNOWLEDGE.md`.
- If this bridge conflicts with canonical, defer to `APP_KNOWLEDGE.md`.
- If docs conflict with code, source code is final truth.

## Quick Routing
- Routing map: `docs/assistant/manifest.json`
- Human index: `docs/assistant/INDEX.md`
- Runbook: `agent.md`
- Golden rules: `docs/assistant/GOLDEN_PRINCIPLES.md`
- Source registry: `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`
- Local host/runtime profile: `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- Local capability inventory: `docs/assistant/LOCAL_CAPABILITIES.md`

## User Support Routing
For support/non-technical explanations, start with:
- `docs/assistant/features/APP_USER_GUIDE.md`
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Qt dashboard shell/launch behavior routes to `docs/assistant/QT_UI_KNOWLEDGE.md` and `docs/assistant/QT_UI_PLAYBOOK.md`.
- Reference-locked Qt UI work routes to `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.
- OCR-heavy translation triage routes to `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`.
- Windows-native GUI launch/debug routes to `docs/assistant/QT_UI_KNOWLEDGE.md` and `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.
- OCR-heavy warning choices, bounded cancel-wait behavior, and translated-output Job Log word counts route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Gmail draft + honorarios attachment reuse routes to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Listener ownership, test isolation, and multi-surface handoff/run/finalization diagnostics route to `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`.
- Gmail intake extension setup, exact-message batch review, per-attachment start-page selection, in-app preview, sequential Save-to-Job-Log checkpoints, and one threaded reply-draft batch semantics route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Gmail intake troubleshooting now routes by failure surface:
  - extension/banner or app-bridge startup issue: `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
  - translation/run issue: `run_report.md`, `run_summary.json`, and `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
  - Gmail batch finalization/draft issue: app-owned `gmail_batch_session.json` plus `APP_KNOWLEDGE.md`
- Same-host Gmail intake/browser/`gog` validation routes to `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`, `docs/assistant/LOCAL_ENV_PROFILE.local.md`, and `docs/assistant/LOCAL_CAPABILITIES.md`.

Cost-guardrail support routing:
- CLI budget cap/policy behavior (`warn` vs `block`) is documented in the primary workflow user guide.
- OCR advisor and analyze-only support route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`.
- Review queue and review export support route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`.
- Queue runner support routes to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`.
- Job-log metric prefill and migration concerns route to `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md` and `docs/assistant/DB_DRIFT_KNOWLEDGE.md`.

## Current-Truth Note
- Canonical current-truth now includes queue runner support, OCR advisor flows, review queue handling, and job-log metric sync.
- Canonical current-truth also includes the screenshot-driven Qt dashboard shell and the real GUI module entrypoint: `python -m legalpdf_translate.qt_app`.
- Canonical current-truth also includes bounded OCR-heavy request deadlines, non-persistent `Apply safe OCR profile` warning behavior, no-wheel guards on run-critical selectors, and DOCX-first Job Log word counting.
- Canonical current-truth also includes Gmail draft attachment reuse for both current-run and historical honorarios exports, with stored-path reuse and exact `run_id` recovery before any manual picker fallback.
- Canonical current-truth also includes the Windows-only Gmail intake bridge, exact-message Gmail fetch/review, sequential Save-to-Job-Log gating, one honorarios DOCX for the confirmed batch, and one threaded Gmail reply draft with no auto-send.
- Canonical current-truth also includes durable Gmail batch session diagnostics (`gmail_batch_session.json`), run-level `gmail_batch_context` in `run_summary.json` / `run_report.md`, per-attachment Gmail review start-page selection, lazy in-app PDF preview, preview-cache reuse during Prepare, visible Gmail bridge-unavailable UI state, stale-output/stale-checkpoint fail-closed behavior, honorarios auto-rename on save collision, duplicate/contaminated attachment blocking before Gmail draft creation, and additive `selected_start_page` reporting.

## Workflow Routing
- Core translation: `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- Data/persistence: `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`
- Localization: `docs/assistant/workflows/LOCALIZATION_WORKFLOW.md`
- Performance: `docs/assistant/workflows/PERFORMANCE_WORKFLOW.md`
- Parity/inspiration: `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md`
- Reference-locked Qt UI work: `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`
- OCR-heavy translation triage: `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`
- Stage-gate execution: `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`
- Browser automation provenance: `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- Cloud machine evaluation: `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`
- OpenAI docs citation: `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`
- CI/repo operations: `docs/assistant/workflows/CI_REPO_WORKFLOW.md`
- Commit/publish: `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
- Docs maintenance: `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- Host-bound integration preflight: `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
- Harness isolation and diagnostics: `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`

## Legacy Supplemental Deep Docs
These are supplemental and non-canonical for app-level status:
- `docs/assistant/API_PROMPTS.md`
- `docs/assistant/PROMPTS_KNOWLEDGE.md`
- `docs/assistant/QT_UI_KNOWLEDGE.md`
- `docs/assistant/QT_UI_PLAYBOOK.md`
- `docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md`
- `docs/assistant/WORKFLOW_GIT_AI.md`
