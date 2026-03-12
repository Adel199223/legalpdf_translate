# Legal Header Glossary And Institutional Header Matching Hardening

## Goal and non-goals
- Goal: harden recurring Portuguese legal institutional header translation so court/prosecution/judicial header phrases translate consistently across EN, FR, and AR.
- Goal: share one reusable institutional header catalog between prompt glossary injection and metadata/header parsing.
- Goal: keep case-specific noise out of the glossary and header matching pipeline.
- Non-goal: redesign the whole glossary system or broaden into non-header legal content.
- Non-goal: add user-facing glossary review-note schema fields.

## Scope (in/out)
- In scope:
  - reusable institutional header phrase and template-family catalog
  - header-specific normalization and variant matching
  - prompt glossary header-priority injection
  - metadata/header parser reuse of the shared institutional matcher
  - EN/FR/AR glossary consistency updates
  - screenshot-derived regression coverage
- Out of scope:
  - process numbers, references, dates, addresses, contact blocks, barcodes, recipient identities, signatures
  - non-header translation behavior except where prompt ordering or source matching must change to support header accuracy

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/legal-header-glossary-hardening`
- Base branch: `main`
- Base SHA: `5a4a2b7379f43193572aae46fcea369b20b8f567`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch off the current approved `main` baseline

## Interfaces/types/contracts affected
- Add a new internal legal-header catalog/matcher module shared by `glossary.py`, `workflow.py`, and `metadata_autofill.py`.
- `workflow._append_glossary_prompt(...)` will prepend matched institutional header entries before the regular capped glossary rows.
- Default EN/FR/AR glossary seeds will generate header-domain rows from one shared source of truth.
- Metadata header extraction will prefer catalog-based institutional matches over the current first-regex-hit behavior.

## File-by-file implementation steps
- `src/legalpdf_translate/legal_header_glossary.py`
  - add canonical institutional phrase/template catalog
  - add normalization helpers for OCR/header variants
  - add matching helpers that return surface-form exact glossary entries for matched phrases
- `src/legalpdf_translate/glossary.py`
  - generate header-domain default entries from the shared catalog
  - keep non-header defaults intact
  - preserve deterministic prompt sorting and deduplication
- `src/legalpdf_translate/workflow.py`
  - inject matched header glossary entries ahead of generic glossary rows
  - ensure header-priority entries survive prompt capping and do not duplicate seeded rows
- `src/legalpdf_translate/metadata_autofill.py`
  - reuse the shared institutional matcher for case-entity extraction
  - keep case number, city, and court-email heuristics intact unless small glue changes are needed
- `tests/test_legal_header_glossary.py`
  - add unit coverage for normalization, variants, template families, and language mappings
- `tests/test_glossary.py`
  - replace brittle fixed-count seed assertions with canonical entry and consistency assertions
- `tests/test_workflow_glossary.py`
  - cover header-priority prompt injection and prompt-cap survival
- `tests/test_metadata_autofill_header.py`
  - cover screenshot-derived institutional header families and specificity preference

## Tests and acceptance criteria
- Focused tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_legal_header_glossary.py tests/test_glossary.py tests/test_workflow_glossary.py tests/test_metadata_autofill_header.py`
- Full regression:
  - `.\.venv311\Scripts\python.exe -m pytest -q`
  - `.\.venv311\Scripts\python.exe -m compileall src tests`
- Acceptance:
  - the same Portuguese institutional header phrase maps consistently across EN/FR/AR
  - screenshot-derived recurring headers are matched as phrases or template families, not by fragile single-word fallback
  - header-priority glossary entries are injected before generic rows and survive prompt caps
  - metadata extraction prefers the most specific institutional phrase
  - no case-specific noise becomes a glossary/header entry

## Executed validations and outcomes
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_legal_header_glossary.py tests/test_glossary.py tests/test_workflow_glossary.py tests/test_metadata_autofill_header.py` -> passed (`69 passed`)
- `.\.venv311\Scripts\python.exe -m compileall src tests` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q` -> passed (`937 passed`)

## Rollout and fallback
- Keep the implementation internal to existing glossary and metadata flows so no migration is needed.
- If a term is too risky to support automatically, exclude it from the enforced catalog and record it in the implementation report review shortlist.
- If a header family cannot be safely normalized, prefer exact canonical phrases over over-broad variant matching.

## Risks and mitigations
- Risk: over-broad normalization could match body text or create false positives.
  - Mitigation: keep matching scoped to institutional/header phrases and prefer specific template families with boundaries.
- Risk: prompt-cap logic could still drop header entries.
  - Mitigation: prepend matched header entries before generic rows and deduplicate early.
- Risk: legal over-translation of Portuguese institutions into foreign equivalents.
  - Mitigation: use institution-preserving translations and rely only on authoritative sources for uncertain terminology.

## Assumptions/defaults
- Supported target languages remain `EN`, `FR`, and `AR`.
- Portuguese place names, sections, and judge numbers remain preserved inside translated institutional titles.
- Ambiguous institutional phrases stay out of the enforced glossary until they can be supported safely.
