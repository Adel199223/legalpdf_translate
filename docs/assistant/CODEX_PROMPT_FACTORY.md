# CODEX_PROMPT_FACTORY

Use this file to generate copy-paste-ready prompts for Codex. All file paths must exist in this repo.

## 1) Reusable Prompt Template
```text
Goal
- <what should change>

Scope boundaries
- Edit only: <paths>
- Do not change: <paths>
- Behavior constraints: <preserve workflows / no correctness regressions>

Files to inspect first
- <path>::<symbol>
- <path>::<symbol>

Implementation constraints
- Minimal diffs only.
- No refactor unless requested.
- Keep secrets out of logs/reports/exceptions.
- If touching prompts/templates, consult docs/assistant/API_PROMPTS.md and update it accordingly.

Acceptance criteria
- <observable outcomes>
- <edge case outcomes>

Commands to run (PowerShell)
- <inspection commands>
- python -m pytest -q
- python -m compileall src tests

Security & privacy constraints
- Never output API keys/tokens/auth headers.
- Redact sensitive strings in shared logs/reports.

Final report format
- Files changed
- Test results
- Any remaining risks
```

## 2) Worked Examples (Repo-Specific)

### Example 1 - Qt UI tweak (status button behavior)
```text
Goal
- Adjust run-report button enable/disable behavior in the Qt main window.

Scope boundaries
- Edit only: src/legalpdf_translate/qt_gui/app_window.py
- Tests: tests/test_qt_app_state.py (or create tests/test_qt_<feature>.py if needed)
- Do not modify workflow semantics.

Files to inspect first
- src/legalpdf_translate/qt_gui/app_window.py::QtMainWindow
- src/legalpdf_translate/qt_gui/app_window.py::_update_controls

Acceptance criteria
- Button state follows requested behavior before/during/after run.
- Existing run/report actions still work.

Commands to run
- rg -n "report_btn|_update_controls|_open_run_report" src/legalpdf_translate/qt_gui/app_window.py
- python -m pytest -q tests/test_qt_app_state.py
- python -m pytest -q
```

### Example 2 - CLI flag change
```text
Goal
- Add or adjust a CLI argument behavior.

Scope boundaries
- Edit: src/legalpdf_translate/cli.py
- Tests: tests/test_cli_flags.py (or add tests/test_cli_<feature>.py)
- Keep existing defaults/backward compatibility unless requested.

Files to inspect first
- src/legalpdf_translate/cli.py::build_arg_parser
- src/legalpdf_translate/cli.py::main

Acceptance criteria
- New/changed flag parses correctly and affects config as intended.
- Existing flags continue to behave correctly.

Commands to run
- rg -n "add_argument|build_arg_parser|main" src/legalpdf_translate/cli.py
- python -m pytest -q tests/test_cli_flags.py
- python -m pytest -q
```

### Example 3 - Cost/time guardrail
```text
Goal
- Add a guardrail for cost/time risk in translation workflow.

Scope boundaries
- Edit: src/legalpdf_translate/workflow.py, optionally src/legalpdf_translate/openai_client.py
- Tests: tests/test_effort_policy_guardrails.py and related workflow tests
- Do not change translation correctness rules.

Files to inspect first
- src/legalpdf_translate/workflow.py::_resolve_attempt1_effort
- src/legalpdf_translate/workflow.py::_classify_suspected_cause
- src/legalpdf_translate/openai_client.py::OpenAIResponsesClient

Acceptance criteria
- Guardrail triggers under specified conditions.
- Summary/diagnostics remain consistent.

Commands to run
- rg -n "effort|guardrail|suspected_cause|retry" src/legalpdf_translate/workflow.py src/legalpdf_translate/openai_client.py
- python -m pytest -q tests/test_effort_policy_guardrails.py tests/test_workflow_parallel.py
- python -m pytest -q
```

### Example 4 - Logging/report enhancement
```text
Goal
- Improve run report detail or formatting without exposing secrets.

Scope boundaries
- Edit: src/legalpdf_translate/run_report.py, src/legalpdf_translate/qt_gui/app_window.py
- Tests: tests/test_run_report.py
- Keep redaction/sanitization strict.

Files to inspect first
- src/legalpdf_translate/run_report.py::RunEventCollector
- src/legalpdf_translate/run_report.py::build_run_report_markdown
- src/legalpdf_translate/qt_gui/app_window.py::_open_run_report

Acceptance criteria
- Exported report shows new requested fields/section.
- Secret-like strings remain redacted.

Commands to run
- rg -n "RunEventCollector|sanitize|build_run_report_markdown|_open_run_report" src/legalpdf_translate/run_report.py src/legalpdf_translate/qt_gui/app_window.py
- python -m pytest -q tests/test_run_report.py tests/test_workflow_logging_safety.py
- python -m pytest -q
```

### Example 5 - Secrets UX change (show/hide key)
```text
Goal
- Adjust stored-key show/hide UX in settings dialog.

Scope boundaries
- Edit: src/legalpdf_translate/qt_gui/dialogs.py, src/legalpdf_translate/secrets_store.py (only if required)
- Settings schema only if needed: src/legalpdf_translate/user_settings.py
- Tests: tests/test_qt_settings_key_toggle.py, tests/test_secrets_store.py

Files to inspect first
- src/legalpdf_translate/qt_gui/dialogs.py::QtSettingsDialog
- src/legalpdf_translate/qt_gui/dialogs.py::_toggle_openai_key
- src/legalpdf_translate/secrets_store.py::get_openai_key

Acceptance criteria
- Stored status, reveal confirm, hide, clear states behave correctly.
- No key value is logged or persisted in plaintext settings.

Commands to run
- rg -n "_toggle_openai_key|_toggle_ocr_key|_refresh_key_status|get_openai_key|get_ocr_key" src/legalpdf_translate/qt_gui/dialogs.py src/legalpdf_translate/secrets_store.py
- python -m pytest -q tests/test_qt_settings_key_toggle.py tests/test_secrets_store.py
- python -m pytest -q
```

### Example 6 - Packaging fix (PyInstaller)
```text
Goal
- Fix Qt packaging issue in PyInstaller configuration.

Scope boundaries
- Edit: build/pyinstaller_qt.spec, scripts/build_qt.ps1 (if needed)
- Tests: tests/test_pyinstaller_specs.py, tests/test_windows_shortcut_scripts.py

Files to inspect first
- build/pyinstaller_qt.spec
- scripts/build_qt.ps1

Acceptance criteria
- Spec resolves project root/resources correctly.
- Build script validates output path correctly.

Commands to run
- rg -n "project_root|entry_script|icon|hiddenimports" build/pyinstaller_qt.spec
- python -m pytest -q tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py
- python -m pytest -q
```

### Example 7 - Add tests matched to touched module
```text
Goal
- Add test coverage for a specific behavior change.

Scope boundaries
- Edit module under src/legalpdf_translate/<module>.py
- Update existing relevant tests/test_*.py if present, else create tests/test_<feature>.py
- Keep tests deterministic and focused.

Files to inspect first
- src/legalpdf_translate/<module>.py::<symbol>
- matching tests via: rg -n "<symbol_or_feature>" tests

Acceptance criteria
- New behavior is asserted with clear pass/fail expectations.
- Existing tests still pass.

Commands to run
- rg -n "<feature_keyword>" src/legalpdf_translate tests
- python -m pytest -q tests/test_<target>.py
- python -m pytest -q
```

### Example 8 - Bug triage workflow (repro -> isolate -> fix -> test)
```text
Goal
- Diagnose and fix a reported bug with minimal blast radius.

Scope boundaries
- Start with read-only triage; patch only confirmed root-cause files.
- Add/adjust tests for regression prevention.

Files to inspect first
- src/legalpdf_translate/qt_gui/app_window.py
- src/legalpdf_translate/workflow.py
- src/legalpdf_translate/run_report.py
- tests/test_qt_app_state.py, tests/test_workflow_parallel.py, tests/test_run_report.py

Acceptance criteria
- Repro steps fail before fix and pass after fix.
- No unrelated behavior changes.

Commands to run
- rg -n "<bug keywords>" src/legalpdf_translate tests
- python -m pytest -q tests/test_<focused>.py
- python -m pytest -q
```

### Example 9 - RTL DOCX ordering/alignment fix
```text
Goal
- Fix Arabic DOCX right-alignment and mixed RTL/LTR run ordering without changing translation logic.

Scope boundaries
- Edit: src/legalpdf_translate/docx_writer.py
- Tests: tests/test_docx_writer_rtl.py (and update tests/test_docx_writer.py only if existing assertions conflict)
- Keep EN/FR output behavior stable.

Files to inspect first
- src/legalpdf_translate/docx_writer.py::assemble_docx
- src/legalpdf_translate/docx_writer.py::sanitize_bidi_controls
- src/legalpdf_translate/workflow.py::TranslationWorkflow.run (confirm lang passthrough only)

Acceptance criteria
- Arabic paragraphs get RTL/bidi + right alignment in DOCX XML.
- No U+2066..U+2069 isolate characters in default Arabic output.
- Mixed Arabic/Latin/digits retain intended run order.

Commands to run
- rg -n "assemble_docx|bidi|rtl|2066|2069|\\u200e" src/legalpdf_translate/docx_writer.py tests
- python -m pytest -q tests/test_docx_writer.py tests/test_docx_writer_rtl.py
- python -m pytest -q
```

### Example 10 - Prompt optimization / cost reduction
```text
Goal
- Reduce prompt token usage while preserving translation/compliance behavior.

Scope boundaries
- Edit only: src/legalpdf_translate/prompt_builder.py, src/legalpdf_translate/workflow.py, src/legalpdf_translate/openai_client.py
- Inspect also: src/legalpdf_translate/resources_loader.py, resources/system_instructions_en.txt, resources/system_instructions_fr.txt, resources/system_instructions_ar.txt
- Documentation must be updated: docs/assistant/API_PROMPTS.md
- Do not change OCR logic, DOCX writer behavior, or unrelated workflow paths.

Files to inspect first
- docs/assistant/API_PROMPTS.md
- src/legalpdf_translate/prompt_builder.py::build_page_prompt
- src/legalpdf_translate/prompt_builder.py::build_retry_prompt
- src/legalpdf_translate/workflow.py::_process_page
- src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response
- src/legalpdf_translate/resources_loader.py::load_system_instructions

Acceptance criteria
- Prompt changes are minimal and scenario-specific.
- Output compliance contract remains valid (single code block, validators unchanged unless requested).
- API payload shape remains compatible.
- docs/assistant/API_PROMPTS.md reflects the new templates/order.

Commands to run
- rg -n "build_page_prompt|build_retry_prompt|create_page_response|_process_page|load_system_instructions" src/legalpdf_translate
- python -m pytest -q
- python -m compileall src tests
```

### Example 11 - Calibration verifier JSON hardening
```text
Goal
- Improve calibration verifier JSON reliability without changing normal translation semantics.

Scope boundaries
- Edit only: src/legalpdf_translate/calibration_audit.py
- Optional UI-only adjustments: src/legalpdf_translate/qt_gui/tools_dialogs.py
- Do not change: src/legalpdf_translate/prompt_builder.py, OCR/reporting flow, DOCX logic
- If touching prompts/templates, consult docs/assistant/API_PROMPTS.md and update it accordingly.

Files to inspect first
- docs/assistant/API_PROMPTS.md
- src/legalpdf_translate/calibration_audit.py::_verifier_prompt
- src/legalpdf_translate/calibration_audit.py::_verifier_retry_prompt
- src/legalpdf_translate/calibration_audit.py::_call_verifier_with_retries

Acceptance criteria
- Verifier output parsing remains deterministic with retry fallback on malformed JSON.
- Findings/suggestions schema remains stable.
- No changes to `TranslationWorkflow._append_glossary_prompt` behavior.

Commands to run
- rg -n "_verifier_prompt|_verifier_retry_prompt|_call_verifier_with_retries|run_calibration_audit" src/legalpdf_translate
- python -m pytest -q tests/test_calibration_audit.py tests/test_workflow_glossary.py
- python -m pytest -q
```

### Example 12 - OCR cost guardrail + reporting semantics
```text
Goal
- Make `ocr_mode=auto` cost-safe and report-safe:
  - OCR only when extraction is required/unusable, or conservatively helpful for layout.
  - Helpful OCR path must be local-only (no automatic API OCR escalation).
  - No OCR-unavailable warnings unless OCR was actually required/requested and unavailable.

Scope boundaries
- Edit only:
  - src/legalpdf_translate/workflow.py
  - src/legalpdf_translate/ocr_engine.py
  - src/legalpdf_translate/run_report.py
  - tests/test_workflow_ocr_routing.py
  - tests/test_run_report.py
- Docs required in same task:
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/CODEX_PROMPT_FACTORY.md
  - docs/assistant/UPDATE_POLICY.md
- Do not change prompt templates / validator contracts / API payload shape (`docs/assistant/API_PROMPTS.md`).

Files to inspect first
- src/legalpdf_translate/workflow.py::_process_page
- src/legalpdf_translate/workflow.py::classify_extracted_text_quality
- src/legalpdf_translate/ocr_engine.py::build_ocr_engine
- src/legalpdf_translate/run_report.py::build_run_report_markdown

Acceptance criteria
- Extractable normal text => direct_text route, no OCR warning, `ocr_requested=false`.
- Unusable extraction => `ocr_request_reason=required`; missing OCR logs warning event.
- Helpful layout-only case => `ocr_request_reason=helpful`; local-only OCR attempt; if local unavailable, info-only event and direct-text fallback.
- Run report includes additive pipeline fields:
  - `ocr_required_pages`, `ocr_helpful_pages`, `ocr_preflight_checked`

Commands to run
- rg -n "classify_extracted_text_quality|ocr_request_reason|ocr_preflight_checked|ocr_required_but_unavailable|ocr_helpful_but_unavailable" src/legalpdf_translate tests
- python -m pytest -q tests/test_workflow_ocr_routing.py tests/test_run_report.py
- python -m pytest -q
- python -m compileall src tests
```

### Example 13 - Arabic token lock + Word stability
```text
Goal
- Prevent Arabic output from reordering or partially translating sensitive LTR values (name/address/IBAN/case IDs), with stable Word rendering.
- Ensure Portuguese month-name dates do not leak in final Arabic output.

Scope boundaries
- Edit only:
  - src/legalpdf_translate/arabic_pre_tokenize.py
  - src/legalpdf_translate/output_normalize.py
  - src/legalpdf_translate/validators.py
  - src/legalpdf_translate/workflow.py
  - resources/system_instructions_ar.txt
  - tests/test_arabic_pre_tokenize.py
  - tests/test_output_normalize.py
  - tests/test_validators_ar.py
  - tests/test_workflow_ar_token_lock.py
  - tests/test_docx_writer_rtl.py
- Keep API payload shape and code-block contract unchanged.

Files to inspect first
- src/legalpdf_translate/arabic_pre_tokenize.py::pretokenize_arabic_source
- src/legalpdf_translate/arabic_pre_tokenize.py::extract_locked_tokens
- src/legalpdf_translate/arabic_pre_tokenize.py::is_portuguese_month_date_token
- src/legalpdf_translate/workflow.py::_process_page
- src/legalpdf_translate/workflow.py::_evaluate_output
- src/legalpdf_translate/validators.py::validate_ar
- src/legalpdf_translate/output_normalize.py::normalize_output_text_with_stats
- src/legalpdf_translate/output_normalize.py::normalize_ar_portuguese_month_dates

Acceptance criteria
- Full `Nome`/`Morada`/`IBAN` values are locked as single tokens in AR pretokenization.
- Portuguese month-name dates are date-flex: Arabic month translation with tokenized day/year, while slash dates can remain one protected token.
- AR output auto-fixes recoverable unwrapped expected tokens.
- Missing/altered expected locked tokens fail AR validation after retry.
- DOCX RTL regression confirms address segment keeps `no 6` order.

Commands to run
- rg -n "pretokenize_arabic_source|extract_locked_tokens|is_portuguese_month_date_token|expected_ar_tokens|validate_ar|normalize_ar_portuguese_month_dates|normalize_output_text_with_stats" src/legalpdf_translate tests resources/system_instructions_ar.txt
- python -m pytest -q tests/test_arabic_pre_tokenize.py tests/test_validators_ar.py tests/test_output_normalize.py tests/test_workflow_ar_token_lock.py tests/test_docx_writer_rtl.py
- python -m pytest -q
- python -m compileall src tests
```

### Example 14 - EN/FR prompt hardening without RTL impact
```text
Goal
- Improve EN/FR translation quality and legal fidelity without touching Arabic RTL/token-lock behavior.

Scope boundaries
- Edit only:
  - resources/system_instructions_en.txt (new)
  - resources/system_instructions_fr.txt (new)
  - src/legalpdf_translate/resources_loader.py
  - src/legalpdf_translate/prompt_builder.py
  - tests/test_resource_path_resolution.py
  - tests/test_resources_loader.py (add if missing)
  - tests/test_prompt_builder.py
  - docs/assistant/API_PROMPTS.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/CODEX_PROMPT_FACTORY.md
  - docs/assistant/UPDATE_POLICY.md
- Do not change:
  - resources/system_instructions_ar.txt
  - Arabic validators/token-lock logic
  - API payload shape
  - code-block contract

Files to inspect first
- src/legalpdf_translate/resources_loader.py::load_system_instructions
- src/legalpdf_translate/prompt_builder.py::build_retry_prompt
- resources/system_instructions_en.txt
- resources/system_instructions_fr.txt

Acceptance criteria
- EN and FR use separate instruction files.
- EN retry prompt adds an English-only hint; FR retry prompt adds a French-only hint.
- AR retry behavior and AR system instructions remain unchanged.
- tests and compile pass.

Commands to run
- rg -n "load_system_instructions|build_retry_prompt|system_instructions_en|system_instructions_fr|system_instructions_ar" src tests resources docs
- python -m pytest -q tests/test_resource_path_resolution.py tests/test_resources_loader.py tests/test_prompt_builder.py
- python -m pytest -q
- python -m compileall src tests
```

### Example 15 - EN/FR Portuguese month-date leak fix
```text
Goal
- Stop Portuguese month-name dates from leaking into FR/EN outputs.

Scope boundaries
- Edit only:
  - src/legalpdf_translate/output_normalize.py
  - resources/system_instructions_en.txt
  - resources/system_instructions_fr.txt
  - tests/test_output_normalize.py
  - tests/test_resources_loader.py
  - docs/assistant/API_PROMPTS.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/CODEX_PROMPT_FACTORY.md
  - docs/assistant/UPDATE_POLICY.md
- Do not change AR token-lock/RTL code paths.

Acceptance criteria
- FR converts `10 de fevereiro de 2026` -> `10 février 2026`.
- EN converts `10 de fevereiro de 2026` -> `10 February 2026`.
- FR/EN also convert no-year month dates (`20 de Março` -> `20 mars` / `20 March`).
- Slash numeric dates remain unchanged.
- Unknown month typos remain unchanged (non-fatal).
- Remaining Portuguese month-date leaks in FR/EN fail validation after normalization (retry/fail guardrail), with address-context exemptions.
- AR behavior remains unchanged.

Commands to run
- rg -n "normalize_output_text_with_stats|PORTUGUESE_MONTH_DATE|system_instructions_en|system_instructions_fr" src tests resources docs
- python -m pytest -q tests/test_output_normalize.py tests/test_resources_loader.py tests/test_prompt_builder.py
- python -m pytest -q
- python -m compileall src tests
```

### Example 16 - Arabic institution naming policy alignment (prompt-only)
```text
Goal
- Align Arabic institution/court naming policy with EN/FR policy without changing AR runtime token-lock/RTL behavior.

Scope boundaries
- Edit only:
  - resources/system_instructions_ar.txt
  - tests/test_resources_loader.py
  - docs/assistant/API_PROMPTS.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/CODEX_PROMPT_FACTORY.md
  - docs/assistant/UPDATE_POLICY.md
- Do not change:
  - src/legalpdf_translate/workflow.py
  - src/legalpdf_translate/validators.py
  - src/legalpdf_translate/output_normalize.py
  - src/legalpdf_translate/docx_writer.py

Acceptance criteria
- AR instructions say full institution/court/prosecution names are translated to Arabic by default when stable equivalents exist.
- AR instructions say Portuguese full names are kept only when uncertain/no stable equivalent.
- AR instructions say dual form is only for acronyms (first mention), not full names.
- AR runtime enforcement/token-lock/RTL behavior remains unchanged.

Commands to run
- python -m pytest -q tests/test_resources_loader.py tests/test_prompt_builder.py
- python -m pytest -q
- python -m compileall src tests
```

## 3) Prompt Quality Checklist
Before finalizing any Codex prompt/output, confirm:
- Exact files are listed (real paths in this repo).
- Scope is minimal and explicit.
- Acceptance criteria are concrete and testable.
- Commands include inspection + `python -m pytest -q`.
- If code changed, include `python -m compileall src tests` when relevant.
- Secrets/privacy constraints are explicit.
- Final summary reports files touched, test outcomes, and residual risks.
