# ExecPlan: Interpretation Honorarios Closing Structure

## Goal and non-goals
- Goal: align the interpretation honorarios closing block with the approved structure by centering `Espera deferimento,` and collapsing the IBAN section into one sentence line.
- Goal: keep the interpretation signature label as `O Requerente,`.
- Non-goal: change the translation honorarios template.
- Non-goal: alter interpretation body wording, recipient wording, or persistence.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/honorarios_docx.py`
  - focused regression tests in `tests/test_honorarios_docx.py`
- Out of scope:
  - UI/forms
  - Job Log/Gmail/session behavior
  - docs sync unless explicitly requested later

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/honorarios-pdf-stage1`
- Base branch: `main`
- Base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`
- Canonical build status: dirty worktree with prior honorários rollout and addressee-fix changes; this template change must stay isolated to interpretation output

## Interfaces/types/contracts affected
- No public API/type changes.
- Interpretation paragraph output contract changes:
  - one-line IBAN sentence
  - centered `Espera deferimento,`
  - no left-aligned `Pede deferimento.` paragraph

## File-by-file implementation steps
1. Update interpretation paragraph construction in `honorarios_docx.py`.
2. Update interpretation paragraph expectation tests and one DOCX-generation regression in `tests/test_honorarios_docx.py`.
3. Validate interpretation-only behavior while leaving translation expectations unchanged.

## Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_honorarios_docx.py`
- `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
- Acceptance:
  - interpretation output uses one-line IBAN sentence
  - `Espera deferimento,` is centered
  - `O Requerente,` remains centered
  - translation output remains unchanged

## Rollout and fallback
- Rollout: isolated template/test change only.
- Fallback: revert this narrow interpretation paragraph change if any wording mismatch appears.

## Risks and mitigations
- Risk: paragraph index shifts break interpretation tests.
- Mitigation: lock the new order and alignment with paragraph-level and DOCX-level assertions.

## Assumptions/defaults
- `Melhores cumprimentos,` stays left-aligned.
- `O Requerente,` remains the signature label even though the old sample used a different variant.

## Completion evidence
- Updated the interpretation paragraph builder in `src/legalpdf_translate/honorarios_docx.py` so the closing block now uses a one-line IBAN sentence, preserves `Melhores cumprimentos,`, inserts a blank line, and centers `Espera deferimento,`.
- Kept `O Requerente,` centered and left translation output unchanged.
- Updated `tests/test_honorarios_docx.py` to lock the new interpretation paragraph order, IBAN sentence, centered deferimento line, and DOCX alignment expectations.
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_honorarios_docx.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q`
