# APP_KNOWLEDGE

This file is canonical for app-level architecture and status.

## App Summary
LegalPDF Translate is a Windows-first Python app that translates PDFs into DOCX using one-page-per-request processing for each translation job, supports sequential multi-document queue execution, supports true multi-window Qt workspaces for parallel jobs, and supports a Windows-only Gmail intake batch-reply workflow.

- Primary UI: local browser app on `127.0.0.1`.
- Secondary UI: Qt/PySide6 desktop shell.
- Secondary interface: CLI.
- Model transport: OpenAI Responses API.
- Key invariant: page-by-page translation flow, no whole-document batch request.
- Preferred day-to-day mode: browser app `live` mode.
- Explicit development/testing mode: browser `shadow` mode with isolated state roots.

## Entrypoints
- Browser app: `python -m legalpdf_translate.shadow_web.server --open`
- Browser app URL (daily use): `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job`
- Browser app URL (isolated testing): `http://127.0.0.1:8877/?mode=shadow&workspace=workspace-1#new-job`
- Browser app Gmail handoff URL: `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
- Browser review-preview URL (fixed branch-review contract): `http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job`
- Detached browser-app launcher: `python tooling/launch_browser_app_live_detached.py`
- Review-preview launcher: double-click `Launch LegalPDF Browser App (Preview).cmd` in the repo root.
- GUI: `python -m legalpdf_translate.qt_app`
- GUI compatibility shim: `python -m legalpdf_translate.qt_main`
- Beginner Windows launcher: double-click `Launch LegalPDF Translate.bat` in the repo root. It delegates to `tooling/launch_qt_build.py --worktree <repo-root>`.
- CLI: `legalpdf-translate --pdf <file> --lang EN|FR|AR --outdir <dir>`
  - Cost guardrails (optional): `--budget-cap-usd <float> --cost-profile-id <string> --budget-on-exceed warn|block`
  - Queue mode (optional): `legalpdf-translate --queue-manifest <manifest.jsonl> --rerun-failed-only true --lang EN --outdir <dir>`
- Build: `powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1`

## Browser App Shell
- The local browser app is now the preferred day-to-day interface for this repo.
- Main beginner-first browser surfaces:
  - `New Job` as the default daily landing screen
  - conditional `Gmail` for dedicated Gmail handoff/review
  - `Recent Jobs`
  - `More`, which keeps `Dashboard`, `Settings`, `Profile`, `Power Tools`, and `Extension Lab` reachable without crowding the first screen
- `New Job` is translation-first by default and keeps interpretation inside the same shell through an in-page task switcher.
- `Gmail` is a dedicated browser view for exact-message context, attachment review, and continuation into translation or interpretation; deeper Gmail session/finalization work stays in same-tab drawers instead of crowding the intake screen.
- Gmail intake now starts as one compact review-first surface instead of a stacked workspace. The first screen keeps message summary, supported attachments, workflow choice, target language, and one primary continue action visible.
- Gmail translation continuation stays bounded in browser-native secondary surfaces:
  - a focused attachment-review drawer for selection and preview
  - a `Finish Translation` drawer for save/export/review actions
  - a `Finalize Gmail Batch` drawer for the last reply step
  - a `Redo Current Attachment` path that resets only the translation-side state for the active unconfirmed Gmail attachment without resetting the whole Gmail workspace or requiring a cold start
- Gmail interpretation continuation now stays inside the same calm shell:
  - `#new-job` shows one compact `Current Interpretation Step` panel during an active Gmail interpretation session
  - the detailed work happens in a bounded `Review Interpretation` drawer instead of a persistent admin-style page stack
- `Recent Jobs` is the main secondary production route. It starts with a bounded overview of the latest saved rows and keeps deeper translation/interpretation histories collapsed until requested.
- `Settings` is a bounded operator sheet with grouped sections for defaults, OCR/Gmail integration, and diagnostics/job-log tuning.
- `Profile` keeps the primary profile and profile list on-page while the actual editor opens in a same-tab drawer.
- `Power Tools` and `Extension Lab` remain available, but they are intentionally treated as operator surfaces instead of part of the normal first-run journey.
- Browser workspace state is URL-scoped through `workspace=<id>`, so separate tabs can keep independent draft/progress state.
- `mode=live` uses the real settings, profiles, job log, outputs, and Gmail workflow.
- `mode=shadow` is the explicit isolated test mode for development and browser automation. It uses separate state roots and never silently falls back to live data.
- Browser shell readiness is now two-stage: the server must be ready and the opened localhost tab must publish a hydrated client-ready marker before the extension treats Gmail handoff as successful.
- Browser JS/CSS/module-worker assets now ship under one runtime `asset_version` so the whole module graph invalidates together. The extension compares server and client `asset_version` values and allows one exact-tab reload before declaring stale-browser-asset failure.
- Port `8877` remains the canonical daily-use/live/Gmail browser port; port `8888` is reserved for fixed branch-review previews so stale review tabs and normal work tabs do not collide.
- The preview port on `8888` never owns the real live Gmail bridge. Live Gmail extension handoff always points back to the canonical browser app on `8877`.
- `Extension Lab` is a diagnostics and simulation companion for the real Gmail extension. It does not replace the extension itself.

## Desktop UI Shell
- The desktop app now uses a dashboard-style shell instead of the older stacked utility card.
- Each top-level app window is an independent workspace under one `QApplication`.
- Main visible regions:
  - left sidebar: `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, `Profile`
  - hero row: centered `LegalPDF Translate` title and right-aligned status text
  - left card: `Job Setup`
  - right card: `Run Status`
  - bottom action rail: `Start Translate`, `Cancel`, `...`
- `Advanced Settings` stays collapsed by default inside the setup card, with a compact info affordance for extra guidance.
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
- The beginner-first primary-flow cleanup also keeps the shell lighter by default: `Run Status` uses shorter visible copy, the always-visible output-format line is hidden, Gmail review compresses provenance/output detail behind an info button, interpretation Job Log uses compact `+` vocabulary buttons plus a default-collapsed `SERVICE` section, and interpretation honorários export now uses `SERVICE`, `TEXT`, and `RECIPIENT` disclosure sections.

## Core Runtime Modules
- `src/legalpdf_translate/workflow.py`: translation pipeline orchestration.
- `src/legalpdf_translate/legal_header_glossary.py`: shared Portuguese legal-header catalog, normalization, and institutional phrase matching for EN/FR/AR glossary injection plus metadata extraction.
- `src/legalpdf_translate/cost_guardrails.py`: deterministic pre-run/post-run cost estimation and budget decisions.
- `src/legalpdf_translate/queue_runner.py`: sequential queue execution, checkpointing, and queue summaries.
- `src/legalpdf_translate/review_export.py`: review queue export to CSV and Markdown.
- `src/legalpdf_translate/gmail_intake.py`: localhost Gmail message intake bridge for exact-message handoff.
- `src/legalpdf_translate/gmail_batch.py`: exact-message Gmail fetch, attachment filtering/download, and batch-state orchestration helpers.
- `src/legalpdf_translate/gmail_draft.py`: Windows `gog` Gmail prerequisite checks and draft creation helpers.
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
12. Start from an open Gmail message in Edge/Chromium, let the native host auto-start the configured checkout when needed, review supported attachments from that exact email, then either run the translation batch flow or handle one interpretation notice attachment, with mandatory Save-to-Job-Log confirmation before the related honorarios and Gmail draft finalization and the ability to redo the current unconfirmed Gmail attachment from the same live workspace without a cold start.
13. Open multiple workspaces and translate different jobs in parallel without interrupting the current run.
14. Create or edit interpretation Job Log rows manually, from a notification PDF, from a photo/screenshot, or from a Gmail notice attachment, then generate the interpretation honorarios DOCX plus sibling PDF locally, create a fresh Gmail draft from the saved row, or create a threaded Gmail reply draft when the flow started from Gmail intake.

Recurring Portuguese court/prosecution headers now use a shared phrase-level institutional catalog across EN, FR, and AR. The translation workflow injects matched header phrases ahead of generic glossary rows, and metadata/header extraction reuses the same matcher so `case_entity` prefers the most specific institutional line instead of falling back to looser regex hits or contact-block noise.

Arabic legal-term hardening now adds a second narrow prompt-first layer on top of that shared institutional seeding: `O Juiz de Direito` is injected as a priority legal title, Portuguese legal citation abbreviations such as `n.º`, `alínea`, and `p. e p. pelos arts.` are canonicalized before glossary matching and diagnostics, `registo criminal` terminology is harmonized on the `السجل العدلي` family, and Arabic quality-risk scoring now consumes persisted numeric/citation/bidi validation counters instead of staying artificially low on citation-heavy runs.

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

For browser translation jobs, `Generate Run Report` now writes or refreshes the same `<run_dir>/run_report.md`, triggers a one-time download immediately, and leaves a persistent `Download Run Report` artifact link in the completion drawer for repeat access.

When a run comes from Gmail intake, the effective output directory also gains durable Gmail session diagnostics:
- `<outdir>/_gmail_batch_sessions/<session_id>/gmail_batch_session.json`
- `<outdir>/_gmail_interpretation_sessions/<session_id>/gmail_interpretation_session.json`

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

For Arabic target runs, persisted page-validation metadata now also feeds the quality-risk layer with numeric mismatch, citation mismatch, structure warning, bidi warning, bidi-control, and replacement-character counts so `quality_risk_score` and `review_queue` better reflect citation-heavy or mixed-direction risk.

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
- The browser app now has two explicit runtime/storage modes:
  - `live`: real settings, profiles, job log, outputs, and Gmail-linked flows
  - `shadow`: isolated test data keyed per build/worktree identity
- Browser runtime metadata records the active mode, workspace, build identity, listener ownership, and bridge provenance so live vs isolated runs stay diagnosable.
- Browser shell/bootstrap state now also records additive asset provenance:
  - `build_sha` for build identity
  - runtime `asset_version` for the served browser asset graph
  - client-ready hydration markers that the extension can probe on the opened localhost tab
- The job log SQLite schema now includes additive run-metric/risk columns: `run_id`, `target_lang`, `total_tokens`, `estimated_api_cost`, and `quality_risk_score`.
- The job log also stores additive translation artifact paths for Gmail/honorarios reuse: `output_docx_path` and `partial_docx_path`.
- Job-form draft edits are workspace-local session state. Shared settings now persist launch fields only when a task explicitly starts, so closing or resetting one workspace does not write another window's draft inputs back into `settings.json`.
- Gmail intake bridge settings persist in GUI settings as `gmail_intake_bridge_enabled`, `gmail_intake_bridge_token`, and `gmail_intake_port`.
- When the browser server is running, the browser app is the primary live Gmail bridge owner. The real extension/native host now hands off into the browser app first and falls back to Qt only when browser launch is unavailable and no healthy browser-owned bridge already exists.
- The browser-owned live Gmail bridge uses the fixed live browser workspace `gmail-intake`, and only a successful extension handoff opens or focuses `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`.
- Rejected or failed `/gmail-intake` posts stay fail-closed in Gmail and show the browser-page banner error instead of spawning the browser app workspace.
- Local source-checkout registration now prefers an app-data native-host wrapper at `AppData\\Roaming\\LegalPDFTranslate\\native_messaging\\LegalPDFGmailFocusHost.cmd` when available. That wrapper sets `PYTHONPATH` and invokes the repo venv module so local Edge handoff does not depend on a packaged host executable that Windows App Control may block.
- Browser live-bridge ownership is now guarded by port: noncanonical live listeners such as the fixed review preview on `8888` skip bridge registration and direct the extension back to the canonical live browser URL on `8877`.
- In normal app launches, the Gmail intake bridge is app-level. It reuses the last active workspace only when that workspace is idle and pristine; otherwise it opens a new blank workspace for the intake automatically.
- Multi-window runs share a controller-owned reservation map keyed by the resolved run directory. A second workspace cannot start `translate`, `analyze`, `rebuild`, or `queue` if it would reuse the same run folder as an active workspace.
- Gmail intake translation batches now write one durable app-owned session report at `<effective_outdir>/_gmail_batch_sessions/<session_id>/gmail_batch_session.json`.
- Gmail intake interpretation notice runs now write one durable app-owned session report at `<effective_outdir>/_gmail_interpretation_sessions/<session_id>/gmail_interpretation_session.json`.
  - These reports are the main cross-run/debug bridge between browser handoff, Save-to-Job-Log confirmation, honorários export, and Gmail draft finalization.
  - The browser extension does not write its own report file.
- Browser/operator diagnostics can now also generate:
  - a browser failure report when Gmail/browser preparation fails before a translation run creates a `run_dir`
  - a Gmail finalization report whenever the last-step Gmail finalization state is blocked or completed, including successful `draft_ready` completion
  - for translation runs, a first-class `run_report.md` artifact in the run folder that the completion drawer can generate/refresh directly and serve back through `Download Run Report`
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
- Editable Job Log and honorários dates now use one shared Monday-first calendar picker while still accepting manual `YYYY-MM-DD` typing. The same shared control also backs inline Job Log date editing.
- The Job Log now supports additive interpretation fields and behavior on top of translation rows:
  - `job_type == "Interpretation"` switches the full dialog to interpretation-first editing
  - blank/manual interpretation rows can be opened from `Job Log > Add... > Blank/manual interpretation entry`
  - the main window also exposes `Tools > New Interpretation Honorários...` and the same footer-overflow action for the save-first no-document path
  - interpretation notification imports keep the local `pdf_path` when present
  - interpretation photo imports stay image-only and do not create a PDF-backed row contract
  - interpretation photo/screenshot imports tolerate missing service entity or city values and keep the form editable instead of failing autofill
  - translation-only inputs are hidden in interpretation mode instead of shown as inactive clutter
  - the primary visible date in interpretation mode is the service date
  - interpretation distance is shown as one visible one-way value in the UI, keyed by `service_city`, and mirrored internally into outbound/return storage for compatibility
  - `Service same as Case` defaults on for interpretation unless an explicit different service location already exists
  - interpretation edit mode now collapses `SERVICE` by default when it simply mirrors the case, and saved entity/city add actions use compact `+` buttons plus inline help affordances instead of long visible helper copy
  - profile-backed distance defaults are reused automatically by service city, and newly entered one-way values are persisted back to that profile-city mapping on save
- Interpretation honorarios now use a kind-aware document branch:
  - manual interpretation rows can generate honorários from the Job Log dialog or from the save-first `Tools > New Interpretation Honorários...` quick action
  - notification PDF and photo/screenshot imports prefill interpretation case/service values before the user confirms the row
  - interpretation honorarios exports use the responsive/scrollable profile-backed export dialog, keep the general case/profile inputs visible first through `SERVICE`, `TEXT`, and `RECIPIENT` disclosure sections, save a DOCX first, then attempt a sibling PDF immediately without blocking the main UI
  - the export dialog keeps `Include transport/distance sentence in honorários text` on by default, but you can turn it off when transport is being handled separately and the generated text should omit that clause
  - generated interpretation honorários now auto-complete a missing case city in generic court addressees, use the revised one-line-IBAN / centered `Espera deferimento,` closing block, keep `service_date` in the body, and use the document creation day in the footer date line before the signature
  - when automatic PDF export fails, the dialog keeps the saved DOCX usable locally and offers retry/select-existing-PDF/open-folder recovery before any Gmail draft path is allowed to continue
  - manual/local interpretation exports can offer a fresh non-threaded Gmail draft when `Court Email`, Gmail prerequisites, and the generated honorários PDF are all available
  - Gmail-started interpretation notice intake can create one threaded Gmail reply draft with the generated honorários PDF only
  - when the originating Gmail message explicitly states a reply address, that address overrides weaker derived recipient guesses in the browser Gmail finalization flow
  - browser interpretation save/export/finalization now guards service-city and distance integrity: unknown cities and transport `0 km` exports are blocked until the operator confirms or adds a valid city/distance pair
- Gmail draft attachment reuse for honorarios now prefers known translated output artifacts in this order: final DOCX path, partial DOCX path, exact `run_id` recovery, then a manual `.docx` picker only as the final fallback.
- If a legacy historical row needs one manual translated-DOCX selection, the app persists that choice back into the row so the picker should not appear again for that same row.
- Gmail intake batch downloads, interpretation-notice staging data, and confirmed per-item results are kept in memory only for the active Gmail intake session. They are cleared on reset, failure paths, app shutdown, or successful finalization.
- Browser Gmail translation jobs now persist additive `gmail_batch_context` identity on the run config so the same live runtime can detect when the current attachment was already run and can offer `Redo Current Attachment` without resetting the whole Gmail workspace.
- Gmail batch draft finalization uses an immutable staged copy of each translated DOCX rather than trusting the mutable user-facing output path directly.
- Gmail honorários drafts now require the generated honorários PDF:
  - translation reply drafts attach the translated DOCX files plus the honorários PDF
  - Gmail-intake interpretation reply drafts attach the honorários PDF only
  - manual/local interpretation drafts attach the honorários PDF only
- Honorários PDF export now uses a dedicated worker/result flow:
  - Word PDF export runs off the GUI thread, so long-running Word startup or timeout paths do not freeze the visible Qt shell
  - PDF failures show a concise warning with expandable technical details instead of a raw inline PowerShell/COM dump
  - partial-success exports keep one calm recovery flow instead of stacking duplicate Gmail missing-PDF warnings

## Queue Behavior Notes
- Queue execution is sequential and checkpoint-aware.
- Queue cancellation is cooperative and leaves untouched jobs resumable instead of converting them into failures.

## Gmail Intake Batch Workflow
- This workflow is Windows-only and starts from Gmail web in Edge/Chromium, not from a second Gmail OAuth stack inside the app.
- A Manifest V3 extension on `https://mail.google.com/*` posts exact Gmail message context to a token-protected localhost bridge bound only to `127.0.0.1`.
- The extension now self-heals stale Gmail tabs by reinjecting its content script when needed and shows visible Gmail-page banner errors instead of failing silently.
- On real toolbar clicks, the native host now prefers launching the browser app live server and only falls back to Qt when browser launch is unavailable and no healthy browser-owned bridge already exists.
- After a successful prepare plus localhost POST, the extension opens or focuses the browser app at the live Gmail workspace URL instead of depending on Qt window focus.
- The intake contract is fail-closed: if the browser cannot identify exactly one open Gmail message, the app is not listening, or the bearer token is wrong, the handoff stops immediately.
- Failed or rejected localhost POST attempts stay on the current Gmail page and report the problem through the Gmail banner instead of opening a stale or empty browser-app handoff tab.
- Duplicate or still-in-progress toolbar clicks can show wait/focus guidance for the existing launch, but they should not create extra browser-app windows or tabs.
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
- The review header now starts with a compact summary banner and keeps sender/account/output-folder provenance behind an inline info button so attachment choices stay primary.
- The Gmail browser flow no longer uses a persistent session control-center page as the normal path. After handoff, the user moves through one focused intake step and then bounded same-tab drawers for review, save, export, and Gmail finalization.
- The attachment review step also includes the target-language selector for the whole Gmail batch, and the selected language is pushed back into the main app UI before preparation starts.
- The review dialog now also supports per-attachment start-page selection and an in-app attachment preview before preparation begins.
- PDF previews use a lazy continuous-scroll viewer backed by the bundled browser PDF path (`pdf.js`) instead of server-startup `PyMuPDF`. Page `1` is always the default first page to translate; use `Start from this page` only when the batch should begin later. Image attachments remain single-page and always start at page `1`.
- The Gmail attachment preview now coalesces resize-driven rescaling instead of recomputing scaled preview geometry on every live resize tick, which reduces visible jitter while dragging the window.
- Previewed attachments are cached temporarily and reused during `Prepare selected attachments` when still valid so the batch does not redownload the same file unnecessarily.
- If preview or `Prepare selected attachments` fails before a translation run exists, the Gmail browser surface preserves the current selection/start-page state, surfaces structured browser diagnostics including raw `pdf.js` worker/module URLs plus fetch/content-type details and raw browser error text, and offers a direct browser failure report action instead of requiring Power Tools-only recovery.
- If live Gmail is opened from a noncanonical build that still contains the approved-base floor, preview and prepare pause behind an explicit provenance warning until the operator either restarts from canonical `main` or continues anyway for isolated validation.
- If the current output folder is stale or missing, Gmail batch startup recovers automatically in this order: current valid output folder, valid `default_outdir`, then `Downloads`.
- Completed checkpoints with missing page artifacts are treated as stale and are not reused as resumable state.
- Translation batches now auto-start from the reviewed Gmail selection, keep the main `#new-job` shell calm, and surface the case-save/export/review actions inside a bounded `Finish Translation` drawer instead of restacking Gmail and translation dashboards together.
- Interpretation-notice handoff now transitions to one compact `Current Interpretation Step` shell plus a bounded `Review Interpretation` drawer. Gmail reply finalization stays inside that interpretation review flow instead of bouncing back to a generic Gmail session dashboard.
- Arabic runs now insert a Word review gate before Save-to-Job-Log opens. In the browser flow, the dialog auto-opens the durable DOCX in Word, waits for a manual save, and offers `Open in Word`, `Continue now`, and `Continue without changes` if save detection misses or the operator wants to skip the edit. The browser no longer auto-mutates the DOCX during this review step.
- Shared Arabic DOCX assembly now keeps mixed Arabic/Latin punctuation, identifier markers, dates, and separator bars in stable runs so manual Word right alignment no longer drags commas or bars into the wrong side of the line.
- Failed Arabic Gmail current-attachment runs now switch the handoff back into an explicit recovery state until rerun or resume produces a completed translation with a real save seed. Gmail confirmation stays blocked for failed or rebuild-only partial outputs.
- Selected attachments are translated one at a time. After each successful translation, the app opens Save to Job Log and requires a confirmed save before continuing.
- For Arabic Gmail batch items, the DOCX saved after that review gate is the reviewed artifact later used by the downstream batch item flow.
- A Gmail batch remains valid only while every confirmed item resolves to the same `case_number`, `case_entity`, `case_city`, and `court_email`. Any mismatch stops the batch and tells the user to split it into separate replies.
- After all selected attachments are translated and confirmed, the user may generate one honorários export for the batch and one Gmail reply draft in the original thread. The app saves the honorários DOCX locally, attempts a sibling PDF immediately, and attaches all translated DOCXs plus that single honorários PDF when draft creation succeeds. Interpretation-notice replies attach only the honorários PDF. The app never auto-sends.
- When the original Gmail message contains an explicit reply destination, Gmail finalization now prefers that reply address over looser case-derived recipient guesses.
- Gmail batch finalization now uses a two-tier Word readiness contract:
  - `launch_preflight` proves Word/COM can be reached
  - `export_canary` proves the same DOCX-to-PDF export path used by finalization can really produce a PDF
  - Gmail draft creation stays blocked until that export-ready path is healthy and the honorários PDF exists
- If the user picks an existing translated filename when saving honorários, the app auto-renames the honorários file instead of overwriting the translation.
- Gmail draft creation now blocks duplicate attachment paths and contaminated translated artifacts (for example, a translated DOCX path that actually contains honorários content).
- Arabic failures now surface additive diagnostics such as `validator_defect_reason`, `ar_violation_kind`, and limited sampled offending snippets in run artifacts and the stop dialog.

## Operational Guidance
- Browser-app launch is now the canonical day-to-day local entry path for this repo:
  - attached/local browser server: `python -m legalpdf_translate.shadow_web.server --open`
  - detached live launcher: `python tooling/launch_browser_app_live_detached.py`
  - default daily-use URL: `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job`
  - explicit isolated test URL: `http://127.0.0.1:8877/?mode=shadow&workspace=workspace-1#new-job`
  - Gmail handoff URL: `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
- Windows-native GUI launch is canonical for this repo:
  - attached launch: `python -m legalpdf_translate.qt_app`
  - detached Windows launch: `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'`
- `python -m legalpdf_translate.qt_gui` remains a valid GUI compatibility entrypoint, but `qt_app` is the canonical docs command.
- On Windows, the beginner-friendly manual launch path is `Launch LegalPDF Translate.bat` in the repo root. It uses the same canonical Qt launcher helper instead of duplicating startup logic.
- Use browser `live` mode for real work. Use browser `shadow` mode only when you intentionally want isolated test data and no real live Gmail bridge ownership.
- Open another browser workspace by using a different `workspace=` URL in a new tab or window. Use Qt `New Window` only when you are intentionally working in the desktop fallback shell.
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
- Gmail intake live validation must use the same Windows host for the signed-in Edge/Chromium Gmail tab, the browser app or Qt shell that owns the workflow, and Windows `gog`; a WSL-only smoke does not satisfy the final host-bound check.
- If Gmail shows `accepted` but the app stays idle, check port ownership first. The listener on `127.0.0.1:<gmail_intake_port>` should normally belong to the browser app server process, not to `pytest`, a stale server, or another stray process.
- If the browser app opens but only a shell or stale tab appears, treat that as a provenance/readiness issue first:
  - confirm `asset_version` agreement between the shell payload and the loaded tab
  - prefer one exact-tab reload or extension reload before treating it as a product regression
- Before live Gmail finalization testing, use the browser operator surfaces to check Translation Auth, OCR Provider, Native Host, and Word PDF export canary readiness instead of assuming shell launch alone proves the last-mile reply path is healthy.
- For future triage, the durable support packet is:
  1. Gmail banner text/screenshot when handoff failed before app intake
  2. browser dashboard or Qt window build identity plus visible bridge status
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
