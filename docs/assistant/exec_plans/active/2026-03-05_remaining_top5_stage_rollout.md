# Remaining Top-5 Implementation Program (Stage-Gated, App-Test-Driven)

## 1) Title
Remaining Top-5 Implementation Program (staged, app-test-driven)

## 2) Goal and non-goals
- Goal:
  - Implement the remaining roadmap features in strict stages with one commit per stage.
  - End every stage with validations, manual app test handoff, and exact continuation token.
- Non-goals:
  - No breaking public signature changes in `TranslationWorkflow.run/analyze/rebuild_docx`.
  - No destructive Git operations.

## 3) Scope (in/out)
- In:
  - Stage 1: Auto Job-Log Sync.
  - Stage 2: Quality Risk Scoring + Review Export (backend/CLI).
  - Stage 3: Review Queue GUI panel.
  - Stage 4: Queue/Batch Runner (desktop-local).
  - Stage 5: Guided OCR/Image Advisor.
  - Stage 6: Final hardening/signoff.
- Out:
  - Deployment/release actions.
  - Breaking CLI/API changes.

## 4) Interfaces/types/contracts affected
- Additive DB columns in `job_runs`:
  - `run_id`, `target_lang`, `total_tokens`, `estimated_api_cost`, `quality_risk_score`.
- Additive `run_summary.json` keys:
  - `quality_risk_score`, `review_queue_count`, `review_queue`.
- Additive CLI flags:
  - `--review-export`, `--queue-manifest`, `--rerun-failed-only`.
- Additive analyze/recommendation keys:
  - `recommended_ocr_mode`, `recommended_image_mode`, `recommendation_reasons`, `confidence`.
  - run metadata: `advisor_recommendation_applied`.

## 5) File-by-file implementation steps
1. Stage 0 baseline lock and scaffold.
2. Stage 1 job-log migration + prefill plumbing + tests.
3. Stage 2 deterministic risk scoring + review export + tests.
4. Stage 3 review queue GUI panel + tests.
5. Stage 4 queue runner core + CLI/GUI surface + tests + CI.
6. Stage 5 OCR/image advisor + GUI apply/ignore + tests + CI.
7. Stage 6 final full validation + CI + signoff packet + docs sync.

## 6) Tests and acceptance criteria
- Baseline and per-stage validation:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
  - `./.venv311/Scripts/python.exe -m compileall src tests`
  - `./.venv311/Scripts/python.exe -m pytest -q`
- Stage-targeted suites are run in each stage packet.
- High-risk stages (4, 5, 6) include cloud CI verification.

## 7) Rollout and fallback
- Rollout:
  - One commit per stage.
  - Stage-gated advancement with exact continuation tokens.
- Fallback:
  - Stop at stage boundary on failure, retain clean diagnostics and do not continue.

## 8) Risks and mitigations
- Risk: feature interaction regressions.
  - Mitigation: full local suite every stage, targeted tests, cloud CI on high-risk stages.
- Risk: schema drift for legacy job log DBs.
  - Mitigation: additive idempotent migration + migration tests.
- Risk: nondeterministic quality scoring.
  - Mitigation: deterministic engine with replay tests.

## 9) Assumptions/defaults
- Branch: `chore/import-optmax-2026-03-05`.
- Windows-native runtime via `.venv311`.
- One commit per stage.
- No history rewrite.

## Stage Packet — Stage 0
- Status: in progress.
- Scope:
  - ExecPlan scaffold creation.
  - Baseline branch/cleanliness capture.
  - Mandatory baseline validators/tests.
- Mandatory commands:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
  - `./.venv311/Scripts/python.exe -m compileall src tests`
  - `./.venv311/Scripts/python.exe -m pytest -q`
- Continuation token: `NEXT_STAGE_1`
