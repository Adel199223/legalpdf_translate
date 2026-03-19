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
- Canonical daily URL: `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#dashboard`
- Gmail handoff workspace: `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job`
- Preferred detached launcher: `python tooling/launch_browser_app_live_detached.py`
- Qt status: supported secondary shell and fallback, not the lead day-to-day surface

## Browser Mode Contract
- `live` mode uses the real settings, job log, outputs, Gmail workflow, and browser-owned Gmail bridge.
- `shadow` mode is the isolated browser testing/development copy. It keeps separate state roots and does not own the real Gmail bridge.
- The real Gmail extension remains canonical. After a successful Gmail handoff, it should open or focus the browser app in the fixed live workspace `gmail-intake`.
- `Extension Lab` is the diagnostics/simulator companion for the real extension. It is not a replacement for the live extension.

## Current Architecture State
- The browser app now supports the full daily-use surface:
  - Dashboard
  - New Job
  - Recent Jobs
  - Settings
  - Profile
  - Extension Lab
  - translation workflows
  - Gmail intake/finalization
  - interpretation/honorários
  - power tools
- Browser-app live vs isolated-test mode is now a deliberate reusable system that should be preserved in project docs and later template-sync work.
- Template-folder synchronization is intentionally deferred for now. If a later task asks to sync the project harness/template files, carry this live-vs-shadow browser-app pattern forward explicitly instead of rediscovering it from thread history.

## Authoritative Worktree
- Worktree: `/mnt/c/Users/FA507/.codex/legalpdf_translate_ocr_hardening`
- Branch: `codex/ocr-hardening-roadmap`
- Stable merged baseline remains `main` on the canonical worktree for merge/publish and future dormant-roadmap continuity.

## Roadmap State
- Dormant roadmap state after OCR/runtime hardening closeout.
- No active roadmap currently open on this worktree.
- No active roadmap tracker is currently authoritative.
- Completed OCR roadmap history for reference:
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_roadmap.md`
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave1.md`
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave2.md`

## Next Concrete Action
- OCR roadmap restart is complete on this worktree.
- For new work, use normal ExecPlan flow unless the user explicitly opens a new roadmap.
- If the user asks to publish or merge this branch, follow the standard commit/publish workflow instead of reopening roadmap mode.

## Resume Order
1. Read this file.
2. Open `APP_KNOWLEDGE.md` for current product truth when implementation context is needed.
3. If historical OCR roadmap context is needed, read:
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_roadmap.md`
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave1.md`
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave2.md`
4. If the task touches browser/live-vs-shadow routing, keep the browser app `live` mode as the preferred daily-use surface unless the task explicitly requires isolated `shadow` mode.
5. Otherwise continue with normal task routing and create a standard ExecPlan only when the task warrants it.

## Authority Notes
- Issue memory is only for repeatable governance/workflow failures. It is not normal roadmap history.
- Completed roadmap and ExecPlan artifacts remain reference history, not live authority.
- This worktree is now back in dormant-roadmap mode after the OCR roadmap closeout.
- If a future roadmap is opened, its wave ExecPlan must be updated first, roadmap tracker second, and `SESSION_RESUME.md` third.
