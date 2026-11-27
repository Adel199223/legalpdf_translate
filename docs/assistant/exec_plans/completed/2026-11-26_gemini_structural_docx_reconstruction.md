# ExecPlan: Gemini Multimodal Structural DOCX Reconstruction (`gemini_structural_v1`)

## 1. Title
Gemini 4 Neon Multimodal Document Structure Reconstruction & High-Fidelity Word OOXML Pipeline (`gemini_structural_v1`).

## 2. Goal and Non-Goals
### Goal
Re-architect LegalPDF Translate's Gemini translation & DOCX generation pipeline so that ordinary translations of Portuguese legal, judicial, prosecutorial, and police PDFs (Citius notifications with Legal Aid panels, Prosecutor/Judicial Despachos with institutional stationery, bordered police forms, and multi-document combined packets) produce clean, editable Word documents whose **layout structure, margins, stationery headers/footers, bordered tables, 2-column bands, horizontal rules, callout panels, indents, bullet/numbered hierarchy, signatures, and RTL bidirectionality** closely match the original documents and the user's proven reference translations.

### Empirical Reference Findings
Inspection of 6 real sent translation pairs (`original.pdf` + finished `.docx` files across EN & AR):
1. **Citius vector-outlined PDFs often expose `0` embedded text blocks** (`drawings=169..1754`) while `find_tables()` misses all 2-column letter bands and metadata bars. Vision-first multimodal input is mandatory whenever `image_mode != off`, paired with deterministic PyMuPDF geometry/drawing hints.
2. **Legacy `legacy_text_v1` + `ordinary_auto_layout` fails structurally** because:
   - First-pass flat text translation destroys tables, 2-column bands, horizontal dividers, and form boundaries before layout begins.
   - `saved_docx_layout_writer.py` forces all table borders to `nil`, lacks real Word repeating stationery headers/footers with extracted crest images and `PAGE`/`NUMPAGES` fields, lacks `firstLine`/hanging indents and paragraph borders/shading, and imposes fixed global body sizing/margins.
3. **Target Document Families**:
   - **Citius Two-Column Notifications & Legal Aid Forms**: compact margins (`~1.35-1.7cm`), borderless `1x2` header/body tables (`42/58` or `50/50`), optional left callout/shaded sidebar, horizontal divider rules, boxed notices, questionnaire sections.
   - **Prosecutor / Judicial Orders (`Despachos`)**: repeating Word header story (top-left stamp, optional centered extracted crest image, centered agency title), generous top margin (`3.5-4.5cm` when header stationery present; `2.2-2.4cm` L/R), repeating footer (`Page X of Y` or localized equivalent), `1x3` top/bottom ruled metadata band (`top/bottom: single`, `left/right: nil`), `Times New Roman 12pt` (EN/FR/ES) or `Arial 12-12.5pt` (AR `bidi`), `firstLine` indented justified paragraphs (`~1.25cm`), `hanging` list items, centered `***` dividers.
   - **Police / Structured Forms**: repeating header/footer, bottom-bordered section headings, bordered `rows x 2` / grid tables (`single` borders, `bidiVisual` for AR), narrative blocks.
   - **Combined Multi-Document PDFs**: distinct document boundaries (`document_starts_here=true`) emit clean Word Section breaks (`NEW_PAGE`) with independent stationery headers/footers, margins, and typography.

### Non-Goals
- Do not break legacy `legacy_text_v1`, `legal_blocks_v2`, historical OpenAI replay paths, `ordinary_auto_layout` V20 OpenAI tests, or public API/UI route contracts.
- Do not bypass Arabic locked `[[...]]` literal token protection, Portuguese term/date leak validators, budget/accounting limits, or unreviewed-output markers.
- Do not copy PII or case text from user sent emails into repository code, fixtures, or tests.

## 3. Scope (In / Out)
### In Scope
- Deterministic PyMuPDF page geometry, drawing-rule, column-split, typography, and safe centered top crest/emblem extractor (`source_structural_evidence.py`).
- Strict Pydantic v2 + flattened JSON Schema IR (`gemini_structural_schema.py`) for one-pass multimodal Gemini 4 Neon (`xhigh`) translation + layout reconstruction, preserving inline formatting (`bold`/`italic`/`underline`), Arabic `[[...]]` wrapping, and deterministic validators.
- Rich Word 2013+ (`compatibilityMode=15`) OOXML assembler (`structural_docx_assembler.py`) supporting section-scoped stationery headers/footers, extracted header crest images, `PAGE`/`NUMPAGES` fields, bordered tables (`gridSpan`, `bidiVisual`), `1x3` ruled metadata bands, two-column bands, `pBdr`/`shd` callout panels, `firstLine`/hanging indents, RTL bidi runs, and smart continuation pagination.
- Clean activation in `workflow.py`, `translation_policy.py`, `translation_service.py`, `qt_gui/worker.py`, `cli.py`, and `user_settings.py` (`default_images_mode` -> `"auto"` for fresh defaults) while preserving all existing mock/legacy/OpenAI tests.
- Additive structural parity evaluation via Gemini Decisions API (`gemini_decisions.py`) when Decisions advisory is enabled.
- Comprehensive offline unit + headless LibreOffice PNG visual verification tests using anonymized synthetic PDFs modeling all 3 archetypes + combined multi-document packet across EN & AR.
- Live Gemini 4 Neon (`xhigh`) end-to-end verification once `GEMINI_API_KEY` / keyring key is supplied.

### Out of Scope
- Changing Browser UI form field schemas, route URLs, or native host contracts.
- Clicking or testing live Gmail extension on `8877`/`8765`.
- Modifying historical `ordinary_layout_contracts.py` / `saved_docx_layout_writer.py` OpenAI V20 code.

## 4. Worktree Provenance
- **Worktree path**: `C:\Users\FA507\.codex\worktrees\gemini-structural-docx\legalpdf_translate`
- **Branch name**: `feat/gemini-structural-docx`
- **Base branch**: `main`
- **Base SHA**: `0155a7556c95d0e3a746688f5970d6fd84fdde08` (contains `approved_base_head_floor` `4e9d20e`)
- **Target integration branch**: `main`
- **Canonical build status**: Isolated noncanonical feature worktree; canonical live runtime remains `C:\Users\FA507\.codex\legalpdf_translate` on `main` until final acceptance & merge.

## 5. Interfaces / Types / Contracts Affected
- `src/legalpdf_translate/translation_policy.py`:
  - Keep `DEFAULT_TRANSLATION_PROTOCOL = "legacy_text_v1"` and preserve existing `resolve_translation_protocol()` contract.
  - Add `"gemini_structural_v1"` to `SUPPORTED_TRANSLATION_PROTOCOLS` and add helper `resolve_gemini_structural_protocol(...)`.
- `src/legalpdf_translate/user_settings.py`:
  - Set `DEFAULT_GLOBAL_SETTINGS["default_images_mode"] = "auto"` so fresh Gemini structural runs include page vision automatically by default while explicit `"off"` stays honored.
- `src/legalpdf_translate/workflow.py`:
  - Support per-page `gemini_structural_v1` execution (multimodal visual+evidence prompt, JSON schema response_format, structural completeness + ENFR/AR validators, `.structural.json` + `.txt` artifacts alongside checkpoint metadata) and final / partial assembly via `structural_docx_assembler.py`.
  - Keep `TranslationWorkflow(gui_settings={})._translation_protocol == "legacy_text_v1"` at construction time; resolve `gemini_structural_v1` when running real Gemini entry points or explicit `translation_protocol="gemini_structural_v1"`.
- `src/legalpdf_translate/translation_service.py`, `src/legalpdf_translate/qt_gui/worker.py`, `src/legalpdf_translate/cli.py`:
  - Route real Gemini ordinary jobs cleanly through `gemini_structural_v1` without triggering the legacy OpenAI post-hoc `ordinary_auto_layout` second pass.
- `src/legalpdf_translate/gemini_decisions.py`:
  - Add fail-open `evaluate_structural_parity_advisory(...)` helper for optional post-assembly visual layout & structural parity triage.

## 6. File-by-File Implementation Steps
1. Create `src/legalpdf_translate/source_structural_evidence.py`: PyMuPDF geometry, horizontal/vertical rules, shaded boxes, column split, text styling hints, safe top-center crest extractor, and anonymized prompt hints builder.
2. Create `src/legalpdf_translate/gemini_structural_schema.py`: Pydantic v2 structural IR (`PageStructuralDocument`, `PageRegionSpec`, `StyledParagraph`, `InlineRun`, `HeaderStationerySpec`, `FooterStationerySpec`), inline-flattened JSON Schema generator (`gemini_structural_response_format()`), system/page/retry prompts, strict parser, Arabic `[[...]]` + EN/FR/ES validation, and source-completeness guards.
3. Create `src/legalpdf_translate/structural_docx_assembler.py`: Rich OOXML DOCX builder implementing section breaks (`document_starts_here`), real Word repeating header/footer parts with crest media and `PAGE`/`NUMPAGES` fields, bordered tables (`gridSpan`, `bidiVisual`), `1x3` ruled metadata bands, two-column bands, callout panels (`pBdr`/`shd`), `firstLine`/hanging indents, RTL bidi runs, `compatibilityMode=15`, and atomic save/verification.
4. Wire `gemini_structural_v1` cleanly into `translation_policy.py`, `workflow.py`, `translation_service.py`, `qt_gui/worker.py`, `cli.py`, `user_settings.py`, and add `evaluate_structural_parity_advisory` in `gemini_decisions.py`.
5. Write comprehensive offline tests (`tests/test_structural_reconstruction.py`, `tests/test_structural_visual_renders.py`) covering:
   - Schema validation & Gemini `$defs`-free JSON Schema generation
   - Vector-outlined & embedded-text PyMuPDF evidence + header crest extraction
   - Bilingual EN & AR (RTL + `[[...]]` + `bidiVisual`) OOXML XML & LibreOffice PNG visual checks on synthetic anonymized PDFs for all 3 document families + combined `Letter + Despacho`
   - Workflow, Browser `TranslationJobManager`, Qt worker, CLI, checkpoint resume, partial export, and `rebuild_docx`
   - Preservation of `test_activation_policy.py`, `test_new_run_callers.py`, OpenAI auto-layout tests, and `gemini_decisions.py` parity check.
6. Run LibreOffice headless renders and visually inspect every synthetic archetype PNG side-by-side against structural goals; iterate until clean.
7. Run full pytest & `scripts/validate_dev.ps1 -Full`; pause cleanly for paid `GEMINI_API_KEY` if unset to perform live Gemini 4 Neon (`xhigh`) end-to-end verification before merging into `main`.

## 7. Tests and Acceptance Criteria
- [x] Targeted tests (`tests/test_structural_reconstruction.py`, `tests/test_activation_policy.py`, `tests/test_new_run_callers.py`, `tests/test_user_settings_schema.py`, `tests/test_gemini_client.py`, `tests/test_gemini_decisions.py`, `tests/test_gemini_pipeline_integration.py`, `tests/test_workflow_dispatch_accounting.py`, `tests/test_translation_service_accounting.py`, `tests/test_workflow_parallel.py`, `tests/test_workflow_ar_token_lock.py`, `tests/test_docx_writer.py`, `tests/test_docx_writer_rtl.py`, `tests/test_docx_writer_structure.py`): **216 passed in 26.99s**; plus non-expired runtime/Gmail/finance/CLI suites (`test_shadow_runtime_metadata_atomic.py`, `test_gmail_review_state.py`, `test_translation_delivery_names.py`, `test_translation_completion_presentation.py`, `test_gmail_browser_service.py`, `test_pricing.py`, `test_translation_finance_browser_state.py`, `test_translation_finance_qt.py`, `test_translation_completion_metrics.py`, `test_cli_flags.py`): **118 passed in 5.05s**.
- [x] Standard `scripts/validate_dev.ps1` passed (`267` browser tests in `43.27s`, `compileall -q src tests tooling`, `dart run tooling/validate_agent_docs.dart`, `dart run tooling/validate_workspace_hygiene.dart`, exit `0`). Pre-existing `scripts/validate_dev.ps1 -Full` historical OpenAI suites (`test_ocr_text_transport.py`, `test_ordinary_layout_reproposal.py`, `test_source_alignment_instructions_v20.py`) fail identically on both `main` (`0155a75`) and this branch solely due to the pre-existing `ordinary_accounting_policy()` `date(2026, 10, 15)` 30-day freshness window when wall-clock date is `2026-11-26` (`pricing_snapshot=None`, leaving `accounting_policy.py` untouched per baseline rules).
- [x] Visual LibreOffice Writer & Microsoft Word (`WINWORD.EXE`) renders verified for:
  - 2-column Citius Notification + Legal Aid shaded sidebar (`pair_01_en_p1_2`: 2p) & top-left crest Citius Notification (`pair_06_en`: 1p; `pair_02_en` p1)
  - Combined `Citius Notification + Prosecutor Despacho` (`pair_02_en`: 2p EN, 2 Word sections; `pair_03_ar_p1_2`: 2p AR, 2 Word sections, `different_first_page` stamp at top-left, centered Coat of Arms, `1x3` RTL rule band, `Arial 12.5pt` first-line indented narrative)
  - Multi-page `Prosecutor Despacho` (`pair_05_en_p1_3`: 3p EN with repeating crest/header, `1x3` metadata band deduplicated on continuation pages, `Times New Roman 12pt`)
  - Combined `Citius Notification + Police Form Record` in Arabic (`pair_04_ar`: 3p AR, top-right Coat of Arms beside agency block, logical `w:jc="start"` RTL tables, crisp `<w:pBdr>` section rules, `different_first_page_header_footer` promotion of continuation running header without mid-body injection)
- [x] Live Gemini 4 Neon & `gemini-decision-1` verification completed with real `gemini_api_key` stored via isolated shadow Settings (`run_gemini_auth_test(model="gemini-4-neon")` latency `2951ms`, live `evaluate_visual_qa_advisory` & workflow `decisions_advisory` `pass` ~`0.977–0.989` on complete packets).

## 8. Rollout and Fallback
- Strictly isolated to Gemini runs (`gemini_structural_v1`) and explicit callers; historical OpenAI (`legacy_text_v1` + `ordinary_auto_layout`) and `legal_blocks_v2` paths remain untouched as instant rollback options via `LEGALPDF_TRANSLATION_PROTOCOL=legacy_text_v1` or selecting OpenAI.
- Within `gemini_structural_v1`, any schema or validator defect triggers one structured targeted retry; `rebuild_docx` / `export_partial_docx` replay cleanly from saved `.structural.json` artifacts.

## 9. Risks and Mitigations
- **JSON Schema compatibility with Gemini Interactions API**: Flattened `$defs`/`$ref` inline without unsupported `const`, avoided forcing defaulted keys into `required`, compacted schema with `StyledParagraph.text`, and set `STRUCTURAL_MAX_OUTPUT_TOKENS = 65536` alongside `HIGH` effort on initial EN/FR structural extraction so vector PDFs complete fast without `xhigh` overthinking loops.
- **Content drops or hallucinated omissions**: Retained deterministic numeric/citation/identifier & Arabic high-signal identifier guards plus semantic normalization for footer `{page}`/`{total}` counters and long underscore capping (`<= 34`).
- **Vector-outlined Citius PDFs with 0 embedded chars**: Automatically bypassed redundant paid API OCR when `image_mode != off` and `ocr_mode != always`, passing high-detail page images (`resolution: "high"`) plus PyMuPDF geometry hints.
- **OOXML RTL alignment & ECMA-376 `<w:pPr>` element order**: Reused `docx_writer._set_rtl_visual_alignment` (`start`/`end`) for `<w:bidi/>` paragraphs so Word/LibreOffice never invert Arabic `right` alignment, and ordered `<w:pBdr>`/`<w:shd>`/`<w:bidi>` before `<w:spacing>`/`<w:jc>`.

## 10. Assumptions and Defaults
- Default Gemini model remains `gemini-4-neon` with `effort="adaptive"` (`high` initial attempt in `gemini_structural_v1`, `xhigh` available explicitly or on escalation); default `default_images_mode` updated to `"auto"`.
- Canonical `main` worktree stayed untouched during live iterative testing; integration into `main` runs only after full repo validation succeeds.

## 11. Progress & Verification Status
- Completed implementation across `source_structural_evidence.py`, `gemini_structural_schema.py`, `gemini_structural_runner.py`, `structural_docx_assembler.py`, `gemini_client.py`, `gemini_decisions.py`, `translation_policy.py`, `checkpoint.py`, `translation_service.py`, `qt_gui/worker.py`, `cli.py`, `user_settings.py`, and `workflow.py`.
- Completed live end-to-end tests across real Portuguese Citius, Despacho, Police Form, and multi-document packets in both EN (`pair_06_en`, `pair_02_en`, `pair_05_en_p1_3`, `pair_01_en_p1_2`) and AR (`pair_04_ar`, `pair_03_ar_p1_2`), visually inspecting LibreOffice 150 DPI PNGs and live Microsoft Word (`WINWORD.EXE`) Page 1–2 renders alongside the user's reference translations.
- Verified OOXML/zip XML integrity and Word 2013+ `compatibilityMode=15` across all generated DOCXs (`pair_06_en`, `pair_02_en`, `pair_05_en_p1_3`, `pair_01_en_p1_2`, `pair_04_ar`, `pair_03_ar_p1_2`).
- Offline targeted tests: `216 passed in 26.99s` (14 structural/Gemini/workflow/DOCX suites), `118 passed in 5.05s` (10 runtime/Gmail/finance/CLI suites), and `scripts/validate_dev.ps1` Standard passed (`267` browser tests + `compileall` + `validate_agent_docs.dart` + `validate_workspace_hygiene.dart`, exit `0`). (Pre-existing `2026-10-15` OpenAI `ordinary_accounting_policy` 30-day freshness expiry reproduced identically on untouched `main` `0155a75`.)

