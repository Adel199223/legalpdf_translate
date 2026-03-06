# Gemini OCR Provider Plan

## Goal and non-goals
- Goal: add Gemini OCR as an optional provider for OCR text extraction, with support for PDF pages and standalone image files.
- Goal: keep the current OCR provider as the default until benchmarks justify a promotion.
- Non-goal: change translation provider/model behavior.
- Non-goal: add generic image-analysis features.

## Scope
- In scope:
  - provider-aware OCR adapter for `openai` and `gemini`
  - standalone image source support for the main translation flow
  - provider-aware settings/UI/diagnostics
  - OCR benchmark helper
- Out of scope:
  - translation provider abstraction
  - multi-image document folders
  - changing the default OCR provider in this pass

## Interfaces/types/contracts affected
- Add OCR API provider concept to run config/settings.
- Keep `RunConfig.pdf_path` as the source path for backward compatibility in this pass.
- Preserve `OcrResult` shape so downstream workflow logic does not branch on provider.

## File-by-file implementation steps
1. `src/legalpdf_translate/types.py`
   - add `OcrApiProvider`
   - extend `RunConfig` with provider field
2. `src/legalpdf_translate/ocr_engine.py`
   - add provider-aware defaults
   - keep existing OpenAI API OCR engine
   - add native Gemini OCR engine using Gemini REST
   - route `build_ocr_engine()` by provider
3. `src/legalpdf_translate/source_document.py`
   - add source-kind detection and helpers for PDF vs single image
4. `src/legalpdf_translate/image_io.py`
   - add single-image data-url rendering path
5. `src/legalpdf_translate/ocr_helpers.py`
   - add single-image OCR helpers
6. `src/legalpdf_translate/workflow.py`
   - switch to source-document helpers for page count, extraction, rendering, OCR
7. `src/legalpdf_translate/metadata_autofill.py`
   - make OCR fallback provider-aware through `build_ocr_engine()`
8. `src/legalpdf_translate/user_settings.py`
   - add OCR provider keys and provider-aware defaults
9. `src/legalpdf_translate/qt_gui/dialogs.py`
   - add OCR provider selector in settings
   - make OCR test provider-aware
10. `src/legalpdf_translate/qt_gui/app_window.py`
   - add OCR provider selector in advanced settings
   - allow PDF or single image source picker
   - update page-count handling and OCR diagnostics to use provider-aware defaults
11. `tooling/ocr_benchmark.py`
   - add OCR benchmark helper for provider/model comparisons
12. `tests/*`
   - add/update provider selection, image-source, settings persistence, and benchmark tests

## Tests and acceptance criteria
- OpenAI OCR still works unchanged.
- Gemini OCR works for rendered PDF pages and standalone images.
- Single image source is treated as one page.
- Provider-aware defaults resolve correctly when model/env are blank.
- OCR diagnostics test the selected provider.
- Benchmark helper emits comparable results.
- Full pytest and compileall pass.

## Rollout and fallback
- Keep OpenAI OCR as the default provider.
- If Gemini OCR fails, user can switch back to OpenAI without changing translation behavior.
- No migration should force users onto Gemini in this pass.

## Risks and mitigations
- Risk: image-source support could destabilize PDF flow.
  - Mitigation: add a source adapter layer instead of rewriting workflow contracts.
- Risk: Gemini request shape drift.
  - Mitigation: use official native REST request shape from current docs and isolate provider logic.
- Risk: provider settings confuse saved-state behavior.
  - Mitigation: provider-aware defaults only when fields are blank; preserve explicit user values.

## Assumptions/defaults
- First pass supports PDFs and single image files only.
- Gemini OCR default model is `gemini-2.5-flash`.
- Optional benchmark model is `gemini-2.5-flash-lite`.
- OCR key storage remains a single shared OCR credential slot.
