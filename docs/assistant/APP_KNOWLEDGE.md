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
- Browser app `live` vs isolated `shadow` mode, browser workspace URLs, or browser-app-first daily-use guidance route to `docs/assistant/features/APP_USER_GUIDE.md`, `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Qt dashboard shell/launch behavior routes to `docs/assistant/QT_UI_KNOWLEDGE.md` and `docs/assistant/QT_UI_PLAYBOOK.md`.
- Future Qt/UI resize or geometry work should start with `docs/assistant/QT_UI_KNOWLEDGE.md`, `docs/assistant/QT_UI_PLAYBOOK.md`, and `src/legalpdf_translate/qt_gui/window_adaptive.py` before any one-off widget geometry edits.
- Reference-locked Qt UI work routes to `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.
- OCR-heavy translation triage routes to `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`.
- Windows-native GUI launch/debug routes to `docs/assistant/QT_UI_KNOWLEDGE.md` and `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.
- OCR-heavy warning choices, bounded cancel-wait behavior, and translated-output Job Log word counts route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Incorrect or inconsistent Portuguese court/prosecution header translations, or wrong `case_entity` extraction from institutional header lines, route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Gmail draft + honorarios attachment reuse routes to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Arabic DOCX Word review, manual Word save detection, mixed Arabic/LTR run-ordering hardening, and `Open translated DOCX` route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, `APP_KNOWLEDGE.md`, and the local host docs.
- Gmail same-attachment reruns without cold start and browser `Download Run Report` behavior route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Job Log row editing, delete confirmation, historical-row recovery, and column resize/scroll behavior route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Interpretation Job Log intake, interpretation-only honorarios generation, and service-city distance behavior route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Listener ownership, test isolation, and multi-surface handoff/run/finalization diagnostics route to `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`.
- Gmail intake extension setup, exact-message batch review, per-attachment start-page selection, in-app preview, sequential Save-to-Job-Log checkpoints, and one threaded reply-draft batch semantics route to `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `APP_KNOWLEDGE.md`.
- Browser-owned Gmail bridge readiness, browser-app handoff URLs, and Extension Lab diagnostics route to `docs/assistant/features/APP_USER_GUIDE.md`, `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`, and `APP_KNOWLEDGE.md`.
- Stale browser shell/asset-version mismatches, pre-run Gmail `Generate Failure Report`, and browser PDF worker/module failures route to `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`, `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
- Word export canary readiness, blocked Gmail finalization, and `Generate Finalization Report` route to `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`, `docs/assistant/features/APP_USER_GUIDE.md`, `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, and `APP_KNOWLEDGE.md`.
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
- Canonical current-truth now includes the local browser app as the preferred daily-use surface, explicit browser `live` vs isolated `shadow` runtime modes, browser workspace URLs, and live Gmail bridge ownership by the browser app when available.
- Canonical current-truth also includes the screenshot-driven Qt dashboard shell and the real GUI module entrypoint: `python -m legalpdf_translate.qt_app`.
- Canonical current-truth also includes a repo-root beginner launcher, `Launch LegalPDF Translate.bat`, which delegates to `tooling/launch_qt_build.py` instead of duplicating the GUI startup path.
- Canonical current-truth also includes a real runtime `ui_theme` contract in the Qt shell: `dark_futuristic` is the elevated default, `dark_simple` is the lower-noise variant, and both are applied live through the shared Qt style system rather than existing as dead settings.
- Canonical current-truth also includes bounded OCR-heavy request deadlines, non-persistent `Apply safe OCR profile` warning behavior, guarded no-wheel selectors for the main shell, Gmail review, settings defaults/provider, and fixed-vocabulary Job Log controls, plain `QComboBox` exceptions for glossary/study/tool selectors plus dense table editors, and DOCX-first Job Log word counting.
- Canonical current-truth also includes Gmail draft attachment reuse for both current-run and historical honorarios exports, with stored-path reuse and exact `run_id` recovery before any manual picker fallback.
- Canonical current-truth also includes the Windows-only Gmail intake bridge, native-host auto-launch of the current repo checkout when the configured bridge is down, exact-message Gmail fetch/review, success-only browser-app open/focus after a localhost handoff, fail-closed Gmail-page banner errors on rejected handoffs, sequential Save-to-Job-Log gating, one honorários DOCX plus sibling PDF attempt for the confirmed batch, and one threaded Gmail reply draft with no auto-send.
- Canonical current-truth also includes the March 28-30 browser-hardening layer: validated native-host runtime selection, shell-safe browser startup, client-ready/asset-version proof for localhost handoff, one exact-tab stale-asset reload, and bundled browser-managed PDF preview/prepare instead of startup-time `PyMuPDF`.
- Canonical current-truth also includes direct operator-facing browser failure reporting and Gmail finalization reporting, raw browser PDF worker/module diagnostics in those failure artifacts, noncanonical live Gmail hard-block/restart behavior, and browser-side settings checks for Translation Auth, OCR Provider, Native Host, and the Word PDF export canary.
- Canonical current-truth also includes true multi-window Qt workspaces, `File > New Window` / `Ctrl+Shift+N`, workspace title numbering, duplicate run-folder blocking across active workspaces, controller-routed Gmail intake reuse vs auto-opened new workspaces, and session-local job-form drafts that no longer leak across windows through shared settings.
- Canonical current-truth also includes durable Gmail batch and interpretation session diagnostics (`gmail_batch_session.json`, `gmail_interpretation_session.json`), run-level `gmail_batch_context` in `run_summary.json` / `run_report.md`, preserved Gmail run-report provenance through Gmail-originated reruns/manual restart prep, per-attachment Gmail review start-page selection with page `1` as the enforced default, lazy in-app PDF preview, preview-cache reuse during Prepare, visible Gmail bridge-unavailable UI state, stale-output/stale-checkpoint fail-closed behavior, in-progress Gmail-click focus guidance without spawning duplicate browser windows, honorarios auto-rename on save collision, duplicate/contaminated attachment blocking before Gmail draft creation, additive honorários DOCX/PDF session-path reporting, and additive `selected_start_page` reporting.
- Canonical current-truth also includes the Arabic-only Word review gate before `Save to Job Log`, browser manual-only Word save detection with `Open in Word` / `Continue now` / `Continue without changes`, Qt manual-or-assisted Word review, `Open translated DOCX` inside `Save to Job Log`, and shared DOCX run-ordering hardening for mixed Arabic/LTR lines. The current supported mitigation is real Word review plus corrected DOCX assembly, not a pure OOXML auto-right-alignment fix.
- Canonical current-truth also includes narrow Arabic legal-term and quality-risk hardening: priority prompt injection for `O Juiz de Direito`, Portuguese legal citation aliasing for `n.º` / `alínea` / `p. e p. pelos arts.`, harmonized `السجل العدلي` terminology for `registo criminal`, and Arabic quality-risk scoring that now surfaces numeric/citation/bidi drift instead of leaving noisy citation-heavy runs artificially green.
- Canonical current-truth also includes an explicit browser/Gmail `translation_recovery` state when the current attachment fails before confirmation, so Gmail confirmation stays blocked until a completed rerun produces a real save seed.
- Canonical current-truth also includes Gmail `Redo Current Attachment` for the active unconfirmed Gmail translation item: it resets only the translation-side UI state, preserves the Gmail batch session, re-applies the same launch context, and waits for a manual rerun without requiring a cold start or whole-workspace reset.
- Canonical current-truth also includes translation `run_report.md` as a first-class browser artifact: the completion drawer can generate or refresh `<run_dir>/run_report.md`, download it immediately once, keep a persistent `Download Run Report` action afterward, and label run tokens separately from billed totals that include reasoning.
- Canonical current-truth also includes fresh Gmail handoff priority over recovered finalized translation batches: report-restored completed sessions are now secondary history (`Open Last Finalization Result`) instead of the primary active workspace state.
- Canonical current-truth also includes the April 8 single-path canonical Gmail recovery: only the primary repo on `main` may own live Gmail, `Prepare selected` is prepare-only with a prepared `New Job` state, fresh Gmail starts force authoritative OCR/image/resume defaults plus Gmail-scoped run directories, and integrity-suspect EN/FR pages escalate to OCR/visual recovery instead of silently finishing as text-only.
- Canonical current-truth also includes historical Job Log row editing through either the icon-triggered full dialog or inline row editing, confirmed row deletion, missing-`pdf_path` historical edit tolerance, and header-auto-fit plus persisted-width horizontal-scroll behavior for dense Job Log tables.
- Canonical current-truth also includes the shared responsive-window helper in `qt_gui/window_adaptive.py`, screen-bounded main/dialog sizing, deferred/coalesced shell and preview resize handling, and the scrollable Save-to-Job-Log form with lower detail sections collapsed by default.
- Canonical current-truth also includes stronger shared visual elevation across the dashboard, settings glossary/study/diagnostics tabs, glossary editor/builder, calibration audit, and core dialogs through centralized `qt_gui/styles.py` selectors and objectName-based chrome, instead of dialog-local inline styling.
- Canonical current-truth also includes the Stage 3 rollout of shared guarded selectors and primary/danger action hierarchy across `QtSettingsDialog` glossary/study/diagnostics areas, `QtGlossaryEditorDialog`, `QtGlossaryBuilderDialog`, and `QtCalibrationAuditDialog`, while dense table-local editors keep their existing plain `QComboBox` contracts.
- Canonical current-truth also includes the shared dashboard combo polish: the closed target-language field stays compact with `EN/FR/AR`, the popup shows full language names, and shared combo hover/open styling no longer activates neighboring controls.
- Canonical current-truth also includes a shared Monday-first date picker used by Save/Edit Job Log, Job Log inline date editing, and interpretation honorários export while preserving manual `YYYY-MM-DD` typing.
- Canonical current-truth also includes the interpretation honorarios workflow: direct `Tools > New Interpretation Honorários...` save-first entry, blank/manual interpretation Job Log entry, interpretation import from local notification PDFs and local photos/screenshots, interpretation-specific edit-mode cleanup that hides translation-only inputs, one visible one-way distance field keyed by `service_city`, profile-backed distance reuse/persistence, a default-on transport-sentence toggle stored on the Job Log row, manual PDF picker fallback for interpretation header autofill, addressee city auto-completion for generic court entities, the revised one-line-IBAN / centered `Espera deferimento,` closing block, body text that keeps `service_date`, footer dates that use the document generation day, automatic sibling PDF export after honorários DOCX save, manual/local interpretation Gmail drafts that attach the honorários PDF when `Court Email` plus Gmail prerequisites are available, and a Gmail-intake interpretation path that replies in-thread with the generated honorários PDF only.
- Canonical current-truth also includes the honorários desktop-stability pass: Word PDF export runs off the GUI thread, PDF failures surface concise summaries plus expandable details, partial-success exports keep one retry/select-existing-PDF/local-only recovery flow, and focus-sensitive Qt dialog tests now use explicit activation plus leaked-popup cleanup instead of inheriting stale modal state.
- Canonical current-truth also includes a stronger Gmail finalization readiness contract: launch-only Word readiness is no longer sufficient, Gmail finalization now checks a real export canary before the reply step, and blocked or recoverable finalization states remain reportable without rerunning translation.
- Canonical current-truth also includes the beginner-first primary-flow declutter pass: the shell now centers default chrome on `Run Status` with shorter visible copy and inline help, Gmail review uses a compact summary banner with provenance tucked behind an info button, interpretation Save/Edit Job Log uses compact `+` buttons plus a default-collapsed `SERVICE` section, interpretation honorários export uses `SERVICE` / `TEXT` / `RECIPIENT` disclosure sections, and interpretation photo/screenshot imports tolerate missing service metadata instead of failing autofill.
- Canonical current-truth also includes a shared legal-header glossary catalog for recurring Portuguese court/prosecution/judicial header phrases, exact institutional-header prompt injection ahead of generic glossary rows, OCR-tolerant matching for common header variants, cross-language EN/FR/AR seed alignment from one source of truth, metadata/header extraction that prefers the most specific institutional match, and a review-first policy for riskier prosecution-office variants instead of silently broadening the enforced glossary.
- Canonical current-truth also includes translation edit-mode cleanup in the Job Log dialog: fixed-vocabulary fields are selection-only, the translation service section is hidden, and the rounded primary action no longer falls back to a native rectangular default-button style.
- Canonical current-truth also includes project-local harness sync from vendored templates, with `implement the template files` / `sync project harness` reserved for local harness application and `update codex bootstrap` / `UCBS` reserved for template-system maintenance.
- Canonical current-truth also includes the browser parity surface as a reusable local-app pattern: one browser app can serve daily-use `live` mode and isolated test mode from the same repo while keeping state roots, listener ownership, and diagnostics explicit instead of relying on separate ad hoc harnesses.
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
