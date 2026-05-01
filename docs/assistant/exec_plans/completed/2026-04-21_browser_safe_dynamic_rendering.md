# Browser Dynamic Rendering Safety Hardening

## Goal and non-goals
- Goal: harden browser-side dynamic rendering so user-controlled or externally-derived values are rendered safely as text instead of being interpolated into unsafe `innerHTML`.
- Non-goals: no backend/API/route changes, no workflow or persistence changes, no UI redesign, no `ui=legacy` changes.

## Scope (in/out)
- In scope:
  - `app.js` renderers for profile distance rows, recent work/history, dashboard/runtime summary cards, parity-audit result, and interpretation export result.
  - `translation.js` renderers for saved translation history and translation run cards.
  - `gmail.js` renderers for attachment list and review detail, plus any additional Gmail renderer found to interpolate unescaped dynamic values.
  - New shared browser-only DOM helper module and focused browser-state tests.
- Out of scope:
  - browser templates/copy changes except where needed to preserve existing markup contracts
  - backend payload shapes and service behavior
  - broader rendering architecture rewrite

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- target integration branch: `main`
- canonical build status: noncanonical feature worktree continuing the browser Qt polish line; no publish actions in this pass

## Interfaces/types/contracts affected
- New browser-only module: `src/legalpdf_translate/shadow_web/static/safe_rendering.js`
- Additive renderer exports only where needed for focused browser ESM safety tests
- No backend or route contract changes

## File-by-file implementation steps
1. Add `safe_rendering.js` with small DOM-safe helpers for text nodes, multiline text, titles, and empty-state construction.
2. Update `app.js` to use the helper for the unsafe dynamic renderers while preserving handlers, layout classes, and existing beginner-friendly copy.
3. Update `translation.js` recent-work renderers to build cards safely and set path tooltips via DOM properties.
4. Update `gmail.js` attachment/detail rendering to avoid raw HTML for filenames and related Gmail-derived values; leave already-safe escaped template blocks alone unless a raw interpolation is found.
5. Add focused browser ESM safety coverage and keep existing copy/route/state tests intact.

## Tests and acceptance criteria
- Acceptance:
  - HTML-like city names, case fields, filenames, and paths render literally as text.
  - No injected nodes appear from those values.
  - Existing buttons/actions still exist and behave the same.
  - Beginner-friendly copy remains unchanged.
- Validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_profile_browser_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_safe_rendering.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py`
  - focused Gmail pytest only if Gmail helper/rendering coverage changes materially
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`

## Rollout and fallback
- Rollout is local-only in this pass through the browser test/validation path.
- If a renderer change causes unexpected DOM regressions, fall back to escaped template rendering for that specific block rather than leaving a raw interpolation in place.

## Risks and mitigations
- Risk: `app.js` is hard to test directly because it bootstraps the whole browser shell.
  - Mitigation: add narrowly-scoped renderer exports only where needed for the browser ESM probe.
- Risk: changing DOM assembly could disturb button wiring or class hooks.
  - Mitigation: preserve existing classes, IDs, and handler binding points exactly.
- Risk: broad Gmail churn could create behavior regressions.
  - Mitigation: keep Gmail changes narrow and only convert blocks that need hardening.

## Assumptions/defaults
- Existing `escapeHtml(...)` helpers stay in place for already-safe template-rendered blocks.
- No new user-facing copy changes are intended.
- Downloads summaries and clean ZIP remain required deliverables for this pass.

## Executed validations and outcomes
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_safe_rendering.py` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_profile_browser_state.py` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> passed
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` -> passed, including direct-Dart fallback for the known `dartdev` AOT snapshot issue
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> passed, including direct-Dart fallback for the known `dartdev` AOT snapshot issue
