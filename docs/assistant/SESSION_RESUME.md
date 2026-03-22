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
- The real Gmail extension remains canonical. After a successful Gmail handoff, it should open or focus the browser app in the fixed live workspace `gmail-intake`.
- Port `8877` remains the canonical daily-use/live/Gmail browser port.
- Port `8888` is review-preview only and must not become the real live Gmail bridge owner.

## Current Architecture State
- The browser-first Gmail flow is the current canonical product experience on this repo:
  - `#new-job` remains the default landing screen
  - `#gmail-intake` remains the dedicated Gmail extension handoff screen
  - the primary browser shell stays reduced to `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
  - Gmail handoff is compact and review-first
  - translation continuation stays bounded in finish/finalize surfaces instead of restacking large Gmail and translation pages
  - interpretation continuation stays in one compact current-step shell plus a bounded same-tab review drawer
  - secondary/browser-operator routes stay reachable, but no longer dominate the normal path
- Local source-checkout Edge native-host registration now prefers the app-data wrapper `LegalPDFGmailFocusHost.cmd` so Gmail handoff does not depend on a packaged host executable that Windows App Control may block.
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
- Publish/merge requests should follow the standard commit/publish workflow.

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
