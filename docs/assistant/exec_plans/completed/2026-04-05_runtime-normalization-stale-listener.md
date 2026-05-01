# Runtime Normalization and Stale Listener Hardening

## 1. Title
Runtime normalization and stale-listener recovery verification

## 2. Goal and non-goals
- Goal: make live browser/Gmail translation runs reliably execute the intended repo/runtime, detect stale listener reuse, and surface enough provenance to prove which runtime produced a run.
- Goal: normalize the user-facing local launch surfaces so the current machine stops drifting to dead shortcuts, stale checkout paths, or noncanonical interpreters.
- Non-goal: redesign the translation pipeline itself beyond the runtime provenance and launch-surface work needed to prove the inline extraction recovery is actually running.

## 3. Scope (in/out)
- In scope:
  - runtime build identity and content-sensitive fingerprints
  - stale listener detection/restart for browser live launch and Gmail auto-launch
  - additive runtime provenance in browser payloads, runtime metadata, Gmail/browser report context, `run_summary.json`, and `run_report.md`
  - repo-managed Windows launcher normalization and current-machine shortcut normalization
  - rerun/verification against `Auto.pdf`
- Out of scope:
  - new OCR/recovery heuristics unless the normalized rerun still proves the existing recovery path is insufficient

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/inline-extraction-recovery`
- Base branch: `main`
- Base SHA floor: `4e9d20e`
- Current HEAD at start: `0683f52`
- Target integration branch: `main`
- Canonical build status: noncanonical worktree that still contains the approved-base floor; prove locally first, then normalize back onto canonical `main`

## 5. Interfaces/types/contracts affected
- `RuntimeBuildIdentity` gains additive provenance fields for dirty state and content-sensitive runtime fingerprint.
- Browser/runtime payloads and runtime metadata JSON gain additive launcher/listener provenance.
- `RunConfig` and generated run artifacts gain additive runtime provenance context.
- Desktop shortcut creation behavior changes from packaged-EXE-first to repo-launcher-first.

## 6. File-by-file implementation steps
- `src/legalpdf_translate/build_identity.py`
  - add dirty-state detection and runtime fingerprint generation from repo runtime inputs
  - include new provenance fields in `RuntimeBuildIdentity`
- `src/legalpdf_translate/shadow_runtime.py`
  - add runtime metadata comparison/probe helpers, launcher-context helpers, and listener termination/restart helpers
- `tooling/launch_browser_app_live_detached.py`
  - replace blind port reuse with match-or-restart logic
- `src/legalpdf_translate/gmail_focus_host.py`
  - use the same listener decision/restart logic before Gmail-triggered browser auto-launch
- `src/legalpdf_translate/shadow_web/app.py` and `src/legalpdf_translate/shadow_web/server.py`
  - expose additive runtime provenance in browser payloads and preserve launcher-context data
  - add a lightweight runtime endpoint for health/provenance checks
- `src/legalpdf_translate/types.py`, `src/legalpdf_translate/translation_service.py`, `src/legalpdf_translate/workflow.py`, `src/legalpdf_translate/run_report.py`
  - thread runtime provenance into run config, run summary, and run report output
- `scripts/create_desktop_shortcut.ps1`, `scripts/build_qt.ps1`, `scripts/register_edge_native_host.ps1`
  - normalize launcher creation around repo-root launchers and `.venv311`
- local desktop launch surfaces
  - regenerate the Qt shortcut and browser live command file from the repo-managed scripts/helpers

## 7. Tests and acceptance criteria
- Unit tests for runtime fingerprint changes on dirty worktree content changes without a new git SHA
- Launcher tests proving:
  - matching healthy listener is reused
  - metadata-missing, probe-unhealthy, and fingerprint-mismatched listeners are restarted
- Shortcut/native-host tests proving repo-root launcher targeting and `.venv311` preference
- Acceptance rerun with `Auto.pdf`:
  - page 4 is no longer plain direct-text/not-requested/no-image
  - runtime provenance is present in artifacts
  - point 10 preserves `498,03 €`

## 8. Rollout and fallback
- First validate from the current worktree/runtime.
- After proof, normalize the machine-facing live launch surfaces so they target canonical `main`.
- If canonical promotion is not possible in this pass, leave the launcher normalization ready and document the exact remaining merge step.

## 9. Risks and mitigations
- Risk: killing the wrong listener on port `8877`.
  - Mitigation: compare runtime metadata PID first, then bound listener PID, and only terminate when reuse is unsafe.
- Risk: shortcut normalization regresses packaged-build expectations.
  - Mitigation: keep packaged EXE support optional and use repo launchers as the default safe path.
- Risk: provenance fields drift across payloads.
  - Mitigation: centralize provenance construction and reuse it for browser payloads and run artifacts.

## 10. Assumptions/defaults
- `.venv311` is the canonical managed environment.
- Repo-root launchers are the preferred source of truth for local usage on this machine.
- The current translation defect should be treated as a stale-runtime problem until a normalized rerun proves otherwise.
