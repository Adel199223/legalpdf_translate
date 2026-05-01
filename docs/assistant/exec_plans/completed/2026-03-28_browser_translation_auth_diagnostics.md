# Browser Translation Auth Diagnostics

## Goal and non-goals
- Goal: make browser and Gmail-started translation auth failures classify and surface as translation authentication problems instead of generic runtime failures.
- Goal: add browser-side translation credential diagnostics and an explicit translation auth test without adding browser secret-entry UI.
- Goal: fail translation runs fast before OCR/page work when translation auth is already known to be invalid.
- Non-goal: add browser save/clear OpenAI key management.
- Non-goal: change analyze/rebuild auth behavior beyond keeping them off the new translate preflight path.

## Scope (in/out)
- In scope:
  - shared OpenAI translation auth helper(s) in the transport layer
  - translate-only auth preflight and auth-specific run classification
  - additive `failure_context` fields for auth failures
  - browser capability/provider-state hydration for translation auth readiness
  - browser translation auth test endpoint and UI copy
  - focused regression tests for transport, workflow, browser API, and browser UI messaging
- Out of scope:
  - browser credential storage or editing
  - unrelated OCR, Gmail draft, or Word export behavior changes
  - broad redesign of translation job UX beyond auth-specific copy

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-gmail-autostart-repair`
- base branch: `main`
- base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- target integration branch: `main`
- canonical build status: canonical worktree per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- `OpenAIResponsesClient` credential resolution and auth-test helpers
- translation run contract for auth failures:
  - `RunSummary.error = "authentication_failure"`
  - `run_state.run_status = "authentication_failure"`
  - `run_summary.json.suspected_cause = "authentication_failure"`
- additive `run_summary.json.failure_context` fields:
  - `scope`
  - `status_code`
  - translation credential source metadata
- browser capability flags:
  - `capability_flags.translation`
- browser settings diagnostics:
  - `settings_admin.provider_state.translation`
- new browser translation auth test route with the same response style as existing settings test routes

## File-by-file implementation steps
1. Update `src/legalpdf_translate/openai_client.py` to expose shared translation credential resolution and a minimal auth test helper that reports safe source metadata without exposing key values.
2. Update `src/legalpdf_translate/workflow.py` so translate runs perform one auth preflight before OCR/page work, classify auth rejection as `authentication_failure`, and persist auth-specific `failure_context`.
3. Update `src/legalpdf_translate/translation_service.py` to carry auth failure context into browser job payloads, enrich translation capability flags with translation credential readiness/source, and improve auth-specific status text.
4. Update browser diagnostics services in `src/legalpdf_translate/power_tools_service.py`, `src/legalpdf_translate/shadow_web/app.py`, and the browser JS under `src/legalpdf_translate/shadow_web/static/` to expose translation credential state, add a translation auth test action, and show auth-specific recovery guidance.
5. Add or update focused tests covering transport helper behavior, workflow auth preflight/page-failure classification, browser capability hydration, translation auth test route behavior, and browser auth-specific job messaging.

## Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_openai_key_resolution.py tests/test_openai_transport_retries.py`
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_workflow_ocr_routing.py tests/test_workflow_parallel.py tests/test_run_report.py`
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_shadow_web_api.py`
- Acceptance criteria:
  - invalid OpenAI translation credentials stop `translate` before OCR/page processing
  - page-level auth rejection is classified as `authentication_failure`
  - browser capability/settings diagnostics show translation credential readiness and safe source metadata
  - browser translation auth test route returns structured success/failure payloads
  - browser job/status copy tells the user this is an OpenAI auth problem and points recovery to Qt Settings or CLI `--set-openai-key`

## Rollout and fallback
- Keep the change additive and diagnostic-first.
- Preserve existing Qt/CLI credential management as the only write path for secrets.
- If browser auth diagnostics regress unexpectedly, keep generic translation execution intact outside the auth-specific paths.

## Risks and mitigations
- Risk: auth preflight could falsely block healthy translation runs.
  - Mitigation: keep the probe minimal, translate-only, and backed by focused tests for missing, stored, env, unauthorized, and success cases.
- Risk: new auth classification could accidentally swallow other runtime failures.
  - Mitigation: scope the new classification strictly to explicit auth exceptions/status codes and leave generic runtime failure behavior unchanged otherwise.
- Risk: browser diagnostics could drift from Qt/CLI credential precedence.
  - Mitigation: centralize source resolution in the shared transport helper and reuse it everywhere.

## Assumptions/defaults
- Recovery guidance should point to existing secure credential flows only.
- Missing and invalid credentials must remain distinct.
- Immediate docs sync is not required unless the implementation materially changes user-facing support guidance.
