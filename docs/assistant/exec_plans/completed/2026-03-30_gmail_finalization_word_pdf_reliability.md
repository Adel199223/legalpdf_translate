# ExecPlan: Gmail Finalization Word PDF Reliability

## Goal and non-goals
- Goal: implement Stage 1 of the staged Gmail finalization reliability plan by rebuilding the Word PDF readiness contract so the browser can distinguish launch-only readiness from real export readiness.
- Goal: add a real Word export canary, phase-aware export diagnostics, and safe app-owned timeout cleanup in the Word automation layer.
- Goal: expose the new readiness contract additively through browser/provider capability payloads without redesigning the Gmail finalization drawer in this stage.
- Goal: stop after Stage 1 with a stage packet and exact continuation token requirement.
- Non-goal: Stage 2 browser finalization drawer blocking/retry/report UX.
- Non-goal: Stage 3 cached browser-side canary test actions and validation environment repair.
- Non-goal: Stage 4 live Gmail/job-log mutation acceptance.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/word_automation.py`
  - `src/legalpdf_translate/interpretation_service.py`
  - `src/legalpdf_translate/power_tools_service.py`
  - `src/legalpdf_translate/browser_app_service.py`
  - minimal browser consumer compatibility in `src/legalpdf_translate/shadow_web/static/app.js` and `src/legalpdf_translate/shadow_web/static/power-tools.js`
  - targeted tests for Word automation and browser/provider-state capability shaping
- Out of scope:
  - Gmail finalization drawer state redesign
  - finalization retry/report UI actions
  - live Gmail draft mutation acceptance
  - docs sync outside this stage packet

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical worktree on an accepted feature branch; branch contains the approved-base floor `4e9d20e` from `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- `WordAutomationResult` gains additive diagnostics fields for timeout phase and app-owned cleanup provenance.
- Browser `word_pdf_export` capability/provider payload becomes additive:
  - `launch_preflight`
  - `export_canary`
  - `finalization_ready`
  - compatibility top-level readiness fields kept for current consumers
- Existing Gmail finalization response shapes remain unchanged in Stage 1.

## File-by-file implementation steps
1. Extend `word_automation.py` with:
   - phase-tagged PowerShell export/preflight scripts
   - helper-process execution with timeout-aware cleanup for app-owned helper trees only
   - a tiny DOCX-to-PDF canary export helper that verifies PDF output
2. Reuse the new Word readiness contract in `interpretation_service.py` / browser provider helpers without changing finalization semantics yet.
3. Update browser/provider capability shaping in `power_tools_service.py` and `browser_app_service.py` to surface launch-vs-export readiness additively.
4. Adjust current browser consumer code in `shadow_web/static/app.js` and `shadow_web/static/power-tools.js` so existing readiness cards summarize finalization readiness instead of launch-only readiness while staying backward compatible.
5. Add focused regression tests for Word automation diagnostics/cleanup/canary behavior and the additive capability payload contract.

## Tests and acceptance criteria
- Targeted tests:
  - `python -m pytest -q tests/test_word_automation.py tests/test_shadow_runtime_service.py tests/test_shadow_web_api.py`
- Acceptance:
  - launch-only Word probe and real export canary are separately represented
  - timeout diagnostics identify the last reached export phase
  - timed-out helper runs are cleaned up only through the app-owned helper tree
  - browser/provider payloads expose `finalization_ready`
  - current browser capability/settings surfaces do not break from the additive contract

## Rollout and fallback
- Rollout: Stage 1 only, then stop and publish the stage packet.
- Fallback: if the canary cannot run, keep the existing launch probe available in diagnostics but mark `finalization_ready` false.

## Risks and mitigations
- Risk: adding helper cleanup could accidentally target user-owned Word sessions.
- Mitigation: only kill the PowerShell helper process tree started by this app run, never arbitrary `WINWORD.EXE` instances by name alone.
- Risk: the new canary could make browser bootstrap too heavy.
- Mitigation: Stage 1 keeps this at the provider/capability layer only; broader caching and UI workflow changes remain Stage 3.
- Risk: additive payload changes could break current browser cards.
- Mitigation: preserve compatibility top-level fields and adjust current consumers in the same stage.

## Assumptions/defaults
- Honorários PDF remains mandatory for Gmail draft creation.
- No non-Word fallback and no DOCX-only Gmail fallback land in this pass.
- A temp honorários-style DOCX can be generated locally for the export canary without mutating user data.

## Stage 1 completion evidence
- Implemented phase-tagged Word helper scripts plus helper-process cleanup for `pdf_preflight` / `export_pdf` timeouts in `src/legalpdf_translate/word_automation.py`.
- Added:
  - additive `WordAutomationResult` fields for `failure_phase`, helper PID, and cleanup provenance
  - a real DOCX-to-PDF export canary with PDF-header verification
  - cached readiness assessment returning `launch_preflight`, `export_canary`, and `finalization_ready`
- Surfaced the additive readiness contract through:
  - `src/legalpdf_translate/power_tools_service.py`
  - `src/legalpdf_translate/browser_app_service.py`
  - `src/legalpdf_translate/shadow_web/app.py`
- Kept browser consumers compatible while shifting summary text away from launch-only readiness in:
  - `src/legalpdf_translate/shadow_web/static/app.js`
  - `src/legalpdf_translate/shadow_web/static/power-tools.js`
- Added focused regressions in:
  - `tests/test_word_automation.py`
  - `tests/test_shadow_runtime_service.py`
  - `tests/test_shadow_web_api.py`
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m py_compile src\\legalpdf_translate\\word_automation.py src\\legalpdf_translate\\power_tools_service.py src\\legalpdf_translate\\browser_app_service.py src\\legalpdf_translate\\shadow_web\\app.py`
  - `node --check src\\legalpdf_translate\\shadow_web\\static\\app.js`
  - `node --check src\\legalpdf_translate\\shadow_web\\static\\power-tools.js`
  - `.\\tmp\\stage3_e2e_venv\\Scripts\\python.exe -m pytest -q tests\\test_word_automation.py`
  - `.\\tmp\\stage3_e2e_venv\\Scripts\\python.exe -m pytest -q tests\\test_shadow_runtime_service.py -k "provider_state or native_host or settings_preflight"`
  - `.\\tmp\\stage3_e2e_venv\\Scripts\\python.exe -m pytest -q tests\\test_shadow_web_api.py -k "word_pdf_export or capabilities"`
- Environment note:
  - the repo `.venv311` can compile code but its `pytest` entry path is still broken because `pygments.lexers._mapping` is missing; Stage 1 validations therefore used the healthy `tmp\\stage3_e2e_venv` runner for pytest evidence.

## Stage 2 completion evidence
- Added a dedicated Gmail finalization preflight route and session-manager method:
  - `POST /api/gmail/batch/finalize-preflight`
  - `GmailBrowserSessionManager.preflight_batch_finalization(...)`
- Preserved batch/session state additively for browser recovery by extending `GmailBatchSession` / serialized payloads with:
  - `finalization_state`
  - `finalization_preflight`
- Updated batch finalization semantics in `src/legalpdf_translate/gmail_browser_service.py`:
  - finalization now hard-blocks early when `finalization_ready` is false
  - post-canary export failures return retryable `local_only` responses with preserved DOCX/session context
  - draft-prereq and draft-creation failures stay retryable and surface additive `finalization_state` / `retry_available`
- Extended diagnostics report generation in:
  - `src/legalpdf_translate/power_tools_service.py`
  - `src/legalpdf_translate/shadow_web/app.py`
  - with additive `gmail_finalization_context` support returning `report_kind = gmail_finalization_report`
- Updated the Gmail batch finalization drawer in:
  - `src/legalpdf_translate/shadow_web/static/gmail.js`
  - `src/legalpdf_translate/shadow_web/templates/index.html`
  - so it now:
    - runs a real Word export preflight before finalization
    - blocks the finalize action when Word export is degraded
    - preserves retryable failure context after `local_only` / `draft_failed`
    - exposes a direct `Generate Finalization Report` action in the drawer
- Added focused regressions in:
  - `tests/test_gmail_browser_service.py`
  - `tests/test_shadow_web_api.py`
- Validation completed:
  - `python -m py_compile src/legalpdf_translate/gmail_batch.py src/legalpdf_translate/gmail_browser_service.py src/legalpdf_translate/power_tools_service.py src/legalpdf_translate/shadow_web/app.py`
  - `node --check src/legalpdf_translate/shadow_web/static/gmail.js`
  - `.\\tmp\\stage3_e2e_venv\\Scripts\\python.exe -m pytest -q tests\\test_gmail_browser_service.py tests\\test_shadow_web_api.py -k "finaliz or word_pdf_export or report"`
- Result:
  - `8 passed, 34 deselected`
- Stage boundary:
  - Stage 3 remains pending for browser/provider diagnostics unification, a dedicated operator-facing Word canary test action, canonical Windows validation-environment repair, and broader regression coverage.

## Stage 3 completion evidence
- Extended the browser/provider Word readiness contract end to end:
  - existing `word_pdf_export` provider payload already carried `launch_preflight`, `export_canary`, `finalization_ready`, `last_checked_at`, and `cache_ttl_seconds`
  - Stage 3 added an operator-facing browser test action for that contract through:
    - `src/legalpdf_translate/power_tools_service.py`
    - `src/legalpdf_translate/shadow_web/app.py`
    - `src/legalpdf_translate/shadow_web/static/power-tools.js`
    - `src/legalpdf_translate/shadow_web/templates/index.html`
- Added deliberate Word canary cache invalidation so stale success state cannot survive:
  - settings/key mutations now clear settings-scoped provider and Gmail-finalization Word readiness caches
  - post-canary finalization export failure now clears both the session-scoped Gmail cache and the provider-state cache
  - implementation landed in:
    - `src/legalpdf_translate/word_automation.py`
    - `src/legalpdf_translate/power_tools_service.py`
    - `src/legalpdf_translate/gmail_browser_service.py`
- Restored two compatibility seams exposed by the broader `.venv311` regression pass:
  - reintroduced a monkeypatchable `run_calibration_audit(...)` wrapper in `src/legalpdf_translate/power_tools_service.py`
  - restored safe page-count reporting on browser upload in `src/legalpdf_translate/translation_service.py` by probing page count when available without making upload fail if counting is unavailable
- Repaired the canonical Windows validation environment in place without network or reinstalls:
  - `.venv311` was missing multiple package files (`typing_extensions`, `click`, `pygments`, `pydantic`, `pydantic_core`, `httpx`, and others)
  - copied only missing files from the already healthy `tmp\\stage3_e2e_venv\\Lib\\site-packages` tree into `.venv311\\Lib\\site-packages`
  - verified import health for:
    - `pytest`
    - `fastapi`
    - `httpx`
    - `openai`
    - `pydantic`
    - `pygments.lexers._mapping`
- Added/extended focused regressions in:
  - `tests/test_word_automation.py`
  - `tests/test_shadow_runtime_service.py`
  - `tests/test_shadow_web_api.py`
  - `tests/test_gmail_browser_service.py`
- Validation completed on the repaired canonical `.venv311` runtime:
  - `.\\.venv311\\Scripts\\python.exe -m py_compile src\\legalpdf_translate\\word_automation.py src\\legalpdf_translate\\power_tools_service.py src\\legalpdf_translate\\gmail_browser_service.py src\\legalpdf_translate\\shadow_web\\app.py src\\legalpdf_translate\\translation_service.py`
  - `node --check src\\legalpdf_translate\\shadow_web\\static\\power-tools.js`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests\\test_word_automation.py tests\\test_shadow_runtime_service.py tests\\test_shadow_web_api.py tests\\test_gmail_browser_service.py -k "word_pdf_export or provider_state or report or finaliz or settings or cache or upload_translation_source or calibration_audit"`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests\\test_gmail_intake.py tests\\test_browser_gmail_bridge.py tests\\test_gmail_focus_host.py`
- Result:
  - `34 passed, 56 deselected`
  - `51 passed`
- Stage boundary:
  - Stage 4 remains pending for non-mutating end-to-end acceptance followed by live Gmail/job-log mutation acceptance on this machine.

## Stage 4 completion evidence
- Re-ran the live path from a true cold state by stopping listeners on `8765` and `8877`, then calling the same native-host browser launch path used by the extension:
  - `legalpdf_translate.gmail_focus_host.prepare_gmail_intake(...)`
  - result: `ok=true`, `launched=true`, `ui_owner=browser_app`, `reason=bridge_owner_ready`
- Verified live shell readiness after relaunch:
  - `GET /api/bootstrap/shell?mode=live&workspace=gmail-intake`
  - shell payload returned `ready=true`, `native_host_ready=true`, `owner_kind=browser_app`, `asset_version=11e36e26471e`
- Re-loaded the real Gmail message into the fresh live workspace:
  - `message_id = 19d0bf7e8dccffc0`
  - `thread_id = 19d0bf7e8dccffc0`
  - account `adel.belghali@gmail.com`
  - exact attachment set confirmed from `/api/gmail/session/current`
- Completed the non-mutating browser-workflow acceptance through the live API/session path using the exact Gmail PDF attachment:
  - selected attachment: `sentença 305.pdf`
  - `POST /api/gmail/prepare-session` succeeded for the fresh session with `page_count=5`
  - launched a real one-page live translation job:
    - `job_id = tx-50d208ec8e36`
    - output dir: `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage4_nonmutating_output`
    - terminal result: `status=completed`, `status_text="Translation complete"`
    - output DOCX: `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage4_nonmutating_output\sentença 305_EN_20260330_214841.docx`
    - run dir: `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage4_nonmutating_output\sentença 305_EN_run`
- Verified the rebuilt Word readiness contract live on this machine before finalization:
  - `POST /api/settings/word-pdf-test?mode=live&workspace=gmail-intake`
  - returned `ok=true`, `finalization_ready=true`, `message="Word PDF export canary passed."`
  - the machine-specific Office recovery path now succeeds by explicitly bootstrapping `WINWORD.EXE /automation` before COM attachment
- Completed the live write-through acceptance on the same session:
  - `POST /api/gmail/batch/confirm-current`
    - saved real job-log row `74`
    - staged translated DOCX into the Gmail batch draft-attachment area
  - `POST /api/gmail/batch/finalize-preflight`
    - returned `status=ok`
    - `finalization_state=ready_to_finalize`
    - `finalization_ready=true`
  - `POST /api/gmail/batch/finalize`
    - returned `status=ok`
    - session advanced to `finalization_state=draft_ready`
    - `draft_created=true`
    - DOCX path: `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage4_nonmutating_output\Requerimento_Honorarios_sem_processo_20260330.docx`
    - PDF path: `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage4_nonmutating_output\Requerimento_Honorarios_sem_processo_20260330.pdf`
- Verified the Gmail draft externally on the real thread using the Gmail connector:
  - draft message id: `19d4082fe77aa864`
  - thread id: `19d0bf7e8dccffc0`
  - label set includes `DRAFT`
  - attachments present on the draft:
    - `Requerimento_Honorarios_sem_processo_20260330.pdf`
    - `sentença 305_EN_20260330_214841.docx`
- Validation notes:
  - the Playwright CLI daemon remained broken in this environment (`Daemon process exited with code 1`), so Stage 4 browser acceptance used the live native-host launch path plus the real browser/session API contract instead of the broken daemon wrapper
  - despite that host limitation, the previously failing live path now ends in a real Gmail draft on this machine instead of `status=local_only`
