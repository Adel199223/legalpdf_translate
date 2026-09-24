# Failed translation run navigation and partial downloads

## Local completion — 2026-09-24

The scoped implementation is independently reviewed and integrated in the unpublished acceptance worktree. All four independently reviewed UI fixes are integrated only in the unpublished acceptance worktree. The final affected suites passed 39 tests; the combined Full wrapper passed 639 selected tests plus compilation and docs/hygiene checks, using the documented direct-Dart fallback. Full is not the complete repository pytest collection. Post-edit closeout docs validation is recorded separately. Desktop and narrow normal-click partial downloads passed using fictional loopback bytes; the actual French download used its observed artifact URL before the UI fix. No paid translation was replayed. The implementation scope is complete; publication is separate. Parent testing is concluded with its documented French failure, deferred optional Arabic formatting and qualified Gmail recovery. Earlier pending-status entries below are retained execution history.

## Goal and non-goals

Make an existing failed run and its available partial DOCX discoverable through normal browser controls. Preserve the failed status and distinguish a partial file from a complete translation. No provider dispatch, resume, rebuild, save, Gmail action, default promotion or publication is part of this patch.

## Scope

The actual FRlong job `tx-bb2068fb7b53` failed after five of nine pages. Its server response exposes `download_partial_docx`, but the anchor is inside a completion-only hidden drawer. Recent Work's Open run callback renders the run without changing the visible route. The private terminal response and root's normal-browser finding are retained under `application_multilingual_gmail_acceptance_20260917_01/cases/fr_long_01/`; public tests use fictional jobs only.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_failed_run_artifacts`.
- Branch: `codex/failed-run-artifacts-20260924`.
- Base: canonical `main`, `7a86cd07a28496eecfbe3cc7e69398a611242184`, verified to contain approved floor `4e9d20e`.
- Intended integration: parent's bounded acceptance integration, then canonical `main` only in a separately authorized publication lifecycle.
- Noncanonical isolated UI patch; canonical main and the active acceptance worktree/server remain unchanged.

## Interfaces and contracts

Keep existing routes, backend payloads, artifact URLs, select values, completion/readiness semantics and Gmail contracts. Reuse the existing safe anchor rendering helper. Add only a DOM anchor/card in Run Status for an available failed/cancelled partial DOCX. The anchor remains an ordinary download and never dispatches translation.

## File-by-file implementation

1. `translation.js`: mirror the existing partial artifact URL into the Run Status link only for a failed/cancelled job; clear it on all other renders. Recent Work Open run navigates to New Job/Translation and opens the existing completion drawer only when that surface is already valid.
2. `templates/index.html`: add a hidden partial-document card beside the run result, stating that the file contains completed pages only and is not a complete translation.
3. `tests/test_translation_browser_state.py`: exercise actual Open run click handlers for failed, cancelled and completed fictional jobs; verify navigation, link lifecycle, failure/completion state and zero resume/rebuild/start requests.

## Tests and acceptance criteria

- Record a red regression on the unchanged product source, then a green focused browser-state suite.
- Use the actual app template/modules/styles in a fictional isolated browser fixture to check the normal Open run event and visible incomplete-file link at desktop and narrow widths. This is synthetic UI evidence, not a real provider/document acceptance pass.
- Preserve normal completed result and prepared Gmail behavior through existing targeted tests.
- Run relevant scoped checks and preserve exact source/test/private receipt pins. The parent runs the required combined Full wrapper before integration/publication.
- Obtain independent patch review. No integration or publication from this worktree.

## Rollout and fallback

Parent may integrate the reviewed exact files alongside the other small accepted UI fixes after frozen acceptance work permits it. Until then this patch remains isolated. If a regression is found, revise this isolated patch with new evidence; do not reset or overwrite historical evidence.

## Risks and mitigations

Treating a failed artifact as a completion surface could make Gmail appear ready to save. Avoid that by keeping the completion surface predicate unchanged and exposing the partial file directly in Run Status. All hrefs remain derived from the existing server action flag and job id. The partial link is cleared when switching to a job without that artifact.

## Assumptions and defaults

The backend's existing artifact action flag is authoritative for availability. Source/default settings and historical run data are read-only. Existing parent authorization covers this reversible concrete fix and scoped validation; it does not include a new paid translation or publication.

## Progress

- 2026-09-24: Actual finding and code cause confirmed; isolated branch created from current canonical main before implementation.
- Implementation complete: Open run resets the selected run's save seed, navigates to Translation, and brings incomplete Run Status into view. Failed/cancelled partial files appear in a separate card using the existing artifact URL; the completion/Gmail predicate is unchanged.
- Regression: unchanged-source red reproduced the inert `#recent-jobs` route. An intermediate green attempt exposed the fixture's ordinary bootstrap Arabic-review read in its request count; the fixture was corrected to measure requests after setup. Final focused suites passed 11 tests in 0.91 seconds. No translation/resume/rebuild request occurs from Open run.
- Fictional full-template Chrome 153.0.8010.53 / Playwright 1.62.1 checks cover desktop 1440x1000 and narrow 390x844, missing artifact, cancelled partial, completed drawer and completed-to-failed switching. The changed card/link fit without clipping; narrow layout uses normal page scrolling and has no horizontal overflow. Screenshots were individually inspected.
- A normal partial-link click emitted the exact expected artifact download URL; Chrome cancelled the `.invalid` intercepted-fixture download before its route callback. This is retained as a fixture limitation, not a successful file download. No real app, provider or native operation occurred. The owned fixture browser was closed.
- Exact private receipts are in `application_multilingual_gmail_acceptance_20260917_01/failed_run_artifacts_patch_01`. Independent review and parent combined Full/integration remain pending. Parent must apply product/test hunks to preserve its already integrated target-card listener and tests; do not copy whole files over the acceptance worktree.
