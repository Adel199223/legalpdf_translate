# Gmail translation count wording

Current status: **Source implementation and required local validation complete.** Canonical application remains separately receipt-gated as described below.

## Goal and non-goals
Use singular Portuguese wording for one attached translation and plural for multiple translations. Preserve signatures, fee attachments, attachment order, original reply subjects and interpretation wording. No Gmail, browser, native application, provider or runtime operation belongs to this implementation task.

## Scope
In: shared Gmail body builder, manual single-translation subject, focused regression cases and scoped documentation. Out: routes, payload schemas, reply/thread contracts, publication, saved data, existing real drafts and completed evidence.

## Worktree provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/email-retest-oct15/legalpdf_translate`
- Branch: `feat/gmail-template-number-20261017`
- Base branch / target integration branch: canonical `main`
- Base SHA: `7b8252894ae8952ad3a2d6b1a89d8a30dbc24578`
- Noncanonical isolated implementation; canonical runtime remains owned by the parent task. Approved-base floor verified by parent before delegation.

## Interfaces/types/contracts affected
The internal body helper receives an explicit translation count. Request builders derive it from translation inputs, excluding the fee PDF; existing request shapes and external contracts stay unchanged. The subject helper is only used for manual single-translation requests.

## File-by-file implementation
1. `src/legalpdf_translate/gmail_draft.py`: choose the requested singular/plural opening, pass actual batch count or manual count one, and make the manual subject singular.
2. `tests/test_gmail_draft.py`: test exact single/manual body, one/two/three translations plus fee PDF, subject/thread/attachment order, signature and unchanged interpretation wording.
3. Touched-scope docs: preserve exact beforeimages privately; record implementation and validation with explicit installation limits. Parent owns final current handoff/validation closeout.

## Tests and acceptance criteria
Use canonical `.venv311/Scripts/python.exe` with this worktree's `src` on `PYTHONPATH`, isolated temp/cache paths and no dependency changes. Run affected draft and service tests. Parent reviews and owns Standard/Full validation. Acceptance: count only translation inputs; one translation with a fee PDF remains singular; two/three translations are plural; original reply subjects, signature and attachment order remain correct; interpretation wording remains exact.

## Rollout and fallback
Hold commit and return the diff plus exact checks to parent. Parent owns review, required validation and authorized promotion. No installation or existing-draft acceptance is inferred from source tests.

## Risks and mitigations
An omitted count could restore static wording: make the internal argument required and inspect all callsites. Total attachment count would include the fee PDF: derive count from the resolved translation tuple only. Preserve interpretation builders unchanged and assert their exact opening.

## Assumptions/defaults
Manual translation requests contain exactly one translated DOCX; batch validation already requires at least one distinct translated artifact. Declaration-only flows do not invoke this translation-body builder.

## Progress
- Plan created before implementation; source and service callsites inspected.
- Implemented required count argument, singular manual subject and exact requested openings. Browser/Qt callsites use the shared request builders; no separate preview body template was found.
- Focused validation passed: canonical `.venv311` Python, worktree `PYTHONPATH`, isolated private temp/cache, `pytest -q tests/test_gmail_draft.py tests/test_gmail_browser_service.py`: **54 passed in 2.66s**, exit 0. Log: private `gmail_template_number_20261017_01/implementation/targeted_01.log`.
- A separate receipt-generation interpreter initially reported its own canonical import because its environment was not inherited across tool calls. That probe was not the test process. A source-bound repeat asserted the exact worktree module path in the same interpreter as pytest: **54 passed in 1.79s**, exit 0 (`targeted_02.log`). Both original evidence and corrected receipt are retained; repeated counts are not additive.
- `git diff --check` passed. Scoped architecture/user-guide beforeimages preserved under private implementation evidence; guides qualify installation status.
- Parent source/test review accepted. Standard passed 267 cases (pytest 47.82 seconds), exit 0; selected Full passed 2,153 executions (1,962 logged grouped plus 191 disjoint formatting), with nine actual intake deselections, exit 0. All 1,215 frozen file pins, path set and package versions stayed exact. Both wrappers recorded known Dart AOT exit 255 and successful direct-Dart docs/hygiene fallback. Exact evidence belongs to private `gmail_template_number_20261017_01/validation/receipt.json`; Full log SHA256 is `1c1fd38f482a72c6cee6b976c42da16d153a386910e2094bbee320a86b52ee34`.
- Parent separately corrected the existing unsent reply in place and verified the exact body, original thread/reply headers/signature and two attachment byte sequences, with all four other drafts unchanged, no new draft and no send. Private `gmail_template_number_20261017_01/draft_edit/verification_receipt.json` and `draft_edit/fresh_checkpoint_01.json` own that live result. No live operation was performed by this implementation subtask.
- Scoped HANDOFF, VALIDATION and architecture closeout preserve immediate beforeimages under private `gmail_template_number_20261017_01/implementation/docs_closeout_01/beforeimages/`. This implementation plan is closed and moved to `completed/` after required local checks; local commit, canonical fast-forward and import/runtime verification remain root-owned.
- Private `gmail_template_number_20261017_01/local_application_receipt.json` owns exact canonical commit/import and runtime status. An absent or failed receipt means application remains unconfirmed. No installation, restart acceptance, remote publication or hosted CI is inferred from source tests or the existing-draft edit.
