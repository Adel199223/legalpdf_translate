# OCR Hardening Wave 1

## 1. Title
OCR hardening roadmap restart wave 1 baseline validation and continuity activation

## 2. Goal and non-goals
- Goal:
  - activate one authoritative OCR/runtime hardening wave on a clean isolated worktree
  - validate the current `f50686a` browser-plus-Qt baseline instead of inheriting assumptions from the dirty local checkout
  - record one gap matrix with exactly three buckets: `already landed`, `regressed/broken`, and `not yet landed`
  - keep future OCR hardening scope constrained to concrete baseline gaps only
- Non-goals:
  - no product/runtime edits in this wave unless a baseline validation failure forces a later follow-up wave
  - no Gmail feature expansion
  - no broader UI redesign
  - no external network refresh/fetch in this wave

## 3. Scope (in/out)
- In:
  - `docs/assistant/exec_plans/active/2026-03-19_ocr_hardening_wave1.md`
  - `docs/assistant/exec_plans/active/2026-03-19_ocr_hardening_roadmap.md`
  - `docs/assistant/SESSION_RESUME.md`
  - clean-worktree OCR/runtime validation on `f50686a`
  - baseline gap-matrix recording
- Out:
  - application/runtime code changes under `src/`
  - Gmail roadmap work
  - harness/template sync
  - merge/publish actions

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_ocr_hardening`
- Branch name: `codex/ocr-hardening-roadmap`
- Base branch: `main`
- Base SHA: `f50686a19f7b0fc5245c7586d60258dfb05de697`
- Target integration branch: `main`
- Canonical build status: noncanonical OCR roadmap worktree; approved base floor satisfied per `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Roadmap continuity only in this wave:
  - `docs/assistant/SESSION_RESUME.md` becomes active-roadmap state for this worktree
  - `docs/assistant/exec_plans/active/2026-03-19_ocr_hardening_roadmap.md` is the sequence source
  - this ExecPlan is the implementation-detail source
- Product contract hold-points for any later wave:
  - preserve `TranslationWorkflow.run`, `TranslationWorkflow.analyze`, and `TranslationWorkflow.rebuild_docx`
  - preserve OCR provider/settings keys and current run-artifact/failure-context fields
  - allow only additive or internal-fix OCR/runtime changes later

## 6. File-by-file implementation steps
- Create this Wave 1 ExecPlan first with the validation commands and gap-matrix contract.
- Create the OCR roadmap tracker second and link this wave as the active implementation slice.
- Update `docs/assistant/SESSION_RESUME.md` third so fresh sessions route to the active roadmap and wave.
- Audit `docs/assistant/exec_plans/active/` for stale OCR-themed plans on this clean baseline and supersede them only if they exist.
- Run the baseline OCR validation pass on this worktree and record the exact outcomes here.
- If the gap matrix shows no real OCR gap, close the roadmap later instead of inventing Wave 2 work.
- If the gap matrix shows real OCR gaps, open Wave 2 only for those concrete gaps.

## 7. Tests and acceptance criteria
- Validation commands:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
  - `.venv311\Scripts\python.exe -m compileall src tests`
  - `.venv311\Scripts\python.exe -m pytest -q tests/test_ocr_policy_routing.py tests/test_workflow_ocr_routing.py tests/test_ocr_translation_probe.py tests/test_source_document.py tests/test_user_settings_schema.py`
- Acceptance:
  - `legalpdf_translate.workflow` imports cleanly on this roadmap baseline
  - OpenAI and Gemini OCR routing both validate
  - OCR-heavy safe-profile, bounded-timeout, and probe-tool behavior stay aligned with current docs
  - a fresh session can reach the active roadmap and this wave from `docs/assistant/SESSION_RESUME.md`

## 8. Rollout and fallback
- Complete the continuity/doc activation and validation in one pass.
- If validation is green and no OCR gaps remain, use roadmap closeout rather than opening a filler wave.
- If validation exposes broken or missing OCR scope, use the gap matrix as the only allowed source for Wave 2 scope.

## 9. Risks and mitigations
- Risk: the older dirty checkout could leak stale assumptions into this roadmap.
  - Mitigation: treat `f50686a` in this worktree as the only baseline authority for Wave 1.
- Risk: browser-app closeout state could obscure whether OCR/runtime behavior is still intact.
  - Mitigation: validate both workflow imports and focused OCR/runtime tests directly on this baseline.
- Risk: stale OCR plans from another checkout could be mistaken for live authority.
  - Mitigation: treat only this worktree's `active/` directory plus `SESSION_RESUME.md` as authoritative.

## 10. Assumptions/defaults
- No network refresh will be performed; the local `f50686a` baseline is the authority for this wave.
- The user's dirty `C:\Users\FA507\.codex\legalpdf_translate` checkout remains untouched.
- If `docs/assistant/exec_plans/active/` on this worktree contains only `.gitkeep`, stale OCR-plan supersession is satisfied by documenting that no active OCR plans exist here.

## 11. Execution status
- Wave 1 activated on the isolated worktree.
- The clean baseline contains only `.gitkeep` plus the new OCR roadmap artifacts under `docs/assistant/exec_plans/active/`, so there were no pre-existing active OCR plans on this worktree to retire or supersede.
- Baseline validation and gap-matrix recording are complete.
- Wave 2 was required for the concrete OCR key-resolution validation gap recorded below.
- Wave 2 completed and resolved that concrete gap without widening scope beyond OCR/runtime validation hardening.

## 12. Executed validations and outcomes
- `dart run tooling/validate_agent_docs.dart` -> PASS
- `dart run tooling/validate_workspace_hygiene.dart` -> PASS
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m compileall src tests` -> PASS
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -c "import legalpdf_translate.workflow as w; print(w.TranslationWorkflow.__name__)"` -> PASS (`TranslationWorkflow`)
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_ocr_policy_routing.py tests/test_workflow_ocr_routing.py tests/test_ocr_translation_probe.py tests/test_source_document.py tests/test_user_settings_schema.py` -> FAIL (`56 passed`, `2 failed`)
- Validation note:
  - this isolated worktree does not have its own materialized `.venv311`, so the shared interpreter from the canonical checkout was used for the Python validation commands

## 13. Baseline Gap Matrix
### `already landed`
- `legalpdf_translate.workflow` imports cleanly on the `f50686a` baseline.
- OCR/runtime docs continuity is active and the fresh-session resume chain now resolves to this roadmap and wave sequence.
- Agent-doc and workspace-hygiene validators pass on the isolated OCR roadmap worktree.
- The focused OCR/runtime suite is mostly healthy on this baseline: `56` targeted tests passed, including workflow routing, OCR translation probe, source-document handling, and user-settings coverage.
- The baseline already contains the intended browser-plus-Qt OCR surfaces:
  - `workflow.py`
  - OCR provider support in `ocr_engine.py`
  - OCR-heavy warning/safe-profile behavior
  - bounded failure-context timeout fields

### `regressed/broken`
- `tests/test_ocr_policy_routing.py::test_api_policy_missing_key_raises` fails on this baseline because the OpenAI-provider key resolution still accepts `OPENAI_API_KEY` compatibility fallback when only `DEEPSEEK_API_KEY` is cleared.
- `tests/test_ocr_policy_routing.py::test_local_then_api_without_key_disables_api_fallback` fails for the same reason: the environment still satisfies the OpenAI fallback path, so `LocalThenApiEngine.api_engine` remains configured.
- The concrete gap is not a broad workflow import/runtime failure; it is a deterministic OCR key-resolution validation mismatch that depends on local env presence.
- Resolution:
  - Wave 2 hardened `tests/test_ocr_policy_routing.py` so the missing-key cases clear both OpenAI-compatible env names and the compatibility-fallback path is asserted explicitly.

### `not yet landed`
- No remaining OCR/runtime gaps from this roadmap baseline after Wave 2.
- If documentation is needed after Wave 2 analysis, add a minimal clarification for the OpenAI OCR compatibility fallback contract without widening scope beyond OCR/runtime hardening.
