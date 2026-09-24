# Persistent Gmail intake failure copy

## Local completion — 2026-09-24

The scoped implementation is independently reviewed and integrated in the unpublished acceptance worktree. All four independently reviewed UI fixes are integrated only in the unpublished acceptance worktree. The final affected suites passed 39 tests; the combined Full wrapper passed 639 selected tests plus compilation and docs/hygiene checks, using the documented direct-Dart fallback. Full is not the complete repository pytest collection. Post-edit closeout docs validation is recorded separately. Desktop and narrow normal-click partial downloads passed using fictional loopback bytes; the actual French download used its observed artifact URL before the UI fix. No paid translation was replayed. The implementation scope is complete; publication is separate. Parent testing is concluded with its documented French failure, deferred optional Arabic formatting and qualified Gmail recovery. Earlier pending-status entries below are retained execution history.

## Goal and non-goals

Show the existing failure reason after a failed Gmail handoff is restored through bootstrap. Preserve detected subject context when no loaded message exists. This addresses a real unavailable-account handoff whose UI displayed only “needs attention” and “No subject”. Authentication, sending email and live acceptance are outside this patch.

## Scope

In scope: browser presentation of failed load results and fictional regression coverage, including safe text rendering. Out of scope: backend, routes, payloads, select values, Gmail/native/extension contracts, credentials, saved defaults and operational helpers.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_gmail_error_copy`
- Branch: `feat/gmail-intake-error-copy-20260918`
- Base branch: canonical `main`
- Base SHA: `7a86cd07a28496eecfbe3cc7e69398a611242184`
- Target integration: parent-owned multilingual acceptance worktree, then separately authorized publication
- Noncanonical, never launched; canonical live server and the campaign source freeze remain unchanged.

## Interfaces and contracts

Use the already returned `load_result.status_message`, `load_result.intake_context`, and existing bootstrap context. No external interface change. Render all dynamic strings with existing safe text insertion.

## File-by-file implementation

1. Preserve exact beforeimages privately under the current campaign's `gmail_error_copy_patch_01`.
2. Add fictional bootstrap failure and malicious-text regressions to the existing Gmail presentation/DOM tests; retain red baseline evidence.
3. Update message-result and panel-status presentation only as needed. Preserve ordinary successful load behavior.
4. Run focused Gmail state/presentation/DOM tests. Parent runs the final combined Full validation after integration.

## Acceptance criteria

An unavailable failed bootstrap without a message displays its actionable reason and retained subject. A failed result without a reason gets useful fallback copy. Successful results retain their current presentation. Markup in a reason or subject appears literally, with no HTML insertion. No live Gmail, provider, OAuth or native calls are made by tests.

## Rollout and fallback

Deliver a bounded uncommitted patch and private evidence receipt to the parent for review. Do not change running canonical assets. If rejected, leave the isolated patch and evidence intact; no operational rollback is necessary.

## Risks and mitigations

Keep the successful result branch unchanged. Prefer precise failed status over generic guidance, without exposing raw diagnostic payloads. Preserve source evidence and distinguish fictional regression success from a later live verification.

## Assumptions and progress

- Existing backend `status_message` is user-facing text; safe insertion remains required.
- Root explicitly authorized this patch and targeted validation, with combined Full deferred until integration.
- 2026-09-18: plan created before implementation; diagnosis and exact source beforeimages sealed privately.
- Added six fictional cases covering three subject-context sources, literal malicious strings, absent failure detail, and unchanged success/active-session copy. Before the patch, five failed and the unchanged-success case passed.
- The final two-file presentation patch passed all six new cases and both complete Gmail review-state tests (8 total). Adjacent message-result/control/stage/DOM coverage passed 12 cases; 210 unrelated cases were deselected. Canonical Python and the existing disposable Node module harness were used; these are synthetic regressions, not live Gmail acceptance.
- `git diff --check` and exact source preservation checks are included in the private handoff receipt. Parent review, integration and combined Full validation remain pending; no publication or running-server change occurred.
