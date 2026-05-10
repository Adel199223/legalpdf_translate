# Gmail Lifecycle Diagnostics Presentation ExecPlan

## Provenance
- Branch: `codex/gmail-lifecycle-diagnostics-presentation`
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_lifecycle_diagnostics_presentation`
- Base: `main@9cece914cb2ce286c166894c16f32faeb7ef0788`
- Created: 2026-05-10
- Completed: 2026-05-10

## Goal
Extract remaining static Gmail lifecycle diagnostic presentation copy from `gmail.js` into a pure browser static module while preserving diagnostics slots, payload objects, hint strings, routes, selectors, Gmail/native-host behavior, and safe rendering.

## Plan
- [x] Add failing lifecycle diagnostics presentation contract/probe coverage in `tests/test_shadow_web_api.py`.
- [x] Create `gmail_lifecycle_diagnostics_presentation.js` with pure diagnostic builders.
- [x] Update `gmail.js` initialization, refresh, prepare, save-current-attachment, and reset flows to call the builders before `setDiagnostics(...)`.
- [x] Update static asset graph coverage for the new module.
- [x] Run targeted, focused, full validation, and Browser shadow smoke.
- [x] Move this ExecPlan to `completed/` before commit.

## Validation Log
- RED confirmed: `tests/test_shadow_web_api.py::test_gmail_lifecycle_diagnostics_presentation_module_builds_lifecycle_diagnostics_state` failed before implementation because the new presentation module did not exist.
- Targeted lifecycle diagnostics test: `1 passed in 3.80s`.
- Static asset graph test: `1 passed in 2.81s`.
- Focused browser/Gmail suite: `209 passed in 186.92s`.
- Full validation: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` completed successfully.
- Full validation recorded the known Dart AOT launcher issue for the docs and workspace hygiene launchers; the wrapper's direct-Dart fallback passed in both cases.
- Browser shadow smoke on port `8888` verified page identity, nonblank content, no framework overlay, empty browser console errors, demo attachment load, preview interaction, and screenshot evidence at `C:\Users\FA507\.codex\browser\gmail-lifecycle-diagnostics-smoke.png`.
