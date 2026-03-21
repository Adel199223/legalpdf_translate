# SESSION_RESUME

## First Resume Stop
Open this file first for:
- `resume master plan`
- `where did we leave off`
- `what is the next roadmap step`
- any fresh session that needs the current recommended product entrypoint

This file is the roadmap anchor file, the staged-execution anchor file, and the stable fresh-session anchor.

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
- The browser app is in an active browser-to-Qt alignment program:
  - `#new-job` remains the default landing screen
  - `#gmail-intake` remains the dedicated Gmail extension handoff screen
  - the primary browser shell stays reduced to `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
  - Stage 1 is complete: routine operator chrome is hidden by default and revealed through `More`, the explicit operator-details toggle, or failure states
  - Stage 2 is complete: Gmail handoff is now a compact review-first surface with session/finalization actions moved into a bounded drawer
  - Stage 3 is complete: translation completion now opens in one bounded finish surface instead of stacking save/artifact work into the main page
  - Stage 4 is complete: interpretation now uses a seeded-review flow with a bounded same-tab review drawer, calmer default disclosures, and Gmail follow-up actions deferred until they are actually relevant
  - Stage 5 is complete: remaining secondary routes now align with calmer Qt-style bounded sheets/drawers, and the whole-app cleanup pass is finished
- Preview/stale-tab contract:
  - port `8877` remains the canonical daily-use/live/Gmail browser port
  - port `8888` is the fixed review-preview port for this feature worktree
  - if a cached review tab on `8888` shows browser fetch failures, restart the preview and reopen the fixed preview URL instead of treating it as the daily app being down
- Browser-app live vs isolated-test mode is now a deliberate reusable system that should be preserved in project docs and later template-sync work.
- Template-folder synchronization is intentionally deferred for now. If a later task asks to sync the project harness/template files, carry this live-vs-shadow browser-app pattern forward explicitly instead of rediscovering it from thread history.

## Authoritative Worktree
- Worktree: `/mnt/c/Users/FA507/.codex/legalpdf_translate_browser_qt_parity`
- Branch: `codex/browser-qt-parity-shell`
- Active master ExecPlan on this worktree:
  - `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_master_plan.md`
- Active stage packet on this worktree:
  - `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage5.md`
- Stable merged baseline remains `main` on the canonical worktree for merge/publish and future dormant-roadmap continuity.

## Roadmap State
- Active staged execution is open on this worktree.
- The active roadmap tracker is:
  - `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_master_plan.md`
- The active wave execplan is:
  - `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage5.md`
- Authority order for this thread:
  1. `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage5.md`
  2. `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_master_plan.md`
  3. `docs/assistant/SESSION_RESUME.md`
- The prior browser beginner-first plan is now historical reference:
  - `docs/assistant/exec_plans/completed/2026-03-20_browser_beginner_first_simple_shell.md`
- Completed browser-to-Qt stage history for reference:
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage1.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage2.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage3.md`
  - `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage4.md`
- Completed OCR roadmap history for reference:
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_roadmap.md`
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave1.md`
  - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave2.md`

## Next Concrete Action
- The staged browser-to-Qt alignment implementation program is complete.
- Use `8877` for daily/live behavior and `8888` for branch review preview while reviewing the final aligned shell.
- The next action is human acceptance review, PR review, or publish flow. No additional stage token is required.

## Resume Order
1. Read this file.
2. Open `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage5.md` for the final implementation packet.
3. Open `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_master_plan.md` for the full staged roadmap.
4. Open `APP_KNOWLEDGE.md` for current product truth when implementation context is needed.
5. If historical OCR roadmap context is needed, read:
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_roadmap.md`
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave1.md`
   - `docs/assistant/exec_plans/completed/2026-03-19_ocr_hardening_wave2.md`
6. If the task touches browser/live-vs-shadow routing, keep the browser app `live` mode as the preferred daily-use surface unless the task explicitly requires isolated `shadow` mode.
7. If more UX work is requested, treat this staged alignment program as complete and open a new follow-on plan instead of expecting another stage token.

## Authority Notes
- Issue memory is only for repeatable governance/workflow failures. It is not normal roadmap history.
- Completed roadmap and ExecPlan artifacts remain reference history, not live authority.
- This worktree is in active staged execution for browser-to-Qt alignment.
- The active stage packet is the first source for current implementation detail.
- The master ExecPlan is the second source for roadmap intent and stage ordering.
