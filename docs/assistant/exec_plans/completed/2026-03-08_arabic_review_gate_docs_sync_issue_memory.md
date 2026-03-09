# Arabic Review Gate Docs Sync + Issue Memory

## Goal And Non-Goals
- Goal: sync the shipped Arabic DOCX Word review-gate behavior into canonical/current-truth docs, user guides, local host docs, refresh notes, and durable issue memory.
- Goal: preserve the failed Arabic OOXML-only alignment attempts and the reverted Gmail post-save continuation experiment in issue memory so future work does not repeat them blindly.
- Non-goal: change code, change product behavior, or revive any reverted Arabic OOXML alignment experiments.

## Scope
- In scope:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
  - `docs/assistant/LOCAL_CAPABILITIES.md`
  - `docs/assistant/LOCAL_ENV_PROFILE.local.md`
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/ISSUE_MEMORY.json`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Out of scope:
  - any code edits
  - any claim that Arabic right alignment is solved purely in OOXML
  - any blanket docs rewrite outside the touched behavior

## Worktree Provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `e57f6679389a1afc43d29f26256987db12a41078`
- Target integration branch: `feat/ai-docs-bootstrap`
- Canonical build status: canonical worktree; docs-only sync against the shipped Arabic review-gate behavior already present in the worktree

## Interfaces Types Contracts Affected
- User-facing docs now state:
  - Arabic runs pause in a Word review gate before `Save to Job Log`
  - the review dialog auto-opens the DOCX in Word, offers `Align Right + Save`, auto-continues after detected save, and falls back to manual save plus `Continue now` / `Continue without changes`
  - Arabic Gmail batch items pause at the same review gate before `Save to Job Log`, and the reviewed saved DOCX is the downstream artifact
  - `Save to Job Log` exposes `Open translated DOCX`
- Local host docs now state:
  - this feature depends on Windows Word plus PowerShell COM automation
  - same-host Windows validation is required
  - WSL-only validation is insufficient for this path
- Issue memory now preserves:
  - failed OOXML-only Arabic alignment attempts and why they failed
  - the reverted Gmail post-save finalization experiment and the higher validation bar it established

## File-By-File Implementation Steps
1. Update `APP_KNOWLEDGE.md` and `docs/assistant/APP_KNOWLEDGE.md` with the Arabic review-gate runtime contract and `Open translated DOCX`.
2. Update `docs/assistant/features/APP_USER_GUIDE.md` and `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` with the shipped Arabic review flow and Windows-host fallback guidance.
3. Update `docs/assistant/workflows/TRANSLATION_WORKFLOW.md` so future triage treats the Word review gate as the supported mitigation and does not default back to speculative OOXML rewrites.
4. Update `docs/assistant/LOCAL_CAPABILITIES.md` and `docs/assistant/LOCAL_ENV_PROFILE.local.md` with the Windows Word + PowerShell COM dependency and same-host validation requirement.
5. Append two durable entries to `docs/assistant/ISSUE_MEMORY.md` and `docs/assistant/ISSUE_MEMORY.json`:
   - Arabic DOCX right alignment in Word: `mitigated`
   - Gmail post-save finalization regression: `mitigated`
6. Append a dated superseding note to `docs/assistant/DOCS_REFRESH_NOTES.md`.

## Tests And Acceptance Criteria
- Acceptance criteria:
  - user-facing docs describe the Arabic review gate and `Open translated DOCX`
  - canonical docs describe the Windows Word automation dependency and fallback behavior
  - issue memory records the failed OOXML-only attempts and the reverted Gmail continuation experiment
  - no current-truth doc claims Arabic auto-right-alignment is solved purely in OOXML
- Executed validations:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
- Outcome:
  - both validators passed
  - `ISSUE_MEMORY.json` parses successfully after the update

## Rollout And Fallback
- Rollout: docs-only; no runtime deployment step required.
- Fallback: if later product behavior changes again, update current-truth docs to the new shipped behavior while retaining the failed-attempt history in issue memory unless it becomes obsolete.

## Risks And Mitigations
- Risk: user-facing docs accidentally describe abandoned OOXML experiments as live behavior.
  - Mitigation: keep failed attempts only in issue memory and refresh notes.
- Risk: future debugging forgets the Windows-host dependency and re-tests only from WSL.
  - Mitigation: document same-host Windows validation in local host docs and workflow docs.
- Risk: future Gmail post-save changes repeat the same regression pattern.
  - Mitigation: store the rollback reason and stronger validation bar in issue memory.

## Assumptions Defaults
- The Arabic Word review gate is the current shipped behavior and should be treated as canonical until replaced.
- The failed OOXML alignment attempts are still valuable context, but not user-facing behavior.
- No `manifest.json` or routing index changes are required for this docs-sync pass.
