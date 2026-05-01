# Targeted Project Harness Reapply From Updated Templates

## 1. Title
Gap-only project-local harness reapply from the updated vendored templates

## 2. Goal and non-goals
- Goal:
  - bring the local harness-sync workflow, manifest, and validator coverage up to the newer vendored template contracts
  - keep the already-aligned roadmap, publish, scratch-path, and issue-memory surfaces unchanged unless a direct contradiction is found
  - preserve the template folder as read-only source input during this pass
- Non-goals:
  - no edits under `docs/assistant/templates/*`
  - no broad project-wide harness rewrite
  - no app/runtime feature changes
  - no commit/push work in this pass

## 3. Scope (in/out)
- In:
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - `docs/assistant/manifest.json`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`
- Out:
  - `docs/assistant/templates/*`
  - already-aligned local roadmap/publish/scratch-path docs unless a contradiction is discovered
  - product/source/test behavior outside agent-doc validation

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/bootstrap-cleanup-continuity-hardening`
- Base branch: `main`
- Base SHA: `62390cb91760ea936395d303fcd53cb2718ad640`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; canonical floor remains satisfied by `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Local harness-apply workflow contract:
  - continuity/cleanup governance resync as part of project harness apply
  - mixed dirty-tree commit-scope guidance for vendored-template plus local-harness changes
- Manifest machine-routing contract:
  - additive local contract keys for dormant roadmap state, cleanup-complete bare `push`, post-merge repair default, and ignored scratch-root default
  - widened `project_harness_sync_workflow.primary_files`
- Validator contract:
  - fail when the project harness workflow or manifest drifts from the new local cleanup/continuity rules

## 6. File-by-file implementation steps
- `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - extend local apply order with continuity/cleanup governance docs
  - add failure mode for template changes that alter continuity or merge-cleanup behavior
  - add commit-scope guidance for mixed vendored-template and local-harness dirty trees
  - widen primary files and handoff checklist to reflect the above
- `docs/assistant/manifest.json`
  - widen `project_harness_sync_workflow.primary_files` to include continuity/cleanup governance docs
  - add additive contract keys for dormant-roadmap allowance on `main`, cleanup-complete bare `push`, follow-up branch/PR repair default, and ignored `tmp/` scratch-root default
- `APP_KNOWLEDGE.md` and `docs/assistant/APP_KNOWLEDGE.md`
  - add one concise routing rule that template-driven continuity/cleanup changes must resync publish/docs-maintenance governance surfaces, not only routing docs and validators
- `tooling/validate_agent_docs.dart`
  - enforce the new project-harness workflow markers
  - enforce the expanded manifest primary files and new manifest contract keys
- `test/tooling/validate_agent_docs_test.dart`
  - add regressions for the new local harness drift conditions

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance:
  - no file under `docs/assistant/templates/*` changes
  - `PROJECT_HARNESS_SYNC_WORKFLOW.md` explicitly covers continuity/cleanup governance resync
  - `docs/assistant/manifest.json` exposes the new cleanup/continuity rules machine-readably
  - local validator coverage fails if those rules drift again
  - already-aligned local roadmap/publish/scratch-path surfaces remain unchanged unless a contradiction was found

## 8. Rollout and fallback
- Land as a docs/governance-only local harness sync pass on the current feature branch.
- If any planned validator requirement proves too strict for current manifest structure, keep the schema style intact and reduce the requirement to marker/primary-file enforcement rather than inventing a new schema shape.
- If an apparently missing local rule is already enforced elsewhere, prefer documenting that in the workflow/manifest rather than duplicating logic across multiple docs.

## 9. Risks and mitigations
- Risk: re-touching already-correct continuity docs and creating noise.
  - Mitigation: limit edits to the six scoped files unless a direct contradiction is discovered.
- Risk: validator drift checks become overly brittle.
  - Mitigation: validate stable behavior markers and required manifest entries, not incidental wording.
- Risk: mixed existing worktree dirt causes accidental scope expansion.
  - Mitigation: avoid unrelated file edits and keep the ExecPlan explicit about touched files.

## 10. Assumptions/defaults
- The current local repo already correctly implements the major cleanup/continuity behavior.
- Remaining gaps are limited to the project-harness sync workflow, manifest expression of the rules, and local validator enforcement.
- Existing dirty template-folder changes on this branch are intentional source input and must stay untouched during this pass.

## 11. Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart`
  - Passed.
- `dart run test/tooling/validate_agent_docs_test.dart`
  - Passed (`66 cases`).
- `dart run tooling/validate_workspace_hygiene.dart`
  - Passed.
- Outcome:
  - the local harness-sync workflow now explicitly resyncs continuity/cleanup governance docs when template contracts change
  - the manifest now exposes dormant-roadmap, cleanup-complete push, post-merge repair default, and scratch-root rules as machine-readable local contracts
  - validator coverage now fails when those local harness rules drift
  - no file under `docs/assistant/templates/*` was edited in this pass
