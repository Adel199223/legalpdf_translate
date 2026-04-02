# Residual Tooling Hardening for Visual DOCX Review and Browser Automation

## Goal and non-goals
- Goal: remove the remaining non-blocking host/tooling gaps by making browser automation preflight reliable on this Windows machine and by adding a canonical DOCX-to-PDF-to-PNG review path for generated artifacts.
- Non-goals: change Gmail handoff semantics, translation/finalization behavior, Word export behavior, or any run-report route shape.

## Scope (in/out)
- In scope:
  - Browser automation preflight invocation and diagnostics
  - Canonical DOCX render-review helper and its tests
  - Machine setup needed for Poppler/pdf2image-based visual review
  - Touched docs/workflows for the updated automation/render-review contracts
- Out of scope:
  - Gmail/browser UX changes unrelated to residual diagnostics
  - New deployment, publish, or release work

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/gmail-finalization-report-success`
- Base branch: `main`
- Base SHA: `18be21ec2d2c632f12ec5da3d2e5351aa5644488`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch carrying the accepted Gmail finalization/report fixes plus this residual tooling hardening pass

## Interfaces/types/contracts affected
- `run_browser_automation_preflight()` will prefer direct Dart script execution and treat `dartdev` launcher failure as a launcher-path problem, not as browser automation unavailability.
- New local toolchain overrides:
  - `LEGALPDF_DART_BIN`
  - `LEGALPDF_SOFFICE_PATH`
  - `LEGALPDF_POPPLER_BIN_DIR`
- New helper CLI:
  - `tooling/render_docx.py --input <docx> --outdir <dir>`

## File-by-file implementation steps
1. Add preflight command resolution and fallback hardening in `src/legalpdf_translate/shadow_runtime.py`.
2. Add targeted regression coverage in `tests/test_shadow_runtime_service.py` and any browser API/runtime tests that assert automation diagnostics.
3. Add `tooling/render_docx.py` with explicit Windows tool discovery, DOCX-to-PDF export, PDF-to-PNG rasterization, and structured fallback payloads.
4. Add tests for the render helper contract and tool resolution.
5. Update the browser automation provenance workflow and touched assistant docs/manifests to reflect direct Dart invocation and the render-review helper.
6. Install Poppler on this host, install `pdf2image` into `.venv311`, then validate the repo-owned helper against real generated Gmail artifacts.

## Tests and acceptance criteria
- Targeted pytest for runtime/preflight and render helper pass.
- Direct automation preflight succeeds and reports `preferred_host_status=available` and `playwright_available=true`.
- Fresh browser/runtime report no longer contains the `dartdev` warning as the primary automation outcome.
- Real generated DOCX artifacts render through the new helper into PDF and PNG page images.
- Existing Gmail handoff, translation, finalization, and finalization-report regressions remain green.

## Rollout and fallback
- Prefer repo-owned auto-detection for Dart/LibreOffice/Poppler so the fix works in fresh shells.
- If Poppler is still unavailable, render helper must return structured non-visual fallback status rather than failing opaquely.
- If direct Dart execution fails unexpectedly, preserve the old `run` fallback and classify the launcher problem explicitly.

## Risks and mitigations
- Risk: touching runtime preflight could regress browser diagnostics.
  - Mitigation: keep JSON shape stable and add targeted runtime/API tests.
- Risk: machine installs could appear successful but remain undiscoverable to the repo.
  - Mitigation: acceptance is through the repo helper and fresh run-report output, not package manager output alone.
- Risk: docs drift after behavior changes.
  - Mitigation: update only the touched browser-automation and local-capability docs in the same pass.

## Assumptions/defaults
- Use the existing Flutter-provided Dart binary rather than installing a separate Dart SDK.
- Reuse the already-installed LibreOffice and avoid requiring PATH edits.
- Poppler and `pdf2image` are the only required new dependencies for the visual review path.

## Outcome
- Completed on `2026-04-01` on `feat/gmail-finalization-report-success`.
- Installed Poppler via WinGet (`oschwartz10612.Poppler`) and installed `pdf2image` into `.venv311`.
- Browser automation preflight now prefers direct Dart execution and fresh live reports show:
  - `preferred_host_status = available`
  - `playwright_available = true`
  - no stale `dartdev` launcher warning
- Added `tooling/render_docx.py` and validated it against live artifacts:
  - translated DOCX rendered to PDF plus 6 PNG pages
  - honorários DOCX rendered to PDF plus 1 PNG page
  - visual spot-check confirmed non-blank, structurally correct output
- Final targeted/broader validation:
  - `dart test/tooling/automation_preflight_test.dart`
  - `python -m pytest -q tests/test_shadow_runtime_service.py tests/test_render_docx.py`
  - `python -m pytest -q tests/test_gmail_batch.py tests/test_gmail_browser_service.py tests/test_shadow_web_api.py tests/test_qt_app_state.py tests/test_shadow_runtime_service.py tests/test_render_docx.py`
  - `dart tooling/validate_agent_docs.dart`
- Fresh live finalization report generated from the running browser app:
  - `C:\Users\FA507\Downloads\power_tools\gmail_finalization_report_20260401_150712.md`
