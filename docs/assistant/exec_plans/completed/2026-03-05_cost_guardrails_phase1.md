# Cost Guardrails Phase 1 (CLI + Workflow First)

## 1) Title
Cost Guardrails Phase 1 Implementation (CLI + Workflow, warn-by-default)

## 2) Goal and non-goals
- Goal:
  - Implement deterministic pre-run/post-run cost guardrails with CLI + workflow integration.
  - Preserve existing public workflow signatures and artifact compatibility.
- Non-goals:
  - No new GUI controls in this phase.
  - No schema-version bump unless tests force it.
  - No checkpoint fingerprint expansion for budget fields.

## 3) Scope (in/out)
- In scope:
  - `RunConfig` additions for budget/cost profile/policy.
  - CLI flags `--budget-cap-usd`, `--cost-profile-id`, `--budget-on-exceed`.
  - New internal module `cost_guardrails.py` with deterministic helpers.
  - Workflow pre-run decision path (allow/warn/block/n-a) and additive summary keys.
  - Run report rendering of new budget section (backward compatible).
  - Tests for CLI, workflow budget behavior, and run report compatibility.
- Out of scope:
  - GUI budget entry and UX.
  - Breaking contract changes in run API signatures.

## 4) Interfaces/types/contracts affected
- `src/legalpdf_translate/types.py`
  - Add `BudgetExceedPolicy` enum.
  - Extend `RunConfig` with `budget_cap_usd`, `cost_profile_id`, `budget_on_exceed`.
- `src/legalpdf_translate/cli.py`
  - Parse/validate/persist new budget-related flags.
- `src/legalpdf_translate/workflow.py`
  - Integrate pre-run budget preflight and block behavior.
  - Add additive `run_summary.json` keys:
    - `cost_estimation_status`
    - `cost_profile_id`
    - `budget_cap_usd`
    - `budget_decision`
    - `budget_decision_reason`
    - `budget_pre_run`
    - `budget_post_run`
- `src/legalpdf_translate/run_report.py`
  - Render budget guardrail summary when present.

## 5) File-by-file implementation steps
1. Add enum and RunConfig fields in `types.py`.
2. Wire new CLI flags/validation and pass values into RunConfig in `cli.py`.
3. Add `cost_guardrails.py` with deterministic rate resolution, pre-run estimation, decision policy, and post-run estimate helpers.
4. Integrate workflow:
   - Compute budget preflight after page selection.
   - Emit `run_budget_preflight` event.
   - Apply allow/warn/block/n-a handling.
   - Preserve checkpoint compatibility.
   - Include budget packets in run summary.
5. Extend run report summary rendering for budget guardrails.
6. Add/extend tests for parser behavior, block/warn behavior, unavailable estimation behavior, and run-report compatibility.

## 6) Tests and acceptance criteria
- Required command set:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
  - `python -m compileall src tests`
  - `python -m pytest -q tests/test_cli_flags.py tests/test_effort_policy_guardrails.py tests/test_run_report.py tests/test_openai_transport_retries.py tests/test_retry_reason_mapping.py`
  - `python -m pytest -q`
- Acceptance:
  - No public signature break on `TranslationWorkflow.run/analyze/rebuild_docx`.
  - Run summaries retain old keys and include new additive keys.
  - `budget_on_exceed=block` halts before page processing and writes artifacts.
  - Legacy run summaries still render in report.

## 7) Rollout and fallback
- Rollout:
  - Single feature branch commit set with additive contracts.
- Fallback:
  - Feature inert when `budget_cap_usd` is unset.
  - Default policy is warn, preserving current execution behavior.

## 8) Risks and mitigations
- Risk: heuristic estimate mismatch vs real cost.
  - Mitigation: explicit status/reason fields and decision trace in run summary.
- Risk: accidental resume incompatibility.
  - Mitigation: do not include budget fields in checkpoint settings fingerprint.
- Risk: report regressions on old artifacts.
  - Mitigation: backward-compatible key access and dedicated tests.

## 9) Assumptions/defaults
- Windows-native local workflow remains canonical for this repo.
- Default exceed policy is `warn`.
- Currency baseline is USD unless `LEGALPDF_COST_CURRENCY` is set.
- Existing unrelated WIP in this branch remains untouched.

## Docs Sync Execution Record (Approved 2026-03-05)
- Scope-limited docs sync completed for Cost Guardrails Phase 1.
- Updated docs:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
  - `docs/assistant/exec_plans/active/2026-03-05_cost_guardrails_phase1.md`
- Validator status after docs sync:
  - `dart run tooling/validate_agent_docs.dart` passed.
  - `dart run tooling/validate_workspace_hygiene.dart` passed.
