# Preserve phone-shaped numeric triplets in Arabic DOCX runs

Implementation, independent review and local validation completed on2026-09-26. Publication is authorized and pending its exact-head lifecycle; root owns merge/application. The private publication receipt below and actual repository state determine that status. Historical progress text remains preserved.

## Goal and non-goals

Fix the demonstrated DOCX direction defect where a complete phone-shaped ASCII number split into three protected three-digit tokens is rendered in reversed group order by native Word. Preserve every source/output character and Arabic word order. Do not broaden Latin-address grouping, alter pre-tokenization/provider prompts, introduce settings, change contracts, or modify the active canonical runtime.

## Scope

- In: a narrow closed three-by-three ASCII numeric grouping rule in the shared Arabic DOCX run builder; fictional run/OOXML regressions; focused no-provider validation and required Full.
- Out: arbitrary numeric whitespace grouping, two-number sequences such as 09 30, postal-address inference, document/source edits, provider retries, live/native/Gmail operations, cap changes and publication before root review.

## Worktree provenance

- Reused managed isolated checkout: C:/Users/FA507/.codex/worktrees/word-startup-readiness/legalpdf_translate.
- New branch: codex/arabic-phone-triplets-20260926.
- Verified base branch: origin/main; base SHA5b2c94b899b6827c3e1b82026009d96b087f6b26; treea06772f303ac8a25e6bd09905c5da8e6131ed258.
- Target integration: main. Canonical live03 uses the same base under root ownership and must remain unchanged while active.
- Existing publication, private closeout draft, beforeimages, ledgers and runtime support remain preserved.

## Interfaces and contracts

Only internal run-direction classification changes. Routes, API payloads, placeholder/token contracts, source/checkpoint text, provider/default settings and native/Gmail contracts remain unchanged. Native visual acceptance is separate from fictional OOXML tests.

## Demonstrated cause

Read-only inspection of the request04 candidate confirms correct logical digit order but separate LTR runs with RTL space runs between them. The placeholder-aware line builder sends each whitespace-only token gap through direction segmentation with no strong neighbor, so it defaults to RTL. Plain/whole-token numeric text already becomes one LTR run. Existing clock and numeric-slash repairs do not cover spaces. The existing no-whitespace-number-grouping test is an intentional boundary and must remain valid.

## File-by-file steps

1. src/legalpdf_translate/docx_writer.py: add a conservative phone-shaped triplet separator repair at the shared placeholder-aware grouping seam. Relabel only the two internal ordinary spaces in a closed ASCII three-digit/three-digit/three-digit sequence; preserve original bytes, outer RTL separators, explicit line barriers and existing controls. Decline partial larger numeric groups, identifier/word attachment, conflicting or incomplete retained bidi scopes, and all non-phone shapes. Keep existing clock/slash and Latin-only-line behavior.
2. tests/test_docx_phone_triplet_runs.py: fictional cases for split, whole, plain and mixed protection; normal LRI/PDI wrappers and stripping modes; safe boundaries and negative groups; exact character concatenation and direction-change locality; saved DOCX via the normal writer with one LTR phone run, Arabic RTL neighbors and provider/native guards.
3. This active plan: record scope review, regression evidence, frozen hashes, focused tests and Full. Coordinate later touched-scope status docs with root; keep the five-request parent active.

## Tests and acceptance

- Reproduce a fictional split-token phone failure before the source change.
- Preserve test_docx_clock_runs.py::test_no_numeric_grouping_across_whitespace_only_boundary and existing numeric-slash/clock/layout regressions.
- Run focused tests with the isolated .venv311 interpreter. No provider/native process or live service may be started.
- Freeze source/tests before independent review and scripts/validate_dev.ps1 -Full. Preserve wrapper log, exit result, raw evidence and file hashes privately under five_oldest_requests_20260926_01/phone_triplet_fix_01/.
- Synthetic tests establish exact OOXML grouping only. Root owns artifact corrections and native review; do not claim new native acceptance from these tests.

## Rollout and fallback

Hold publication for root's patch review. User already authorized demonstrated corrections/publication; root owns merge/application after runtime retirement. No active helper/source mutation or successful-job replay. Preserve original artifacts and receipts if any future adoption fails.

## Risks and mitigations

Three separated numbers are not universally a phone number. Recognize only the evidenced closed nine-digit triplet shape, decline larger/ambiguous expressions, and retain separate-number regressions. Do not swallow Arabic or Latin words, punctuation, tabs or line breaks. Retained bidi controls require complete compatible scope proof; conflicting scope keeps existing behavior.

## Assumptions and progress

- Root explicitly authorized this narrow fix after the demonstrated artifact failure; independent scope review must agree before code edits.
- Initial checkpoint: read-only diagnosis and fresh-base isolation completed before any code or test change. The previous five-request closeout preparation remains private and unfinished.
- Independent scope review approved the exact closed ASCII triplet and whole-paragraph retained-control guard before source edits. The implementation changes only its two internal spaces to LTR after normal paragraph segmentation, on both existing routes; it preserves outer separators, text bytes, line barriers and earlier clock/slash behavior.
- Before-fix fictional regression receipt `phone_triplet_fix_01/before_tests_02` contains six failures (four split-token variants and two saved-DOCX variants), with twelve controls passing. The earlier first attempt also included four overstrict plain-parenthesis assertions; that fixture expectation was corrected and its original log is preserved separately.
- Focused phone/clock/numeric-slash/layout validation passed548 cases in8.28seconds; whitespace check passed. Source/test freeze and independent review precede required selected Full. These are no-provider synthetic tests, not new native Word visual acceptance. Root's later transient metrics observation resolved asynchronously and did not establish another defect or expand this scope.
- Independent frozen-source review found no blocker, and all103 new phone cases passed in0.84seconds. Source SHA `bbf634dc88a4eda677223668fcf8f5bcfa1194b9c02a39baab11d66632359a55`, test SHA `9a6eef5211dc82391de2c2c55262762f1f51ef3d54a33f8a376888718a68d0cd`; independent JUnit SHA `11a2f0f946f00dccb1bc068dc936f11e1ab4192f2f984f4fb0d742f464338565`. Required Full now runs on this frozen three-file scope; publication remains held for root review and runtime lifecycle coordination.
- Required Full subsequently passed with exit0 in804.604seconds:664 selected executions (245 browser/API,2 Gmail state,5 intake with9expected deselections,239 reviewed-source,173 formatting), compilation and docs/hygiene. Both formatting workers passed; expected Dart AOT255 recovered through direct-Dart fallback. All three frozen source/test/plan hashes stayed unchanged. Private `phone_triplet_fix_01/full_01/result.json` SHA `6d9f227ff8d5c460eed8e9e34a68d15c4be57329efe913772f1765be8b7e099f`, wrapper SHA `7c7ded79050237116314e1be0f555841f945e032575ddf5e314fb2b4596c8e20`; raw evidence `tmp/validation/formatting-d8aee6a7b67349418828dd31785901cc/`.
- Root reviewed the exact frozen writer patch and found no blocker. Publication is authorized under existing user scope but briefly held to include verified parent-workflow terminal documentation in the same PR. Source/tests remain frozen; only docs may change after Full, with exact beforeimages and one final direct docs/hygiene/whitespace check. Root alone merges/applies after owned runtime retirement. This append does not assert request04/05 or parent completion.

## Final workflow coordination and publication handoff

The parent five-request workflow is now verified complete and moves to `completed/`: all five reached reviewed drafts, the user later sent1–3, and4–5 remain unsent. Final live03 terminal audit passed34 checks with owned runtime/native cleanup and current interactive Word preserved. This supersedes the earlier temporary publication hold; root has released scoped publication under existing user authorization, subject to final docs/privacy review. No source/test changed after the passed Full.

Final docs scope is limited to root/bridge APP_KNOWLEDGE, HANDOFF, SESSION_RESUME, VALIDATION, completed parent plan and this plan. Exact beforeimages are private `phone_triplet_fix_01/parent_docs_closeout_01/beforeimages/`. Run direct docs/hygiene/whitespace once, confirm frozen source/test hashes, and obtain scoped independent/root review. Commit/push the reviewed source/tests and docs as logical commits; create/attach its PR and verify the exact-head checks. Root alone merges/applies; this explicitly narrows the default push lifecycle. Preserve all failed tests and historical CI receipts.

Actual phone publication identity and subsequent integration status belong in `phone_triplet_fix_01/publication_01/publication_receipt.json` plus actual repository state; do not invent a future SHA or claim the patch is applied before that evidence. No further selected translation, artifact replacement or consumed-helper execution is required. Broader address grouping remains outside product scope.

Root requested branch-scoped closeout before merge: this implementation plan moves to `completed/` with all scoped links updated. Its publication lifecycle remains pending via the private receipt, not implied complete by this plan move. Final direct docs/hygiene/whitespace and frozen-source checks cover this docs-only change.
