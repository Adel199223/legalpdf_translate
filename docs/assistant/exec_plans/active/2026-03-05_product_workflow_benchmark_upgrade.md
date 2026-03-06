# LegalPDF Translate Product-Workflow Benchmark and Upgrade Plan (2026-03-05)

## Goal and non-goals
- Goal: Execute a staged, evidence-backed product/workflow optimization program for quality/reliability-first evolution.
- Non-goals: implement all roadmap features in this single pass; perform deployment/release; introduce breaking contract changes.

## Scope (in/out)
- In:
  - Usage intelligence packet from local artifacts.
  - Similar-app benchmark using official sources only.
  - Gap/opportunity map + prioritized top candidates.
  - Decision-complete specs for locked top-5 upgrades.
  - 30/60/90 roadmap and reliability signoff artifact.
- Out:
  - Full production implementation of the top-5 upgrades.
  - Remote release/deployment actions.

## Interfaces/types/contracts affected
- This execution pass is docs/research/spec heavy.
- Proposed additive interfaces (for future implementation) are specified in:
  - `docs/assistant/audits/TOP5_UPGRADE_SPECS_2026-03-05.md`

## File-by-file implementation steps
1. Stage 1: Build `AUDIT_USAGE_PACKET_2026-03-05` from run artifacts, settings, and job-log.
2. Stage 2: Build official-source benchmark matrix with weighted similarity scores.
3. Stage 3: Map current state vs benchmark capabilities; produce top-12 opportunities and locked top-5.
4. Stage 4: Produce decision-complete specs for top-5 upgrades.
5. Stage 5: Produce 30/60/90 implementation roadmap.
6. Stage 6: Run validation/test suite and produce reliability signoff packet.

## Tests and acceptance criteria
- Docs/tooling validators pass:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
- Compile/test pass:
  - `python -m compileall src tests`
  - targeted regression tests
  - full suite when available
- Reliability signoff file includes explicit GO/NO-GO rationale and residual risks.

## Rollout and fallback
- Rollout: docs/spec artifacts only in this pass.
- Fallback: revert new audit files if validator drift appears.

## Risks and mitigations
- Risk: benchmark claims drift over time.
  - Mitigation: verification date stamped per source (2026-03-05).
- Risk: overfitting roadmap to small run sample.
  - Mitigation: explicitly document sample size and preserve assumptions.
- Risk: roadmap ambiguity.
  - Mitigation: decision-complete specs with explicit acceptance tests.

## Assumptions/defaults
- Windows-native workflow remains canonical.
- Quality/reliability dominates throughput/cost in prioritization.
- Low new spend default is preserved.
- Official-source-only external facts.

## Stage Packet — Stage 1
- Output: `docs/assistant/audits/AUDIT_USAGE_PACKET_2026-03-05.md`
- Status: complete.
- Continuation token: `NEXT_STAGE_2` (satisfied in this execution pass).

## Stage Packet — Stage 2
- Output: `docs/assistant/audits/SIMILAR_APP_BENCHMARK_2026-03-05.md`
- Status: complete.
- Continuation token: `NEXT_STAGE_3` (satisfied in this execution pass).

## Stage Packet — Stage 3
- Output: `docs/assistant/audits/GAP_OPPORTUNITY_MAP_2026-03-05.md`
- Status: complete.
- Continuation token: `NEXT_STAGE_4` (satisfied in this execution pass).

## Stage Packet — Stage 4
- Output: `docs/assistant/audits/TOP5_UPGRADE_SPECS_2026-03-05.md`
- Status: complete.
- Continuation token: `NEXT_STAGE_5` (satisfied in this execution pass).

## Stage Packet — Stage 5
- Output: `docs/assistant/audits/ROADMAP_30_60_90_2026-03-05.md`
- Status: complete.
- Continuation token: `NEXT_STAGE_6` (satisfied in this execution pass).

## Stage Packet — Stage 6
- Output: `docs/assistant/audits/RELIABILITY_SIGNOFF_2026-03-05.md`
- Status: complete.
- Validation outputs:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `python -m compileall src tests` -> PASS
  - `python -m py_compile tooling/build_usage_audit_packet.py` -> PASS
  - targeted reliability suite -> `26 passed`
  - full suite -> `443 passed`
- Cloud evidence:
  - `gh run list --workflow CI --branch chore/import-optmax-2026-03-05 --limit 3`
  - latest run ids: `22723888520`, `22723883895`, `22723872295` (all success)

## Lineage Note
- The benchmark/top-5 outputs from this plan were later implemented under:
  - `docs/assistant/exec_plans/active/2026-03-05_remaining_top5_stage_rollout.md`
  - `docs/assistant/exec_plans/active/2026-03-05_ocr_first_stage_rollout.md`
- The live final signoff for the implemented work is:
  - `docs/assistant/audits/RELIABILITY_SIGNOFF_2026-03-05.md`
