# OCR Hardening Wave 2

## 1. Title
OCR key-resolution contract and validation hardening

## 2. Goal and non-goals
- Goal:
  - restore deterministic OCR routing validation on the clean `f50686a` baseline
  - keep the intended OpenAI OCR compatibility behavior explicit when `OPENAI_API_KEY` and legacy `DEEPSEEK_API_KEY` naming coexist
  - resolve the two failing targeted OCR tests without widening scope beyond OCR/runtime hardening
- Non-goals:
  - no Gmail workflow changes
  - no broader browser/Qt UX work
  - no OCR provider redesign unless current runtime code is proven inconsistent with the intended compatibility contract

## 3. Scope (in/out)
- In:
  - `tests/test_ocr_policy_routing.py`
  - `src/legalpdf_translate/ocr_engine.py` only if runtime behavior and intended contract are genuinely misaligned
  - minimal OCR contract clarification in docs only if the final fix changes or formalizes expected fallback behavior
- Out:
  - unrelated OCR/UI tests
  - Gmail and interpretation flows
  - browser-app architecture work

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_ocr_hardening`
- Branch name: `codex/ocr-hardening-roadmap`
- Base branch: `main`
- Base SHA: `f50686a19f7b0fc5245c7586d60258dfb05de697`
- Target integration branch: `main`
- Canonical build status: noncanonical OCR roadmap worktree; approved base floor satisfied per `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- OCR key-resolution contract for OpenAI provider compatibility:
  - default env name: `OPENAI_API_KEY`
  - legacy compatibility env name: `DEEPSEEK_API_KEY`
- Validation contract:
  - missing-key tests must be hermetic even when developer machines already export `OPENAI_API_KEY`
- Runtime hold-point:
  - do not change `TranslationWorkflow` or downstream run-artifact contracts in this wave

## 6. File-by-file implementation steps
- Confirm the intended OpenAI OCR key-resolution contract in `src/legalpdf_translate/ocr_engine.py`.
- Treat the current dual-name fallback as authoritative unless code analysis proves it is accidental.
- Update `tests/test_ocr_policy_routing.py` so the missing-key cases clear or isolate both OpenAI-compatible env names and no longer depend on the machine's ambient secrets.
- Touch `src/legalpdf_translate/ocr_engine.py` only if the current implementation contradicts the intended compatibility contract after that analysis.
- If runtime contract wording is still ambiguous after the fix, add one minimal doc clarification in the OCR/runtime docs and keep it scoped to env fallback behavior.

## 7. Tests and acceptance criteria
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_ocr_policy_routing.py tests/test_workflow_ocr_routing.py tests/test_ocr_translation_probe.py tests/test_source_document.py tests/test_user_settings_schema.py`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance:
  - the two currently failing missing-key OCR routing tests pass on machines with or without `OPENAI_API_KEY`
  - OpenAI and Gemini OCR routing coverage still passes
  - runtime behavior stays aligned with the intended compatibility contract

## 8. Rollout and fallback
- Prefer the smallest fix that makes the validation contract deterministic.
- If tests alone can express the intended contract, keep runtime code unchanged.
- If runtime code is actually wrong, fix only the OCR key-resolution layer and rerun the targeted suite.

## 9. Risks and mitigations
- Risk: a test-only fix could mask a real runtime contract problem.
  - Mitigation: inspect `candidate_ocr_api_env_names()` and `build_ocr_engine()` before deciding whether tests or runtime code should change.
- Risk: changing runtime env resolution could break compatibility for existing users relying on legacy OCR env names.
  - Mitigation: preserve OpenAI default plus legacy fallback unless a stronger compatibility reason emerges from code analysis.
- Risk: doc wording drifts from the final implemented contract.
  - Mitigation: only add minimal OCR contract clarification if the final fix requires it.

## 10. Assumptions/defaults
- The current `OPENAI_API_KEY` fallback behavior appears intentional on this baseline.
- The Wave 1 failures are concrete enough to justify one follow-up wave even though they are narrow.
- The shared interpreter from `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe` remains the validation interpreter for this isolated worktree unless a local `.venv311` is later materialized.

## 11. Current status
- Wave 2 is complete.
- The OCR key-resolution validation contract is now deterministic on machines with or without `OPENAI_API_KEY`.
- Runtime OCR behavior remains unchanged; this wave resolved the gap by hardening `tests/test_ocr_policy_routing.py`.

## 12. Executed validations and outcomes
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_ocr_policy_routing.py tests/test_workflow_ocr_routing.py tests/test_ocr_translation_probe.py tests/test_source_document.py tests/test_user_settings_schema.py` -> PASS (`59 passed`)
- `dart run tooling/validate_agent_docs.dart` -> PASS
- `dart run tooling/validate_workspace_hygiene.dart` -> PASS

## 13. Implementation outcome
- Confirmed in code and completed-plan history that OpenAI OCR intentionally uses:
  - default env name `OPENAI_API_KEY`
  - legacy compatibility fallback `DEEPSEEK_API_KEY`
- Hardened the missing-key routing tests so they clear both compatible env names instead of depending on ambient machine secrets.
- Added an explicit test that proves `OPENAI_API_KEY` still satisfies the OpenAI OCR engine when the config references the legacy env label.
