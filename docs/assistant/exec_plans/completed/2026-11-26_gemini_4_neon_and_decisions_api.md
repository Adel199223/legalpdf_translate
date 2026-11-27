# ExecPlan: Add Google Gemini API (`gemini-4-neon` at `xhigh`) + Opt-In Advisory Gemini Decisions API (`gemini-decision-1`)

## 1. Title
Add Google Gemini API (`gemini-4-neon` at `xhigh`) as default translation/review/layout/OCR provider alongside OpenAI, plus opt-in advisory Gemini Decisions API (`gemini-decision-1`).

## 2. Goal and non-goals
- **Goal**:
  - Integrate Google's Gemini Interactions API (`google-genai >= 3.5.0`, `gemini-4-neon`, `thinking_level="xhigh"`, `store=False`) across primary translation, 3-stage semantic review/repair, source-image layout proposals, and Gemini OCR/helpers (configurable `helper_thinking_level`, default `"high"`), making Gemini 4 Neon (`xhigh`) the new default while keeping OpenAI selectable and preserving historical OpenAI runs/checkpoints byte-exact.
  - Add an isolated, opt-in advisory Gemini Decisions API (`gemini-decision-1`, `v1beta` `client.decisions.create`) module behind `gemini_decisions_advisory_enabled` (default `False`) for page-routing and visual QA triage.
- **Non-goals**:
  - Modifying canonical `main` (`C:\Users\FA507\.codex\legalpdf_translate`) or live Gmail/port-8877 state.
  - Executing live paid API calls, merging to `main`, or publishing to remote.
  - Replacing deterministic literal/numeric/XML/billing verification with probabilistic decisions.

## 3. Scope (in/out)
- **In**: `pyproject.toml`, `uv.lock`, `scripts/setup_python311_env.ps1`, `config.py`, `types.py`, `secrets_store.py`, `usage_accounting.py`, `cost_guardrails.py`, `accounting_policy.py`, `gemini_client.py`, `provider_client.py`, `openai_client.py`, `workflow.py`, `new_translation_blocks.py`, `translation_service.py`, `cli.py`, `calibration_audit.py`, `study_glossary.py`, `lemma_normalizer.py`, `power_tools_service.py`, `run_report.py`, `checkpoint.py`, `semantic_review_model_policy.py`, `semantic_review_billing.py`, `workflow_semantic_audit.py`, `ordinary_semantic_review.py`, `ordinary_semantic_repair.py`, `ordinary_layout_contracts.py`, `ordinary_layout_accounting.py`, `ordinary_layout_manager.py`, `ordinary_layout_reproposal.py`, `ocr_engine.py`, `ocr_text_transport.py`, `metadata_autofill.py`, `user_settings.py`, `qt_gui/*`, `shadow_web/*`, `gemini_decisions.py`, `workflow_components/ocr_advisor.py`, `workflow_components/quality_risk.py`, offline unit/integration tests, shadow UI check, and touched-scope docs.
- **Out**: Live paid API calls, live Gmail, modifying canonical `main`.

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\worktrees\gemini-4-neon-api\legalpdf_translate`
- Branch name: `feat/gemini-4-neon-api`
- Base branch: `main`
- Base SHA: `e70dbbdb25ba512462b8bd87110b258d13a3994f`
- Target integration branch: `main`
- Canonical build status: Non-canonical isolated feature worktree (`CANONICAL_BUILD.json` floor `4e9d20e` preserved).

## 5. Interfaces/types/contracts affected
- `RunConfig`: additive fields `translation_provider`, `translation_model`, `helper_thinking_level`, `gemini_decisions_advisory_enabled`.
- `user_settings.py` / browser settings payload: additive keys `translation_provider`, `translation_model`, `helper_thinking_level`, `gemini_decisions_advisory_enabled`.
- `shadow_web/app.py`: additive endpoints `/api/settings/gemini-key/save`, `/api/settings/gemini-key/clear`, provider-aware `/api/settings/translation-key/*`, `/api/settings/test-translation`, and additive `provider_state.gemini` / `provider_state.openai` keys while preserving `provider_state.translation`.
- `ordinary_layout_contracts.py`: `LayoutSuggestionPolicy.public()` accepts `"xhigh"` effort.
- `semantic_review_model_policy.py`, `semantic_review_billing.py`, `ocr_text_transport.py`, `accounting_policy.py`: additive Gemini policies alongside untouched OpenAI policies.

## 6. File-by-file implementation steps
1. Worktree, `pyproject.toml`, `uv.lock`, `.venv311` setup & SDK inspection.
2. Config, types, secrets, usage normalization, cost guardrails, accounting policies.
3. `gemini_client.py`, `provider_client.py`, `openai_client.py`.
4. Stage 1 wiring: `workflow.py`, `new_translation_blocks.py`, `translation_service.py`, `cli.py`, `calibration_audit.py`, `study_glossary.py`, `lemma_normalizer.py`, `qt_gui/*`.
5. Stage 2-4 wiring: semantic review/repair, layout accounting/manager/reproposal, OCR engine/transport, metadata autofill.
6. Settings persistence, endpoints, browser UI (`index.html`, JS modules).
7. Phase 2: `gemini_decisions.py` + opt-in hooks in `ocr_advisor.py`, `quality_risk.py`, `workflow.py`.
8. Tests, `validate_dev.ps1`, shadow UI verification, docs sync.

## 7. Tests and acceptance criteria
- Offline pytest suites (`test_gemini_client.py`, `test_gemini_pipeline_integration.py`, `test_gemini_decisions.py`, plus existing accounting, semantic review, layout, OCR, settings, service, workflow, CLI suites) pass with 0 failures.
- `scripts/validate_dev.ps1` passes.
- Isolated `mode=shadow` browser check confirms Settings UI renders cleanly with zero console errors.

## 8. Rollout and fallback
- Feature branch remains isolated in worktree until user reviews and approves merge to `main`.
- Users can switch back to OpenAI anytime in Settings (`translation_provider="openai"`).

## 9. Risks and mitigations
- Interactions API token accounting: fold `total_thought_tokens` into `output_tokens`.
- Confidentiality: pass `store=False` on all Interactions calls.
- Hidden SDK retries: configure `retry_options={"attempts": 1}` on `genai.Client`.
- Historical OpenAI replay: keep OpenAI policies/models/pricing untouched.

## 10. Assumptions/defaults
- Paid-tier Gemini Developer API keys will be supplied by user at runtime (`gemini_api_key` in keyring or `GEMINI_API_KEY`).
- Default translation/review/layout model: `gemini-4-neon` (`xhigh`); default helper thinking level: `high`; Decisions API advisory toggle: `False` by default.

## 11. Implementation and verification log
- **Implemented scope (`feat/gemini-4-neon-api`)**:
  - Locked `google-genai==3.6.1` (`pyproject.toml`, `uv.lock`, `scripts/setup_python311_env.ps1`, `.venv311`).
  - Added `src/legalpdf_translate/gemini_client.py` (`GeminiInteractionsClient` with `store=False`, `retry_options={"attempts": 1}`, `DispatchAccounting`, thought-token folding into `output_tokens`, and strict raw-byte semantic review retention) and `src/legalpdf_translate/provider_client.py`.
  - Wired `gemini-4-neon` (`thinking_level="xhigh"`) as default across primary translation, 3-stage semantic review/repair, source-image layout proposals, and Gemini OCR/metadata helpers (`helper_thinking_level="high"`), while keeping OpenAI selectable and preserving historical OpenAI runs, checkpoints, and pricing snapshots.
  - Added isolated opt-in advisory `src/legalpdf_translate/gemini_decisions.py` (`gemini-decision-1` on `v1beta` `decisions.create`, `gemini_decisions_advisory_enabled=False` default, confidence abstention `< 0.70`, fail-open) hooked into `ocr_advisor.py`, `quality_risk.py`, and `workflow.py`.
  - Updated settings, secure keyring (`gemini_api_key`), browser UI (`index.html`, `power-tools.js`, `power_tools_ui.js`, `settings_presentation.js`, `shadow_web/app.py`), and Qt settings (`qt_gui/dialogs.py`).
- **Observed verification in isolated worktree**:
  - Targeted regression + Gemini suite (`tests/test_workflow_semantic_review_integration.py`, `tests/test_semantic_review_model_integration.py`, `tests/test_ordinary_semantic_repair.py`, `tests/test_ocr_preflight.py`, `tests/test_ocr_benchmark.py`, `tests/test_qt_settings_key_toggle.py`, `tests/test_gemini_client.py`, `tests/test_gemini_pipeline_integration.py`, `tests/test_gemini_decisions.py`): **138 passed in 40.77s**.
  - Prior targeted sweeps: **206 passed** (`test_new_run_callers.py`, `test_translation_service_accounting.py`, `test_qt_app_state.py`), **134 passed** (`test_gemini_*`, `test_browser_source_review.py`, `test_user_settings_schema.py`, `test_settings_browser_state.py`, `test_effort_settings.py`, `test_formatting_policy_isolation.py`, `test_ocr_policy_routing.py`, `test_transport_dispatch_accounting.py`), **173 passed** (`test_qt_ocr_advisor_panel.py`, `test_ordinary_semantic_audit.py`, `test_workflow_*`, `test_gmail_*`).
  - Isolated shadow UI check on port `8891` (`http://127.0.0.1:8891/?mode=shadow&workspace=smoke-gemini#settings`, isolated scratch `APPDATA`): verified `Gemini (gemini-4-neon)` selected by default, `gemini-4-neon`, `Extra high`, `Helper thinking level = High`, `Enable advisory Gemini Decisions QA triage (opt-in)` unchecked, and `Gemini API key (write-only)` controls/status rendered with 0 console errors.
  - Known pre-existing caveat (confirmed identical on untouched canonical `main`): tests relying on `ordinary_accounting_policy()` (`2026-10-15`) and `ordinary_layout_accounting.layout_accounting_policy()` (`2026-10-09`) 30-day OpenAI pricing windows fail on `2026-11-26` with `pricing_snapshot_unavailable` / `ordinary_layout_pricing_reference_expired`; historical OpenAI dates were intentionally left unchanged.
  - Gemini prioritization hardening (schema v9 → v10 automatic migration for saved `settings.json` legacy pre-Gemini OpenAI OCR/`high`/`adaptive` defaults; eliminated remaining OpenAI fallback defaults across `power_tools_service.py` Glossary Builder lemma normalization, `qt_gui/dialogs.py` `_StudyTranslationWorker`, `qt_gui/app_window.py` `_build_run_config` and `_test_api_keys`, `metadata_autofill.py`, `interpretation_service.py`, `joblog_flow.py`, `translation_service.py`, and `new_translation_blocks.py`, while preserving explicit OpenAI choices in Settings).
  - Post-hardening targeted pytest suite (14 modules including `test_gemini_*`, `test_user_settings_schema.py`, `test_metadata_autofill_*`, `test_qt_*`, `test_new_translation_blocks.py`, `test_translation_service_accounting.py`, `test_interpretation_review_state.py`, `test_cli_flags.py`): **338 passed in 30.75s**.
  - Standard validation (`scripts/validate_dev.ps1`) ran after the final docs sync.
