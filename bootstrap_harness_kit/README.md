# Bootstrap Harness Kit

`bootstrap_harness_kit/` is the portable reusable source for the profile-driven assistant harness. It is designed for **AI-assisted** adoption in a new or existing repo.

This phase does **not** claim a full scripted generator for every repo-local harness file. It does provide a self-contained seed path, profile/preview tooling, examples, and enough source material for Codex to create the repo-local harness without consulting files outside this kit.

## What This Kit Includes

Reusable source-of-truth files:

- `docs/assistant/templates/**`
- `docs/assistant/schemas/HARNESS_PROFILE.schema.json`
- `docs/assistant/CODEX_ENVIRONMENT.md`
- `.vscode/mcp.json.example`
- `tooling/bootstrap_profile_wizard.py`
- `tooling/check_harness_profile.py`
- `tooling/preview_harness_sync.py`
- `tooling/harness_profile_lib.py`
- `tooling/seed_bootstrap_harness.py`

Canonical reusable examples live under:

- `docs/assistant/templates/examples/`

## What This Kit Does Not Include

These are repo-local outputs and must be written or generated per repo:

- `docs/assistant/HARNESS_PROFILE.json`
- `docs/assistant/runtime/BOOTSTRAP_STATE.json`
- `docs/assistant/HARNESS_OUTPUT_MAP.json`
- `README.md`
- `agent.md`
- `docs/assistant/manifest.json`
- `docs/assistant/START_HERE.md`
- `docs/assistant/SAFE_COMMANDS.md`
- `docs/assistant/TERMS_IN_PLAIN_ENGLISH.md`
- `docs/assistant/DIAGNOSTICS.md`
- `docs/assistant/QA_CHECKS.md`
- `docs/assistant/runtime/CANONICAL_BUILD.json`
- `docs/assistant/workflows/SESSION_RESUME.md`
- app-specific files such as `APP_KNOWLEDGE.md` or `BROWSER_BRIDGE.md`

## Recommended Adoption Order

1. Copy `bootstrap_harness_kit/` into the target repo.
2. Seed the reusable source into the target repo.
3. Create `docs/assistant/HARNESS_PROFILE.json`.
4. Run preview and write `docs/assistant/runtime/BOOTSTRAP_STATE.json`.
5. Run the AI-assisted local harness sync.
6. Run validation.
7. Add `docs/assistant/HARNESS_OUTPUT_MAP.json` only if the repo already has established local harness equivalents.

## Seed Command

From the target repo root after copying this folder into it:

```bash
python bootstrap_harness_kit/tooling/seed_bootstrap_harness.py --repo-root .
```

Use `--overwrite` only when you intentionally want to refresh kit-managed source files already copied into the repo.

## AI-Assisted Sync Boundary

This kit is self-contained for:

- seeding reusable source
- creating and validating a harness profile
- previewing the resolved module/output set
- AI-guided sync of repo-local harness files
- portable validation of the preview/state flow

This kit is **not** yet a full scripted generator for every repo-local output in a blank repo.

## Next Reading

- `QUICKSTART_NEW_REPO.md`
- `QUICKSTART_EXISTING_REPO.md`
- `docs/assistant/templates/NEW_PROJECT_BOOTSTRAP_WORKFLOW.md`
- `docs/assistant/templates/examples/`
