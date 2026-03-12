# APP_KNOWLEDGE

This file is canonical for app-level architecture and status.

## App Summary
LegalPDF Translate is a Windows-first Python app that translates PDFs into DOCX using one-page-per-request processing for each translation job, supports sequential multi-document queue execution, supports true multi-window Qt workspaces for parallel jobs, and supports a Windows-only Gmail intake batch-reply workflow.

- Primary UI: Qt/PySide6 desktop app.
- Secondary interface: CLI.
- Model transport: OpenAI Responses API.
- Key invariant: page-by-page translation flow, no whole-document batch request.

## Entrypoints
- GUI: `python -m legalpdf_translate.qt_app`
- GUI compatibility shim: `python -m legalpdf_translate.qt_main`
- Beginner Windows launcher: double-click `Launch LegalPDF Translate.bat` in the repo root. It delegates to `tooling/launch_qt_build.py --worktree <repo-root>`.
- CLI: `legalpdf-translate --pdf <file> --lang EN|FR|AR --outdir <dir>`
  - Cost guardrails (optional): `--budget-cap-usd <float> --cost-profile-id <string> --budget-on-exceed warn|block`
  - Queue mode (optional): `legalpdf-translate --queue-manifest <manifest.jsonl> --rerun-failed-only true --lang EN --outdir <dir>`
- Build: `powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1`

## Desktop UI Shell
- The desktop app now uses a dashboard-style shell instead of the older stacked utility card.
- Each top-level app window is an independent workspace under one `QApplication`.
- Main visible regions:
  - left sidebar: `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, `Profile`
  - hero row: centered `LegalPDF Translate` title and right-aligned status text
  - left card: `Job Setup`
  - right card: `Conversion Output`
  - bottom action rail: `Start Translate`, `Cancel`, `...`
- `Advanced Settings` stays collapsed by default inside the setup card.
- Review Queue and Save to Job Log remain available from the `Tools` menu; the `...` menu keeps output/report/job-log actions.
- Workspace titles show `Workspace N` and can add the current source filename as a hint so parallel windows stay distinguishable.
- The shell uses three responsive layout modes:
  - `desktop_exact`
  - `desktop_compact`
  - `stacked_compact`
- `Settings > Appearance > Theme` is now a real live runtime choice:
  - `dark_futuristic`: the elevated default with stronger translucent depth and cyan-accent glow
  - `dark_simple`: a toned-down darker variant built from the same shared style system
- The dashboard plus the shared dialog/tool surfaces (`Settings` appearance/glossary/study/diagnostics tabs, Gmail review/preview, glossary editor, glossary builder, calibration audit, Save/Edit Job Log, and honorários export) now share one centralized elevated/translucent visual language from `src/legalpdf_translate/qt_gui/styles.py` instead of drifting through local widget styling.
- Top-level fixed-vocabulary selectors in the shell, settings/admin tabs, and glossary/calibration tool dialogs now use guarded non-editable combos/spins; dense table-local editors keep their existing local combo contract.
- Top-level windows and major dialogs now use shared screen-bounded sizing via `src/legalpdf_translate/qt_gui/window_adaptive.py`.
- Main-shell resize work is deferred/coalesced so live resizing stays stable; the hero row also reserves width for the status label so short states such as `Idle` are not clipped during narrow-width transitions.

## Core Runtime Modules
- `src/legalpdf_translate/workflow.py`: translation pipeline orchestration.
- `src/legalpdf_translate/cost_guardrails.py`: deterministic pre-run/post-run cost estimation and budget decisions.
- `src/legalpdf_translate/queue_runner.py`: sequential queue execution, checkpointing, and queue summaries.
- `src/legalpdf_translate/review_export.py`: review queue export to CSV and Markdown.
- `src/legalpdf_translate/gmail_intake.py`: localhost Gmail message intake bridge for exact-message handoff.
- `src/legalpdf_translate/gmail_batch.py`: exact-message Gmail fetch, attachment filtering/download, and batch-state orchestration helpers.
- `src/legalpdf_translate/gmail_draft.py`: Windows `gog` Gmail prerequisite checks and draft creation helpers.
- `src/legalpdf_translate/court_email.py`: shared court-email ranking, normalization, provenance, and Gmail-draft safety guards.
- `src/legalpdf_translate/workflow_components/contracts.py`: typed workflow internal contracts.
- `src/legalpdf_translate/workflow_components/evaluation.py`: output-evaluation and retry-reason delegation.
- `src/legalpdf_translate/workflow_components/quality_risk.py`: deterministic quality risk scoring and review queue construction.
- `src/legalpdf_translate/workflow_components/ocr_advisor.py`: deterministic OCR/image recommendation logic.
- `src/legalpdf_translate/workflow_components/summary.py`: run-summary and cost/suspected-cause delegation.
- `src/legalpdf_translate/cli.py`: CLI parsing/execution.
- `src/legalpdf_translate/qt_gui/app_window.py`: main GUI workflow orchestration.
- `src/legalpdf_translate/qt_gui/window_adaptive.py`: shared screen-bounded top-level sizing, deferred resize callbacks, and collapsible section helpers.
- `src/legalpdf_translate/openai_client.py`: OpenAI transport and retry handling.
- `src/legalpdf_translate/ocr_engine.py`: OCR routing and policy.
- `src/legalpdf_translate/docx_writer.py`: DOCX output construction.
- `src/legalpdf_translate/joblog_db.py`: SQLite schema and migrations for job logging.
- `src/legalpdf_translate/user_settings.py`: settings schema and persistence.

## Primary User Journeys
1. Translate a PDF to EN/FR/AR.
2. Analyze-only extraction preflight without translation API calls.
3. Resume interrupted runs from checkpoint artifacts.
4. Rebuild DOCX from existing page outputs.
5. Use glossary and diagnostics workflows for consistency and QA.
6. Optionally apply CLI budget guardrails (`warn` continue or `block` before page processing).
7. Run analyze-only first and inspect/apply an OCR advisor recommendation before translation.
8. Inspect or export a Review Queue when high-risk pages are flagged.
9. Save completed runs to the Job Log with prefilled run metrics.
10. Review historical Job Log rows, edit them inline or through the full dialog, delete mistaken rows with confirmation, and resize the table for dense saved data.
11. Execute a queue manifest with checkpoint-aware resume and failed-only rerun behavior.
12. Start from an open Gmail message in Edge/Chromium, let the native host auto-start the configured checkout when needed, review supported attachments from that exact email, then either run the translation batch flow or handle one interpretation notice attachment, with mandatory Save-to-Job-Log confirmation before the related honorarios and Gmail draft finalization.
13. Open multiple workspaces and translate different jobs in parallel without interrupting the current run.
14. Create or edit interpretation Job Log rows manually, from a notification PDF, from a photo/screenshot, or from a Gmail notice attachment, then generate the interpretation honorarios DOCX locally or create a threaded Gmail reply draft when the flow started from Gmail intake.

## Output and Run Artifacts
Run artifacts live under:
- `<outdir>/<pdf_stem>_<LANG>_run/`

Typical files:
- `pages/page_XXXX.txt`
- `run_state.json`
- `run_summary.json`
- `run_report.md` (when generated)
- `run_events.jsonl`
- `analyze_report.json` (analyze-only)

When a run comes from Gmail intake, the effective output directory also gains a durable batch-level diagnostics folder:
- `<outdir>/_gmail_batch_sessions/<session_id>/gmail_batch_session.json`

`run_summary.json` keeps existing totals and now also supports additive cost/risk/advisor fields:
- `cost_estimation_status`
- `cost_profile_id`
- `budget_cap_usd`
- `budget_decision`
- `budget_decision_reason`
- `budget_pre_run`
- `budget_post_run`
- `quality_risk_score`
- `review_queue_count`
- `review_queue`
- `advisor_recommendation_applied`
- `advisor_recommendation`
- `failure_context`
- `gmail_batch_context`

When present, `gmail_batch_context` records the selected Gmail attachment filename/count, the Gmail intake workflow kind, the translation target language when that workflow is `translation`, the selected start page for that run, and the durable Gmail batch session report path.

`failure_context` is used for bounded OCR/runtime failure reporting and includes:
- `request_type`
- `request_timeout_budget_seconds`
- `request_elapsed_before_failure_seconds`
- `cancel_requested_before_failure`
- `exception_class`

For larger host-bound workflows, keep these per-run artifacts primary. If a feature later adds a broader handoff/finalization session layer, route it through `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md` and keep any additive `workflow_context` or session artifact secondary to the run report/summary.

`analyze_report.json` now also supports additive OCR advisor keys:
- `recommended_ocr_mode`
- `recommended_image_mode`
- `recommendation_reasons`
- `confidence`
- `advisor_track`

Queue manifests create sidecar artifacts beside the manifest file:
- `<manifest_stem>.queue_checkpoint.json`
- `<manifest_stem>.queue_summary.json`

## Persistence Notes
- The job log SQLite schema now includes additive run-metric/risk columns: `run_id`, `target_lang`, `total_tokens`, `estimated_api_cost`, and `quality_risk_score`.
- The job log also stores additive translation artifact paths for Gmail/honorarios reuse: `output_docx_path` and `partial_docx_path`.
- Job-form draft edits are workspace-local session state. Shared settings now persist launch fields only when a task explicitly starts, so closing or resetting one workspace does not write another window's draft inputs back into `settings.json`.
- Gmail intake bridge settings persist in GUI settings as `gmail_intake_bridge_enabled`, `gmail_intake_bridge_token`, and `gmail_intake_port`.
- In normal app launches, the Gmail intake bridge is app-level. It reuses the last active workspace only when that workspace is idle and pristine; otherwise it opens a new blank workspace for the intake automatically.
- Multi-window runs share a controller-owned reservation map keyed by the resolved run directory. A second workspace cannot start `translate`, `analyze`, `rebuild`, or `queue` if it would reuse the same run folder as an active workspace.
- Gmail intake batches now write one durable app-owned session report at `<effective_outdir>/_gmail_batch_sessions/<session_id>/gmail_batch_session.json`.
  - This is the main cross-run/debug bridge between browser handoff, per-item translation runs, and Gmail draft finalization.
  - The browser extension does not write its own report file.
- Save-to-Job-Log pre-fills those values from `run_summary.json` when available, while preserving user edit control before save.
- Save-to-Job-Log now also exposes `Open translated DOCX`, which reopens the resolved final or partial DOCX for the current run without leaving the dialog.
- Save-to-Job-Log now uses a scrollable form body with a fixed action row so create/edit flows stay usable on smaller screens without hiding `Save`, `Cancel`, `Open translated DOCX`, or the honorários action.
- In that dialog, `Run Metrics` and `Amounts` start collapsed by default on every open; the main case/service/edit fields remain visible first.
- The same Job Log payload normalization now backs create-mode save, historical full-dialog edit mode, and inline row editing, so numeric/date validation and `expected_total` / `profit` recalculation stay aligned.
- Job Log `Words` now means translated output words, with precedence: final DOCX, then partial DOCX, then `pages/page_*.txt`, then `0`.
- `expected_total` and `profit` in the Save-to-Job-Log flow are recalculated from that translated-output word count.
- Existing Job Log rows can now be updated in place either through the full `Edit Job Log Entry` dialog or by double-clicking visible cells for row-scoped inline editing.
- The Job Log window now uses a fixed `Actions` column with icon-based edit/delete controls; row deletion is confirmation-gated and only one row can be inline-edited at a time.
- Historical Job Log editing no longer requires the original `pdf_path`. Translation rows simply disable `Autofill from PDF header` when no source PDF is available, while interpretation rows can still use `Autofill from PDF header` through a manual PDF picker fallback; `Open translated DOCX` still works when stored translated DOCX paths resolve.
- Job Log columns now auto-fit visible headers by default, remain user-resizable, persist their widths in settings, and overflow through a horizontal scrollbar instead of squeezing the table to the viewport.
- Save/Edit Job Log now uses selection-only guarded combos for fixed vocab fields such as `Job type`, `Lang`, and case/service entity or city; `Court Email` stays editable.
- Court-email resolution is now shared across metadata autofill, Save/Edit Job Log, and Gmail draft flows:
  - exact document emails always win
  - priority-page header extraction retries the same page's full text when no usable email is found
  - same-local-part saved variants are normalized with canonical `tribunais.org.pt` preference ahead of alternates such as `.gov.pt`
  - inferred or ambiguous recipients stay visible in the Job Log dialog and block Gmail draft creation until `Court Email` is manually confirmed
- Editable Job Log and honorários dates now use one shared Monday-first calendar picker while still accepting manual `YYYY-MM-DD` typing. The same shared control also backs inline Job Log date editing.
- The Job Log now supports additive interpretation fields and behavior on top of translation rows:
  - `job_type == "Interpretation"` switches the full dialog to interpretation-first editing
  - blank/manual interpretation rows can be opened from `Job Log > Add...`
  - interpretation notification imports keep the local `pdf_path` when present
  - interpretation photo imports stay image-only and do not create a PDF-backed row contract
  - translation-only inputs are hidden in interpretation mode instead of shown as inactive clutter
  - the primary visible date in interpretation mode is the service date
  - interpretation distance is shown as one visible one-way value in the UI, keyed by `service_city`, and mirrored internally into outbound/return storage for compatibility
  - `Service same as Case` defaults on for interpretation unless an explicit different service location already exists
  - profile-backed distance defaults are reused automatically by service city, and newly entered one-way values are persisted back to that profile-city mapping on save
- Interpretation honorarios now use a kind-aware document branch:
  - manual interpretation rows can generate a local honorarios DOCX directly from the Job Log dialog
  - notification PDF and photo/screenshot imports prefill interpretation case/service values before the user confirms the row
  - interpretation honorarios exports use the responsive/scrollable profile-backed export dialog
  - interpretation honorarios close with `service_date` when it is a valid ISO date, even if the DOCX is generated before or after the hearing day
  - manual/local interpretation exports still stay local-doc only
  - Gmail-started interpretation notice intake can create one threaded Gmail reply draft with the generated honorarios DOCX only
- Gmail draft attachment reuse for honorarios now prefers known translated output artifacts in this order: final DOCX path, partial DOCX path, exact `run_id` recovery, then a manual `.docx` picker only as the final fallback.
- If a legacy historical row needs one manual translated-DOCX selection, the app persists that choice back into the row so the picker should not appear again for that same row.
- Gmail intake batch downloads, interpretation-notice staging data, and confirmed per-item results are kept in memory only for the active Gmail intake session. They are cleared on reset, failure paths, app shutdown, or successful finalization.
- Gmail batch draft finalization uses an immutable staged copy of each translated DOCX rather than trusting the mutable user-facing output path directly.

## Queue Behavior Notes
- Queue execution is sequential and checkpoint-aware.
- Queue cancellation is cooperative and leaves untouched jobs resumable instead of converting them into failures.

## Gmail Intake Batch Workflow
- This workflow is Windows-only and starts from Gmail web in Edge/Chromium, not from a second Gmail OAuth stack inside the app.
- A Manifest V3 extension on `https://mail.google.com/*` posts exact Gmail message context to a token-protected localhost bridge bound only to `127.0.0.1`.
- The extension now self-heals stale Gmail tabs by reinjecting its content script when needed and shows visible Gmail-page banner errors instead of failing silently.
- On real toolbar clicks, the Edge native host now auto-starts the current repo checkout through `tooling/launch_qt_build.py` when the Gmail bridge is configured but not already running.
- The intake contract is fail-closed: if the browser cannot identify exactly one open Gmail message, the app is not listening, or the bearer token is wrong, the handoff stops immediately.
- If the app cannot bind the localhost bridge port, the UI now shows a visible `Gmail intake bridge unavailable` state instead of looking idle.
- The app fetches only the exact intake message through Windows `gog`, resolves the Gmail account in this order, and no other order:
  1. explicit Settings `gmail_account_email`
  2. intake `account_email` if that account is authenticated in `gog`
  3. single authenticated Gmail account from `gog`
  4. otherwise stop with a clear Settings/preflight error
- The attachment review step shows only supported, non-inline attachments from that exact message. Inline/signature/media junk stays hidden.
- The review dialog first selects the Gmail intake workflow kind:
  - `Translation` keeps the existing multi-attachment translation batch flow
  - `Interpretation notice` handles exactly one selected PDF/image court notice that should not be translated
- The attachment review step also includes the target-language selector for the whole Gmail batch, and the selected language is pushed back into the main app UI before preparation starts.
- The review dialog now also supports per-attachment start-page selection and an in-app attachment preview before preparation begins.
- PDF previews use a lazy continuous-scroll viewer so the user can inspect the document. Page `1` is always the default first page to translate; use `Start from this page` only when the batch should begin later. Image attachments remain single-page and always start at page `1`.
- The Gmail attachment preview now coalesces resize-driven rescaling instead of recomputing scaled preview geometry on every live resize tick, which reduces visible jitter while dragging the window.
- Previewed attachments are cached temporarily and reused during `Prepare selected attachments` when still valid so the batch does not redownload the same file unnecessarily.
- If the current output folder is stale or missing, Gmail batch startup recovers automatically in this order: current valid output folder, valid `default_outdir`, then `Downloads`.
- Completed checkpoints with missing page artifacts are treated as stale and are not reused as resumable state.
- Arabic runs now insert a Word review gate before Save-to-Job-Log opens. The dialog auto-opens the DOCX in Word, offers `Align Right + Save`, auto-continues after a detected save, and still allows manual save plus `Continue now` / `Continue without changes` when automation or reopen fails.
- Selected attachments are translated one at a time. After each successful translation, the app opens Save to Job Log and requires a confirmed save before continuing.
- For Arabic Gmail batch items, the DOCX saved after that review gate is the reviewed artifact later used by the downstream batch item flow.
- A Gmail batch remains valid only while every confirmed item resolves to the same `case_number`, `case_entity`, `case_city`, and `court_email`. Any mismatch stops the batch and tells the user to split it into separate replies.
- Save-to-Job-Log and Gmail batch finalization now share the same court-email resolver. Exact document emails win; if the address is only inferred from saved suggestions or conflicting saved variants exist, the dialog shows that state and Gmail draft creation stops until `Court Email` is corrected or manually confirmed.
- After all selected attachments are translated and confirmed, the user may generate one honorarios DOCX for the batch and one Gmail reply draft in the original thread. The app attaches all translated DOCXs plus that single honorarios DOCX and never auto-sends.
- If the user picks an existing translated filename when saving honorários, the app auto-renames the honorários file instead of overwriting the translation.
- Gmail draft creation now blocks duplicate attachment paths and contaminated translated artifacts (for example, a translated DOCX path that actually contains honorários content).
- Arabic failures now surface additive diagnostics such as `validator_defect_reason`, `ar_violation_kind`, and limited sampled offending snippets in run artifacts and the stop dialog.

## Operational Guidance
- Windows-native GUI launch is canonical for this repo:
  - attached launch: `python -m legalpdf_translate.qt_app`
  - detached Windows launch: `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'`
- `python -m legalpdf_translate.qt_gui` remains a valid GUI compatibility entrypoint, but `qt_app` is the canonical docs command.
- On Windows, the beginner-friendly manual launch path is `Launch LegalPDF Translate.bat` in the repo root. It uses the same canonical Qt launcher helper instead of duplicating startup logic.
- Open another workspace from `File > New Window`, `Ctrl+Shift+N`, or the `...` overflow action. `New Window` stays available even while another workspace is busy.
- The main dashboard shell should stay horizontally adaptive without a shell-level horizontal scrollbar; dense secondary tables such as Job Log may still overflow horizontally inside their own window or table viewport.
- Major dialogs and dense secondary windows should remain screen-bounded and user-resizable instead of relying on fixed geometries that can open off-screen on smaller displays.
- Duplicate run-folder blocking across windows is intentional. If two workspaces resolve to the same run directory, the second start is blocked until the owner workspace finishes or you change the effective source/output/language combination.
- Arabic DOCX review/automation is a Windows-host feature that depends on installed Microsoft Word plus PowerShell COM automation; WSL-only validation is not enough for this path.
- Screenshot-driven Qt UI work should use the fixed render contract in `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md` rather than approximate visual review.
- OCR-heavy documents should start with a small slice and safe settings:
  - `ocr_mode=always`
  - `ocr_engine=api` when local OCR is unavailable
  - `image_mode=off`
  - `workers=1`
  - `keep_intermediates=on`
  - first prove pages `1-2`, then continue in small batches
- OCR-heavy runs now use bounded per-request deadlines instead of effectively unbounded waits.
- `Cancel and wait` is still cooperative, but it is bounded by the active request deadline and persists clearer halt reasons instead of looking indefinitely hung.
- OCR-success pages stay text-first; page images remain off unless a concrete layout/quality reason justifies them.
- The GUI can show an OCR-heavy warning with an optional per-run `Apply safe OCR profile` action. It updates the current form only and does not overwrite saved defaults.
- Mouse-wheel guards now cover the main run controls, Gmail review workflow/target-language selectors, settings defaults/provider selectors, and fixed-vocabulary Job Log combos; glossary/study/tool selectors and dense table editors still keep their local plain-combo behavior.
- OCR-heavy runtime triage routes to `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`.
- Host-bound workflows that add localhost listeners, browser/app bridges, or separate handoff/run/finalization failure surfaces should also route through `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`.
- Gmail intake live validation must use the same Windows host for the signed-in Edge/Chromium Gmail tab, the Qt app, and Windows `gog`; a WSL-only smoke does not satisfy the final host-bound check.
- If Gmail shows `accepted` but the app stays idle, check port ownership first. The listener on `127.0.0.1:<gmail_intake_port>` must belong to `python.exe -m legalpdf_translate.qt_app`, not to `pytest` or another stray process.
- For future triage, the durable support packet is:
  1. Gmail banner text/screenshot when handoff failed before app intake
  2. app window title + visible bridge status
  3. `run_report.md` / `run_summary.json` for the affected translation run
  4. `gmail_batch_session.json` for batch-level finalization or draft issues

## Governance and Routing Docs
- Assistant docs index: `docs/assistant/INDEX.md`
- Machine routing map: `docs/assistant/manifest.json`
- Roadmap anchor / fresh-session resume: `docs/assistant/SESSION_RESUME.md`
- Golden rules: `docs/assistant/GOLDEN_PRINCIPLES.md`
- Workflow runbooks: `docs/assistant/workflows/`
- User guides: `docs/assistant/features/`
- External-source registry: `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`
- Local host/runtime profile: `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- Local capability inventory: `docs/assistant/LOCAL_CAPABILITIES.md`
- Host-bound integration preflight: `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
- Harness isolation and diagnostics: `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
- Project-local harness sync: `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- Roadmap governance: `docs/assistant/workflows/ROADMAP_WORKFLOW.md`

## Project Harness and Roadmap Continuity
- `implement the template files` is a project-local harness apply trigger. It reads vendored templates in `docs/assistant/templates/` as source input and updates only the local harness surfaces for this repo.
- `sync project harness` is the accepted technical alias for the same local apply behavior.
- `audit project harness` inspects vendored-template drift without editing files.
- `check project harness` runs harness validation without editing files.
- `update codex bootstrap` and `UCBS` target the reusable template system itself. They are not aliases for project-local harness sync.
- When vendored template changes alter continuity or cleanup contracts, project-local harness sync must resync the publish/docs-maintenance governance surfaces instead of stopping at routing docs and validators.
- `docs/assistant/SESSION_RESUME.md` is the roadmap anchor file and the stable first resume stop for `resume master plan`, `where did we leave off`, and equivalent fresh-session resume requests.
- Roadmap governance supports both active and dormant states. In active state, `SESSION_RESUME.md` links one active roadmap tracker and one active wave ExecPlan. In dormant roadmap state on `main`, it must explicitly say that no active roadmap is currently open and route normal tasks back to standard ExecPlan flow.
- During active worktree execution, that worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan are authoritative for live roadmap state. `main` remains the stable merged baseline and may carry a dormant roadmap anchor between roadmap-scoped threads.
- Issue memory remains a reusable repeated-issue registry. It is not normal roadmap history and it does not replace the roadmap tracker or `SESSION_RESUME.md`.

## Module Status (Bootstrap v2)
All optional modules are enabled and enforced:
- Beginner Layer
- Localization + Performance
- Issue Memory System
- Project Harness Sync
- Local Environment Overlay
- Capability Discovery
- Worktree / Build Identity
- Roadmap Governance
- Host Integration Preflight
- Harness Isolation + Diagnostics
- Reference Discovery
- Browser Automation + Environment Provenance
- Cloud Machine Evaluation + Local Acceptance Gate
- Staged Execution
- OpenAI Docs + Citation

## Canonical and Bridge Contract
- Canonical app truth lives here.
- `docs/assistant/APP_KNOWLEDGE.md` is intentionally shorter and defers here.
- Source code is final truth when documentation conflicts occur.

## Deep-Dive Supplemental References
These remain valid supplemental references for implementation detail:
- `docs/assistant/API_PROMPTS.md`
- `docs/assistant/PROMPTS_KNOWLEDGE.md`
- `docs/assistant/QT_UI_KNOWLEDGE.md`
- `docs/assistant/QT_UI_PLAYBOOK.md`
- `docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md`
- `docs/assistant/WORKFLOW_GIT_AI.md`

## Verification Commands
PowerShell:
- `python -m pytest -q`
- `python -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

POSIX:
- `python3 -m pytest -q`
- `python3 -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

## Local Python Baseline (Windows)
- Preferred interpreter: Python `3.11`.
- Preferred local environment path: `.venv311`.
- Bootstrap/recovery script: `scripts/setup_python311_env.ps1`.

If local `pip`/`pytest` fails with import errors like `html.entities` or `idna`, treat it as a machine Python issue and rebuild `.venv311`:
- `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`
- `. .\.venv311\Scripts\Activate.ps1`
