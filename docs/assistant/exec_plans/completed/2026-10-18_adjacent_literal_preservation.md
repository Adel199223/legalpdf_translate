# Exact adjacent protected-literal preservation

## Goal and non-goals
Accept correction-only split/merge of adjacent protected literals when every visible character is identical. Keep case, diacritics, punctuation, numbers, occurrence multiplicity and disjoint ownership exact. No translation rerun, live API/Gmail/native operation, installation or publication.

## Scope and provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/oct15-adjacent-literal-preservation/legalpdf_translate`
- Branch: `feat/oct15-adjacent-literal-preservation`
- Base branch/SHA: canonical `main`, `e148535c5e3018c48d31a627c0b94aa1edeb5ce4`
- Target: root-owned integration after scoped local commit.
- This checkout is noncanonical and serves no app.

## Contracts
No route, payload, saved setting, checkpoint, required-literal or provider contract changes. Existing source-bound address repair/canonicalization and numeric regrouping remain intact.

## Implementation steps
1. Read preserved primary/correction/source evidence without displaying private content; confirm exact wrapper regrouping failure.
2. Validate complete wrapper structure and add exact adjacent-token span matching. Only whitespace/punctuation between protected tokens may belong to a group; visible strings must match exactly.
3. Allocate each preserved primary and corrected occurrence once. Reject omitted repetitions, widened digits, changed punctuation/case/diacritics, intervening unprotected words and malformed wrappers.
4. Add fictional direct and evaluate-output regressions, plus retained-evidence offline verification. Run targeted tests and direct docs checks, close plan and commit scoped files.

## Tests and acceptance
Demonstrated street/house and postal/locality splitting passes; inverse merging passes. Exact content changes, repeated/overlapping occurrence loss and unprotected prose remain rejected. Existing required-token and source-bound repair checks retain their outcomes. No network/native dispatch occurs.

## Rollout and fallback
Root cherry-picks the local commit into the combined integration branch and owns final Full validation and live acceptance. Original failed responses, charges and source bytes remain unchanged.

## Risks and mitigations
Overlapping group candidates must never reuse an occurrence. Strict token parsing and exact bounded groups prevent substring/numeric widening. Keep a fast exact-token count path and fail closed if a bounded ambiguous search cannot establish disjoint ownership.

## Assumptions and status
Current private review establishes identical visible source-proven spans with wrapper-only changes. Implementation is complete. The existing strict source-field parser validates wrappers, and whole-token group matching retains exact whitespace/punctuation without crossing unprotected words. Disjoint allocation includes required occurrences so a number inside one preserved group cannot mask a second required number. Existing source-bound numeric/address repair exemptions remain unchanged.

## Validation and limitations
- The six-file targeted suite passed all 199 tests in 1.75 seconds. Private JUnit: `oct15_request_20261018_01/fix_adjacent_literal_01/targeted_02.xml`.
- New tests cover split/merge, exact case/diacritics/punctuation/whitespace, numeric widening, unprotected words/numbers, duplicate/nested/overlapping loss, non-greedy occurrence allocation, malformed wrappers and fail-closed resource bounds. The initial tests caught required-number masking; allocation was corrected before the passing suite.
- Independent review found no correctness blocker in ten additional adversarial probes. Its resource-budget observation was addressed by charging searched edges to the same bounded proof budget; pending/visited states are separately capped. Final review disposition remains separately retained by the reviewer.
- The exact retained primary/correction pair failed the old guard and passes the repaired guard with every primary occurrence protected. Input hashes match and original files remain unchanged. This is pure local guard causality, not a new accepted run: the original full source/required-token pack was not retained, so full-evaluator acceptance is not claimed.
- Private `final_validation_01.json` retains source pins, JUnit identity, beforeimage hash and the qualified retained-pair result. No provider/native/Gmail operation or checkpoint write occurred.
- Direct-Dart docs and workspace-hygiene validators and `git diff --check` passed. Root owns combined integration, final Full validation and any live recovery.
