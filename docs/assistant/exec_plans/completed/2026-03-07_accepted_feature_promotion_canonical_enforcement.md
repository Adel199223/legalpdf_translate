# Accepted Feature Promotion and Canonical Build Enforcement

## Goal
Make the approved base branch and canonical runnable build explicit, machine-checked, and validator-enforced so accepted features do not remain stranded on side branches and routine app testing always defaults to the correct build.

## Non-Goals
- No product feature changes.
- No branch deletion or merge execution in this pass.
- No broader docs sync outside the governance/build-identity surface.

## Scope
- `docs/assistant/runtime/CANONICAL_BUILD.json`
- build identity helpers / launcher
- governance workflow docs
- validator rules and tests

## Worktree Provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/ai-docs-bootstrap`
- base branch: `feat/ai-docs-bootstrap`
- base SHA: `4e9d20e`
- target integration branch: `feat/ai-docs-bootstrap`
- canonical build status: canonical repo-root build

## Interfaces / Contracts
- canonical build policy adds approved-base fields
- noncanonical launch override remains allowed only for branches that still contain the approved-base floor
- branches missing approved-base lineage are blocked from normal launch/testing

## File Plan
1. Extend `CANONICAL_BUILD.json` with approved-base branch/floor fields.
2. Update `build_identity.py` and `launch_qt_build.py` to enforce approved-base lineage separately from canonical-worktree status.
3. Update governance docs to encode:
   - merge immediately after acceptance
   - latest approved base lock
   - canonical launch default
   - noncanonical override rule
4. Extend docs validator/tests to enforce the new governance markers.
5. Update Qt/build-identity tests to cover approved-base summary and stale-branch launch blocking.

## Validation
- `python -m pytest -q tests/test_launch_qt_build.py tests/test_qt_main_smoke.py tests/test_qt_app_state.py`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

## Risks / Mitigations
- Risk: hardening blocks legitimate feature-branch launches.
  - Mitigation: keep `--allow-noncanonical`, but only for branches that still contain the approved-base floor.
- Risk: existing docs partially overlap and drift.
  - Mitigation: validator enforcement for approved-base promotion markers.
