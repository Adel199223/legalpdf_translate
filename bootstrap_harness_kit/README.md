# Bootstrap Harness Kit

This folder is a portable export of the reusable profile-driven harness source. Copy it into another repo when you want to seed the vendored bootstrap layer without bringing along app-specific outputs.

## What Belongs In This Kit

- `docs/assistant/templates/**`
- `docs/assistant/schemas/HARNESS_PROFILE.schema.json`
- `tooling/bootstrap_profile_wizard.py`
- `tooling/check_harness_profile.py`
- `tooling/preview_harness_sync.py`
- `tooling/harness_profile_lib.py`
- `.vscode/mcp.json.example`

These files are the reusable source of truth.

## What Does Not Belong In This Kit

Do not treat repo-local outputs as reusable source. Generate or write these per repo:

- `docs/assistant/HARNESS_PROFILE.json`
- `docs/assistant/runtime/BOOTSTRAP_STATE.json`
- repo-local `docs/assistant/BROWSER_BRIDGE.md`
- app-specific `README.md`
- app-specific `APP_KNOWLEDGE.md`
- any repo-local `docs/assistant/HARNESS_OUTPUT_MAP.json`

## How To Copy It Into Another Repo

1. Copy the contents of this folder into the target repo root, preserving paths.
2. Create `docs/assistant/HARNESS_PROFILE.json` for that repo.
3. Run the preview flow to resolve modules and write `docs/assistant/runtime/BOOTSTRAP_STATE.json`.
4. Apply the repo-local harness sync for that repo.
5. Validate the result.

## Recommended Order

```text
create HARNESS_PROFILE.json
-> preview
-> sync
-> validate
```

## Suggested Commands

```bash
python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json
python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json
```

## Optional Repo-Local Overlay

If a repo already has established local harness equivalents, add a repo-local `docs/assistant/HARNESS_OUTPUT_MAP.json`. Keep that overlay outside this kit so the reusable layer stays generic.
