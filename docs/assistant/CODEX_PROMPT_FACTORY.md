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
- Inspect also: src/legalpdf_translate/resources_loader.py, resources/system_instructions_enfr.txt, resources/system_instructions_ar.txt
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

## 3) Prompt Quality Checklist
Before finalizing any Codex prompt/output, confirm:
- Exact files are listed (real paths in this repo).
- Scope is minimal and explicit.
- Acceptance criteria are concrete and testable.
- Commands include inspection + `python -m pytest -q`.
- If code changed, include `python -m compileall src tests` when relevant.
- Secrets/privacy constraints are explicit.
- Final summary reports files touched, test outcomes, and residual risks.
