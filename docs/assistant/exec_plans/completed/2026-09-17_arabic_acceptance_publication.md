# Publish the accepted Arabic workflow fixes

Status: completed on 2026-09-17 after PR #298 merge, canonical update, owned HTTP verification and recorded cleanup. The sections below retain the original scope and chronological prepublication checkpoints; their pending language is historical. No paid/native acceptance was replayed.

## Final publication outcome

- PR: [#298](https://github.com/Adel199223/legalpdf_translate/pull/298); exact reviewed CI head `b3480e092530ab65d569842ba488a3d7c1e6f102`; merge `751185fca959ab074c328050adf0184f5db76d2c`.
- Required CI: All four PR/push Windows and Linux jobs succeeded. Both complete pytest runs passed 6,607 tests with two dependency-deprecation warnings each (PR 2,314.94 seconds; push 2,201.84 seconds); each targeted core run passed 34 tests. Original failed runs remain preserved. Evidence: [terminal run](https://github.com/Adel199223/legalpdf_translate/actions/runs/35262295310).
- Fresh local Full after the test-only correction: at 2026-09-17T19:11:15.0243841Z, head `b3480e092530ab65d569842ba488a3d7c1e6f102` passed 629 selected tests, with 9 deselected, compilation and direct-Dart docs/hygiene fallbacks after two known AOT255 wrapper failures. This is not complete repository pytest. Receipt `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/application_ar_publication_20260917_01/ci_correction_01/full_validation_result_01.json`, SHA256 `7621db63f23165478c4de817bc38185191ba9bfb54b5835b3b7263f5c23ec2bd`.
- Canonical checkout: `C:/Users/FA507/.codex/legalpdf_translate`, `main`, updated cleanly to implementation merge `751185fca959ab074c328050adf0184f5db76d2c`.
- Actual canonical verification: receipt recorded at 2026-09-17T19:44:52.8118593Z; owned isolated loopback runtime and all 93 served assets matched, asset version `3a37cb2d78df`. Receipt `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/application_ar_publication_20260917_01/canonical_http_verification_run_01/result.json`, SHA256 `513212ea397b21a01caac8eebc3f87603f36501cc46290d9425b550e561be3d6`. Owned server/process cleanup confirmed; settings, original USD10 lifetime ledger and shared Word journal unchanged. No provider/OCR/Word-readiness/native/Gmail/OAuth/external network activity. This verifies HTTP identity/assets, not browser JavaScript behaviour.
- Worktree/branch/ref cleanup disposition: The merged feature branch `feat/arabic-browser-acceptance-20260917` was deleted locally and remotely and refs were pruned. The acceptance worktree is retained with ignored/private evidence and used `codex/arabic-publication-closeout-20260917` at this documentation-authoring checkpoint; inspect actual Git state before reuse.
- Scoped closeout docs validation: Direct-Dart agent-docs and workspace-hygiene validators passed, with 105 agent-docs contract cases and seven hygiene cases. All 54 local Markdown destinations across the six touched documents resolve; LF, final-newline, unresolved-token and whitespace checks passed. `git diff --check` passed. These are documentation checks, not a new HTTP or real-document acceptance run.

The HTTP verification applies to that implementation revision. Later documentation-only revisions do not change its evidence scope or establish a new HTTP-tested HEAD. A subsequent docs-only PR may publish this closeout without replaying the completed HTTP, paid or native operation. Its own required docs/CI checks remain separate; a later implementation change requires proportionate validation.

## Goal and non-goals

Bring the reviewed Arabic reliability fixes into canonical main through scoped commits, a pull request, green exact-head CI, merge, canonical build verification and safe branch cleanup. The user approved the next recommended step after the explanation that these tested changes awaited publication. Prioritize those accepted fixes over optional UI polish or further translation experiments.

No new paid translation/OCR/native acceptance, live Gmail, public hosting, global-default promotion, schema work, historical checkpoint merge or forced history change is included. Preserve all qualified results, consumed helpers, private legal artifacts and saved defaults.

## Scope and worktree provenance

- Authoring worktree: `C:/Users/FA507/.codex/legalpdf_translate_arabic_acceptance`.
- Branch: `feat/arabic-browser-acceptance-20260917`.
- Canonical worktree: `C:/Users/FA507/.codex/legalpdf_translate`, `main`.
- Verified prepublication base and origin/main: `2e31edccad2252c20d55332fe5167c7ff439460f`; the approved floor `4e9d20e` is an ancestor.
- Prepublication worktree status: noncanonical until merge/update. Canonical main was clean and no relevant app/Word process was found at preflight.
- Private publication evidence: `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/application_ar_publication_20260917_01`; six original scoped documentation beforeimages retained.

## Interfaces and implementation

Publication preserves existing routes, payloads, select values, source/formatting ownership and safe text rendering. The accepted change set has eight production files and eight test files, all reverified against the final acceptance inventory. It repairs bounded Arabic signature/witness attribution and citation punctuation, clarifies translation instructions, serializes own-review startup reads, suppresses busy preview reads, closes the formatting launcher menu and corrects generic recovery copy.

1. Inspect the full staged/unstaged/untracked tree and review all intended files; exclude private evidence and scratch output.
2. Reuse exact applicable final targeted/Full evidence while product/test hashes remain unchanged; require fresh CI on the actual PR head. Split product/tests and acceptance/docs into logical commits.
3. Update only current publication/continuity guidance in `HANDOFF.md`, `APP_KNOWLEDGE.md`, `SESSION_RESUME.md` and this plan, preserving beforeimages and earlier acceptance history.
4. Push the reviewed branch, open a PR against main and check its exact head, all CI jobs and review state. Fix concrete failures in this scope without weakening contracts or tests.
5. After green checks, merge with expected-head protection and fast-forward clean canonical main. Recheck process ownership before updating.
6. Verify actual canonical browser build/assets using a fresh bounded isolated verification operation with no provider/OCR/Word/Gmail activity. Record scope honestly; an HTTP asset check does not prove browser JavaScript behaviour.
7. Complete documentation/plan outcome and safe branch/ref cleanup. Preserve retained worktrees when ignored/private artifacts make removal unsafe; never delete evidence to make Git clean.

## Validation and acceptance

The accepted final product/test snapshot passed975 targeted Arabic/parser/protocol tests,24 later UI tests and629 selected Full tests (9 deselected), compilation and successful direct-Dart docs/hygiene fallbacks after the known AOT wrapper error. The Full wrapper is not complete repository pytest. Complete actual E acceptance is separately recorded in the [acceptance closeout](../completed/2026-09-17_arabic_normal_browser_acceptance.md), including terminology/text-only layout and strict PDF extraction qualifications. No consumed helper is reused by publication.

Current CI runs Windows targeted and complete pytest plus documentation/tooling checks; both Windows and Linux jobs must finish successfully on the actual head. Any newer implementation, test or workflow change requires proportionate fresh local validation. Documentation-only updates require direct docs/hygiene validation. Publication is complete only after actual merge, canonical update/verification and recorded cleanup, not merely branch push.

## Rollout, fallback and risks

Use normal PR integration without force push. Stop only the dependent step for red CI, lineage conflicts, unsafe dirty-file overlap or authentication failure; finish independent preparation. Current explicit publication authorization applies to this bounded lifecycle, not unrelated historical branches or acceptance purchases. No new research/cost stage is being started.

## Execution record

Initial prepublication checkpoint (historical), 2026-09-17: Canonical/main/origin/main agree at the base above after fresh fetch; no open runtime was found. Independent source/test review reports no actionable defect and all16 acceptance pins match. GitHub CLI authentication returns401, but the installed GitHub connector successfully accesses this repository with push/admin permission; use an authenticated supported route without exposing or changing credentials. No publication commit/push/PR has yet occurred.

Prepublication reviewed product commits were `38ab786c982a7cb92e85c813ca4f50b379d43be3` (Arabic attribution/citation/prompt plus regressions) and `9757c7f5ea33ea3f9f7974b1d921e99801d5f5ba` (browser ownership/menu/recovery fixes plus regressions). All16 source/test pins remain identical to the accepted final snapshot. Authenticated Git push dry-run succeeded through the existing credential manager; PR and CI operations can use the installed GitHub connector. Current direct-Dart docs/hygiene checks and47 local documentation links pass; a stale acceptance-plan link was repaired before publication. No private runtime/evidence files are included in either product commit.

PR [#298](https://github.com/Adel199223/legalpdf_translate/pull/298) opened on exact head `aa923a0dde60d0135fef63d3c3b49b6bdd35002e`. Its first complete CI run `35257324677` failed: 8 failed, 6,596 passed, 2 warnings in 1,970.88 seconds. The six Arabic historical-instruction cases constructed an obsolete prompt from today's changed instructions, contradicting the deliberately immutable historical digest contract. Two UI checks still expected the replaced Gmail-specific recovery sentence. Merge remains blocked pending corrected tests and fresh exact-head CI; no production admission rule, saved historical profile or actual acceptance artifact is to be changed to satisfy these fixtures. The complete failed log is retained privately under `application_ar_publication_20260917_01/ci_pr298`.

The test-only correction freezes the exact historical instructions from commit `59c086b80014f95ea4760a97eca32cd78002d82d`, independently checks their three established digests, and updates the two expected recovery sentences. All historical rejection cases remain. The five related recovery/review modules passed 202 tests in 11.93 seconds; the two UI message tests passed separately. All 16 originally accepted source/test pins still match, with three additional test files corrected. Fresh standard Full validation and exact-head CI remain required before merge.
