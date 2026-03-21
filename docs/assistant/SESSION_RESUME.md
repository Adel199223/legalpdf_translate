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
- Fixed review-preview launcher: `Launch LegalPDF Browser App (Preview).cmd`
- Qt status: supported secondary shell and fallback, not the lead day-to-day surface

## Browser Mode Contract
- `live` mode uses the real settings, job log, outputs, Gmail workflow, and browser-owned Gmail bridge.
- `shadow` mode is the isolated browser testing/development copy. It keeps separate state roots and does not own the real Gmail bridge.
- The real Gmail extension remains canonical. After a successful Gmail handoff, it should open or focus the browser app in the fixed live workspace `gmail-intake`.
- `Extension Lab` is the diagnostics/simulator companion for the real extension. It is not a replacement for the live extension.

## Current Architecture State
- The browser-to-Qt alignment program is complete on this worktree:
  - `#new-job` remains the default landing screen
  - `#gmail-intake` remains the dedicated Gmail extension handoff screen
  - the primary browser shell stays reduced to `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
  - Gmail handoff is compact and review-first
  - translation completion is bounded in a finish surface instead of stacked into the home shell
  - interpretation uses a seeded-review flow with a bounded same-tab review drawer
  - remaining secondary routes now use calmer bounded sheets/drawers instead of sprawling operator-console pages
- Preview/stale-tab contract:
  - port `8877` remains the canonical daily-use/live/Gmail browser port
  - port `8888` is the fixed review-preview port for this feature worktree
  - if a cached review tab on `8888` shows browser fetch failures, restart the preview and reopen the fixed preview URL instead of treating it as the daily app being down
- Browser-app live vs isolated-test mode is now a deliberate reusable system that should be preserved in project docs and later template-sync work.
- Template-folder synchronization is intentionally deferred for now. If a later task asks to sync the project harness/template files, carry this live-vs-shadow browser-app pattern forward explicitly instead of rediscovering it from thread history.

## Authoritative Worktree
- Worktree: `/mnt/c/Users/FA507/.codex/legalpdf_translate_browser_qt_parity`
- Branch: `codex/browser-qt-parity-shell`
- Stable merged baseline remains `main` on the canonical worktree for merge/publish and future dormant-roadmap continuity.

## Roadmap State
- Dormant roadmap state after browser-to-Qt alignment closeout.
- No active roadmap currently open on this worktree.
- No active roadmap tracker is currently authoritative.
- The prior browser beginner-first plan is now historical reference:
  - `docs/assistant/exec_plans/completed/2026-03-20_browser_beginner_first_simple_shell.md`
- Completed browser-to-Qt roadmap history for reference:
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_master_plan.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage1.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage2.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage3.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage4.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage5.md`
- Completed OCR roadmap history for reference:
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_roadmap.md`
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave1.md`
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave2.md`

## Next Concrete Action
- Browser-to-Qt alignment closeout is complete on this worktree.
- For new work, use normal ExecPlan flow unless the user explicitly opens a new roadmap.
- If the user asks to publish or merge this branch, follow the standard commit/publish workflow instead of reopening roadmap mode.

## Resume Order
1. Read this file.
2. Open `APP_KNOWLEDGE.md` for current product truth when implementation context is needed.
3. If historical browser-to-Qt roadmap context is needed, read:
   - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_master_plan.md`
   - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage1.md`
   - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage2.md`
   - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage3.md`
   - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage4.md`
   - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage5.md`
4. If historical OCR roadmap context is needed, read:
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_roadmap.md`
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave1.md`
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave2.md`
5. If the task touches browser/live-vs-shadow routing, keep the browser app `live` mode as the preferred daily-use surface unless the task explicitly requires isolated `shadow` mode.
6. Otherwise continue with normal task routing and create a standard ExecPlan only when the task warrants it.

## Authority Notes
- Issue memory is only for repeatable governance/workflow failures. It is not normal roadmap history.
- Completed roadmap and ExecPlan artifacts remain reference history, not live authority.
- This worktree is now back in dormant-roadmap mode after the browser-to-Qt alignment closeout.
- If a future roadmap is opened, its wave ExecPlan must be updated first, roadmap tracker second, and `SESSION_RESUME.md` third.
