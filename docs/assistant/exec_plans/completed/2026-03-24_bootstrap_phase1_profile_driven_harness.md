# Bootstrap Phase 1 Profile-Driven Harness Upgrade

## Goal and non-goals
- Goal: apply the phase 1 bootstrap-only harness upgrade from `bootstrap-harness-upgrade (1).zip` to `legalpdf_translate`, keeping the rollout additive and backward-compatible.
- Non-goals: product/runtime code changes, user-facing feature changes, `accessible_reader` work, new worktree creation.

## Scope (in/out)
- In: vendored template additions, repo-local harness/profile/state files, Python harness tooling, validator/test updates, bootstrap workflow/prompt/template-map integration, requested commit.
- Out: app behavior, Qt/browser/Gmail runtime logic, DB/schema work, unrelated dirty-tree changes.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `main`
- Base branch: `main`
- Base SHA: `97387493eb6a449a5b47005123b95ab91882cf0c`
- Target integration branch: `main`
- Canonical build status: canonical worktree on the approved base branch per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Add `docs/assistant/HARNESS_PROFILE.json`, schema, and generated bootstrap state.
- Add phase 1 vendored bootstrap template assets and Python harness tooling.
- Extend `tooling/validate_agent_docs.dart` and its Dart test to support profile/state/registry-aware validation while preserving legacy contract behavior.
- Preserve existing manifest contract keys and local harness outputs during migration.

## File-by-file implementation steps
1. Unpack the upgrade zip to a temporary folder and copy `new-files/` into the repo root, preserving paths.
2. Create `docs/assistant/HARNESS_PROFILE.json` with the requested `legalpdf_translate` values.
3. Merge the profile-resolution insertion into `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md`.
4. Merge the resolution-first sync section into `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`.
5. Extend `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json` with the new top-level `targets` entries.
6. Update `tooling/validate_agent_docs.dart` for optional profile/state/registry loading, alias normalization, and legacy-compatible required-file behavior.
7. Update `test/tooling/validate_agent_docs_test.dart` for legacy fallback and profile/state coverage.
8. Run validation commands and iterate until all requested checks pass.
9. Commit only harness/bootstrap files with `bootstrap: add profile-driven harness phase 1`.

## Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `python -m unittest tests/tooling/test_harness_tools.py`
- `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
- `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json`
- Acceptance: all commands pass, preview resolves the expected module set, and the unrelated `extensions/gmail_intake/background.js` change remains outside the commit.

## Rollout and fallback
- Rollout: additive repo-local/vendored harness upgrade on current branch.
- Fallback: if validation fails, adjust only harness/profile/tooling files; do not broaden scope into product code.

## Risks and mitigations
- Risk: new registry outputs could falsely fail current repo validation.
- Mitigation: keep legacy required outputs/contracts as the baseline and use profile resolution only as a compatibility layer in phase 1.
- Risk: unrelated dirty change could leak into the commit.
- Mitigation: explicitly stage only the harness/bootstrap file set.

## Assumptions/defaults
- `uses_openai=true`
- `has_browser_bridge=false`
- `needs_codespaces=false`
- Stay on `main` because the user explicitly requested the current branch and no new worktree.

## Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart` -> PASS
- `dart run test/tooling/validate_agent_docs_test.dart` -> PASS (`72` cases)
- `python -m unittest tests/tooling/test_harness_tools.py` -> PASS (`4` tests)
- `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json` -> PASS
- `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json` -> PASS
- Final state: `BOOTSTRAP_STATE.json` written, expected module set resolved, unrelated `extensions/gmail_intake/background.js` left outside this work scope.
