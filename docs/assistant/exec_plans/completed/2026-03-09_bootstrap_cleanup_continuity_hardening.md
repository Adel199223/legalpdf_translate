# Bootstrap Cleanup Continuity Hardening

## 1. Title
Bootstrap cleanup and continuity hardening

## 2. Goal and non-goals
- Goal:
  - upstream the recent cleanup lessons into the reusable bootstrap templates
  - make roadmap continuity valid in both active and dormant states
  - make bare `push` cleanup-complete by contract
  - standardize ignored `tmp/` scratch-root guidance for deterministic assistant artifacts
  - extend bootstrap validator coverage so template drift is caught automatically
- Non-goals:
  - no project-local harness reapply in this pass
  - no product/app feature changes
  - no template-map schema change

## 3. Scope (in/out)
- In:
  - `docs/assistant/templates/BOOTSTRAP_ROADMAP_GOVERNANCE.md`
  - `docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md`
  - `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md`
  - `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
  - `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
  - `docs/assistant/templates/BOOTSTRAP_PROJECT_HARNESS_SYNC_POLICY.md`
  - `docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`
  - `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
  - bootstrap marker coverage in `tooling/validate_agent_docs.dart`
  - bootstrap validator regressions in `test/tooling/validate_agent_docs_test.dart`
- Out:
  - project-local non-template harness files
  - template schema version changes unless JSON shape changes
  - unrelated workflow/module redesign

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/bootstrap-cleanup-continuity-hardening`
- Base branch: `main`
- Base SHA: `62390cb91760ea936395d303fcd53cb2718ad640`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path

## 5. Interfaces/types/contracts affected
- Bootstrap prompt + trigger model
- Bootstrap roadmap-governance contract
- Bootstrap core commit/push and scratch-output contract
- Bootstrap issue-memory promotion examples
- Bootstrap validator required marker sets and regression fixtures

## 6. File-by-file implementation steps
- Add dormant-roadmap and closeout-complete semantics to the roadmap-governance template.
- Add cleanup-complete bare `push`, follow-up PR repair default, and ignored `tmp/` scratch-root guidance to the core contract.
- Sync the bootstrap prompt, trigger matrix, update policy, harness-sync policy, issue-memory system, and template map topics to the same model.
- Extend bootstrap marker validation and validator tests so drift around dormant roadmap state, cleanup-complete push semantics, and ignored scratch-root guidance fails automatically.

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- Acceptance:
  - bootstrap docs agree on dormant-roadmap support, cleanup-complete `push`, follow-up PR repair default, and ignored `tmp/` scratch-root guidance
  - bootstrap validator coverage fails if those markers drift
  - no project-local harness files are edited as part of this template pass

## 8. Rollout and fallback
- Land as a template-only/bootstrap-validator pass.
- If a new marker is too project-specific, remove or generalize it instead of hardcoding repo-local behavior into templates.

## 9. Risks and mitigations
- Risk: leaking repo-specific cleanup details into universal templates.
  - Mitigation: keep wording generic and process-level; no app/tool-specific filenames except reusable contracts like `SESSION_RESUME.md`.
- Risk: validator drift between template docs and bootstrap prompt.
  - Mitigation: update both marker sets and regression tests in the same pass.

## 10. Assumptions/defaults
- Missed post-merge repair defaults to a follow-up branch/PR.
- `SESSION_RESUME.md` remains as a dormant anchor on `main`.
- Ignored `tmp/` is the standard bootstrap scratch root unless a generated repo defines a stricter local equivalent.

## 11. Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart`
  - Passed.
- `dart run test/tooling/validate_agent_docs_test.dart`
  - Passed (`60 cases`).
- `dart run tooling/validate_workspace_hygiene.dart`
  - Passed.
- Outcome:
  - bootstrap roadmap governance, core commit/push semantics, update policy, issue-memory guidance, prompt, triggers, and template-map topics now agree on dormant-roadmap support, cleanup-complete bare `push`, follow-up branch/PR repair default, and ignored `tmp/` scratch-root guidance
