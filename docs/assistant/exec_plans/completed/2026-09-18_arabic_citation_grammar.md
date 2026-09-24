# Bounded Arabic citation grammar

## Local completion — 2026-09-24

The scoped implementation is independently reviewed and integrated in the unpublished acceptance worktree. All four independently reviewed UI fixes are integrated only in the unpublished acceptance worktree. The final affected suites passed 39 tests; the combined Full wrapper passed 639 selected tests plus compilation and docs/hygiene checks, using the documented direct-Dart fallback. Full is not the complete repository pytest collection. Post-edit closeout docs validation is recorded separately. Desktop and narrow normal-click partial downloads passed using fictional loopback bytes; the actual French download used its observed artifact URL before the UI fix. No paid translation was replayed. The implementation scope is complete; publication is separate. Parent testing is concluded with its documented French failure, deferred optional Arabic formatting and qualified Gmail recovery. Earlier pending-status entries below are retained execution history.

## Goal and non-goals

Recognize supported contracted Arabic article heads and explicit Arabic subdivision labels in the existing bounded citation counter. An actual Arabic short-document correction retained the required article numbers and passed literal/numeric validation, but the citation parser did not recognize these constructions. The original failed run remains failed and immutable. This work does not certify translation quality or authorize a replay.

## Scope

In: narrow citation grammar, its policy fingerprint, and fictional positive/adversarial regressions. Out: source/target edits, glossary/default changes, numeric or literal-validator relaxation, retry changes, provider/native/server operations, publication and Gmail.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_arabic_citation_grammar`
- Branch: `feat/arabic-citation-grammar-20260918`
- Base: canonical `main`, `7a86cd07a28496eecfbe3cc7e69398a611242184`
- Approved floor: `4e9d20e`, ancestry checked before worktree creation.
- Target integration: the parent's isolated multilingual acceptance worktree; parent owns integration and combined Full validation.
- Status: noncanonical offline authoring only; no app launched.

## Interfaces and contracts

No routes, payload shapes or user defaults change. The citation-policy version changes deliberately so old-policy resume identities are rejected. Existing literal and numeric validators, one normal correction and failure boundaries remain unchanged.

## File-by-file steps

1. `tests/test_citation_elision.py`: add minimal fictional failures for contracted definite article heads and Arabic subdivision chains; retain explicit bounds and reject unrelated prose/bare numbers.
2. `src/legalpdf_translate/new_translation_blocks.py`: extend only those recognized forms and bump citation policy.
3. Update this plan with focused results and immutable actual-response offline revalidation.

## Tests and acceptance

Use canonical `.venv311/Scripts/python.exe` with this worktree's source. Record baseline red tests, then run citation/literal/integration-focused tests. Positive grammar must preserve source citation counts; malformed/punctuation/line/date/step-bound cases must remain rejected. Revalidate the unchanged actual correction using its exact saved glossary/prepared-source contract, privately pinning all inputs. Primary language/token failure must remain a failure. Do not claim fresh end-to-end acceptance from offline checks.

## Rollout and fallback

Export a scoped patch and exact file hashes for parent review and integration. Parent runs the combined Full wrapper and separately decides any future paid case. No commit, push or publication is delegated here.

## Risks and mitigations

Arabic paragraph labels can resemble article references. Consume them only after explicit citation heads and comma-delimited recognized subdivision labels. After a subdivision, an elided article must still carry the existing ordinal/suffix marker. Do not cross a line, sentence, semicolon or unrelated prose; keep character/step caps and exact occurrence counts.

## Assumptions and defaults

The current two-page accepted source and both provider responses are immutable evidence. No source-specific article value or label exception is permitted. Saved app model, effort, protocol and all budget controls remain unchanged.

## Executed validation and outcome

Baseline fictional checks produced 10 failures and 5 passing boundary cases. The v5 change then passed all 135 citation tests, followed by 550 affected citation, block integration, literal, glossary and translation-structure tests (7.59 seconds). Parent and independent reviewer found no actionable issue in the scoped diff.

Pure offline revalidation used the unchanged actual accepted source, both retained responses and the exact saved nine-entry glossary fingerprint. The primary response still fails `unsupported_latin_or_digit_content`; the correction now passes the complete block validator. No source or response substitutions were used. Wrapper/isolate canonicalization occurs in memory as in the normal validator; no retained artifact changed. The original case remains a failed, zero-commit run. Private evidence is under `application_multilingual_gmail_acceptance_20260917_01/arabic_citation_grammar_patch_01`; the unchanged-response receipt SHA256 is `25f798dd4dc4108efa320c0f6059fc6ac3df8659a94b1f0d3e034a19760e33bb`.

Only contracted definite heads and explicit comma-delimited Arabic subdivision labels were added. Numeric `الفقرة 1` remains outside this deliberately narrow grammar. Strict literal/numeric validation, exact citation counts, tail limits and retry policy remain intact. Parent owns integration, combined Full validation and any separately authorized fresh real case; none was performed in this worktree.
