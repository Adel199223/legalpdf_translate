# Test feedback performance

## Goal and non-goals

Measure the slow test paths and shorten ordinary developer feedback and complete CI validation without removing coverage. The user approved proceeding after the explanation of the 36–41 minute CI runs. This is test infrastructure work, not an application rewrite or new provider/native/Gmail acceptance.

## Scope

In scope: duration evidence, demonstrated expensive test setup, fast versus integration validation, bounded safe concurrency, duplicate CI scheduling, scoped validation documentation. Out of scope: application contracts, translation defaults, paid dispatch, Gmail/email, Word automation, budget reconciliation, historical evidence modification, dependency modernization unrelated to testing.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/worktrees/word-startup-readiness/legalpdf_translate` (existing clean free checkout reused).
- Branch: `codex/test-performance-20260926`.
- Base branch and target integration branch: `main`.
- Base SHA: `b35be1c3ad401ba70ca3dc4464f09bf64782958b`, equal freshly fetched `origin/main`; contains approved floor `4e9d20e`.
- Noncanonical test/tooling checkout. Canonical main and saved application data remain untouched. No application server was observed on the known ports at preparation.

## Interfaces and contracts

Keep application source/contracts unchanged unless profiling demonstrates a separate local defect requiring explicit plan revision. Retain test assertions, collected coverage, fixture isolation and external/native launch guards. Preserve required CI check names or provide an equivalent explicit aggregate. Preserve selected Full versus complete-repository coverage distinctions.

## Implementation steps

1. Record baseline collection, duration/JUnit/profile evidence outside the repository, beginning with the previously slow 173-case formatting group.
2. Inspect `tests/` fixtures/helpers and optimize only measured avoidable overhead, retaining real integration cases and isolated per-test state.
3. Update `scripts/validate_dev.ps1` and any small supporting test runner for clear fast/full/complete tiers and bounded independent execution where demonstrated safe.
4. Update `.github/workflows/python-package.yml` for duration artifacts, safe parallel coverage if justified, and avoid duplicate branch-push/PR full suites while retaining main/manual validation.
5. Add meaningful harness contract tests for coverage completeness, failures and isolation where behavior changes.
6. Sync `docs/assistant/VALIDATION.md`, CI workflow guidance and current continuity routes only as needed; preserve exact beforeimages privately.

## Tests and acceptance

- Use project `.venv311/Scripts/python.exe` and fictional inputs only.
- Compare unchanged baseline versus final timings with identical selected node IDs and report collection/coverage separately from elapsed time.
- Profile before choosing fixture changes; do not claim a specific speedup from speculation.
- Run targeted harness/affected regressions, standard validation and Full, plus complete collection validation for integrated test/workflow changes. Avoid redundant repeats without a new change or failure.
- Preserve docs/localization/workspace validators and their tests, compilation and core regressions.
- Verify no application source/default/ledger/history changes. Keep original failures and timing artifacts.

## Rollout and fallback

Prepare a concrete reviewed, tested change before publication. Publication remains a distinct boundary under current authority. Revert test infrastructure changes if coverage, isolation or determinism regresses; no live data migration is involved.

## Risks and mitigations

Concurrency can expose shared resources: use isolated process/app-data/temp roots, bounded workers and retain sequential fallback. Fixture caching can hide mutations: do not share mutable workflow state between cases. CI deduplication can strand required checks: preserve PR/main/manual events and stable aggregate status. Timing noise: compare like-for-like commands and disclose runner differences.

## Assumptions and decisions

This authorized task has one test-infrastructure surface, no live-service/cost risk and no destructive schema work; the risk-triggered staged execution workflow does not require a historical continuation token. No paid/native/provider retry is authorized or necessary. The shelved FRlong hold/block, original USD10 limit and all prior evidence remain intact.

## Progress and evidence

- Preparation: clean worktree reused at verified main; read-only CI and fixture reviews delegated. No implementation or benchmark completed yet.
- Private evidence root: `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/test_performance_20260926_01/`. Exact docs/script/workflow beforeimages and all failed/partial validation attempts remain there. Initial preservation checked all 68 historical protected files and froze 484 existing source/test pins.
- The profiled `test_explicit_table_owners_create_editable_cells` passed in 10.60 seconds (8.88-second call). Its profile records 72,139 filesystem stat calls and 2,884 buffered reads. Real evidence/path revalidation dominates enough that shared accepted fixtures or disabled integrity checks are inappropriate first optimizations. No application code or existing test assertion was changed.
- The complete unchanged baseline ran with durations and JUnit (`baseline_complete.*`); its successful terminal result below was required before generating timing weights or claiming a speedup.
- Implementation direction: dependency-free whole-file partitions, automatic inclusion of new tests, strict collection/execution/JUnit verification, two local formatting workers and four complete CI partitions. All Qt-prefixed files plus honorarios tests share one partition after a concrete focus-conflict risk was identified. Child execution/temp roots stay separate from retained report artifacts.
- Added an opt-in Quick tier while retaining default and Full coverage/filter selection. CI retains the existing required `test (3.11)` name as a strict aggregate, all Windows/Linux contracts, PR/main/manual coverage and report-only artifacts; duplicate feature push runs are removed.
- Independent workflow/PowerShell review found no blocker. Official checksum-verified actionlint v1.7.12 passed the edited workflow. Runner synthetic tests and broader validation results will be recorded after their final revisions; these are not product/live acceptance.
- Quick01 passed 89 tests in 42.28 seconds; two DOM-to-workflow cases consumed 27.08 and 4.69 seconds. Those exact cases now stay in Full/complete coverage rather than Quick. Quick02 passed 87 tests/two intentional deselections in 10.72 seconds; the entire wrapper passed in 16.202 seconds including compilation/docs/hygiene. Both measurements overlapped the baseline and are recorded as such. The two Dart AOT exit255 attempts and successful direct fallbacks remain in each log.
- Final runner revision preserves the inherited Qt platform, including the Windows CI platform. Only explicitly offscreen Windows children receive the default font directory. Local baseline/comparison deliberately set offscreen with the same system fonts (192 families verified). Independent review caught and resolved the initial forced-platform change before broad runner validation.
- All 37 runner regressions passed in 18.35 seconds, including actual independent four-shard execution/reconciliation, failure/exit5/drift/missing evidence, relocated artifacts, per-worker roots and Qt environment inheritance. `runner_validation_01/qt_platform_tests_01.json` pins source/tests/log; independent semantic review is clear.
- Local tooling checks passed: docs/localization, 105 docs-validator cases, hygiene and seven hygiene cases, nine automation-preflight cases and three cloud-preflight cases. The latter are fictional local contract tests, not cloud operations. Exact logs and hashes remain under `docs_tool_validation_01/`, `docs_tool_validation_02/` and `preflight_tool_contracts_01/`.
- Baseline complete: 6,717 passed, zero failures/skips/warnings reported, pytest 1,832.59 seconds and wall 1,835.010 seconds. The 250 test files sum to 1,818.755 JUnit seconds. All 484 existing source/test hashes remained unchanged. Five files account for 1,078.625 seconds; the largest is `test_browser_formatting_review.py` (30 cases/327.709 seconds). `baseline_summary.json` and original logs/JUnit retain the details; baseline overlapped only the recorded short tooling/Quick validations, not another full suite.
- `tooling/test_timings.json` is generated solely from that successful baseline, with positive weights for every measured file (SHA256 `df9a48722d3a7ac5b6d8026f6b69ef0bda4e7d435f28ae9eae1a75d8c05d90da`). It controls balancing, never inclusion. New runner tests are automatically included by collection. The queued selected Full and complete four-worker comparisons now run sequentially under one recorded local owner; no broad run was restarted.

## Verified local outcomes

- Selected Full completed successfully with the same 659-case selection: 240 browser, two Gmail review, five Gmail intake (nine expected deselections), 239 source review and 173 formatting. Whole wrapper: 838.559 seconds (13m59s); formatting workers: 538.359 and 516.531 seconds. Compilation/docs/hygiene passed. Preserve both AOT255 attempts and successful direct-Dart fallbacks. `full_01_audit.json` verifies the 173 exact formatting assignments and counts; the initial audit parser's UTF-8 assumption failed against the Windows PowerShell UTF-16 log, then was corrected without modifying the successful validation evidence.
- Complete four-worker comparison passed all 6,754 cases in 537.941 seconds (8m58s). The original 6,717 ordered node IDs match the baseline exactly; the other 37 are new runner regressions. Every test phase passed, with no skipped or missing case. Workers executed 1,790 / 1,925 / 1,279 / 1,760 cases. `comparison_audit_01.json` independently checks exact coverage, JUnit/execution receipts, five frozen comparison pins, all 484 existing source/test hashes and all 68 protected historical files.
- Compared with the local complete baseline's 1,835.010 seconds (30m35s), the measured complete run used 70.68% less wall time (3.41x throughput). This is one local comparison, not a hosted-CI guarantee. The baseline overlapped the documented short Quick/tool validations; the parallel complete comparison did not overlap another test suite. Both used the same explicit offscreen Qt platform and Windows system fonts. Do not compare selected Full or Quick directly with complete coverage.
- Immutable CI artifacts now include `github.run_attempt`. New `tooling/ci_test_evidence.py` selects the greatest numeric attempt independently for each of four shards, retains earlier artifacts and refuses missing/failed/mismatched latest evidence. The aggregate's prerequisite-success gate remains required when a newer failed job produced no artifact. Twenty new selector regressions passed in 0.76 seconds (`selector_validation_01/`), separately from the earlier 6,754-case comparison. Final repository collection therefore adds these 20 cases; do not relabel the earlier benchmark as covering them.
- `final_tooling_01/` records successful final actionlint, compilation and stdlib-only selector verification of all 6,754 actual local results repackaged into the CI artifact layout. This is a local artifact-layout check, not a hosted GitHub run. Independent static review found no actionable selector defect.
- Final collection confirms 6,774 cases: the same ordered 6,754 complete-benchmark cases plus the separately passed 20 selector cases (`final_collection_01/`). Independent final review reconciled baseline JUnit, all four complete workers, selected Full and selector evidence. Final workflow SHA256 is `4621873e85caf5508b3f95d2990edee21f68f9dd49086fc83b020defaed25461`; the earlier comparison audit's workflow pin intentionally predates the rerun-artifact correction.
- Final docs/localization/hygiene checks passed. A whitespace-only failure in `final_docs_01/` exposed CRLF output from the continuity-doc writer; restoring those two files to their original LF convention made `git diff --check` pass. The initial failed check remains preserved. No broad test rerun is necessary for that line-ending repair.
- The newly staged timing JSON exposed the same CRLF issue, which unstaged `git diff --check` had not covered. Local commit `4d4bffd` and the exact original JSON/check output remain preserved; a follow-up normalizes only line endings, with identical parsed weights. Final timing SHA256 is `b4e69713aa9f5b88e024a80a04e65a4e83bc197452fffedd146e0699b53a359a`; `timings_line_endings_01/` records both hashes and successful full branch-diff whitespace validation. No test selection or balancing value changed.

## Implementation closure and authorized publication

Implementation, independent review and local validation are complete. The user explicitly approved publishing through GitHub checks, merging and applying the tested change on 2026-09-26. This plan moves to completed for implementation closeout before publication. The private `test_performance_20260926_01/publication_01/publication_receipt.json` records actual PR/head checks, merge, clean canonical application and preservation once terminal; its absence means the authorized publication lifecycle remains unfinished. At approval canonical main was clean at `b35be1c`. No application code, saved defaults, ledger rows, paid operations or live acceptance changed. Hosted CI timing/success must come from its actual run, never from the local benchmark.
