# Reliability Polish For Gmail Translation Closeout

## Goal and non-goals
1. Goal: make repo-owned standalone Dart validators use direct script invocation so this machine does not depend on the broken `dartdev` launcher path.
2. Goal: clarify citation-delta diagnostics without changing review-queue thresholds or adding noisy workflow blockers.
3. Goal: keep generated run-report artifact paths consistent across top-level job artifacts and nested result artifacts.
4. Non-goal: change Gmail same-tab handoff, native-host EXE registration, AppData runtime-state ownership, CMD-window suppression, OCR routing, or translation behavior.

## Scope
- In scope:
  - direct Dart command references in current docs, workflows, manifest metadata, and validator-enforced expectations
  - additive citation marker/parenthesis diagnostics
  - run report wording for citation/parenthesis drift
  - `TranslationJobManager.generate_run_report()` artifact payload consistency
  - targeted regression tests for diagnostics, risk policy, report generation, and docs validator command expectations
- Out of scope:
  - historical completed ExecPlans and old refresh notes unless current validators require them
  - Flutter cache repair
  - Gmail launch/runtime/native-host code paths
  - publishing or merging

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `codex/reliability-polish-gmail-translation-closeout`
- base branch: `main`
- base SHA: `b6a847f`
- target integration branch: `main`
- canonical build status: follow-up branch from clean canonical `main`; no live Gmail runtime changes intended in this pass

## Interfaces/types/contracts affected
- Additive page diagnostics:
  - `citation_marker_delta_abs`
  - `parenthesis_delta_abs`
  - source/output citation marker counts
  - source/output parenthesis marker counts
- Preserved compatibility field:
  - `citation_mismatches_count`
- Direct Dart validator command contract:
  - `dart tooling/validate_agent_docs.dart`
  - `dart tooling/validate_workspace_hygiene.dart`
  - `dart test/tooling/validate_agent_docs_test.dart`
  - `dart test/tooling/validate_workspace_hygiene_test.dart`
- Run-report generation contract:
  - generated reports populate both `job.artifacts_payload["run_report_path"]` and `job.result_payload["artifacts"]["run_report_path"]`

## File-by-file implementation steps
1. Update `src/legalpdf_translate/translation_diagnostics.py` to emit additive citation marker and parenthesis drift fields while preserving `citation_mismatches_count`.
2. Update `src/legalpdf_translate/run_report.py` so the validation section labels citation/parenthesis drift clearly.
3. Update `src/legalpdf_translate/translation_service.py` so `generate_run_report()` writes the resolved report path into nested result artifacts.
4. Update targeted tests under `tests/` for diagnostics fields, moderate citation drift behavior, report wording, and nested artifact consistency.
5. Update current docs, manifest metadata, and validator expectations from package-run standalone script commands to direct `dart <standalone-script>` commands.
6. Add or update validator tests so stale package-run expectations cannot re-enter current guidance.

## Tests and acceptance criteria
1. Targeted Python tests pass:
   - `.\.venv311\Scripts\python.exe -m pytest tests/test_translation_diagnostics.py tests/test_quality_risk_scoring.py tests/test_translation_report.py tests/test_translation_service_run_report.py tests/test_shadow_web_api.py -q`
2. Direct Dart validators and tests pass:
   - `dart tooling/validate_agent_docs.dart`
   - `dart tooling/validate_workspace_hygiene.dart`
   - `dart test/tooling/validate_agent_docs_test.dart`
   - `dart test/tooling/validate_workspace_hygiene_test.dart`
3. Current docs/tooling/tests have no package-run command references for standalone validator or cloud-evaluation scripts outside historical completed records, if any.
4. Moderate citation drift remains out of the review queue unless stronger quality-risk signals are present.
5. Generated run reports populate nested `result.artifacts.run_report_path`.

## Rollout and fallback
- Commit as a small follow-up reliability polish branch after validation.
- Fallback is straightforward revert of this focused commit; no runtime launch contract changes are included.

## Risks and mitigations
1. Risk: bulk docs command updates touch historical evidence.
   - Mitigation: update only current docs/workflows/manifest/tooling/tests, not completed ExecPlans or old notes.
2. Risk: citation wording implies stricter validation than intended.
   - Mitigation: keep thresholds unchanged and explicitly document moderate drift as diagnostic unless risk policy flags it.
3. Risk: run-report payload mutation breaks old artifacts.
   - Mitigation: only add/populate nested dicts when generating a new report; existing artifact readers remain compatible.

## Assumptions/defaults
1. Package-run invocation is noncanonical for standalone repo scripts on this machine.
2. The citation policy is clarify-only.
3. The latest accepted Gmail same-tab behavior remains in place and should not be modified.

## Execution closeout
1. Implementation:
   - added additive citation marker/parenthesis drift fields while preserving `citation_mismatches_count`
   - clarified run-report wording so moderate citation/parenthesis drift is diagnostic rather than automatically actionable
   - made generated run reports populate nested `result.artifacts.run_report_path`
   - updated current validator command references to direct Dart script invocation
2. Validation:
   - `.\.venv311\Scripts\python.exe -m pytest tests/test_translation_diagnostics.py tests/test_quality_risk_scoring.py tests/test_translation_report.py tests/test_translation_service_run_report.py tests/test_shadow_web_api.py -q` -> `103 passed`
   - `dart tooling/validate_agent_docs.dart` -> PASS
   - `dart tooling/validate_workspace_hygiene.dart` -> PASS
   - `dart test/tooling/validate_agent_docs_test.dart` -> `72 passed`
   - `dart test/tooling/validate_workspace_hygiene_test.dart` -> `7 passed`
   - current-doc/tooling/test scan for stale package-run validator command references -> none found outside excluded historical records
3. Status:
   - completed as a focused reliability-polish follow-up
