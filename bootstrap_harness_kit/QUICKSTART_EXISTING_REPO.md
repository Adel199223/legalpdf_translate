# Quickstart Existing Repo

Use this path when the target repo already has docs, harness files, or established local equivalents that should be preserved.

## Steps

1. Copy `bootstrap_harness_kit/` into the target repo root.
2. Seed the reusable source:

```bash
python bootstrap_harness_kit/tooling/seed_bootstrap_harness.py --repo-root .
```

3. Create or update `docs/assistant/HARNESS_PROFILE.json`.
4. Run:

```bash
python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json
python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json
```

5. Inspect the preview result.
6. If the repo already has established local harness equivalents, add `docs/assistant/HARNESS_OUTPUT_MAP.json` before the AI-assisted sync.
7. Ask Codex to sync the project harness without editing `docs/assistant/templates/*`.
8. Re-run preview and local validation until the resolved sync targets are fully satisfied.

## When To Add HARNESS_OUTPUT_MAP.json

Add it only if the repo already has established equivalents for generic outputs such as:

- a repo-local runbook instead of a generic `START_HERE.md`
- an existing local environment doc instead of `LOCAL_ENVIRONMENT.md`
- an existing session resume file outside the generic output path

Keep this file repo-local. Do not push those mappings back into the reusable kit unless they are truly generic.

## Good Defaults

- start with the closest archetype from `docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
- keep `mode = standard` unless the repo is tiny or unusually integration-heavy
- use the examples under `docs/assistant/templates/examples/` to avoid guessing field shapes
