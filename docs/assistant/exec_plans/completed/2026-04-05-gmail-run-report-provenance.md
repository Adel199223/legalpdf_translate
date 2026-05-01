# Gmail Run Report Provenance and Token Labeling

## Goal and non-goals
- Goal: preserve Gmail intake provenance through browser translation runs so `run_summary.json` and `run_report.md` reliably include Gmail batch context for Gmail-started runs.
- Goal: tighten run report token wording so summary totals do not look contradictory next to billing totals.
- Non-goal: change Arabic review gating, Gmail confirmation/finalization flow, or Arabic glossary/risk scoring behavior.

## Scope (in/out)
- In scope: browser translation launch/reset state, Gmail-originated run-summary provenance persistence verification, run report summary wording, focused regression coverage.
- Out of scope: DOCX translation content changes, new public APIs, or publish/merge work.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_provenance_fix`
- Branch name: `feat/gmail-run-report-provenance-fix`
- Base branch: `main`
- Base SHA: `804ef487424d16c7cb53654dc806a2b593e8cca5`
- Target integration branch: `main`
- Canonical build status: noncanonical isolated fix worktree; canonical launcher remains on clean `main` until explicit promotion.

## Interfaces/types/contracts affected
- Browser translation launch state for Gmail-originated runs.
- Additive run-summary/report provenance behavior for Gmail-started runs.
- Run report summary wording only; no schema removals.

## File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/static/translation.js`
  - preserve Gmail context across Gmail launch/redo preparation even when stale file-input state exists.
  - ensure Gmail launch path clears conflicting manual-upload state instead of silently dropping provenance before submit.
- `src/legalpdf_translate/workflow.py`
  - verify Gmail batch context persistence remains complete for Gmail-started runs; add any missing forwarded fields only if needed for stable provenance.
- `src/legalpdf_translate/run_report.py`
  - rename token summary wording so run tokens vs billed total are explicitly distinguished.
- `tests/...`
  - add focused coverage for Gmail launch/redo submitting `gmail_batch_context`.
  - add report wording coverage for the clarified token labels and Gmail provenance section rendering.

## Tests and acceptance criteria
- Gmail-started translation submit includes `form_values.gmail_batch_context`.
- Gmail redo preserves context through manual rerun preparation.
- Generated `run_summary.json` for Gmail-originated runs contains `gmail_batch_context`.
- Generated `run_report.md` renders the Gmail Intake / Batch Context section when that context exists.
- Run report summary wording no longer makes `41560` vs `58739` look contradictory.
- Existing run-report download, Arabic review, and Gmail redo tests remain green.

## Rollout and fallback
- Keep the fix isolated in this worktree until browser testing passes.
- If the state-preservation change causes unintended carryover for manual uploads, fall back to a narrower fix that clears only Gmail launch collisions while preserving manual upload semantics.

## Risks and mitigations
- Risk: preserving Gmail context too broadly could leak Gmail provenance into manual file uploads.
- Mitigation: clear Gmail context only on true manual upload paths and clear manual upload state on Gmail launch/redo paths.
- Risk: report wording changes could break existing expectations in tests or downstream review habits.
- Mitigation: keep JSON fields unchanged and limit wording changes to human-readable Markdown summary lines.

## Assumptions/defaults
- The problematic run was intended to originate from Gmail intake.
- A stale file-input/manual-upload state is the likeliest trigger for the missing provenance on rerun without cold start.
- Attachment-level Gmail provenance is more useful when preserved than when silently dropped; additive context fields are acceptable.
