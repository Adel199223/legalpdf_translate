# Phase 2B Shared Harness Stabilization And Export

## 1. Title
Phase 2B shared harness stabilization, second-pilot support, and portable kit export

## 2. Goal and non-goals
- Goal:
  - remove `legalpdf_translate`-specific output mappings from the reusable vendored layer
  - add a repo-local overlay for `legalpdf_translate`
  - stabilize the shared preview logic so a second repo can resolve cleanly
  - export the reusable source into `bootstrap_harness_kit/` after the second pilot succeeds
- Non-goals:
  - no product/runtime logic changes
  - no direct `accessible_reader` repo-local sync changes in this repo
  - no changes to `extensions/gmail_intake/background.js`
  - no new template modules unless the second pilot proves they are required

## 3. Scope (in/out)
- In:
  - `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
  - `docs/assistant/HARNESS_OUTPUT_MAP.json`
  - `tooling/harness_profile_lib.py`
  - `tooling/preview_harness_sync.py`
  - `tests/tooling/test_harness_tools.py`
  - `bootstrap_harness_kit/`
  - this ExecPlan
- Out:
  - product/app source files
  - `accessible_reader` repo-local outputs
  - unrelated dirty-tree files

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `main`
- Base branch: `main`
- Base SHA: `00a1408f8a1f06cd1814d6d7477f44e3b8b1150f`
- Target integration branch: `main`
- Canonical build status: canonical worktree on the current branch per user instruction

## 5. Interfaces/types/contracts affected
- Shared preview contract:
  - generic template-map mappings remain reusable
  - optional repo-local `docs/assistant/HARNESS_OUTPUT_MAP.json` overlays them
  - repo-local overlay wins on collisions
  - legacy `output_mappings` inside `BOOTSTRAP_TEMPLATE_MAP.json` remain supported
- Portable export contract:
  - `bootstrap_harness_kit/` contains reusable source only, never repo-local generated outputs

## 6. File-by-file implementation steps
- Add the active ExecPlan.
- Move `legalpdf_translate` output mappings into `docs/assistant/HARNESS_OUTPUT_MAP.json`.
- Update preview resolution helpers and tests for overlay precedence plus legacy fallback.
- Re-run the shared-layer Python checks in this repo.
- If the second pilot is clean, copy the stabilized reusable source into `bootstrap_harness_kit/` and add a kit README.

## 7. Tests and acceptance criteria
- `python -m unittest tests/tooling/test_harness_tools.py`
- `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
- `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json`
- Acceptance:
  - `BOOTSTRAP_TEMPLATE_MAP.json` no longer carries `legalpdf_translate`-specific mappings
  - `legalpdf_translate` still previews cleanly through `HARNESS_OUTPUT_MAP.json`
  - exported kit contains only reusable source

## 8. Rollout and fallback
- Land the smallest generic fix first.
- If the second pilot exposes another shared gap, patch only the minimum reusable layer before export.
- Keep the legalpdf shared fix/export commit separate from the accessible_reader pilot commit.

## 9. Risks and mitigations
- Risk: repo-local assumptions remain hidden in the reusable layer.
  - Mitigation: move mappings into a repo-local overlay and test a second repo shape explicitly.
- Risk: accidental inclusion of unrelated dirty work.
  - Mitigation: stage only shared harness files and the final export folder.

## 10. Assumptions/defaults
- The known blocker is output mapping reuse, not module design.
- Python-based validation is the portable baseline for this pass.

## 11. Executed validations and outcomes
- `python -m unittest tests/tooling/test_harness_tools.py`
  - Passed.
- `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
  - Passed.
- `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json --json`
  - Passed.
  - `legalpdf_translate` still resolves with `missing_sync_targets: []` through the repo-local `HARNESS_OUTPUT_MAP.json`.
- Outcome:
  - the shared reusable layer no longer carries `legalpdf_translate`-specific output mappings
  - a second pilot repo was able to resolve cleanly without inheriting those mappings
  - `bootstrap_harness_kit/` now contains only reusable source files plus its export README
