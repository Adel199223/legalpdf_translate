# Browser Qt-Parity Shell

## Goal and non-goals
- Goal: make the default browser app shell mirror the Qt app's primary working layout so `live` and `shadow` feel like the same app with different data roots.
- Goal: keep browser runtime semantics unchanged while bringing the primary browser flow into parity with Qt hierarchy and collapsed-default behavior.
- Goal: keep the current browser-native shell available only as a temporary internal fallback during rollout.
- Non-goal: add a third runtime mode.
- Non-goal: fully restyle every secondary browser surface in the first pass.
- Non-goal: modify or absorb the dirty launcher work already present in the canonical checkout.

## Scope (in/out)
- In scope:
  - browser shell layout and routing entrypoints under `src/legalpdf_translate/shadow_web/`
  - additive `ui=legacy` fallback routing for the old shell
  - Qt-like primary-flow structure for dashboard, new job, translation framing, interpretation grouping, and save/edit collapse defaults
  - focused browser regression coverage for the new default shell plus legacy fallback
  - deterministic Qt render-reference capture for the parity baseline
- Out of scope:
  - changing `mode=live|shadow` semantics or storage behavior
  - deleting secondary browser surfaces
  - full visual-polish clone work for every dialog and admin surface
  - committing or publishing the branch in this pass

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_browser_qt_parity`
- branch name: `codex/browser-qt-parity-shell`
- base branch: `main`
- base SHA: `b6f75586fed51b3965c68bdc35a6e3d58c490a0d`
- target integration branch: `main`
- canonical build status: noncanonical worktree allowed by build policy; branch contains the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`
- preserved parallel work: dirty launcher changes remain isolated in `C:\Users\FA507\.codex\legalpdf_translate` on `main`

## Interfaces/types/contracts affected
- Browser URLs keep:
  - `mode=live|shadow`
  - `workspace=<id>`
- One additive temporary UI contract:
  - `ui=legacy` serves the old browser-native shell during rollout
- Browser APIs should remain backward compatible; any parity metadata added to bootstrap must be additive only.

## File-by-file implementation steps
1. Capture the Qt reference baseline with `tooling/qt_render_review.py --preview reference_sample` and derive the shell/disclosure defaults that the browser must mirror.
2. Refactor `src/legalpdf_translate/shadow_web/app.py` to support default Qt-parity shell rendering plus non-default `ui=legacy` fallback selection.
3. Replace the default browser template in `src/legalpdf_translate/shadow_web/templates/` with a Qt-like hierarchy and preserve the current shell as a separate legacy template.
4. Update browser static modules in `src/legalpdf_translate/shadow_web/static/` so route state tracks the additive UI flag, the translation flow uses Qt-like setup/status/action grouping, and primary disclosures start collapsed by default.
5. Keep `Recent Jobs`, `Settings`, `Profile`, `Power Tools`, and `Extension Lab` reachable while limiting first-pass restyling to what is required for the new shell to read coherently.
6. Add/update targeted tests in `tests/test_shadow_web_api.py` and any focused browser-static test coverage needed for new shell contracts and the legacy fallback.

## Tests and acceptance criteria
- Reference baseline:
  - `.\.venv311\Scripts\python.exe tooling\qt_render_review.py --outdir tmp\qt_ui_review_browser_parity --preview reference_sample`
- Focused tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py`
  - plus any new focused browser test modules added in this pass
- Acceptance:
  - default browser shell reads as Qt-like in both `live` and `shadow`
  - `Advanced Settings` starts collapsed
  - translation uses explicit `Job Setup`, `Run Status`, and action-rail grouping
  - save/edit browser sections open with `Run Metrics` and `Amounts` collapsed
  - interpretation disclosure defaults mirror the Qt-derived rules used in this pass
  - `ui=legacy` still reaches the old shell without changing runtime mode behavior

## Progress notes
- The desktop shell was compacted after a live Playwright audit showed the Qt-like frame sat too low in a `1600x1000` viewport.
- The default Qt variant now uses the topbar as the effective hero/status row, matching the Qt shell more closely and removing the redundant full-width browser-only hero panel from the primary desktop flow.
- The desktop shell now wraps `Job Setup`, `Run Status`, and the action rail in a unified Qt-style dashboard frame and visually promotes the primary/danger actions to mirror the desktop footer emphasis.
- The Qt sidebar chrome was further compacted and now reuses the same dashboard icon language as the desktop app for `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, `Profile`, `Power Tools`, and `Extension Lab`.
- Route-state handling was hardened so the browser shell now respects the requested hash view immediately on first paint and on later hash changes instead of waiting for bootstrap to finish before switching away from `Dashboard`.
- Default entry behavior is now split by UI variant:
  - Qt variant without a hash opens directly to `#new-job`
  - legacy fallback without a hash still opens to `#dashboard`
- Automated route-state coverage now asserts:
  - Qt default view falls back to `new-job`
  - legacy default view falls back to `dashboard`
  - explicit hashes and later hash changes stay authoritative
- Current verified desktop geometry on the parity server places:
  - `Job Setup` at `y=153`
  - `Run Status` at `y=153`
  - `Action Rail` at `y=700`
- The primary action rail is now visibly inside the first desktop viewport while preserving the Qt-derived collapsed defaults for:
  - `Advanced Settings`
  - translation save `Run Metrics`
  - translation save `Amounts`
  - interpretation `SERVICE`
  - interpretation `RECIPIENT`
  - interpretation `Amounts`
- Remaining work in this plan is visual/user acceptance polish, not structural parity recovery.

## Rollout and fallback
- Default to the Qt-like shell immediately in this branch.
- Keep the old shell behind `ui=legacy` only as an internal migration fallback.
- Remove the fallback in a later cleanup pass after user acceptance.

## Risks and mitigations
- Risk: shell refactor breaks existing browser flows.
  - Mitigation: preserve current API contracts, keep focused browser tests green, and retain the legacy fallback during rollout.
- Risk: parity drifts into visual-clone scope and balloons.
  - Mitigation: follow Qt structure and collapsed-default behavior first, defer fine polish.
- Risk: confusion between runtime mode and UI choice.
  - Mitigation: keep `live`/`shadow` untouched and make the fallback parameter explicit and non-default.

## Assumptions/defaults
- Repo-native Qt docs, source, and render-review outputs are sufficient for the first-pass parity target.
- The first pass prioritizes behavioral parity over exact visual matching.
- The preserved dirty launcher work remains separate and should not be edited from this worktree.
