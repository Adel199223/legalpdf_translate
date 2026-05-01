# Gmail Focus Shell Layout Fix

## Closeout Note
- Absorbed and superseded by the later Gmail browser parity and post-handoff closeout passes on `feat/gmail-review-parity-browser`.
- Keep this file only as early-stage history for the final merged Gmail/browser workflow.

## Title
Repair the browser-app Gmail focus shell so the live extension handoff lands on a real single-panel workspace instead of a squeezed left-column layout.

## Goal and non-goals
- Goal: make `workspace=gmail-intake#gmail-intake` render as a centered, simplified Gmail intake surface in the live browser app.
- Goal: preserve the working native-host and extension handoff path already active on this machine.
- Non-goal: redesign the Gmail workflow, create a new route, or rework the native-host registration again.

## Scope (in/out)
- In scope: browser-app Gmail focus-shell CSS precedence, focused-shell regression coverage, targeted live verification.
- Out of scope: extension manifest changes, native-host protocol changes, installer work, Qt workflow redesign.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/gmail-focus-shell-layout-fix`
- Base branch: `main`
- Base SHA: `e990ef3fca7aad1ed29d4f121bf05b405f37cf31`
- Target integration branch: `main`
- Canonical build status: canonical worktree, live browser app under test on port `8877`

## Interfaces/types/contracts affected
- Browser route contract remains `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
- `document.body.dataset.shellMode === "gmail-focus"` remains the focus-shell state contract
- No API payload or native-host contract changes

## File-by-file implementation steps
- Update `src/legalpdf_translate/shadow_web/static/style.css` so the Gmail focus-shell overrides are declared late and beat the general Qt Gmail layout rules.
- Keep `state.js`, `app.js`, `gmail.js`, and template behavior intact unless verification shows a functional gap.
- Extend browser-app tests to guard the focus-shell CSS contract in addition to route-state assertions.

## Tests and acceptance criteria
- `python -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py`
- Add and run a focused layout regression test that checks the stylesheet ordering/selector contract.
- `dart run tooling/automation_preflight.dart`
- Playwright verification against the live Gmail URL must confirm:
  - `shellMode` is `gmail-focus`
  - `.app-shell` resolves to a single-column grid
  - Gmail hero is hidden
  - screenshot shows one centered Gmail panel without the empty right-side shell

## Rollout and fallback
- Restart or refresh the live browser app on port `8877` after the CSS fix lands.
- If the live page still shows the old layout, close the browser-app window and reopen through the extension to force a fresh page load.

## Risks and mitigations
- Risk: later Qt CSS rules override focus-shell rules again.
  - Mitigation: move focus-shell rules to final precedence and add regression coverage.
- Risk: live browser app serves stale assets from an old process.
  - Mitigation: re-verify the running port owner and inspect the served CSS/DOM directly.

## Assumptions/defaults
- The current broken page is the correct Gmail route with incorrect final CSS precedence.
- The focused Gmail intake design should stay as the default landing surface, with `Open Full Workspace` as the explicit expansion path.
