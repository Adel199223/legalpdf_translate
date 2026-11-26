---
name: legalpdf-validate
description: >-
  Run LegalPDF Translate pytest suites, validate_dev.ps1 tiers, direct-Dart
  docs/hygiene checks, and read-only workstation checks in Antigravity. Use when
  testing changes, checking docs/workspace hygiene, or diagnosing test isolation.
---

# LegalPDF Validation

Use `docs/assistant/VALIDATION.md` and `docs/assistant/WORKSTATION_SETUP.md` as canonical references.

## Interpreter & Isolation Rules

- Always use `.\.venv311\Scripts\python.exe` for Python and `pytest` (never bare/global Python).
- Never run unlocked `pip install`, `uv lock --upgrade`, or `scripts/setup_python311_env.ps1 -Recreate` on a live environment just to validate a change.
- Keep tests isolated with temporary roots and non-live/ephemeral ports. For offscreen Windows Qt tests, set child-only `QT_QPA_FONTDIR` to the Windows Fonts directory and verify `QFontDatabase.families()` is nonempty.

## Steps

1. **Targeted tests** (fast feedback; add a unique `--basetemp` when inspecting failure artifacts):
   ```powershell
   .\.venv311\Scripts\python.exe -m pytest -q <test_paths>
   ```
2. **Validation wrapper** (`scripts/validate_dev.ps1`):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick
   powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
   powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
   ```
   - Use `-Full -Workers 1` for sequential formatting-group diagnosis.
   - `Test-DocsValidationTriggered` automatically runs docs validation when `AGENTS.md`, `agent.md`, `.agents/*`, `docs/assistant/*`, `README.md`, or `APP_KNOWLEDGE.md` changed.
3. **Complete repository pytest** (`-Full` is NOT the entire repository collection; use a new `--output` path per run):
   ```powershell
   .\.venv311\Scripts\python.exe tooling/test_shards.py run --workers 4 --timings tooling/test_timings.json --output tmp/validation/<run-id> -- tests
   ```
4. **Docs & workspace hygiene checks** (use the direct Dart binary directly or as fallback if `dart run` prints `Unable to find AOT snapshot for dartdev`):
   ```powershell
   & 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_agent_docs.dart
   & 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_agent_docs.dart --scope localization
   & 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' test/tooling/validate_agent_docs_test.dart
   & 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_workspace_hygiene.dart
   & 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' test/tooling/validate_workspace_hygiene_test.dart
   ```
5. **Read-only workstation check**:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1 -ConfigurationOnly
   ```

## Verification

- Confirm every command exited `0` and record exact scopes (targeted vs `-Quick` vs `-Full` vs sharded complete suite).
- If `dart run` hit the `dartdev` AOT snapshot error, report both the wrapper error and the passing direct-Dart command results.
