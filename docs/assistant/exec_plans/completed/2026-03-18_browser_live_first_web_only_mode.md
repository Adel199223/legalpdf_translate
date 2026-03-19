## Goal
- Make the browser app the primary day-to-day entrypoint for non-technical use by defaulting the web UI to live mode, not isolated shadow mode.
- Keep isolated test mode available, but present it as an explicit secondary option instead of the default browser experience.
- Simplify browser-app copy so it reads like the real app rather than a parity/developer harness.

## Scope
- In scope:
  - browser root/default mode and default launcher URL
  - browser-visible runtime-mode labels and copy
  - top-level UI language that still exposes testing mode without centering it
  - targeted regression tests for the new default and wording
- Out of scope:
  - removing isolated mode entirely
  - changing Gmail bridge ownership logic
  - public deployment or non-localhost hosting

## Files
- `src/legalpdf_translate/shadow_web/app.py`
- `src/legalpdf_translate/shadow_web/server.py`
- `src/legalpdf_translate/shadow_web/static/state.js`
- `src/legalpdf_translate/shadow_web/static/app.js`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `src/legalpdf_translate/shadow_runtime.py`
- `src/legalpdf_translate/browser_app_service.py`
- `tests/test_shadow_web_api.py`
- `tests/test_shadow_runtime_service.py`

## Acceptance
- Opening `/` with no mode query loads the browser app in live mode by default.
- `--open` launches the live browser app URL directly.
- The UI labels `live` as the primary day-to-day mode and `shadow` as isolated test mode.
- Core top-level browser copy no longer centers “parity preview” wording.
- Targeted tests, JS syntax checks, and a live browser smoke pass.
