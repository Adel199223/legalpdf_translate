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
- Authoritative worktree after publish/merge: canonical merged checkout on `main`
- Branch: `main`

## Roadmap State
- Dormant roadmap state after the browser-app closeout.
- No active roadmap currently open on this worktree.
- No active roadmap tracker is currently authoritative.

## Next Concrete Action
- For normal new work, follow normal ExecPlan flow when scope or risk requires it.
- For browser product work, start from the browser app in `live` mode unless the task explicitly calls for isolated testing in `shadow` mode.
- If the user later asks to sync the project harness/template layer, use the current browser-app live/shadow system as one of the main reusable patterns to preserve.
- Do not require a `NEXT_STAGE_X` continuation token unless a new staged roadmap is explicitly opened.

## Resume Order
1. Read this file.
2. Open `APP_KNOWLEDGE.md` for current product truth.
3. If the task touches browser/live-vs-shadow routing, read:
   - `docs/assistant/APP_KNOWLEDGE.md`
   - `docs/assistant/features/APP_USER_GUIDE.md`
   - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
4. If the task touches reusable harness/template strategy later, preserve the browser-app live/shadow pattern without editing templates unless the user explicitly asks for template sync.
5. Otherwise continue with normal task routing and create a standard ExecPlan only when the task warrants it.

## Authority Notes
- Issue memory is only for repeatable governance/workflow failures. It is not normal roadmap history.
- Completed roadmap and ExecPlan artifacts remain reference history, not live authority.
- During active roadmap work in a separate worktree, that worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan become authoritative for live roadmap state.
- When roadmap work is dormant on `main`, this file must say so explicitly instead of pointing at stale feature-branch artifacts.
