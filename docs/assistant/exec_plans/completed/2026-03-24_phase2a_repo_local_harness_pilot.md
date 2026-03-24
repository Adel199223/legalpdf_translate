# Phase 2A Repo-Local Harness Pilot

## 1. Title
Phase 2A repo-local harness pilot from the vendored template system

## 2. Goal and non-goals
- Goal:
  - run the real `legalpdf_translate` harness pilot against the vendored template set and current profile/state
  - keep the sync focused on repo-local harness surfaces
  - correct the top-level README so it reflects the browser-primary architecture
  - fix only the minimum output-mapping gap if the pilot exposes one
- Non-goals:
  - no `accessible_reader` work
  - no product/runtime behavior changes
  - no unrelated bootstrap redesign
  - no changes to `extensions/gmail_intake/background.js`

## 3. Scope (in/out)
- In:
  - `README.md`
  - `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json` only if a minimum mapping fix is required
  - `tooling/harness_profile_lib.py` and `tooling/preview_harness_sync.py` only if needed to support the minimum mapping fix
  - `tests/tooling/test_harness_tools.py` only if tooling changes
  - this ExecPlan
- Out:
  - `accessible_reader`
  - `docs/assistant/templates/*` except the minimum mapping fix if the pilot proves it is required
  - product/app source logic
  - unrelated dirty-tree files

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `main`
- Base branch: `main`
- Base SHA: `97387493eb6a449a5b47005123b95ab91882cf0c`
- Target integration branch: `main`
- Canonical build status: canonical worktree on `main`; the user explicitly requested current-branch execution for this harness pilot

## 5. Interfaces/types/contracts affected
- Repo-local harness pilot contract:
  - the vendored template system must distinguish generic resolved outputs from repo-local equivalent apply targets when this repo already has established harness surfaces
- README onboarding contract:
  - beginner-facing entrypoint must describe browser-primary, Qt-secondary, CLI-secondary, and Gmail bridge support accurately

## 6. File-by-file implementation steps
- Re-run profile validation and preview resolution.
- If the pilot exposes unmapped generic outputs, add the smallest repo-local output-mapping metadata needed to the vendored template map and teach preview tooling to surface mapped sync targets without changing the generic module resolution.
- Update `README.md` to reflect the browser-primary architecture and beginner-friendly quickstart.
- Re-run harness validation.

## 7. Tests and acceptance criteria
- `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
- `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `python -m unittest tests/tooling/test_harness_tools.py` if harness tooling or template-map behavior changes
- Acceptance:
  - sync stays limited to repo-local harness scope
  - README is browser-primary and beginner-clear
  - repo-specific browser/Qt/CLI/Gmail truths remain intact
  - unrelated `extensions/gmail_intake/background.js` remains uncommitted

## 8. Rollout and fallback
- Prefer a repo-local sync with no template edits.
- If preview shows a real output-mapping blocker, land the smallest template-map/tooling fix needed for this repo and re-run the pilot.
- Keep staging scoped so no stash is required unless commit hygiene truly needs it.

## 9. Risks and mitigations
- Risk: widening this into abstract bootstrap redesign.
  - Mitigation: limit template changes to repo-local output mapping only if the pilot proves necessary.
- Risk: accidental inclusion of unrelated dirty-tree work.
  - Mitigation: stage only explicit harness files.

## 10. Assumptions/defaults
- The likely phase 2A blocker is an output-mapping gap, not a missing module.
- Existing repo-local surfaces remain canonical unless the minimum mapping fix needs to point at them explicitly.

## 11. Executed validations and outcomes
- `python tooling/check_harness_profile.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json`
  - Passed.
- `python tooling/preview_harness_sync.py --profile docs/assistant/HARNESS_PROFILE.json --registry docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json --write-state docs/assistant/runtime/BOOTSTRAP_STATE.json --json`
  - Passed.
  - Resolved generic outputs now map to repo-local sync targets with `missing_sync_targets: []`.
- `python -m unittest tests/tooling/test_harness_tools.py`
  - Passed.
- `dart run tooling/validate_agent_docs.dart`
  - Passed.
- `dart run tooling/validate_workspace_hygiene.dart`
  - Passed.
- `dart run test/tooling/validate_agent_docs_test.dart`
  - Passed (`72 cases`).
- Outcome:
  - the pilot exposed a real output-mapping gap between generic resolved outputs and `legalpdf_translate`'s existing repo-local harness surfaces
  - the minimum fix was an additive template-map plus preview-tool mapping layer, not a new module
  - `README.md` now reflects the browser-primary architecture while preserving Windows-first, Qt, CLI, and Gmail bridge truths
  - no stash was needed and the unrelated `extensions/gmail_intake/background.js` change remains outside this scope
