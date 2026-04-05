## Title
Redo Current Gmail Attachment Without Cold Start

## Goal and non-goals
- Goal: let the browser Gmail workspace intentionally rerun the current unconfirmed attachment without a cold start, while keeping the existing Gmail batch session intact.
- Non-goals: whole-batch replay, browser/Gmail reset behavior changes, Arabic review flow changes, or automatic rerun after selecting redo.

## Scope (in/out)
- In scope: Gmail batch launch metadata, Gmail home/strip CTA logic, translation UI reset hook for Gmail redo, and focused test coverage.
- Out of scope: new external APIs, translation-job persistence across full app restarts, and changes to finalization or confirmation semantics.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_redo`
- Branch name: `feat/gmail-redo-current-attachment`
- Base branch: `main`
- Base SHA: `7c5923578bb8f109fdf7327d5bad71d6e1fcf7a1`
- Target integration branch: `main`
- Canonical build status: noncanonical implementation worktree; intended to merge back into canonical `main`

## Interfaces/types/contracts affected
- Additive Gmail translation launch metadata for current-attachment identity and batch provenance.
- Additive `form_values.gmail_batch_context` passed into browser translation starts.
- Additive Gmail UI action/CTA path for `Redo Current Attachment`.

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_browser_service.py`
  - Extend suggested translation launch payloads with Gmail batch context for the current attachment.
- `src/legalpdf_translate/translation_service.py`
  - Accept/persist `gmail_batch_context` from browser form values into `RunConfig`.
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - Add redo-aware CTA derivation and matching-job warning logic.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Render the secondary redo action, block it for actively running jobs, and wire it to translation reset hooks.
- `src/legalpdf_translate/shadow_web/static/translation.js`
  - Add a Gmail redo reset helper that clears translation-side state only, reapplies the launch payload, and leaves the operator ready to start manually.
- `tests/test_gmail_review_state.py`
  - Add redo CTA and matching-job warning coverage.
- `tests/test_gmail_browser_service.py`
  - Add suggested-translation launch context coverage.
- `tests/test_shadow_web_api.py`
  - Add additive payload assertions if bootstrap/session responses now expose the new launch metadata.

## Tests and acceptance criteria
- Gmail home shows both resume and redo for an active unconfirmed translation attachment.
- Completed/finalized sessions do not expose redo.
- Matching active running/cancel_requested jobs block redo with clear guidance.
- Matching completed/failed/cancelled jobs allow redo with warning copy.
- Redo clears translation-side state only and leaves the Gmail batch session/current index untouched.
- Translation jobs launched from Gmail retain `gmail_batch_context`.

## Executed validations and outcomes
- `py_compile` passed for the touched Python files.
- `python -m pytest -q tests/test_gmail_review_state.py tests/test_gmail_browser_service.py tests/test_shadow_web_api.py tests/test_translation_service_gmail_context.py`
  - Outcome: `54 passed`
- `node --check` passed for:
  - `src/legalpdf_translate/shadow_web/static/gmail.js`
  - `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - `src/legalpdf_translate/shadow_web/static/translation.js`

## Rollout and fallback
- Ship as additive UI/state behavior only.
- If matching logic misfires, fallback is still available through existing `Resume Current Step` and `Reset Gmail Workspace`.

## Risks and mitigations
- Risk: redo could accidentally target the wrong attachment after navigation.
  - Mitigation: match by stored Gmail batch context first, then use `source_path` only as fallback.
- Risk: redo could feel like a duplicate run launcher for already-running jobs.
  - Mitigation: explicitly block redo while a matching job is still running or cancel-requested.
- Risk: clearing too much state could break Gmail batch continuity.
  - Mitigation: keep the reset hook translation-local and avoid mutating Gmail session manager state.

## Assumptions/defaults
- Redo applies only to the current attachment.
- Redo should prefill and wait for manual `Start Translate`.
- Existing output files remain on disk.
- No full app/server restart persistence is required for this pass beyond the current live runtime.
