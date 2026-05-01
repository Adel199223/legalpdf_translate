# OCR Hardening Roadmap Restart

## 1. Title
OCR/runtime hardening roadmap restart from the clean `f50686a` browser-app baseline

## 2. Goal and non-goals
- Goal:
  - reopen roadmap governance for OCR/runtime hardening on a fresh isolated worktree
  - establish one durable resume anchor, one active roadmap tracker, and one active wave ExecPlan
  - base later OCR work on validated gaps from the current approved baseline instead of stale local WIP
- Non-goals:
  - no Gmail product expansion in this roadmap
  - no broad browser/Qt redesign roadmap
  - no assumption that older dirty-checkout active plans are authoritative

## 3. Scope (in/out)
- In:
  - roadmap continuity artifacts for this worktree
  - Wave 1 baseline validation and gap matrix
  - later OCR/runtime hardening waves only if Wave 1 surfaces concrete gaps
- Out:
  - unrelated product feature work
  - publish/merge actions in this restart pass
  - template/harness sync

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_ocr_hardening`
- Branch name: `codex/ocr-hardening-roadmap`
- Base branch: `main`
- Base SHA: `f50686a19f7b0fc5245c7586d60258dfb05de697`
- Target integration branch: `main`
- Canonical build status: noncanonical dedicated roadmap worktree; approved base floor satisfied per `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Active roadmap continuity:
  - `docs/assistant/SESSION_RESUME.md`
  - `docs/assistant/exec_plans/active/2026-03-19_ocr_hardening_roadmap.md`
  - `docs/assistant/exec_plans/active/2026-03-19_ocr_hardening_wave1.md`
- Future OCR work guardrails:
  - preserve `TranslationWorkflow` entrypoints
  - preserve OCR provider/settings contract
  - preserve current run summary/report/failure-context field names

## 6. File-by-file implementation steps
- Wave 1:
  - activate the roadmap on this isolated worktree
  - update `docs/assistant/SESSION_RESUME.md` to link this roadmap and the active wave
  - validate the OCR/runtime baseline and record one three-bucket gap matrix
  - determine whether Wave 2 is actually needed
- Wave 2:
  - open only if Wave 1 records concrete OCR/runtime regressions or missing OCR scope
  - keep changes limited to OCR/runtime hardening and any continuity cleanup directly required by that work
  - current Wave 2 scope is the OCR key-resolution validation gap recorded by Wave 1

## 7. Tests and acceptance criteria
- Wave 1 validations are the baseline gate:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
  - `.venv311\Scripts\python.exe -m compileall src tests`
  - `.venv311\Scripts\python.exe -m pytest -q tests/test_ocr_policy_routing.py tests/test_workflow_ocr_routing.py tests/test_ocr_translation_probe.py tests/test_source_document.py tests/test_user_settings_schema.py`
- Acceptance:
  - Wave 1 produces an explicit gap matrix with only `already landed`, `regressed/broken`, and `not yet landed`
  - fresh-session resume lands on this roadmap and the active wave without chat history
  - no later wave is opened unless the gap matrix justifies it

## 8. Rollout and fallback
- Start with docs/continuity activation and baseline validation only.
- If Wave 1 shows no meaningful OCR gap, close the roadmap instead of prolonging it.
- If Wave 1 shows actionable OCR scope, open one concrete follow-up wave scoped only to those findings.

## 9. Risks and mitigations
- Risk: roadmap restart duplicates stale continuity from non-authoritative worktrees.
  - Mitigation: treat this worktree's `SESSION_RESUME.md`, this roadmap, and the active wave as the only live authority.
- Risk: broad browser-app state could tempt the roadmap into unrelated feature work.
  - Mitigation: keep the roadmap explicitly OCR/runtime only.
- Risk: validation noise could be mistaken for a product gap.
  - Mitigation: record exact command outcomes and separate landed behavior from real regressions.

## 10. Assumptions/defaults
- The local `f50686a` baseline is sufficient; no fetch is needed for this restart.
- The clean OCR roadmap worktree is the active authority until this roadmap is closed.
- Any stale OCR-themed plans in other checkouts are historical references, not active authority.

## 11. Current status
- Roadmap implementation is complete on `codex/ocr-hardening-roadmap`.
- Wave 1 completed the baseline validation pass and recorded one concrete OCR key-resolution validation gap.
- Wave 2 resolved that gap through hermetic test hardening while preserving the intended OpenAI default-plus-legacy fallback contract.
- No remaining OCR/runtime gaps remain from the `f50686a` baseline covered by this roadmap.
- The next step after roadmap closeout is normal ExecPlan flow or commit/publish work only if the user explicitly asks for it.
