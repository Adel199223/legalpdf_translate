# Recover Word PDF Export on the Local Host

## Goal and non-goals
- Goal: restore reliable DOCX->PDF export for interpretation honorarios on this Windows machine from the latest-feature runtime and shadow harness.
- Goal: distinguish true host/Word COM launch failures from missing-PowerShell or other wrapper failures so the app reports the right problem.
- Goal: keep the current calm local-only fallback while improving the underlying export success path.
- Non-goal: change Gmail draft gating or broader translation/export workflows beyond what is necessary for the shared Word automation path.
- Non-goal: make destructive system changes or require external downloads unless explicitly approved.

## Scope (in/out)
- In scope:
  - reproduce the Word COM failure in foreground and background process contexts
  - inspect and correct failure-code classification/messaging in the Word automation helper
  - adjust launch/runtime behavior if the detached shadow server context is the real blocker
  - add targeted regression tests for the recovered behavior
- Out of scope:
  - Office installation/repair via external installers
  - schema changes
  - replacing Word automation with a different PDF engine

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Target integration branch: `main`

## Interfaces/types/contracts affected
- `src/legalpdf_translate/word_automation.py`
- Possibly the shadow server/launcher behavior if process context is the cause
- Interpretation export callers that surface Word automation failures

## File-by-file implementation steps
1. Reproduce the Word COM startup/export failure outside the browser harness and compare foreground versus detached/background contexts.
2. Correct failure-code classification and user-facing messaging in `word_automation.py`.
3. If detached server context is the issue, update the shadow runtime/launcher to avoid the broken context or route export through a safe helper path.
4. Add targeted tests for classification and the recovered export path semantics.
5. Revalidate with a real honorarios DOCX->PDF attempt from the latest-feature runtime.

## Tests and acceptance criteria
- Foreground/healthy latest-feature runtime can export a real interpretation honorarios PDF on this machine, or the remaining block is precisely identified as a host limitation outside app control.
- `0x80080005` / `CO_E_SERVER_EXEC_FAILURE` classifies as `com_launch_failed`, not `powershell_missing`.
- Shadow/local-only fallback still works and still blocks Gmail/PDF-dependent behavior when no PDF exists.
- Targeted tests pass for any new classification or recovery logic.

## Risks and mitigations
- Risk: detached/background process context is incompatible with Office COM automation.
  - Mitigation: verify with direct host repro before changing code; if confirmed, route export through a safe foreground helper.
- Risk: host-level Office state remains broken even with correct code.
  - Mitigation: improve diagnostics and preserve local-only fallback rather than masking the issue.
- Risk: changes affect Qt and shadow export paths together because they share the helper.
  - Mitigation: validate both via shared helper tests and a real export repro.

## Assumptions/defaults
- The shadow harness and Qt app should share the same Word automation behavior where practical.
- This machine has Microsoft Word installed, but COM startup may depend on the caller’s process/session context.
- External Office repair/install actions are not assumed in this pass.
