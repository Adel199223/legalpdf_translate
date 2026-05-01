# Gmail Fast-Start and Single-Window Recovery

## 1. Title
Gmail fast-start and single-window recovery

## 2. Goal and non-goals
- Goal: make a true cold-start Gmail click open or reuse exactly one LegalPDF browser surface, bring the browser listener and Gmail bridge up as early as possible, and defer non-critical diagnostics until after the first visible shell is ready.
- Goal: replace timeout-only warm-up handling with process-aware launch tracking so slow but healthy browser startup does not collapse into restart storms or stacked translucent windows.
- Non-goals:
  - redesign the Gmail workflow after the browser shell is visible
  - change translation/OCR behavior
  - introduce a new packaged runtime or non-localhost browser delivery model

## 3. Scope (in/out)
- In scope:
  - deferred browser automation preflight during browser-app startup
  - lightweight staged shell-readiness endpoint for first paint
  - process-aware Gmail native-host warm-up tracking and stale-lock cleanup
  - session-backed pending browser-surface reuse in the Gmail extension
  - staged bootstrap changes so draft prereq diagnostics do not block first paint
  - focused regression coverage for runtime, native host, and extension warm-up behavior
- Out of scope:
  - unrelated shell UI redesign
  - broader Gmail drafting/report UX changes after the workspace is hydrated
  - canonical-branch promotion/publish work in this pass

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/inline-extraction-recovery`
- Base branch: `main`
- Base SHA floor: `4e9d20e`
- Current HEAD at start: `0683f529b9adf65b7ed44051376fa21f1d6fd0b4`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree that still satisfies the approved-base floor; live validation will be tied to this worktree/build identity

## 5. Interfaces/types/contracts affected
- Additive browser API:
  - `GET /api/bootstrap/shell/ready?mode=...&workspace=...`
- Additive payload fields:
  - `automation_preflight.status`
  - `draft_prereqs.status`
  - browser launch-lock/runtime tracking fields such as `launch_pid`, `launch_started_at`, `last_checked_at`, and `listener_pid`
- Gmail native-host response contract:
  - `launch_in_progress` remains non-terminal while the launched process is alive and within the startup ceiling
  - `launch_timeout` becomes terminal only after process death or absolute timeout expiry
- Extension background behavior:
  - pending browser-surface reuse must survive service-worker restarts via `chrome.storage.session`

## 6. File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/app.py`
  - stop running browser automation preflight synchronously during app construction
  - initialize pending automation-preflight state and compute it after the server is listening
  - add a lightweight `/api/bootstrap/shell/ready` route for first-paint shell readiness
- `src/legalpdf_translate/shadow_web/static/app.js`
  - point staged shell bootstrap at `/api/bootstrap/shell/ready`
  - keep full bootstrap hydration separate from shell-ready first paint
- `src/legalpdf_translate/gmail_browser_service.py`
  - split cheap staged shell/workspace readiness from heavy bootstrap diagnostics
  - avoid running `assess_gmail_draft_prereqs()` on the staged shell-ready path
  - expose additive `draft_prereqs.status`
- `src/legalpdf_translate/gmail_focus_host.py`
  - extend launch-lock state with process-aware metadata
  - keep launch state non-terminal while the spawned process is alive or the listener/bridge is still warming
  - clear stale runtime/bridge metadata and launch locks when dead-PID evidence is found
- `extensions/gmail_intake/background.js`
  - replace the in-memory pending-browser registry with a `chrome.storage.session` backed registry
  - reuse/focus the stored pending surface during warm-up and across service-worker restarts
  - reserve hard-error messaging for terminal failures only
- Tests:
  - extend shadow web API, Gmail focus host, Gmail browser session/bootstrap, and Gmail extension tests for fast-start/staged-warm-up behavior

## 7. Tests and acceptance criteria
- Automated:
  - browser app answers the lightweight shell-ready endpoint before deferred automation preflight completes
  - shell-ready/staged bootstrap does not invoke draft-prereq shell-outs or other heavy diagnostics
  - Gmail native-host returns `launch_in_progress` while the launched process remains alive beyond the old lock window
  - stale dead-PID launch locks are cleaned before relaunch decisions
  - repeated extension clicks during warm-up reuse the same pending browser surface even after simulated service-worker restart
- Manual acceptance:
  - from a true cold start, one Gmail click opens or focuses at most one LegalPDF browser surface
  - no stacked transparent localhost windows appear
  - if startup is slow, a waiting/info message is shown and the same surface is reused
  - once the shell is visible, Gmail workspace hydration can continue in place without relaunch
  - hard failure messaging appears only after a confirmed dead launch or startup-ceiling expiry

## 8. Rollout and fallback
- Roll out on the current feature worktree first and validate against the live Gmail intake workspace.
- If the lightweight shell-ready route regresses staged bootstrap, fall back to the richer endpoint only for local operator/debug flows while keeping the new route additive and available for launcher/native-host use.

## 9. Risks and mitigations
- Risk: deferring automation preflight could hide broken browser automation until after first paint.
  - Mitigation: keep an explicit `automation_preflight.status` payload and hydrate detailed preflight state asynchronously.
- Risk: process-aware warm-up tracking could keep a dead launch around too long.
  - Mitigation: clear stale locks on dead-PID evidence and enforce a hard `120s` startup ceiling.
- Risk: persistent pending-surface tracking could strand stale tab ids after browser closure.
  - Mitigation: clear/update the session-backed registry on tab removal, observed tab refresh, and terminal failures.

## 10. Assumptions/defaults
- Fast start is the chosen default, even if some diagnostics appear after first paint.
- Existing `/api/runtime/ready` remains the listener/runtime probe; this work adds a similarly lightweight shell/bootstrap readiness path.
- The browser app remains a localhost-tab surface; the fix should improve startup semantics rather than introduce a second runtime.

## 11. Validation outcomes
- Focused regression suite passed on the feature worktree:
  - `tests/test_shadow_runtime_service.py`
  - `tests/test_shadow_web_api.py`
  - `tests/test_gmail_focus_host.py`
  - `tests/test_gmail_intake.py`
- Command outcome: `129 passed in 129.41s`
- Manual live Gmail cold-start verification is still pending after implementation; the next operator step is a true cold-start click from Gmail to confirm one visible browser surface and no translucent window stack.
