# Gmail Honorarios Local Court City Fix

## Goal And Non-Goals
- Goal: correct Gmail translation save/finalization metadata so specific local court evidence, such as `Juízo de Competência Genérica de Cuba`, wins over generic comarca evidence, such as `Comarca de Beja`, for job-log and honorarios output.
- Non-goal: change Gmail same-tab intake, native-host launch, CMD-window mitigation, runtime-state roots, or Gmail draft routing.

## Scope
- In scope: metadata autofill ranking, translation save seed propagation, honorarios regression coverage, and focused validation.
- Out of scope: direct edits to existing live job-log rows or already-created Gmail drafts/PDFs.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/gmail-honorarios-local-court-city-fix`
- Base branch: `main`
- Base SHA: `bdfbde8`
- Target integration branch: `main`
- Canonical build status: canonical primary worktree, branch created from clean `main`
- Approved-base floor: `4e9d20e`

## Interfaces And Contracts
- `MetadataSuggestion` remains backward compatible.
- Translation `save_seed.case_city` and `save_seed.service_city` should use the most specific local court city when available.
- Gmail draft `court_email` selection remains unchanged and continues to prefer the extracted exact email.

## Implementation Steps
- Add wrapped/local prosecution unit recognition for metadata extraction.
- Rank metadata suggestions so specific local court units outrank earlier generic comarca or plain `Ministério Público` hits.
- Preserve fallback behavior when only generic comarca evidence exists.
- Add regression coverage for metadata, translation save seeds, and honorarios recipient text.

## Tests And Acceptance Criteria
- `Comarca de Beja` plus `Juízo de Competência Genérica de Cuba` resolves to `Cuba`.
- Translation save seed propagates `Cuba` into both case and service city while keeping `cuba.ministeriopublico@tribunais.org.pt`.
- Honorarios recipient and closing city use `Cuba`.
- Focused test gate passes without touching Gmail launch code.

## Executed Validation
- `.\.venv311\Scripts\python.exe -m pytest tests/test_metadata_autofill_header.py::test_extract_header_metadata_prefers_wrapped_general_jurisdiction_city_over_generic_public_prosecution tests/test_metadata_autofill_header.py::test_priority_page_metadata_prefers_specific_local_unit_over_earlier_generic_comarca_email tests/test_translation_service_run_report.py::test_translation_seed_uses_specific_local_court_city_for_honorarios_metadata tests/test_honorarios_docx.py::test_build_honorarios_paragraph_texts_uses_cuba_for_plain_ministerio_publico_when_seed_city_is_cuba -q` -> PASS, 4 passed.
- `.\.venv311\Scripts\python.exe -m pytest tests/test_metadata_autofill_header.py tests/test_translation_service_run_report.py tests/test_honorarios_docx.py tests/test_gmail_browser_service.py -q` -> PASS, 102 passed.
- Live artifact simulation against the cold-start source PDF at `C:\Users\FA507\AppData\Local\Temp\legalpdf_gmail_batch_qn_wl3fq\pedido de tradução.pdf` now resolves page 1, page 2, and merged metadata to `case_city=Cuba`, `service_city=Cuba`, and `court_email=cuba.ministeriopublico@tribunais.org.pt`.
- Post-merge live closeout: user cold-start run `20260419_215231` on canonical `main` build `0b2687f` completed the intentional page-2 slice as `Processed pages: 2/2`, populated both `job.artifacts.run_report_path` and nested `result.artifacts.run_report_path`, and finalized Gmail batch `gmail_batch_92aecc9772da` as `draft_ready`.
- Post-merge honorários proof: `Requerimento_Honorarios_48_26.5GACUB_20260419_02.pdf` renders the recipient as `Exmo. Sr(a). Procurador(a) da república do Juízo de Competência Genérica de Cuba` and the closing city as `Cuba`.
- Citation diagnostics note: page-2 citation marker/parenthesis drift in the accepted run stayed diagnostic-only because numeric, structure, language, review-queue, and quality-risk checks stayed clean. Do not raise review thresholds or change Gmail workflow behavior solely because moderate citation drift appears without stronger risk signals.

## Rollout And Fallback
- Publish through PR merge after local validation.
- Existing stale drafts/PDFs should be regenerated after the fix rather than manually editing persisted live rows.

## Risks And Mitigations
- Risk: over-preferring local-unit cities in documents where only comarca city is valid.
- Mitigation: keep generic comarca fallback and add tests for mixed and generic-only cases.
- Risk: reintroducing Gmail launch regressions.
- Mitigation: do not edit extension/native-host/runtime launch code in this pass.

## Assumptions
- A more specific local court unit city is the correct addressee/location for honorarios when it conflicts with a broader comarca district.
- Existing stale Gmail tabs and drafts are left untouched.
