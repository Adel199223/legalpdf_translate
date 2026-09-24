# French legal-language clarification

## Local completion — 2026-09-24

The scoped implementation is independently reviewed and integrated in the unpublished acceptance worktree. All four independently reviewed UI fixes are integrated only in the unpublished acceptance worktree. The final affected suites passed 39 tests; the combined Full wrapper passed 639 selected tests plus compilation and docs/hygiene checks, using the documented direct-Dart fallback. Full is not the complete repository pytest collection. Post-edit closeout docs validation is recorded separately. Desktop and narrow normal-click partial downloads passed using fictional loopback bytes; the actual French download used its observed artifact URL before the UI fix. No paid translation was replayed. The implementation scope is complete; publication is separate. Parent testing is concluded with its documented French failure, deferred optional Arabic formatting and qualified Gmail recovery. Earlier pending-status entries below are retained execution history.

## Goal and non-goals

Clarify the structured French system instruction after an actual two-page ordinary-browser run stopped on its first page. Both retained primary and correction responses left Portuguese criminal-code titles untranslated; the strict language validator rejected them. The exact effective glossary matched the run fingerprint and did not mandate either code title; the French addendum was empty. The existing instruction ambiguously applies “verbatim” to Portuguese legal concepts as well as proper names. That contradiction is concrete; provider reasoning and deterministic causation are not established.

This task changes instructions only. It does not weaken validation, substitute French law, alter saved settings/models/effort, add retries, dispatch providers, operate Word/Gmail, or accept the failed output.

## Scope

In scope: one French instruction, synthetic workflow/fingerprint regressions, unchanged-response offline diagnosis, and a private integration patch. Out of scope: other language instructions, glossary edits, API/payload/schema changes, real acceptance replay, publication, and unrelated UI work.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_french_legal_language`.
- Branch: `codex/french-legal-language-20260917`.
- Base branch: canonical `main`.
- Base SHA: `7a86cd07a28496eecfbe3cc7e69398a611242184`, containing approved floor `4e9d20e`.
- Integration target: root-owned `C:/Users/FA507/.codex/legalpdf_translate_multilingual_acceptance`; no direct edits there.
- This is a noncanonical offline authoring worktree. No app/server is launched from it.

## Interfaces, types and contracts

No route, payload, schema, source/target text, token validator, retry count or runtime/default contract changes. French system-instruction and translation fingerprints are expected to change; historical requests remain pinned to their original instructions. English and Arabic instructions remain byte-identical.

## File-by-file implementation

1. `src/legalpdf_translate/translation_structure.py`: distinguish preservation of Portuguese legal meaning/jurisdiction from translation of legal terms, titles and ordinary labels into formal French; preserve accented proper names and identifiers verbatim.
2. `tests/test_new_translation_blocks.py`: exercise the actual offline workflow request/correction/commit path and rejection of stale prompt fingerprints with fictional legal content.
3. This plan: record validation and handoff scope. Private evidence is stored outside Git under `application_multilingual_gmail_acceptance_20260917_01`.

## Tests and acceptance criteria

- Existing strict language validation continues to reject the unchanged actual failed responses with their exact effective glossary.
- Fictional French workflow fixtures demonstrate that translated legal labels, source names, identifiers and citation numbers can pass the existing contract, while Portuguese legal-title leakage is rejected and receives only the existing correction attempt.
- Changed French instructions invalidate an existing old-instruction resume fingerprint before a further synthetic dispatch; English and Arabic instructions remain unchanged.
- Run affected targeted tests plus direct documentation/hygiene validation. Root explicitly owns one later combined Full validation after integration; do not start a duplicate Full wrapper.
- Independent static review must find no extra behavioral scope.

## Rollout and fallback

Export an uncommitted private patch and exact inventory for root review/integration. A later fresh ordinary-browser case, separately authorized and budgeted by root, is needed for actual outcome evidence. Do not replay the consumed failed case. If regressions fail, retain failures and revise only the scoped change.

## Risks and mitigations

A stronger prompt cannot guarantee legal fidelity. Preserve the failed responses and explicit quality limitations; do not equate successful synthetic validation with real translation quality. Keep Portuguese jurisdiction and ambiguous source meaning explicit, and retain strict literal/citation checks. Do not turn code titles into protected proper names or silently replace them with another jurisdiction’s law.

## Assumptions and defaults

The current user authorizes scoped fixes and useful docs synchronization. Root authorized this isolated change and targeted-only validation. Saved glossary/addendum/defaults remain authoritative and unchanged. No commit, push, network, provider, OCR, native or ledger operation is included.

## Progress and outcome

The exact effective glossary reconstruction matched all nine entries and the retained page fingerprint. Both unchanged paid responses still fail the unchanged `validate_block` contract with `block_language_or_token_defect`: each has seven untranslated criminal-code titles, plus an untranslated civil-code title outside that specific detector. The correction also has an ordinary Portuguese label. Separate number and citation inventories match; these observations do not override the language failure. The private failed-target review is SHA256 `80eb2bbc276a3f8aa31d1e3588792e1c4cd08a53ca3813ffcee4e7698e87cb62`; no source, response, settings, run state or ledger was changed.

Validation: all 291 affected structure/workflow/EN-FR validator/glossary tests passed in 6.46 seconds, including three new synthetic workflow/identity cases. An earlier invocation referenced a nonexistent validator filename and ran zero tests; its exit-4 log is preserved separately, not counted as a pass. Independent static review found no actionable issue in the frozen French-only source/test diff. Synthetic completion keeps fidelity review `not_evaluated`. No real translation was attempted with the clarified instruction in this task. Root owns the integrated Full validation and any fresh actual acceptance case; this branch does not claim either result.
