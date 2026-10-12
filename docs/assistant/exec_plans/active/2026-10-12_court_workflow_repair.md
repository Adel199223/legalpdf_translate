# Court translation workflow repair

## Goal and non-goals

Repair defects exposed by the October 12 real court-request audit, then finish both requested formal-Arabic translations, complete source and native Word review, and prepare one unsent reply when the full set is acceptable. Do not send mail, change saved translation models, weaken literal fidelity, or replay successful paid work.

The user explicitly authorized fixing the defects and finishing translations after reviewing the blockers. Implementation and validation are authorized. Publication and application to the canonical live app remain a separate approval gate; prepare a concrete tested result before requesting that approval. Current authorization supersedes historical stage tokens for this bounded work.

## Scope

In: source-proven Arabic literal/address boundary equivalence; composite LTR identifier grouping; safe text correction in paragraphs containing retained page-break controls; recovery controls that preserve failed-job state; bounded diagnostics needed to establish lost-literal causes. Relevant tests and touched-scope documentation.

Out: schema/routes/payload/extension contract changes; broad redesign; automatic batch skip or general restart persistence redesign; unrelated settings or providers; publication before approval. A bounded local, hash-verified recovery capsule/import is necessary to preserve these terminal in-memory jobs across the approved update; it performs no provider, save, fee, draft, or review-acceptance action.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/worktrees/court-workflow-repair/legalpdf_translate`
- Branch: `feat/court-workflow-repair-20261012`
- Base branch: `main`
- Base SHA: `9250d61f0fbba55f58723894674f8f362fe641fa`
- Target integration: canonical `main`
- Status: noncanonical implementation; approved-base floor `4e9d20e` verified as ancestor.
- Canonical live app remains unchanged in `C:/Users/FA507/.codex/legalpdf_translate`, PID 21888, ports 8877/8765, asset `dc7afa0279f6`.
- Parallel coding must use separate worktrees; no concurrent writes to canonical files.

## Interfaces and contracts

Preserve backend paths, API payload shapes, browser route IDs and submitted values. Preserve safe text insertion. Keep source occurrence/multiplicity and protected-content validation strict. Text-only correction must preserve page breaks, paragraph properties and unsupported controls; allow only the proven safe subset. Reject field edits and structural mutations.

## Implementation steps

1. Arabic modules (`arabic_pre_tokenize.py`, `validators.py`, `ar_literal_fidelity.py`, relevant DOCX token writers): trace actual retained failure, design source-bound equivalence and atomic LTR field handling; add fictional adversarial regressions before changing behavior. Do not infer missing rejected response bodies.
2. Correction module (`ordinary_text_correction.py` and consumers): permit bounded wording replacement around retained page-break controls, preserving their structural placement and rejecting control changes in Word imports. Cover raw and automatically formatted documents.
3. Recovery UI (`translation.js`, Gmail stage action routing/presentation): Resume Recovery must restore the exact failed job/config and preserve completed-page reuse. Redo stays explicit and separate. Add causal browser/service tests.
4. Add bounded private failure evidence/literal deltas if needed for reproducible diagnosis; do not print private response bodies or secrets.
5. Integrate independently reviewed patches in this worktree; update architecture, handoff, validation and user guidance only where behavior changes.
6. Capture raw job bootstrap, separate selected-delivery overlays and both Gmail sessions privately before stopping the live server. Implement and dry-run local terminal recovery with immutable file pins, trusted baseline reconstruction, selected correction history, exact identities and idempotency. Preserve separate batch ownership; any future cross-batch adoption is outside this repair.

## Tests and acceptance

- Pinned `.venv311` setup via tracked setup script; no version upgrades.
- Focused fictional regressions: whole address versus postcode, extra/missing/repeated literals, altered identifiers, ambiguous numeric regrouping, composite LTR runs, page-break preservation, Word-import structure rejection, failed Gmail recovery versus redo.
- Retained-input offline reproductions without provider calls. Preserve source/run/accounting beforeimages and inspect all four accusation native Word pages after correction.
- Standard `scripts/validate_dev.ps1` and required `-Full`; record Dart wrapper fallback accurately. Independent review before live application request.
- Review UI in shadow mode with isolated app data only. No real Gmail on feature branches.
- After approved application, recover retained completed outputs and failed-page work without duplicating saves, charges or drafts. If restart loses in-memory sessions, implement/use a verified supported restoration path or present that concrete limitation before touching the running server.
- Manually review every final translated page and all exact source fields; verify normal download bytes, selected-delivery word counts, save joins, fee PDF and one unsent draft. No send.

## Rollout and fallback

Keep the canonical live server, two workspaces and artifacts intact until a tested rollout/recovery plan is reviewable and approved. Preserve all original/partial/corrected documents and journals. Do not modify checkpoints to force success. Request live-application approval only after checks and concrete recovery planning are complete.

## Risks and mitigations

False-positive literal equivalence could hide source loss: require source proof, exact characters and occurrence accounting; test adversarial boundaries. Correction could drop pagination or fields: preserve control tokens and reject unsupported structure changes. Recovery could repeat completed work: bind actual job identity, immutable config and completed-page reuse. Live restart can lose Gmail batch state: preserve the running process and prepare restoration before asking to apply.

## Assumptions and evidence

Formal legal Arabic is explicitly confirmed. Private evidence root is `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/court_request_20261012_01`. Notice has two terminal failed attempts on page 1 with pages 2/3 retained. Accusation has four successful translations, automatic layout and three supported approved terminology changes; the mandatory measurement-clause correction remains blocked and full output review is not confirmed. No new case, fee document, draft or sent reply exists. Known cost is USD1.11332725 plus one unknown OCR billing result. Original source/private content must not enter public tests or repository docs.

## Progress

- Audit completed; user expanded scope to fixes and completion.
- Isolated integration worktree created; implementation design and preservation review underway.
- Arabic literal/writer and safe page-break correction implementations pass focused tests in separate worktrees. Recovery navigation passes 27 focused browser/state cases; it only fetches retained jobs, rejects binding changes and leaves the existing failure intact when unavailable.
- Read-only private recovery capture retained both failed notice jobs and the completed accusation, raw bootstrap and selected overlays separately. Latest notice job is `tx-c50df1d59a89`; canonical process remains untouched. Recovery implementation is in a fourth isolated worktree.
- All worker changes are integrated. Independent review found and resolved stale polling/recovery responses, prepared-session reload, paragraph bidi restoration, overlapping address-field ownership and preferred reply-email restoration. Focused tests cover each. Source-field preprocessing prevents generic wrappers from nesting known overlapping values, while disjoint exact occurrence counts/order remain strict.
- Private native correction probe has four pages and 927 words, preserves the original 925-word selected delivery, all protected numbers and the three earlier approved edits. It is only a validation artifact, not an app-selected or approved final delivery. A separate same-text road-formatting probe improved Latin order but worsened mixed-script spacing; do not adopt that probe automatically.
- Recovery capsule02 dry-run restores the latest failed notice and completed accusation into two separate registries, preserving selected correction history, raw costs and pending review. Its source backup covers two owned temp directories/three source files. All 569 protected originals were unchanged. Explicit missing-source restoration requires live-update approval and refuses mismatched existing bytes.
- Integrated Standard01 passed 262 cases plus compilation/docs/hygiene before final narrow review fixes. Known Dart AOT wrapper exit255 recovered via successful direct fallback. Final integrated focused and Full validation are next; no live application or final document acceptance is inferred.
- Final focused validation passed 377 Arabic-related cases and 98 combined recovery/correction/browser cases. Full01 ran all selected test groups: 2,123 passes and one reproduced baseline Qt sidebar-width failure (2,124 executions including 191 formatting cases; nine expected deselections), exit1 in 2,567.195 seconds. No product/test/script changed during Full; only INDEX and recovery-workflow documentation were intentionally corrected. The final docs/hygiene validators pass separately. Preserve the qualified Full result; do not weaken the unchanged desktop test or claim it passed.
- Final offline accusation probe04 supersedes earlier probes: both pending paragraph corrections render correctly in four native Word pages, with 927 words, exact quantities, prior edits and all page/field controls preserved. The action JSON uses the normal correction function and remains unapplied to the live selected output. Generic Arabic Word audit flags only its header/footer template convention; actual app page presentation is separately reviewed.
- Stage 1 implementation and bounded validation are ready for review with the disclosed baseline Qt qualification. Stage 2 is the separate local canonical update/restart and normal completion of both translations, subject to explicit live approval. Stage 3 is final delivery/audit closeout within the existing completion authorization; it adds no publication or sending scope. Private Live_Update_Review.md carries changed-file, validation, risk, decision-lock and next-stage prompt details. The live approval token is NEXT_STAGE_2; no new token is needed for work already authorized within the approved completion scope.
