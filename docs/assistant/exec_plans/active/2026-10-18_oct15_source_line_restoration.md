# October 15 source-bound address line restoration

## Goal and non-goals
Permit the correction guard to accept an exact source address block whose CR/LF boundaries the primary flattened to single ASCII spaces. Retain all content, multiplicity, required-token and whole-token ownership guards. No runtime, provider, Gmail, protocol, pretokenization or general whitespace changes.

## Scope
Bounded correction-fidelity helper and new synthetic regression module; existing tests remain unchanged. Private diagnostics are read without exposing retained document text. Broad docs integration, Standard/Full validation and installation belong to the parent task.

## Worktree provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/oct15-source-line-restoration/legalpdf_translate`
- Branch: `feat/oct15-source-line-restoration`
- Base branch: `main`
- Base SHA: `c4cd6b953661ed3207c6a1b1b6892727242cfe9a`
- Target integration: parent review/integration; canonical main remains live and untouched.
- Status: noncanonical source-only worktree; no app launched.

## Interfaces/types/contracts affected
No public contracts. Extend only private correction proof with source-bound address candidates. Existing evaluator arguments and source extraction remain unchanged.

## File-by-file implementation steps
1. `src/legalpdf_translate/ar_source_fields.py`: add a bounded exact 2/3-line address-block classifier using existing street/locality recognition, strict postal final line and unmodified CR/LF witness.
2. `src/legalpdf_translate/ar_literal_fidelity.py`: add source-proven flattened/restored group candidates to the existing disjoint whole-token allocator; require exact source uniqueness and unique target occurrences, complete token boundaries, protected coverage, ordered association and resource limits.
3. `tests/test_ar_source_line_restoration.py`: fictional full evaluator reproduction using real pretokenization/required tokens; positive exact source restoration and strict negatives for source absence/ambiguity/order, content changes, arbitrary whitespace/newlines, wrapper errors, occurrence reuse and bounds. Existing tests unchanged.
4. This ExecPlan: record test and private read-only proof receipts and deferred parent validations.

## Tests and acceptance criteria
Run targeted Arabic fidelity/address/pretokenization/evaluator tests via this worktree's `.venv311/Scripts/python.exe`, reconstructed offline from existing locked dependencies with no upgrades. Verify old pair still passes and new pair passes in a private read-only evaluator check, with source provenance qualification if runtime inputs cannot be proven. No provider calls. Local logical commit only after targeted success; no push.

## Rollout and fallback
Parent independently reviews, integrates and runs required Full before any separately authorized installation. Failure leaves canonical live main unchanged; original diagnostics retained.

## Risks and mitigations
Fail closed on malformed/oversized source, ambiguous witnesses, widened/nested token ownership and exhausted bounded proof work. Do not collapse arbitrary whitespace or alter case, punctuation, accents, digits or inline spaces.

## Assumptions/defaults
Current bounded implementation authorization supersedes historical stage tokens; no external/live boundaries crossed. Do not touch the parent's dirty integration documentation.

## Progress and validation
- 2026-10-18: isolated exact base; read project runbooks, private pair summary and independent forensic audit. Concrete files locked above before editing code/tests.

### Implemented result
- Added `source_address_line_blocks` as a correction-only classifier. Existing `source_address_fields`, pretokenization, required-token contract, canonicalizer and evaluator remain unchanged.
- Integrated exact source restoration candidates into the existing disjoint whole-token allocator. Source, primary and correction occurrences must be unique; candidate and unchanged address blocks preserve source order; all protected occurrences reserve distinct target ownership.
- Added a separate bounded source witness scan budget, alongside the existing group work/state budgets. Exact inline content and CR/LF witness boundaries remain untouched by this guard.
- Test fixtures match the retained correction's five-token packaging (street fragment, house digits, intermediate locality, postal digits, final locality). Initial synthetic full-line wrappers did not satisfy the real numeric required-token contract: first run had 3 failures/246 passes; later full-postcode variant had 1 failure/262 passes. These were fixture corrections, with no source-token or canonicalizer expansion. Private receipt retains these outcomes.

### Validation and evidence (2026-10-18)
- Offline locked environment reconstruction completed in this worktree with `UV_OFFLINE=1`; pinned Python 3.11.9 and application imports verified, existing lock/package versions unchanged.
- Seven targeted Arabic modules: **271 passed in 2.06s**. Private `source_line_restoration_code_01/targeted_pytest_02.txt` SHA256 `be73ed1a79e957078e3fed7a32410ab7a340a169fc2c001d985c59d2caca6f55`. Existing tracked tests are unchanged.
- Agent docs validator and `git diff --check` passed.
- Independent review accepted frozen production files; reviewer reran all 271 in 2.02s and 41 additional adversarial checks. A 2,000-witness source failed closed in 0.078s. Reviewer evidence is owned by the parent operation.
- Private `source_line_restoration_code_01/retained_evaluator_comparison_01.json` SHA256 `3fefd0f6405f9e4d46f5fc17e884b7e13d0e7893df367784d0efc7598471898f`: identical checkpoint PDF fingerprint/settings/extracted/pretokenized/required-array hashes for baseline and patch. Source route is recorded direct text, no OCR or browser bundle, repeated actual extraction is identical, extraction length and locked-token count match checkpoint. Both retained primaries reproduce exactly through initial evaluation, and both expected-token packaging deltas reproduce exactly.
- With those identical reconstructed inputs, original pair full evaluation passes before/after; new pair changes from `correction_literal_fidelity_loss` on c4cd6b9 to full evaluator acceptance on the patch, with identical correction normalized-output hashes. The private probe is rerunnable read-only with an explicit code-root argument.
- Qualification: the original runtime source pack was not retained. These are deterministic reconstructed source inputs supported by exact PDF fingerprint, recorded direct-text route/counts and expected-token delta hashes; original runtime source bytes are not independently attested. This is retained-response causal validation, not another paid Resume or end-to-end delivery run.
- Existing raw-output normalization collapses blank LF lines and canonicalizes CRLF before correction proof. Compatibility is tested explicitly; this patch introduces no arbitrary whitespace normalization. The guard itself requires exact normalized candidate/source boundaries.

### Frozen file hashes
- `src/legalpdf_translate/ar_literal_fidelity.py`: `b31dbb124399dcc1977e526f9f515791f3ce44edd7e793dd2907efe18fe83c61`
- `src/legalpdf_translate/ar_source_fields.py`: `3f59cde12674a472ac7ccf769a6164bfb993d87edf89159b16f866a6324d0940`
- `tests/test_ar_source_line_restoration.py`: `eba6ee22aefc36b2b870ceb3a0d3acdb00590722904939fa2d0398517ef11f50`

### Handoff boundary
Implementation and targeted review are complete. Keep this plan active until parent integration/closeout; parent owns Standard/Full validation on the clean committed child tree and any separately authorized application. Canonical main/live services, provider calls, Gmail and the parent's dirty integration docs were untouched. Local logical commit only; no push.
