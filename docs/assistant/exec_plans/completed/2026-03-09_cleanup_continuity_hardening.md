# Cleanup Continuity Hardening

## 1. Title
Assistant Docs Sync for cleanup and continuity hardening

## 2. Goal and non-goals
- Goal:
  - repair stale roadmap continuity after the merged feature-branch cleanup
  - archive only the deterministically stale active ExecPlans
  - harden publish/docs governance so roadmap closeout and scratch-output cleanup happen before merge next time
  - make the validator catch the stale-resume and scratch-path drift that slipped through here
- Non-goals:
  - no app-user guide rewrite beyond touched assistant-facing Qt/workflow references
  - no bootstrap/template edits under `docs/assistant/templates/`
  - no product/runtime behavior change outside the render-review tool default scratch path

## 3. Scope (in/out)
- In:
  - `docs/assistant/SESSION_RESUME.md`
  - stale-plan triage in `docs/assistant/exec_plans/active/` and `completed/`
  - roadmap/publish/docs-maintenance governance docs
  - assistant-facing Qt render-review doc references
  - `tooling/qt_render_review.py`
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/ISSUE_MEMORY.json`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`
- Out:
  - `docs/assistant/templates/*`
  - end-user feature docs outside the touched governance/Qt scratch-path references
  - unrelated product/source changes

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `main`
- Base branch: `main`
- Base SHA: `62390cb91760ea936395d303fcd53cb2718ad640`
- Target integration branch: `main`
- Canonical build status: canonical branch on the canonical worktree path

## 5. Interfaces/types/contracts affected
- Roadmap continuity contract:
  - `docs/assistant/SESSION_RESUME.md`
  - `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `agent.md`
  - `AGENTS.md`
  - `README.md`
- Cleanup/publish governance:
  - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/UPDATE_POLICY.md`
- Scratch-output contract:
  - `tooling/qt_render_review.py`
  - `docs/assistant/QT_UI_PLAYBOOK.md`
  - `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`
- Durable memory and enforcement:
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/ISSUE_MEMORY.json`
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`

## 6. File-by-file implementation steps
- `docs/assistant/SESSION_RESUME.md`
  - convert the stale feature-branch resume anchor into a dormant-roadmap state on `main`
- `docs/assistant/exec_plans/active/` -> `completed/`
  - move only the deterministically stale plans that are complete/superseded, tied to dead branches, or clearly tied to merged March 9 work
- `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - define both active-roadmap and dormant-roadmap states and spell out closeout order
- `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - require roadmap/ExecPlan/resume closeout before merge and default to follow-up branch/PR for missed post-merge repair
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - require docs sync to fix stale continuity state when merge/cleanup drift is discovered
- `docs/assistant/UPDATE_POLICY.md`
  - clarify that scoped docs sync must repair stale continuity anchors when found
- `tooling/qt_render_review.py`
  - switch the default output directory to an ignored path under `tmp/`
- `docs/assistant/QT_UI_PLAYBOOK.md`
  - update the render-review command examples to the new ignored scratch path
- `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`
  - update the render-review command examples to the new ignored scratch path
- `docs/assistant/ISSUE_MEMORY.md` and `.json`
  - add a cleanup/continuity drift entry for stale resume anchors, stale active-plan inventory, post-merge main repairs, and scratch artifact noise
- `docs/assistant/DOCS_REFRESH_NOTES.md`
  - record this sync and the stale continuity/scratch-path fixes
- `tooling/validate_agent_docs.dart` and `test/tooling/validate_agent_docs_test.dart`
  - allow dormant-roadmap state
  - fail on stale `SESSION_RESUME.md` branches when running inside a git repo
  - fail if Qt render-review guidance still points to `tmp_ui_review/`

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_render_review.py`
- Acceptance:
  - `docs/assistant/SESSION_RESUME.md` reflects `main` plus dormant-roadmap state
  - `docs/assistant/exec_plans/active/` keeps only clearly live plans after deterministic triage
  - Qt render-review defaults to an ignored scratch path under `tmp/`
  - validator coverage would catch the stale resume branch and old scratch-path guidance
  - no files under `docs/assistant/templates/` change

## 8. Rollout and fallback
- Land as a project-local docs/governance hardening pass on `main`.
- If validator changes require test-fixture git state, add that state only inside the temp fixture helper.
- If any active-plan move proves ambiguous, leave that plan in `active/` and document the conservative choice.

## 9. Risks and mitigations
- Risk: over-archiving genuinely live plans.
  - Mitigation: move only files that satisfy the explicit archive criteria; leave ambiguous cases untouched.
- Risk: validator branch-existence checks break temp-fixture tests.
  - Mitigation: gate the branch check on real git-repo availability and add targeted fixture repo setup for the failure case.
- Risk: roadmap docs become over-prescriptive for dormant state.
  - Mitigation: keep dormant state minimal: authoritative branch, no active roadmap, next-action rule, and restart conditions.

## 10. Assumptions/defaults
- There is no currently active roadmap on `main`.
- `feat/gmail-honorarios-draft` may still have genuinely live work and should not be archived accidentally.
- `tmp/` remains an ignored scratch area, so moving Qt render-review output there avoids future Source Control noise without extra repo cleanup.

## 11. Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart`
  - Passed.
- `dart run test/tooling/validate_agent_docs_test.dart`
  - Passed (`56 cases`).
- `dart run tooling/validate_workspace_hygiene.dart`
  - Passed.
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_render_review.py`
  - Passed (`7 passed`).
- Continuity outcome:
  - `docs/assistant/SESSION_RESUME.md` now reflects `main` with a dormant roadmap state and no stale feature-branch links.
- Active-plan triage outcome:
  - deterministically stale March 5 to March 9 plans were archived to `docs/assistant/exec_plans/completed/`
  - ambiguous older plans and genuinely live branch work remained in `docs/assistant/exec_plans/active/`
