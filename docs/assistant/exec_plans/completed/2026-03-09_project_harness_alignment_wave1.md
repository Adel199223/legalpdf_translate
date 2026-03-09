# Project Harness Alignment Wave 1

## 1. Title
Project harness alignment wave 1 implementation

## 2. Goal and non-goals
- Goal:
  - implement the local harness-sync trigger and roadmap-governance continuity layer in this repo
  - align routing docs, manifest contracts, workflows, and validator/test coverage to the current vendored template set
- Non-goals:
  - no template-folder edits
  - no runtime/product code changes

## 3. Scope (in/out)
- In:
  - `agent.md`
  - `AGENTS.md`
  - `README.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/INDEX.md`
  - `docs/assistant/UPDATE_POLICY.md`
  - `docs/assistant/manifest.json`
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - `docs/assistant/SESSION_RESUME.md`
  - one new audit or refresh note
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`
- Out:
  - `docs/assistant/templates/*`
  - `src/`
  - older historical docs cleanup beyond minimal supersession wording

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/joblog-inline-editing`
- Base branch: `main`
- Base SHA: `674098c5aec8a711368b3653c6a4364fb7b01a8c`
- Target integration branch: `main`
- Canonical build status: noncanonical branch on the canonical worktree path; approved base floor satisfied per `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- new local harness-apply routing
- new roadmap resume/anchor contract
- new manifest module/workflow/contract entries
- updated validator/test enforcement for current vendored templates

## 6. File-by-file implementation steps
- Add the new local workflow and roadmap workflow docs.
- Add `SESSION_RESUME.md` and point it to:
  - `docs/assistant/exec_plans/active/2026-03-09_project_harness_alignment_roadmap.md`
  - this wave ExecPlan
- Update runbook/bridge/index/readme/canonical docs so local trigger phrases and roadmap continuity are discoverable.
- Extend manifest module flags, workflows, and contracts.
- Update validator and fixture tests to require the current vendored template set plus the local workflow/roadmap surfaces.

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance:
  - `implement the template files` routes to local harness apply, not bootstrap maintenance
  - `resume master plan` and equivalent resume intent route to `docs/assistant/SESSION_RESUME.md`
  - `SESSION_RESUME.md` clearly identifies the active roadmap tracker, active wave, authoritative worktree/branch, and next step
  - validator/test coverage matches the new current vendored template set

## 8. Rollout and fallback
- Roll out in one commit-ready pass after validation.
- If a validator still references older bootstrap assumptions, update the local validator/tests instead of editing templates.

## 9. Risks and mitigations
- Risk: manifest/routing drift after adding new workflows.
  - Mitigation: update index, runbook, and manifest together.
- Risk: roadmap artifacts become vague and fail the continuity goal.
  - Mitigation: make `SESSION_RESUME.md` concrete: authoritative worktree, active files, next step.

## 10. Assumptions/defaults
- The active roadmap tracker for this work is the authoritative live roadmap state.
- This wave is the current implementation slice and should be the linked execution-detail source from `SESSION_RESUME.md`.

## 11. Execution status
- Wave 1 implementation is complete.
- The local harness now includes:
  - vendored-template apply routing
  - roadmap-governance workflow routing
  - `SESSION_RESUME.md` as the roadmap anchor file
  - manifest/validator/test coverage aligned to the current vendored template set
- No files under `docs/assistant/templates/*` were edited in this wave.

## 12. Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart` -> PASS
- `dart run test/tooling/validate_agent_docs_test.dart` -> PASS (`53 cases`)
- `dart run tooling/validate_workspace_hygiene.dart` -> PASS
