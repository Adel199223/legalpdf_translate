# Project Harness Alignment Roadmap

## 1. Title
Project harness alignment roadmap from vendored templates

## 2. Goal and non-goals
- Goal:
  - implement the current vendored template contracts into this repo's local harness without editing `docs/assistant/templates/*`
  - activate roadmap governance so the repo gains a durable `SESSION_RESUME.md` anchor and explicit roadmap/worktree authority rules
  - align project-local docs, workflow routing, manifest contracts, and validator/test coverage with the current vendored template set
- Non-goals:
  - no edits inside `docs/assistant/templates/*`
  - no app/runtime feature changes under `src/`
  - no broad cleanup of old active ExecPlans beyond making `SESSION_RESUME.md` the authoritative continuity entrypoint

## 3. Scope (in/out)
- In:
  - project-local governance docs
  - project-local workflow docs
  - `docs/assistant/manifest.json`
  - validator/test coverage for assistant-doc integrity
  - roadmap anchor/tracker artifacts for this repo
- Out:
  - vendored template folder edits
  - product runtime code
  - historical audit rewrites except for a small superseding note or new audit

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/joblog-inline-editing`
- Base branch: `main`
- Base SHA: `674098c5aec8a711368b3653c6a4364fb7b01a8c`
- Target integration branch: `main`
- Canonical build status: noncanonical branch on the canonical worktree path; approved base floor satisfied per `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Local harness triggers:
  - `implement the template files`
  - `sync project harness`
  - `audit project harness`
  - `check project harness`
- New project-local workflow docs:
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
- New roadmap anchor:
  - `docs/assistant/SESSION_RESUME.md`
- Manifest additions:
  - module flags for local template-derived modules
  - workflow entries for project harness sync and roadmap governance
  - contract strings for local apply boundary and roadmap continuity

## 6. File-by-file implementation steps
- Wave 1:
  - update `agent.md`, `AGENTS.md`, `README.md`, `docs/assistant/INDEX.md`, `APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, and `docs/assistant/UPDATE_POLICY.md`
  - add `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - add `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - add `docs/assistant/SESSION_RESUME.md`
  - add one small superseding audit or refresh note for the newer vendored-template state
  - extend `docs/assistant/manifest.json`
  - extend `tooling/validate_agent_docs.dart` and `test/tooling/validate_agent_docs_test.dart`
- Roadmap continuity artifacts:
  - keep this roadmap tracker active during implementation
  - create and maintain one active wave ExecPlan for the concrete implementation pass
  - update `SESSION_RESUME.md` to point to both active artifacts and the authoritative worktree/branch

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance:
  - a fresh session can open `docs/assistant/SESSION_RESUME.md` first and reach the active roadmap tracker plus active wave ExecPlan without chat history
  - project-local routing distinguishes local harness apply from global bootstrap maintenance
  - validator baseline passes against the current vendored template set
  - no file under `docs/assistant/templates/*` changes during this pass

## 8. Rollout and fallback
- Land as one local-harness alignment pass.
- If validator failures expose a missing project-local contract, patch the local harness and tests rather than normalizing the vendored template folder.

## 9. Risks and mitigations
- Risk: accidentally editing vendored templates while aligning to them.
  - Mitigation: treat `docs/assistant/templates/*` as read-only input and verify final diff excludes them.
- Risk: roadmap activation creates continuity duplication with legacy active ExecPlans.
  - Mitigation: make `SESSION_RESUME.md` explicitly authoritative without bulk-cleaning the backlog in this pass.
- Risk: validator drift between old project assumptions and new vendored template set.
  - Mitigation: update validator markers, required files, and fixture coverage in the same pass as manifest/workflow changes.

## 10. Assumptions/defaults
- Roadmap governance is activated now because the user explicitly wants the master-plan / anchor-file system.
- The vendored template set is the source of truth for this pass.
- Existing repo-specific adaptations stay unless they conflict with the template floor contracts.

## 11. Current status
- Local harness implementation is complete for this roadmap.
- The continuity system now exists project-locally through:
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - `docs/assistant/SESSION_RESUME.md`
- The next step is commit/publish only if the user explicitly asks for it.

## 12. Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart` -> PASS
- `dart run test/tooling/validate_agent_docs_test.dart` -> PASS (`53 cases`)
- `dart run tooling/validate_workspace_hygiene.dart` -> PASS
