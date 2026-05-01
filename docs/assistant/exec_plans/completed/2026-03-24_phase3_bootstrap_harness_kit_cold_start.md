# Phase 3 Bootstrap Harness Kit Cold-Start Hardening

## 1. Title
Phase 3 bootstrap_harness_kit cold-start validation and hardening

## 2. Goal and non-goals
- Goal:
  - prove `bootstrap_harness_kit/` is standalone for AI-assisted reuse in a new repo
  - harden the kit docs and seed path so a future repo can adopt it without reaching back into `legalpdf_translate`
  - run a scratch cold-start simulation using only the exported kit
- Non-goals:
  - no product/app logic changes in `legalpdf_translate`
  - no product/app logic changes in `accessible_reader`
  - no third real repo pilot
  - no tracked scratch output
  - no changes to `extensions/gmail_intake/background.js`

## 3. Scope (in/out)
- In:
  - `bootstrap_harness_kit/**`
  - this ExecPlan
- Out:
  - app/runtime code
  - repo-local harness outputs outside the kit
  - unrelated dirty-tree files

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `main`
- Base branch: `main`
- Base SHA: `cd0d5527be46fecdc849265047c8b824f4f8ae03`
- Target integration branch: `main`
- Canonical build status: current canonical worktree per active branch

## 5. Interfaces/types/contracts affected
- Portable kit contract:
  - kit must include every reusable source file its own template map depends on
  - kit must provide a standalone reusable-source seed path
  - docs must state clearly that this phase supports AI-assisted sync, not a full scripted generator
- Seed helper contract:
  - copy reusable source files only
  - never generate repo-local outputs

## 6. File-by-file implementation steps
- Audit the kit against the real reusable core and add any missing reusable source files.
- Expand kit docs with README plus two quickstarts.
- Add a small portable seed helper script.
- Run a cold-start scratch simulation using only the kit.
- If the scratch run exposes hidden dependencies, patch the kit and rerun.

## 7. Tests and acceptance criteria
- Verify every template-map target exists inside the kit.
- Verify the kit contains the same reusable source set as the current repo core.
- Search the kit for repo-specific references and machine-path assumptions.
- In scratch:
  - seed reusable source from the kit only
  - create a minimal profile
  - run profile check and preview
  - create the minimal AI-assisted sync outputs
  - rerun preview and require `missing_sync_targets: []`
  - parse generated `docs/assistant/manifest.json` and verify referenced paths exist
- Acceptance:
  - no hidden dependency on host-repo files outside `bootstrap_harness_kit/`
  - docs explain exact adoption order and the optional `HARNESS_OUTPUT_MAP.json` rule
  - only real kit-hardening files are committed

## 8. Rollout and fallback
- Prefer the smallest kit-only fix for any exposed dependency.
- Keep scratch output outside git and delete it after validation.
- Do not create a tracked zip by default; any zip is optional and local only.

## 9. Risks and mitigations
- Risk: the kit still assumes host-repo files that were never exported.
  - Mitigation: audit template-map targets and run a cold-start scratch proof using only the kit.
- Risk: over-claiming full scripted sync.
  - Mitigation: document the AI-assisted limitation explicitly in README and quickstarts.

## 10. Assumptions/defaults
- Existing `docs/assistant/templates/examples/*.json` stay the canonical reusable examples unless scratch validation proves they are insufficient.
- The minimal real blocker already known is the missing exported `docs/assistant/CODEX_ENVIRONMENT.md`.

## 11. Executed validations and outcomes
- Kit audit results:
  - every `BOOTSTRAP_TEMPLATE_MAP.json` target template now exists inside `bootstrap_harness_kit/`
  - the exported kit contains the required reusable source set:
    - `docs/assistant/templates/**`
    - `docs/assistant/schemas/HARNESS_PROFILE.schema.json`
    - `docs/assistant/CODEX_ENVIRONMENT.md`
    - `.vscode/mcp.json.example`
    - `tooling/bootstrap_profile_wizard.py`
    - `tooling/check_harness_profile.py`
    - `tooling/preview_harness_sync.py`
    - `tooling/harness_profile_lib.py`
  - search for repo-specific references and machine-local paths returned no matches after README cleanup
- Scratch cold-start proof:
  - scratch root: `C:\Users\FA507\AppData\Local\Temp\bootstrap_harness_kit_phase3_20260324_223051`
  - copied only `bootstrap_harness_kit/` into the scratch repo
  - ran `python bootstrap_harness_kit/tooling/seed_bootstrap_harness.py --repo-root .`
  - created a minimal `cli_tool` + `lite` `docs/assistant/HARNESS_PROFILE.json`
  - ran `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
  - ran `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json --json`
  - created only the repo-local outputs requested by preview using kit-local source material
  - reran preview and got `missing_sync_targets: []`
  - parsed `docs/assistant/manifest.json` and confirmed all referenced harness paths existed
- Outcome:
  - the kit is self-contained for seeding, profile validation, preview/state generation, AI-assisted repo-local sync, and portable validation
  - the kit still does not claim a full scripted generator for blank-repo harness outputs
