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
- Fresh-session roadmap resume: `docs/assistant/SESSION_RESUME.md`
- Local harness sync from vendored templates: `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- Roadmap governance rules: `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
- Golden rules: `docs/assistant/GOLDEN_PRINCIPLES.md`
- Source registry: `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`
- Local host/runtime profile: `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- Local capability inventory: `docs/assistant/LOCAL_CAPABILITIES.md`

## User Support Routing
For support/non-technical explanations, start with:
- `docs/assistant/features/APP_USER_GUIDE.md`
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Local folder/worktree/workspace organization questions route to `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md` first, then `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md` if branch/build provenance matters.
- Multi-window workspace usage, duplicate-target blocking, or Gmail intake opening/reusing a workspace route to `docs/assistant/features/APP_USER_GUIDE.md`, `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Qt dashboard shell/launch behavior routes to `docs/assistant/QT_UI_KNOWLEDGE.md` and `docs/assistant/QT_UI_PLAYBOOK.md`.
- Future Qt/UI resize or geometry work should start with `docs/assistant/QT_UI_KNOWLEDGE.md`, `docs/assistant/QT_UI_PLAYBOOK.md`, and `src/legalpdf_translate/qt_gui/window_adaptive.py` before any one-off widget geometry edits.
- Reference-locked Qt UI work routes to `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.
- OCR-heavy translation triage routes to `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`.
- Windows-native GUI launch/debug routes to `docs/assistant/QT_UI_KNOWLEDGE.md` and `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.
- OCR-heavy warning choices, bounded cancel-wait behavior, and translated-output Job Log word counts route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Gmail draft + honorarios attachment reuse routes to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Arabic DOCX Word review, `Align Right + Save`, save-detection fallback behavior, and `Open translated DOCX` route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, `APP_KNOWLEDGE.md`, and the local host docs.
- Job Log row editing, delete confirmation, historical-row recovery, and column resize/scroll behavior route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Interpretation Job Log intake, interpretation-only honorarios generation, and service-city distance behavior route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
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
- Canonical current-truth also includes true multi-window Qt workspaces, `File > New Window` / `Ctrl+Shift+N`, workspace title numbering, duplicate run-folder blocking across active workspaces, controller-routed Gmail intake reuse vs auto-opened new workspaces, and session-local job-form drafts that no longer leak across windows through shared settings.
- Canonical current-truth also includes durable Gmail batch session diagnostics (`gmail_batch_session.json`), run-level `gmail_batch_context` in `run_summary.json` / `run_report.md`, per-attachment Gmail review start-page selection, lazy in-app PDF preview, preview-cache reuse during Prepare, visible Gmail bridge-unavailable UI state, stale-output/stale-checkpoint fail-closed behavior, honorarios auto-rename on save collision, duplicate/contaminated attachment blocking before Gmail draft creation, and additive `selected_start_page` reporting.
- Canonical current-truth also includes the Arabic-only Word review gate before `Save to Job Log`, Windows Word + PowerShell COM automation for `Align Right + Save`, save-detection auto-resume plus manual fallback actions, and `Open translated DOCX` inside `Save to Job Log`. The current supported mitigation is manual-or-assisted Word review, not a pure OOXML auto-right-alignment fix.
- Canonical current-truth also includes historical Job Log row editing through either the icon-triggered full dialog or inline row editing, confirmed row deletion, missing-`pdf_path` historical edit tolerance, and header-auto-fit plus persisted-width horizontal-scroll behavior for dense Job Log tables.
- Canonical current-truth also includes the shared responsive-window helper in `qt_gui/window_adaptive.py`, screen-bounded main/dialog sizing, deferred/coalesced shell and preview resize handling, and the scrollable Save-to-Job-Log form with lower detail sections collapsed by default.
- Canonical current-truth also includes the interpretation honorarios workflow: blank/manual interpretation Job Log entry, interpretation import from local notification PDFs and local photos/screenshots, interpretation-specific edit-mode cleanup that hides translation-only inputs, one visible one-way distance field keyed by `service_city`, profile-backed distance reuse/persistence, manual PDF picker fallback for interpretation header autofill, and local-only interpretation honorarios generation with no Gmail draft branch.
- Canonical current-truth also includes project-local harness sync from vendored templates, with `implement the template files` / `sync project harness` reserved for local harness application and `update codex bootstrap` / `UCBS` reserved for template-system maintenance.
- Canonical current-truth also includes the local harness-sync rule that vendored template changes affecting continuity or cleanup must resync the publish/docs-maintenance governance surfaces, not just routing docs and validators.
- Canonical current-truth also includes roadmap governance for this repo: `docs/assistant/SESSION_RESUME.md` is the roadmap anchor file, roadmap state may be active or in a dormant roadmap state, the active roadmap tracker is the sequence source when present, the active wave ExecPlan is the implementation-detail source when present, and issue memory is not roadmap history.
- Canonical current-truth also includes active-worktree authority for live roadmap state during in-progress wave work, while `main` may intentionally carry a dormant roadmap state between roadmap-scoped threads.

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
- Project harness sync: `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- Roadmap governance: `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
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
