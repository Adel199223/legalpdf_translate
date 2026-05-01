# PROJECT_HARNESS_SYNC_WORKFLOW

## What This Workflow Is For
Applying the vendored template set in `docs/assistant/templates/` to this repo's local harness without editing the template folder itself.

## Expected Outputs
- Updated project-local routing docs, manifest contracts, workflows, and validator coverage that match the current vendored template set.
- Explicit boundary between local harness application and global bootstrap maintenance.
- Resynced continuity/cleanup governance docs when vendored template changes alter resume, merge-cleanup, or scratch-output rules.
- Successful harness validation after the local apply pass.

## When To Use
- The user says `implement the template files`.
- The user says `sync project harness`.
- The user says `audit project harness`.
- The user says `check project harness`.
- Vendored template files changed and this repo now needs its local harness brought up to that newer source of truth.

Don't use this workflow when:
- the user wants to maintain or refactor the reusable template system itself
- the work is normal product implementation or ordinary docs sync with no vendored-template apply request

Instead use:
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md` for touched-scope docs sync after normal implementation
- `update codex bootstrap` / `UCBS` when the user explicitly wants template-system maintenance

## What Not To Do
- Do not edit `docs/assistant/templates/*` during project-local harness application.
- Do not treat vendored templates as cleanup candidates, ignored files, or disposable scaffolding.
- Do not auto-commit or auto-push at the end of a harness sync pass unless the user separately asks for commit/publish work.
- Do not overwrite repo-specific adaptations unless they conflict with a bootstrap floor contract from the vendored template set.

## Resolution-first sync workflow

Before applying a harness sync, run the profile and registry resolution step:

1. validate `docs/assistant/HARNESS_PROFILE.json`
2. resolve the effective module set from:
   - archetype defaults
   - mode defaults
   - boolean feature flags
   - `enabled_modules`
   - `disabled_modules`
3. preview the proposed file surface and module set
4. write `docs/assistant/runtime/BOOTSTRAP_STATE.json`
5. apply the sync
6. re-run validators and update any affected local docs or manifests

### Recommended commands

```bash
python tooling/check_harness_profile.py   --profile docs/assistant/HARNESS_PROFILE.json   --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json

python tooling/preview_harness_sync.py   --profile docs/assistant/HARNESS_PROFILE.json   --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json   --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json
```

### Migration note

During the first rollout, treat missing profile files as a legacy repo case and fall back to the current behavior. New or actively maintained repos should gain `HARNESS_PROFILE.json` as soon as possible.

## Primary Files
- `agent.md`
- `AGENTS.md`
- `README.md`
- `docs/assistant/INDEX.md`
- `docs/assistant/manifest.json`
- `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
- `docs/assistant/SESSION_RESUME.md`
- `tooling/validate_agent_docs.dart`
- `test/tooling/validate_agent_docs_test.dart`

## Minimal Commands
PowerShell:
```powershell
Get-Content docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
```

POSIX:
```bash
sed -n '1,220p' docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
```

## Targeted Tests
- `dart test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- The local harness drifts from the vendored template set:
  - read `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json` first
  - load only the vendored template files needed for the requested scope
  - patch project-local docs, workflows, manifest contracts, and validators in that order
- Template changes affect continuity or merge cleanup behavior:
  - resync `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - resync `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - resync local deterministic review/debug tooling docs when scratch-path rules changed
- The work accidentally starts targeting `docs/assistant/templates/*`:
  - stop
  - restate the boundary between local harness apply and global bootstrap maintenance
  - continue only on project-local files unless the user explicitly authorizes template-folder work
- Validator coverage still assumes an older template set:
  - update `tooling/validate_agent_docs.dart` and `test/tooling/validate_agent_docs_test.dart`
  - do not normalize the vendored template folder to fit the old validator
- Vendored template changes and local harness changes coexist in one dirty tree:
  - keep vendored template sync and project-local harness implementation as separate logical commit scopes by default
- The requested change is inspection only:
  - switch to `audit project harness` or `check project harness` behavior
  - report drift without editing files by default

## Handoff Checklist
1. State whether the pass was `implement`, `sync`, `audit`, or `check`.
2. Confirm that `docs/assistant/templates/*` was treated as read-only source input.
3. State the local apply order used:
   1. `agent.md` and `docs/assistant/manifest.json`
   2. bridge/routing docs
   3. workflow docs
   4. validator and test coverage
   5. roadmap docs when continuity contracts changed
   6. cleanup/publish and scratch-output guidance when continuity or merge cleanup behavior changed:
      - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
      - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
      - local deterministic review/debug tooling docs
4. Confirm whether continuity/cleanup governance docs were resynced during the pass.
5. If vendored template changes and local harness changes coexisted, state the intended logical commit split.
6. Confirm the boundary between local harness apply and `update codex bootstrap` / `UCBS`.
7. Report validator/test results.
