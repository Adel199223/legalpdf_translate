# Validation Guide

## Default Rules
- Use the repo Python executable: `.\.venv311\Scripts\python.exe`.
- Do not run pytest through bare or global `python`.
- Run targeted tests first, then broader validation when the touched scope warrants it.
- Stop before merge if local validation, GitHub checks, branch identity, or worktree cleanliness is not clean.

## Approved formatting integration

### Current source-associated publication candidate (Stage 4)

The isolated `codex/structured-new-translations` candidate is opt-in only. Use the exact new-run worktree's `src` and assert import origins; `.venv311` may reuse the canonical environment through the documented local junction. No provider, auth, OCR or native Word call is needed for offline tests. Keep the default protocol/model/effort/OCR routes and all browser/CLI/Qt/Gmail submitted contracts unchanged.

Stage 4 publication/canonical verification is explicitly authorized, and the bounded native/human layout acceptance below is complete. Final source-grapheme hardening uses `structured_arabic_literals_v5_exact_source_graphemes`: a two-file source/test delta with 318 focused tests passed in 7.39s; final full pytest passed 3,391 tests in 428.49s, and independent review is clear. Serial release validation passed with exit code 0; the known Dart AOT wrapper issue used a successful direct-Dart fallback. Coverage preserves exact source-owned decomposed accents/internal marks and rejects invented marks. Do not reuse historical full-suite totals as evidence for this final delta. Record observed exact-head GitHub checks, merge and canonical verification in [the implementation/publication closeout](exec_plans/completed/2026-09-09_structured_new_translations.md); none of those publication results is implied by this documentation.

Ordinary launches continue to default to `legacy_text_v1`. A process-only `legal_blocks_v2` flag may select the opt-in path for verification, but it is not durable activation. A bounded canonical smoke is read-only at the UI level, with private metadata/DB initialization, shadow-only routing and the live Gmail bridge disabled. It does not authorize a new translation, paid operation, Word/native check or host repair. Canonical `main` remains routine app authority; the task branch remains the publication candidate until merge is verified.

Cover `test_new_translation_blocks.py`, `test_new_run_callers.py`, `test_new_run_extraction.py`, `test_new_run_source_binding.py`, `test_new_run_adapter_safety.py`, `test_new_run_preflight.py`, `test_new_run_continuations.py`, `test_translation_structure.py`, `test_openai_structured_transport.py` and the `test_structured_*` suites. Real source extraction, coordinator/publication and DOCX assembly must execute with fake provider responses; mocked coordinator success alone is insufficient. Exercise EN/FR/AR, both layout modes, digital tables/list/empty-cell coverage, actual OCR-winner binding, page selection, event/date swaps, accented Arabic/Latin names, terminal refusal/incomplete output, bounded correction, cancellation and retained failed-call usage.

Require protocol/source/context/glossary version invalidation, no-write rejected resume (including output-probe sentinels), strict commit-last recovery without redispatch, mixed/orphan checkpoint rejection, completed-page whitelists, TXT-only manual rebuild without overwriting prior DOCX, explicit retention opt-out and the existing budget block. Derive confirmed sentence continuations only in memory from verified completed source/target pairs; hash-bound artifacts must survive assembly/resume/rebuild unchanged. Partial or missing pages and manually edited/uncertain evidence must not manufacture continuation proof.

Same-ID clause omissions must remain fidelity `not_evaluated`, not quality acceptance. All-call structured cost remains `not_evaluated_all_calls`; reasoning tokens are a breakdown of output, not added again. Fake-provider passage does not prove live model compatibility, 20% savings, a reservation-safe paid path or Word-rendered page counts. Run full pytest and then serial `validate_dev.ps1 -Full`; record final exact counts and any native diagnostic in [the implementation/publication closeout](exec_plans/completed/2026-09-09_structured_new_translations.md). Past Stage 3/native authorities are consumed; the original lifetime budget and fresh specific authorization remain mandatory for any separately proposed paid/native work.

### Historical candidate and corrective validation evidence

The dated stages below retain their original outcomes, counts and failure evidence. Their then-current continuation tokens and "active ExecPlan" references describe past checkpoints, not present authorization or current-build validation. Current Stage 4 status is above; the plan's retained history is now linked from its completed closeout path.

Stage 2 finished-code evidence on 2026-09-09: **2,924 full-suite tests passed in 378.69s**, then serial full validation passed (233 browser tests, compilation, 2 review tests, 5 intake tests with 9 deselected, docs/hygiene and successful direct-Dart fallbacks). Final composition coverage verifies split sentences together with consolidated section headers/contact footers, complete source mapping and unchanged bundle hashes. This is isolated offline implementation acceptance only; the canonical live app remains unchanged.

Stage 3 outcome on the same frozen code: **rollout acceptance failed**. The normal browser-bundle route was exercised with explicitly synthetic OCR/provider responses, not pre-certified digital source evidence. A two-page EN control completed all 26 blocks and flagged both pages for review. One fresh native Word export passed in 6,536 ms with confirmed cleanup; all of its one rendered page was inspected and showed repeated headers/contact groups within body flow. AR source-exact `João Guerreiro` after `Destinatário` and in table-like text was wrongly rejected; pure per-block replay and independent review confirmed missing source-name association. Do not count the corrected private glossary/list-fragment fixture failures as product failures. No actual OCR/model/legal quality, French/full-reference visual result, human approval or paid cost comparison is claimed. See the active ExecPlan for preserved evidence, consumed native authority and corrective regression requirements.

Corrective coverage adds `test_structured_arabic_source_names.py`, `test_source_layout_eligibility.py` and `test_new_run_layout_eligibility.py`. Exercise the real browser bundle, image rendering, OCR helper binding, coordinator and writer with only the recognition command/provider replaced; a pre-certified structure injected at the workflow boundary is insufficient. Require exact per-word confidence/ownership/geometry, raw-raster versus re-encoded OCR-input hash binding, simple-flow-only admission in both layout/furniture planners, same-paragraph list wrapping, split sentences, stale/missing proof, changed raster, partial selection, manual edits and no-call byte-preserving rebuild. Reject columns, ambiguous boundaries, low confidence, word/line overlap and unresolved table/ruling evidence; never clear the original page uncertainty. Freeze a new runtime/test digest, then run targeted/full pytest and serial full validation before the fresh Stage 3 gate. No native/paid operation belongs in corrective Stage 2.

Corrective finished-build evidence: **646 targeted tests passed in 32.07s; 3,085 full-suite tests passed in 437.29s**, with zero failures/errors/skips. Serial full validation passed (233 browser tests in 191.65s, compilation, 2 review tests, 5 intake tests with 9 deselected, docs/hygiene and the two documented successful direct-Dart fallbacks). No COM diagnostic appeared; no native readiness or visual acceptance is inferred. The new 42-file runtime/test digest and log paths are recorded in the active ExecPlan. Its subsequent fresh `NEXT_STAGE_3` is now consumed for the corrective acceptance below; production remains unchanged.

Corrective Stage 3 browser/local checks passed EN/FR/AR with 20 mapped blocks, one join and real header/footer parts using synthetic recognition/provider responses. The old EN checker stopped verdict remains preserved; separate EN visual review passed. Fresh FR/AR native exports passed in 6,157/6,060 ms with confirmed ownership/cleanup. Every-page Poppler review found one A4 page each: French passes; Arabic fails because `09:30` displays `30:09`. PDF glyph x coordinates and DOCX LTR09/RTLcolon/LTR30 runs independently confirm it; logical PDF text can mask the reversal. This historical visual failure remains valid for those unchanged outputs.

The subsequent clock corrective Stage 2 adds `test_docx_clock_runs.py`, `test_docx_clock_contexts.py` and `test_docx_clock_rebuild.py`, plus the v11 profile regression. Require coherent LTR standalone ASCII `HH:MM[:SS]` values across split/whole/plain/mixed tokens, stripped/retained LRI/PDI, six paragraph contexts, typography/alignment/page fields and zero-call legacy/structured rebuilds. Preserve invalid/identifier/prose/line boundaries and unsupported explicit direction controls; do not silently reinterpret ambiguous numeric text. Check formatting invalidation independently from unchanged translation fingerprints and exact source/TXT/target/commits/history plus retained usage/fidelity data. Finished evidence: 298 core tests (9.76s), 910 broader targeted tests (49.90s) and 3,322 full tests (429.73s) pass on the frozen 46-file candidate, with zero failures/errors/skips. Serial `validate_dev.ps1 -Full` also passed: 233 browser tests (181.37s), compilation, 2 review tests, 5 intake tests with 9 deselected, docs and hygiene. Both known Dart AOT wrapper failures used successful direct-Dart fallbacks; no COM diagnostic appeared. Logs, exact digest and final read-only checks are in the active ExecPlan. Offline Stage 2 is complete; await fresh `NEXT_STAGE_3`. No native/paid operation belongs here. Fresh Word rendering and every-page/time-glyph inspection remain required after a new Stage 3 and scoped native authority; XML tests alone cannot accept the corrected Arabic document.

The [completed 2026-09-09 footer-spacing integration](exec_plans/completed/2026-09-09_footer_spacing_integration.md) has user approval of the retained v18 native/visual pilot and passed local new-tree validation: 615 focused tests in 95.66 seconds, 2,492 full-suite tests in 380.77 seconds and serial `validate_dev.ps1 -Full` (233 browser compatibility tests, compilation, 2 review tests, 5 intake tests with 9 deselected, docs and hygiene). Both known Dart AOT wrapper failures used successful direct-Dart fallbacks. No COM diagnostic appeared; this does not claim the historical host diagnostic is fixed. The user explicitly approved publication, merge after checks and app verification; verify actual exact-head CI and canonical post-merge results separately. Do not reuse research-tree totals as integration results or replay the consumed native helper. This lifecycle requires no new Word operation, OCR/API call or recovery publication.

Cover source-folio detection and provenance, header-to-body gaps, footer separation, and the contact-only exception for a complete isolated single-source-page output. Require compact reflow (`page_breaks=False`) and complete matching source/target sidecars. Negative fixtures must retain substantive/uncertain footer-like text in the body, reject isolated-header adoption and partial-preview adoption, and preserve TXT-only production, explicit page matching, separate sections and existing review findings. Include subset dependency/import-origin and unchanged production-policy checks.

Validate compact writer, structure/regions, source-spacing and section-furniture suites, including different/headerless/footerless sections, source/target hash binding, ambiguous evidence, all source-map aliases, readable Arabic/Latin runs, PAGE continuity, tables, legacy TXT and explicit page matching. Run local rebuild integration and production-policy isolation regressions: saved translation bytes, prior usage/costs and existing review findings must remain intact, and no new API/OCR client may be constructed by rebuilding. Keep prompt/effort/image/source-extraction regressions in the compatibility set.

Rich source-aware formatting requires complete matching structured pairs. Current production TXT output cannot be made source-associated merely by matching paragraph counts or numeric anchors. Tests must exercise this fallback rather than use the experimental translation workflow to manufacture a passing release.

Rebuild private accepted examples into new outputs; compare every DOCX package entry against the accepted Word-rendered version. Exact package equality permits reuse of its bound render evidence. Any layout/content difference requires fresh rendering and every-page inspection. Keep private PDFs/DOCXs/PNGs outside Git; use synthetic accented names in published fixtures. Translation deliverables remain DOCX.

The existing native Windows `0x8001010d` diagnostic can occur at the honorarios small-screen dialog's `app.processEvents()` even when assertions pass. Record native and isolated rerun outcomes; do not suppress the diagnostic. This layout-only test does not invoke Word export, and offscreen success is not native export acceptance. The honorarios export repair below does not claim to fix this separate Qt event-processing diagnostic.

Qt render-review subprocess tests must read the renderer's JSON artifact rather than assume stdout contains only JSON: dependency diagnostics can also appear there. Keep strict artifact parsing, successful process exit and geometry assertions; exercise noisy stdout without suppressing warnings or weakening layout checks.

### Clock corrective Stage 3 native verification

The fresh `NEXT_STAGE_3` was supplied after the 3,322-test offline candidate passed. Three public rebuilds on exact private saved-run copies passed all content/mapping/font checks and retained source/TXT/targets/commits/history, usage and fidelity. English/French each match all 23 uncompressed package entries of the original native-reviewed document; independently verified manifest/DOCX/PDF/PNG bindings justify reuse of their one-page synthetic visuals. Preserve the old English runner's stopped verdict and separate visual review. Arabic differs only in body paragraph index 10: LTR `09`, RTL colon and LTR `30` become one LTR `09:30` with the same visible text and numeric run formatting. The subsequent explicitly authorized native check below supplies its fresh visual evidence.

The new private AR-only helper passed 125 offline tests, and file-only preparation bound the corrected DOCX/map, source fixture, 46-file change lock, all 276 Python files, executable identities and original journal. Its manifest is `clock_native_preparation/manifest.json`, SHA256 `7ebdff47c3a162dd991ed42419e29422980ae6171c6a7fa9a3fa630f479ff4c9`. The user's explicit `yes` authorized exactly one 45-second/no-retry Word check. It succeeded in 6.183 seconds: one native call, zero retries/recoveries/paid calls, original-slot journal verification, confirmed owned-process exit and unchanged pre-existing process identities. User document contents were not inspected. Preserve the legitimately advanced original journal, SHA256 `94cdbb415aa8439951958680528c461296e3a0f12174ce96a493ad9e7a97dd8f`; authority is consumed.

Fresh Word PDF SHA256 `e21809d9301eaa45f5a03539d60fe8a462b79368bf949438776e8e3a7c7807c5` contains one A4 page. Both complete-page visual reviewers passed the clock, accented names, header gap, bottom contact footer and page number with no observed clipping or overlap. Physical left-to-right glyph positions for `0`, `9`, `:`, `3`, `0` are respectively 328.134, 334.272, 340.907, 343.490 and 349.629 points; unlike logical extracted text alone, this verifies the corrected display order. Supplemental private `clock_native_review.json` records this review without rewriting helper or historical verdicts. The user approved this exact corrected Arabic preview with `looks right` on 2026-09-09; private `clock_human_approval.json` records the PNG/DOCX hashes and that stage's unchanged runtime digest. This completed bounded Stage 3 layout acceptance; Stage 4 publication was subsequently explicitly authorized as recorded above. No real legal/model/full-reference/cost acceptance or durable production activation follows from the layout result. App/test bytes were unchanged during that private-QA/docs-only pass; the later two-file v5 validator delta requires its own final validation.

## Honorarios Word-to-PDF export

Translation deliverables remain editable DOCX. Validate PDF generation only for the separate honorarios document; retain its DOCX and do not change legal wording, fees or layout to obtain a passing export.

Focused offline regressions:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_word_automation.py tests/test_word_pdf_control.py tests/test_word_pdf_artifacts.py tests/test_word_pdf_runtime.py tests/test_word_pdf_script.py tests/test_honorarios_docx.py
```

These tests must not launch Word implicitly. Keep the native-launch guards in `tests/conftest.py`; parser, compiler and fake-COM checks do not establish native export readiness. Cover process identity and reuse, existing documents, content-free durable phases, early setup/pipe failures, bounded helper cleanup, cross-process exclusion, uncertain-cleanup quarantine, stale output, atomic publication, origin/security rejection, original-file hashes and accurate cleanup metadata. Browser/Qt callers perform one export with a 45-second allowance and bounded cleanup, not an automatic timeout re-probe/re-export.

For direct hidden startup, include `tests/test_word_process_start.py`, `tests/test_word_direct_launch_safety.py` and `tests/test_word_startup_diagnostics.py`. Compile the exact wrapper without invoking it and exercise native API behavior only with fully substituted fakes. Require all seven startup predicates: returned process, running process, new PID, matching session, `WINWORD` name, start time not before launch, and matching executable. Preserve retained-handle ownership, legacy journal compatibility and bounded content-free diagnostics; failed checks must stop before document opening.

Run opt-in native acceptance on the same Windows host/interpreter as the app, only after the ownership and journal safeguards are active. Keep one original state directory across failure/recovery; changing APPDATA or deleting the journal must not bypass quarantine. Use synthetic data, an isolated shadow workspace and ignored/private artifacts. Never terminate unknown Word sessions or change Office security settings to make a test pass.

Require a real expected-text canary, translation-kind and interpretation-kind honorarios through shared caller paths, the browser export route and asynchronous Qt worker, coexistence with an unsaved synthetic Word document, and an already-open source DOCX. Check unchanged source hashes and pre-existing window/content state, fresh readable PDF pages, confirmed owned-process exit and a healthy export after a bounded startup timeout. A startup-only probe, a PDF header, or an older PDF is insufficient. Render and inspect every page of retained Word-produced PDFs; neither XML checks nor another renderer substitute for Word-native acceptance. Observe cold conditions only when safely available, without closing unknown user work.

Accepted 2026-09-07 evidence: eight successful native exports, including the two canaries, shared/browser/Qt paths and both coexistence cases; all six retained honorarios PDFs were one page and passed complete-page Poppler PNG inspection. Full pytest passed **2,176 tests** and `validate_dev.ps1 -Full` passed with the documented Dart fallback. The separate native small-screen Qt test passed its assertions but repeated `0x8001010d` on serial rerun; preserve that limitation. Browser acceptance exercised the real route with isolated data, not a claimed browser-button click. No live Gmail operation, Office repair or host-security change was part of this acceptance. See the [completed repair ExecPlan](exec_plans/completed/2026-09-07_honorarios_pdf_export_reliability.md) for exact evidence and scope.

## Common Targeted Browser And Gmail Tests
```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py
```

Add the Qt Delete-key regression when the task touches Qt Job Log behavior or merge readiness:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py::test_joblog_window_delete_key_removes_selected_rows_when_table_has_focus
```

## Full Local Regression
```powershell
.\.venv311\Scripts\python.exe -m pytest -q
```

Use full pytest before merge, after test/code/workflow changes, or when a focused failure might be suite-order dependent.

## Validation Wrapper
```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
```

`validate_dev.ps1` runs focused browser tests, compileall, docs validation when docs changed, and workspace hygiene. `-Full` adds focused Gmail review/intake coverage.

## Dart AOT Fallback
On this machine, `dart run ...` can fail with:

```text
Unable to find AOT snapshot for dartdev
```

That is a known launcher issue, not automatically a product failure. The validation wrapper should fall back to:

```powershell
C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling\validate_agent_docs.dart
C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling\validate_workspace_hygiene.dart
```

Record both the wrapper failure and direct-Dart fallback success in validation summaries.

## Google Photos Interpretation Validation
Use this section for the Interpretation-only Google Photos Picker import feature.

Focused commands:
```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_google_photos_picker.py tests/test_interpretation_google_photos.py tests/test_metadata_autofill_photo.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_honorarios_docx.py tests/test_qt_app_state.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_runtime_service.py
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
```

Run the safe config gate before live OAuth/Picker work:
- `configured=true`
- `client_id_source=process_env` or `windows_user_env`
- `client_secret_source=process_env` or `windows_user_env`
- scope exactly `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`
- shadow redirect exactly `http://127.0.0.1:8890/api/interpretation/google-photos/oauth/callback`
- live redirect exactly `http://127.0.0.1:8877/api/interpretation/google-photos/oauth/callback`

Live validation acceptance checklist:
- OAuth reaches `connected=true`.
- Token store is present.
- `Choose from Google Photos` is enabled.
- Picker session is created and polled.
- User selects exactly one non-private test photo.
- Google Photos completion screen or auto-close indicates selection finished.
- `mediaItemsSet=true` is observed.
- selected media items are listed.
- import route is called.
- selected image imports into the existing Interpretation photo/OCR autofill flow.
- `Review Case Details` opens.
- Translation controls are avoided.
- `createTime` and downloaded EXIF date are photo-date provenance only; OCR/legal dates win, and photo date may prefill service date only as an editable fallback.
- `service_city` and `case_city` remain OCR/document- or user-confirmed; Google Photos place/location is not available from the Picker API.
- Review Details does not silently default blank service city or KM to the case city.
- Recovered distinct case/service evidence stays distinct, for example case city `Beja` and service location `Serviço de Turno | Moura`.
- KM is keyed to the effective service city and refreshes from profile distances when the service city changes.
- City-aware court email options use the case city, not the service city.
- Picker session cleanup succeeds.
- No final honorários DOCX/PDF is generated unless explicitly approved and then manually reviewed.

Sanitized route logs for this flow may contain method/path only. Drop query strings immediately and normalize Picker session IDs.

## CI Expectations
GitHub CI currently runs on Windows Python 3.11 and includes:
- agent docs validation,
- localization contracts,
- workspace hygiene,
- compileall,
- targeted core regressions,
- full pytest.

Do not merge if required checks such as `test (3.11)` or `docs_tooling_contracts` are failing, pending unexpectedly, blocked, or attached to an unexpected head SHA.

## Coverage Map For PR #46 Risks
- Numeric mismatch and decimal-comma preservation: `tests/test_translation_diagnostics.py`, `tests/test_translation_report.py`, `tests/test_quality_risk_scoring.py`, and PR #46 browser state tests.
- Safe rendering: `tests/test_browser_safe_rendering.py`.
- Shadow/test-mode banner and friendly live copy: `tests/test_shadow_web_api.py`.
- Gmail prepared state: `tests/test_translation_browser_state.py` and Gmail review/intake tests.
- Profile summary/list distinction: `tests/test_profile_browser_state.py` and `tests/test_shadow_web_api.py`.
- Recent Work empty-state copy: `tests/test_translation_browser_state.py` and `tests/test_shadow_web_api.py`.
- Qt Job Log Delete-key multi-select: `tests/test_qt_app_state.py::test_joblog_window_delete_key_removes_selected_rows_when_table_has_focus`.
- Windows browser ESM UTF-8 probe behavior: `tests/browser_esm_probe.py` with Gmail/interpretation browser ESM tests.
- Validation wrapper fallback: `scripts/validate_dev.ps1` and completed validation artifacts.
