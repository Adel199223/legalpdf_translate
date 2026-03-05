# Maximum-Enforcement Optimization Program (2026-03-05)

## Goal and non-goals
- Goal: Upgrade repository governance/docs/tooling/runtime modularization to bootstrap v2 maximum-enforcement with reliability-first execution.
- Non-goals: deployment/release actions; breaking CLI changes; destructive migration/history actions.

## Scope (in/out)
- In: docs contracts, manifest/workflows, validators/tests, preflight tooling, workflow modularization delegations, CI hardening.
- Out: feature behavior redesign; API-provider substitutions; destructive repo operations.

## Interfaces/types/contracts affected
- docs/assistant/manifest.json (module_flags + expanded contracts/workflows)
- tooling/validate_agent_docs.dart (+ tests)
- tooling preflight utilities and tests
- workflow internal delegation modules in src/legalpdf_translate/workflow_components/*

## File-by-file implementation steps
1. Stage 1: isolation baseline and stage packet.
2. Stage 2: official-source dossier and EXTERNAL_SOURCE_REGISTRY.
3. Stage 3: governance/workflow docs + manifest max-module updates.
4. Stage 4: validator/test expansion for module-gated enforcement.
5. Stage 5: automation/cloud preflight tooling + tests.
6. Stage 6: runtime reliability modularization delegation.
7. Stage 7: CI cross-platform docs/tooling job + full validation.

## Tests and acceptance criteria
- Docs validators and validator tests pass.
- Workspace hygiene validators/tests pass.
- New preflight tooling tests pass.
- Python compileall passes.
- Python pytest full suite run locally if available; otherwise run in CI.

## Rollout and fallback
- Rollout via isolated feature branch in dedicated worktree.
- Fallback: revert scoped commits by file group if validator/runtime regressions occur.

## Risks and mitigations
- Risk: broad docs drift. Mitigation: validator-gated updates + contract-key compatibility retention.
- Risk: runtime regressions from modularization. Mitigation: delegate by extraction while preserving method signatures/behavior.
- Risk: local test environment limitations. Mitigation: compile checks locally, full pytest on CI.

## Assumptions/defaults
- All optional modules enabled.
- Official primary sources only for external facts.
- Hard stage-gate protocol modeled in documentation and validator contracts.

## Stage Packet — Stage 1 (Isolation + Baseline)
1. changed files list:
   - `docs/assistant/exec_plans/active/2026-03-05_max_enforcement_optimization.md`
2. validation command outputs:
   - `dart run tooling/validate_agent_docs.dart` -> PASS
   - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
   - `./.venv/Scripts/python.exe -m compileall src tests` -> unavailable in isolated worktree (`.venv` missing)
   - `./.venv/Scripts/python.exe -m pytest -q` -> unavailable in isolated worktree (`.venv` missing)
3. discovered drift/risks:
   - local isolated worktree does not include runnable `.venv` interpreter.
4. decisions locked/unlocked:
   - Locked: worktree isolation enforced.
   - Unlocked: use `python3` fallback for compile checks and defer pytest to CI.
5. prepared prompt pack (next 2 stages):
   - NEXT_STAGE_2: gather official sources and build registry.
   - NEXT_STAGE_3: apply governance/manifest/workflow contract updates.
6. re-adaptation notes:
   - adapted baseline from `.venv` commands to `python3` where possible.

## Stage Packet — Stage 2 (Official Source Dossier)
1. changed files list:
   - `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`
2. validation command outputs:
   - source links verified against official domains and recorded with dates.
3. discovered drift/risks:
   - no direct model/runtime dependency drift found during source check.
4. decisions locked/unlocked:
   - Locked: official-only source policy and date stamping.
5. prepared prompt pack (next 2 stages):
   - NEXT_STAGE_3: docs/manifest/workflow expansion.
   - NEXT_STAGE_4: validator enforcement expansion.
6. re-adaptation notes:
   - normalized links to canonical official pages where possible.

## Stage Packet — Stage 3–6 (Contracts + Validators + Tooling + Runtime)
1. changed files list:
   - Governance docs: `AGENTS.md`, `agent.md`, `APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, `docs/assistant/INDEX.md`, `docs/assistant/GOLDEN_PRINCIPLES.md`
   - Protected docs: `docs/assistant/PROJECT_INSTRUCTIONS.txt`, `docs/assistant/UPDATE_POLICY.md`
   - Manifest/workflows: `docs/assistant/manifest.json`, all updated workflow docs plus new module workflow files
   - Validator: `tooling/validate_agent_docs.dart`, `test/tooling/validate_agent_docs_test.dart`
   - Tooling stage 5: `tooling/automation_preflight.dart`, `tooling/cloud_eval_preflight.dart`, tests under `test/tooling/`
   - Runtime stage 6: `src/legalpdf_translate/workflow_components/*`, `src/legalpdf_translate/workflow.py`, `src/legalpdf_translate/openai_client.py`, `pyproject.toml`
   - CI stage 7: `.github/workflows/python-package.yml`
2. validation command outputs:
   - `dart run tooling/validate_agent_docs.dart` -> PASS
   - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
   - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS (29 cases)
   - `dart run test/tooling/validate_workspace_hygiene_test.dart` -> PASS (7 cases)
   - `dart run test/tooling/automation_preflight_test.dart` -> PASS (3 cases)
   - `dart run test/tooling/cloud_eval_preflight_test.dart` -> PASS (3 cases)
   - `python3 -m compileall src tests` -> PASS
   - `python3 -m pytest -q` -> unavailable (`No module named pytest`)
3. discovered drift/risks:
   - local environment cannot run pytest in this worktree; CI required for full Python suite.
4. decisions locked/unlocked:
   - Locked: maximum module enforcement + contract compatibility keys retained.
   - Locked: runtime public signatures preserved; delegation-only modularization.
   - Unlocked: none remaining for current scope.
5. prepared prompt pack (next 2 stages):
   - NEXT_STAGE_7: CI+validation hardening execution and packet close-out.
   - NEXT_STAGE_8: optional follow-up for deeper runtime decomposition if requested.
6. re-adaptation notes:
   - adjusted stage-token validation regex to require numeric token examples.
   - updated tests to account for both generic and numeric stage token text.

## Final Stage Packet (Schema 1–19)
1. changed files list:
   - See Stage 3–6 packet list plus CI file update.
2. validation command outputs:
   - See Stage 3–6 packet list.
3. discovered drift/risks:
   - local pytest unavailable in this isolated environment.
4. decisions locked/unlocked:
   - locked: module flags all enabled; contracts + workflows + validators aligned.
5. prepared prompt pack (next 2 stages):
   - NEXT_STAGE_7 complete.
   - NEXT_STAGE_8 optional cleanup/refactor follow-up.
6. re-adaptation notes:
   - no unresolved contract drift after final validation.
7. automation packet path:
   - `tooling/automation_preflight.dart` output (runtime JSON packet; command-run capture).
8. automation host selected + fallback status:
   - selected: `local`; preferred status: `unavailable`; fallback status: `n/a` (current environment).
9. manual operator checks pending/complete:
   - `pending` (per automation packet default).
10. automation browser binary path/id:
   - empty in current environment (no resolved browser binary).
11. automation browser version:
   - empty in current environment.
12. automation browser source (`system|chrome_for_testing|playwright_managed`):
   - `system` (default packet output for unresolved local browser source).
13. execution venue selected (`cloud|local`):
   - `cloud` (policy default in cloud preflight packet).
14. heavy-run trigger reason:
   - `n/a` (no explicit heavy trigger env override set).
15. cloud preflight status:
   - `ready` in current environment packet.
16. cloud failure semantics (`unavailable|failed|n/a`):
   - `n/a` for current packet state (includes full failure semantics mapping).
17. cloud-to-local fallback used:
   - `false`.
18. manual acceptance status:
   - `pending`.
19. auto-apply block enforced:
   - `true`.

## Docs Sync Execution Record (Approved)
- User approval response captured: `yes if relevant`.
- Docs sync method: touched-scope drift check across canonical, bridge, workflows, manifest, and source registry.
- Additional doc edits required: none (current docs already aligned with implementation scope).
- Post-sync verification:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS (29 cases)
  - `dart run test/tooling/validate_workspace_hygiene_test.dart` -> PASS (7 cases)
  - `dart run test/tooling/automation_preflight_test.dart` -> PASS (3 cases)
  - `dart run test/tooling/cloud_eval_preflight_test.dart` -> PASS (3 cases)
  - `python3 -m compileall src tests` -> PASS
  - `python3 -m pytest -q` -> unavailable (`No module named pytest`)
