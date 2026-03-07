# Gmail Draft Suggestion for Honorarios Export (V1)

## 1) Title
Add a Windows-only Gmail draft suggestion after successful current-run honorarios DOCX export.

## 2) Goal and non-goals
- Goal:
  - suggest creating a Gmail draft immediately after successful current-run honorarios DOCX generation
  - use current run `court_email` as recipient
  - attach the translated output DOCX and the generated honorarios DOCX
  - use Windows `gog.exe` with deterministic subject/body
  - add small settings for `gog` path and Gmail account detection/testing
- Non-goals:
  - no auto-send
  - no historical Job Log row support in V1
  - no Gmail OAuth management in-app
  - no translation/OCR/model changes

## 3) Scope (in/out)
- In:
  - Gmail draft helper module
  - current-run Save-to-Job-Log honorarios flow
  - Windows-only settings/test UI for `gog`
  - unit and Qt tests
- Out:
  - historical Job Log email drafting
  - WSL/Linux Gmail integration
  - sending emails automatically

## 4) Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail`
- Branch name: `feat/gmail-honorarios-draft`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `1d63121`
- Target integration branch: `feat/ai-docs-bootstrap`

## 5) Interfaces/types/contracts affected
- Add internal Gmail draft contracts:
  - `GmailDraftRequest`
  - `GmailDraftResult`
  - `GmailPrereqStatus`
- Add additive GUI settings:
  - `gmail_gog_path`
  - `gmail_account_email`
- Current-run only hook after honorarios export from Save-to-Job-Log dialog

## 6) File-by-file implementation steps
- Add `src/legalpdf_translate/gmail_draft.py` with `gog` path resolution, account detection, prerequisites check, and draft creation
- Extend `src/legalpdf_translate/user_settings.py` with Gmail settings defaults/load/save
- Extend `src/legalpdf_translate/qt_gui/dialogs.py`:
  - settings tab for Gmail draft integration
  - current-run post-export suggestion after honorarios generation
- Add tests for helper logic and Qt flow

## 7) Tests and acceptance criteria
- Gmail prerequisite detection reads real Windows `gog` JSON shapes
- Draft payload uses exact fixed subject/body and both attachments
- Save-to-Job-Log current-run flow prompts only when prerequisites and `court_email` are available
- Missing attachment or missing recipient blocks draft creation with a clear message
- Historical Job Log flow does not offer Gmail draft creation in V1

## 8) Rollout and fallback
- Local feature branch only
- If Gmail prerequisites are not available, honorarios export still succeeds and email drafting is skipped
- If draft creation fails, show a clear error and keep exported DOCX files intact

## 9) Risks and mitigations
- Risk: Windows `gog` path or account setup drift
  - Mitigation: explicit settings, auto-detect fallback, and a prerequisite test button
- Risk: ambiguous account selection
  - Mitigation: auto-detect only when exactly one Gmail account exists; otherwise require settings selection
- Risk: incomplete draft due missing attachments
  - Mitigation: block draft creation when any required attachment path is unavailable

## 10) Assumptions/defaults
- V1 is Windows-only and draft-only
- Recipient comes from current form `Court Email`
- Subject is `Traduções e requerimento de honorários - Processo [Case #]`
- Body is the locked Portuguese template provided by the user
