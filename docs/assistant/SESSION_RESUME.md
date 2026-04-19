# SESSION_RESUME

## First Resume Stop
Open this file first for:
- `resume master plan`
- `where did we leave off`
- `what is the next roadmap step`
- any fresh session that needs the current recommended product entrypoint

This file is the roadmap anchor file and the stable fresh-session anchor.

## Current Recommended Entry
- Preferred daily-use surface: local browser app in `live` mode
- Canonical daily URL: `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job`
- Gmail handoff workspace: `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
- Preferred detached launcher: `python tooling/launch_browser_app_live_detached.py`
- Fixed review-preview URL: `http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job`
- Qt status: supported secondary shell and fallback, not the lead day-to-day surface

## Browser Mode Contract
- `live` mode uses the real settings, job log, outputs, Gmail workflow, and browser-owned Gmail bridge.
- `shadow` mode is the isolated browser testing/development copy. It keeps separate state roots and does not own the real Gmail bridge.
- The real Gmail extension remains canonical. After a successful Gmail click, the current Gmail tab redirects into the fixed live workspace `gmail-intake`; `Return to Gmail` restores the captured source Gmail URL.
- Live Gmail is hard-blocked on noncanonical runtimes. `Restart from Canonical Main` is the only supported recovery path for normal work.
- Port `8877` remains the canonical daily-use/live/Gmail browser port.
- Port `8888` is review-preview only and must not become the real live Gmail bridge owner.

## Current Architecture State
- The browser-first Gmail flow is the current canonical product experience on this repo:
  - `#new-job` remains the default landing screen
  - `#gmail-intake` remains the dedicated Gmail extension handoff screen
  - `Prepare selected` is prepare-only and opens `#new-job` in a prepared state that waits for explicit `Start Translate`
  - the primary browser shell stays reduced to `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
  - Gmail handoff is compact and review-first
  - translation continuation stays bounded in finish/finalize surfaces instead of restacking large Gmail and translation pages
  - interpretation continuation stays in one compact current-step shell plus a bounded same-tab review drawer
  - secondary/browser-operator routes stay reachable, but no longer dominate the normal path
- Canonical Edge native-host registration now targets `LegalPDFGmailFocusHost.exe`; the old `.cmd` wrapper is diagnostic fallback only and must not be the normal live target because it can surface visible CMD/PseudoConsole churn.
- Browser Gmail handoff now uses per-click `handoff_session_id`, same-tab redirect, immediate post-redirect `/gmail-intake`, and client/server `asset_version` diagnostics so stale service workers, stale tabs, and `Pending load` states do not masquerade as accepted handoffs.
- Browser-managed Gmail PDF preview/prepare now uses the bundled browser `pdf.js` path instead of depending on `PyMuPDF` during browser startup.
- Gmail batch finalization readiness now depends on a real Word export canary, not a launch-only Word probe.
- Gmail translation honorários metadata now prefers the specific local court-unit city over a broader comarca city. The accepted April 19 live closeout on build `0b2687f` confirmed `case_city=Cuba`, `service_city=Cuba`, populated nested `result.artifacts.run_report_path`, `Processed pages: 2/2` for an intentional page-2 start, and finalization `draft_ready` with a Cuba honorários PDF.
- Report-restored completed Gmail translation batches are now secondary recovered history only; a fresh extension handoff or loaded Gmail message should supersede them automatically.
- Browser-app live vs isolated-test mode remains a deliberate reusable system that should be preserved in later template-sync work.

## Authoritative Worktree
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch: `main`
- Canonical status: stable merged baseline and the default authority for fresh sessions

## Roadmap State
- Dormant roadmap state.
- No active roadmap currently open on this worktree.
- No active roadmap tracker is currently authoritative.
- Recent completed Gmail/browser closeout history for reference:
  - `docs/assistant/exec_plans/completed/2026-04-05_gmail_fresh_handoff_priority.md`
  - `docs/assistant/exec_plans/completed/2026-04-05-gmail-run-report-provenance.md`
  - `docs/assistant/exec_plans/completed/2026-04-05_browser_run_report_artifacts.md`
  - `docs/assistant/exec_plans/completed/2026-04-19_gmail_honorarios_local_court_city_fix.md`
  - `docs/assistant/exec_plans/completed/2026-04-03_gmail_redo_current_attachment.md`
  - `docs/assistant/exec_plans/completed/2026-04-03_arabic_legal_risk_hardening.md`
  - `docs/assistant/exec_plans/completed/2026-03-30_gmail_finalization_word_pdf_reliability.md`
  - `docs/assistant/exec_plans/completed/2026-03-30_browser_asset_provenance_gmail_prepare.md`
  - `docs/assistant/exec_plans/completed/2026-03-30_first_open_gmail_hydration_recovery.md`
  - `docs/assistant/exec_plans/completed/2026-03-30_gmail_prepare_pdf_worker_reportability.md`
  - `docs/assistant/exec_plans/completed/2026-03-30_windows_blocked_pdf_browser_recovery.md`
  - `docs/assistant/exec_plans/completed/2026-03-29_web_app_end_to_end_stabilization.md`
  - `docs/assistant/exec_plans/completed/2026-03-29_gmail_inline_preview_regression.md`
  - `docs/assistant/exec_plans/completed/2026-03-29_cold_start_reliability_rebuild.md`
  - `docs/assistant/exec_plans/completed/2026-03-28_browser_translation_auth_diagnostics.md`
  - `docs/assistant/exec_plans/completed/2026-03-28_browser_gmail_autostart_repair.md`
  - `docs/assistant/exec_plans/completed/2026-03-28_gmail_intake_regression_fixes.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_gmail_focus_shell_layout_fix.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_gmail_review_parity_stage1.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_gmail_review_declutter.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_gmail_post_handoff_qt_parity.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_gmail_bridge_host_fix.md`
  - `docs/assistant/exec_plans/completed/2026-03-22_gmail_reply_address_fix.md`
  - `docs/assistant/exec_plans/completed/2026-03-22_interpretation_browser_ux_polish.md`
  - `docs/assistant/exec_plans/completed/2026-03-22_interpretation_city_distance_integrity.md`
- Historical browser-to-Qt roadmap history remains available under `docs/assistant/exec_plans/completed/`.

## Next Concrete Action
- No active roadmap needs resume handling.
- For new work, use normal ExecPlan flow unless the user explicitly opens a new roadmap.
- Publish/merge requests should follow the standard commit/publish workflow and should not start a new Gmail/runtime thread while accepted live fixes remain only in local commits.

## Resume Order
1. Read this file.
2. Open `APP_KNOWLEDGE.md` for current product truth when implementation context is needed.
3. If the task touches Gmail/browser parity or native-host behavior, read the recent completed Gmail/browser closeout ExecPlans listed above.
4. If older browser-to-Qt roadmap context is needed, use the completed browser-to-Qt packets under `docs/assistant/exec_plans/completed/`.
5. If older OCR roadmap context is needed, use the completed OCR packets under `docs/assistant/exec_plans/completed/`.
6. Otherwise continue with normal task routing and create a standard ExecPlan only when the task warrants it.

## Authority Notes
- Issue memory is only for repeatable governance/workflow failures. It is not normal roadmap history.
- Completed roadmap and ExecPlan artifacts remain reference history, not live authority.
- If a future roadmap is opened, its wave ExecPlan must be updated first, roadmap tracker second, and `SESSION_RESUME.md` third.
