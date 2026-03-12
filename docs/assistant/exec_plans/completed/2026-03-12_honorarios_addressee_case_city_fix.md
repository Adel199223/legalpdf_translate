# ExecPlan: Honorarios Addressee Case City Fix

## Goal and non-goals
- Goal: fix honorários addressee generation so generic court entities include the case city when the entity text does not already mention it.
- Goal: apply the same completion rule to both translation and interpretation default recipient generation.
- Non-goal: change stored Job Log payloads or add any migration/backfill.
- Non-goal: alter manually edited interpretation recipient blocks.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/honorarios_docx.py`
  - focused regression tests in `tests/test_honorarios_docx.py`
- Out of scope:
  - persistence schema changes
  - Gmail/session behavior
  - unrelated docs sync unless requested after implementation

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/honorarios-pdf-stage1`
- Base branch: `main`
- Base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`
- Canonical build status: dirty worktree with prior honorários PDF rollout and docs-governance edits already present; this fix must be additive and isolated

## Interfaces/types/contracts affected
- Add one shared helper in `honorarios_docx.py` that completes a court entity with `case_city` when safe and necessary.
- `default_interpretation_recipient_block(...)` and translation recipient generation keep the same public signatures but change default output text for generic entities missing the city.

## File-by-file implementation steps
1. Add a normalization/completion helper in `honorarios_docx.py` that:
   - leaves blank-city or already-complete entities untouched
   - appends the city without duplicating trailing prepositions like `de`, `do`, or `da`
   - uses case-insensitive, whitespace-tolerant, accent-insensitive city matching
2. Route both translation and interpretation default recipient builders through that helper while preserving the special `Ministério Público` phrasing.
3. Add regression tests covering:
   - generic entity + separate city
   - already-complete entity
   - trailing-preposition entity
   - translation and interpretation paragraph output
   - interpretation recipient auto-sync still tracking `case_city` changes for generic entities

## Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_honorarios_docx.py`
- `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
- Acceptance:
  - `Tribunal Judicial` + `Ferreira do Alentejo` includes the city in the recipient
  - `Tribunal do Trabalho` + `Beja` includes the city in both translation and interpretation defaults
  - `Juízo Local Criminal de Beja` does not duplicate the city
  - manual interpretation recipient overrides still stop auto-sync

## Rollout and fallback
- Rollout: code/test-only fix in the honorários draft generator.
- Fallback: none required beyond reverting this isolated helper change if a wording regression appears.

## Risks and mitigations
- Risk: naive string appending produces malformed phrasing such as `de de Beja`.
- Mitigation: handle trailing prepositions explicitly and lock the behavior with unit tests.
- Risk: duplicate city text when the entity already includes the city with different accents/casing.
- Mitigation: compare using accent-insensitive normalized text before appending.

## Assumptions/defaults
- `case_city` is the authoritative location for addressee completion.
- No UI toggle is needed; this is the default output rule.

## Completion evidence
- Added shared addressee completion logic in `src/legalpdf_translate/honorarios_docx.py` so generic entities now inherit `case_city` only when the entity text is still incomplete.
- Preserved current special handling for `Ministério Público` and preserved interpretation manual-recipient override behavior.
- Added regression coverage in `tests/test_honorarios_docx.py` for:
  - generic translation and interpretation entities
  - accent-insensitive no-duplicate matching
  - trailing-preposition completion
  - dialog auto-sync and manual-override stop behavior
  - DOCX paragraph output for the reported interpretation-style case
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_honorarios_docx.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q`
