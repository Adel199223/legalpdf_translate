# Browser-to-Qt UX Alignment Master Plan

## Summary
- Goal: align the browser app with the Qt information hierarchy while keeping the browser app clearly web-native and calmer for daily use.
- Goal: replace the remaining operator-console feel with one focused main shell, staged Gmail intake, and bounded secondary work in same-tab dialogs/drawers.
- Preserve `mode=live|shadow`, default `#new-job`, Gmail handoff on `#gmail-intake`, daily app ownership on `127.0.0.1:8877`, review preview on `127.0.0.1:8888`, and temporary `ui=legacy`.
- Execution was hard stage-gated. Stages 1 through 5 are complete, and the implementation program is ready for review and publish flow.

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_browser_qt_parity`
- branch name: `codex/browser-qt-parity-shell`
- base branch: `main`
- update target: PR `#30`

## Authority order during execution
1. Active stage packet in `docs/assistant/exec_plans/active/`
2. This master ExecPlan
3. `docs/assistant/SESSION_RESUME.md`

## Route-to-Qt parity matrix
| Surface | Current browser state | Qt authority target | Planned stage |
| --- | --- | --- | --- |
| Main shell | Calm default shell exists, but technical chrome is still too visible | Focused shell first, secondary detail behind compact affordances | Stage 1 |
| Gmail handoff | Dedicated route, but still reads like a full workspace | Compact review flow with decision-first controls and deferred provenance/session detail | Stage 2 |
| Translation completion | Status, overflow, artifacts, and save flow are split across multiple areas | One bounded completion/save surface with fixed actions and collapsed detail sections | Stage 3 |
| Interpretation | Autofill plus long admin form still share the same working page | Seeded review flow with redundant sections collapsed until needed | Stage 4 |
| Secondary tools | Settings/profile/power tools/lab remain reachable but still feel product-level | Dialog/table/preview style operator surfaces, not part of the main journey | Stage 5 |

## Stage breakdown
### Stage 1: Parity lock and shell simplification
- Create the stage-gated continuity docs and parity matrix.
- Keep primary nav limited to `New Job`, conditional `Gmail`, `Recent Jobs`, and `More`.
- Hide build/listener/runtime/debug cards and routine diagnostics from the calm daily shell.
- Keep operator surfaces behind `More`, with explicit operator-detail reveal and automatic failure reveal.

### Stage 2: Gmail intake becomes a compact review surface
- Keep `#gmail-intake` but reduce it to message summary, attachment choice, workflow choice, target language, and one continue action.
- Move provenance, session state, and finalization flows into contextual drawers/dialogs shown only when relevant.

### Stage 3: Translation completion becomes a bounded finish-the-job flow
- Keep the main translation home limited to `Job Setup`, `Run Status`, and `Action Rail`.
- Remove inline save-to-job-log from the default page and replace it with a bounded completion surface.

### Stage 4: Interpretation becomes seeded review
- Turn autofill into a short intake step or overlay.
- Keep `SERVICE`, `TEXT`, `RECIPIENT`, and `Amounts` collapsed unless the current state makes them necessary.

### Stage 5: Whole-app secondary surface cleanup
- Align settings, review, job-log, preview, save/edit, and export routes with Qt-like bounded dialog/table/preview behavior.
- Keep `Recent Jobs` as the main secondary production page and de-emphasize admin/testing views.

## Tests and acceptance
- Stage 1: route/nav coverage, operator-chrome hidden-by-default checks, and direct-hash preservation.
- Stage 2: Gmail handoff Playwright and focused Gmail route tests.
- Stage 3: translation completion/save surface tests with collapsed `Run Metrics` and `Amounts`.
- Stage 4: interpretation seeded-review and disclosure-default tests.
- Stage 5: wide/narrow parity review, operator-surface reachability, and failure-visibility audit.

## Assumptions and locked defaults
- Same-tab dialogs/drawers are the default secondary-surface model.
- Gmail handoff starts with focused intake review first.
- Qt is authoritative for information hierarchy, collapse defaults, and when dense work moves off the main shell.
- `ui=legacy` remains available until the full alignment program is accepted and a cleanup pass explicitly removes it.
