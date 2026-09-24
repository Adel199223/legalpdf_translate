# Refresh the target-language source summary

## Local completion — 2026-09-24

The scoped implementation is independently reviewed and integrated in the unpublished acceptance worktree. All four independently reviewed UI fixes are integrated only in the unpublished acceptance worktree. The final affected suites passed 39 tests; the combined Full wrapper passed 639 selected tests plus compilation and docs/hygiene checks, using the documented direct-Dart fallback. Full is not the complete repository pytest collection. Post-edit closeout docs validation is recorded separately. Desktop and narrow normal-click partial downloads passed using fictional loopback bytes; the actual French download used its observed artifact URL before the UI fix. No paid translation was replayed. The implementation scope is complete; publication is separate. Parent testing is concluded with its documented French failure, deferred optional Arabic formatting and qualified Gmail recovery. Earlier pending-status entries below are retained execution history.

## Goal and non-goals

Update the source card immediately when a user changes the target language. Parent observed a French selection with the card still showing the saved Arabic default during actual FRlong setup. The submitted setup reads the selected value; this patch addresses stale presentation. No translation, source review, settings, Gmail or provider behavior is changed.

## Scope

Bind normal target-select input/change events to the existing source-card renderer. Cover the listener through event-driven regressions. Preserve prepared Gmail target precedence. Do not change payloads, values, routes or safe text rendering.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_target_card_refresh`
- Branch: `codex/target-card-refresh-20260924`
- Base branch: canonical `main`
- Base SHA: `7a86cd07a28496eecfbe3cc7e69398a611242184`, contains approved floor `4e9d20e`.
- Intended later integration: parent-owned `feat/multilingual-gmail-acceptance-20260917`, after its app-source freeze is released.
- Noncanonical isolated preparation only; no app server, publication or live Gmail activity.

## Interfaces and implementation

1. Preserve exact source/test beforeimages privately.
2. Extend the existing translation browser-state harness with normal target input/change dispatch and assertions for immediate summary refresh, saved-default preservation and prepared Gmail precedence.
3. Retain baseline red evidence, add the narrow event listener in `translation.js`, then run affected state/presentation coverage.
4. Seal exact patch and test receipt for independent review. Parent owns integration and combined Full.

## Acceptance criteria

On a local staged source, selecting FR from saved AR and dispatching change updates the visible card to FR without a refresh/upload. Input events also refresh the card, and selecting AR again restores its label. Saved bootstrap defaults remain AR, and no request is dispatched merely from target changes. Prepared Gmail continues to display its fixed prepared target and the separate saved default.

## Rollout and fallback

Leave an uncommitted isolated patch for review; do not integrate or publish. Keep beforeimages and baseline failures. If rejected, retain all evidence without changing the campaign or canonical app.

## Risks and assumptions

The existing presentation function already implements target precedence and safe rendering. Calling it for target events should avoid broad form rerenders or settings writes. Synthetic event-driven tests support this behavior but do not establish a new actual FRlong acceptance result. Current canonical main and frozen campaign source must remain byte-for-byte unchanged.

## Progress

- Plan created before implementation. Parent explicitly authorized this scoped fix and independent review, with Full deferred to integration.
- Added two event-driven scenarios to the existing Node browser-state harness. The local source transitions AR → FR (change) → EN (input) → AR (change) and checks visible card text, retained filename, unchanged saved AR default and zero requests from those changes. The prepared Gmail scenario confirms the prepared EN target and separate AR default remain displayed despite select events.
- Baseline: the local event case failed because the summary stayed AR; prepared Gmail preservation passed. After the one-line listener addition, all10 browser-state tests passed in0.66s, and two adjacent source-card presentation/renderer tests passed. These are fictional module/DOM regressions; no actual browser app or FRlong run was driven by this patch task.
- Exact source/test beforeimages and red/green logs are retained privately. `git diff --check` passed. Canonical and frozen campaign target files remain unchanged. Independent review, parent integration and combined Full remain pending. No app server, provider, Gmail, native or settings operation occurred.
