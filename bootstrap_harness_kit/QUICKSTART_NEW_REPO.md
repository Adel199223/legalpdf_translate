# Quickstart New Repo

Use this path when the target repo is blank or only lightly initialized.

## Goal

Seed the reusable harness source first, then let Codex create the repo-local harness outputs using only the copied kit files.

## Steps

1. Copy `bootstrap_harness_kit/` into the target repo root.
2. Seed the reusable source:

```bash
python bootstrap_harness_kit/tooling/seed_bootstrap_harness.py --repo-root .
```

3. Create `docs/assistant/HARNESS_PROFILE.json`.
   Use `docs/assistant/templates/examples/HARNESS_PROFILE.template.json` or the wizard:

```bash
python tooling/bootstrap_profile_wizard.py --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --output docs/assistant/HARNESS_PROFILE.json
```

4. Run profile validation:

```bash
python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json
```

5. Run preview and write state:

```bash
python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json
```

6. Ask Codex to create the repo-local harness files from the copied kit source.
   Recommended wording:
   `Using only the copied bootstrap_harness_kit source now seeded into this repo, create the repo-local harness outputs required by HARNESS_PROFILE.json and BOOTSTRAP_STATE.json. Do not edit docs/assistant/templates/* during this sync.`

7. Re-run preview and confirm `missing_sync_targets: []`.
8. Validate any generated `docs/assistant/manifest.json` by parsing it and checking that the referenced harness paths exist.

## Notes

- For a brand-new repo, do **not** add `docs/assistant/HARNESS_OUTPUT_MAP.json` unless you discover you already have established local harness equivalents to preserve.
- The canonical reusable examples live in `docs/assistant/templates/examples/`.
