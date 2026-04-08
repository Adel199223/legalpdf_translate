# Single-Path Canonical Recovery for Gmail Runtime and Translation

## Goal
- Make `C:\Users\FA507\.codex\legalpdf_translate` on `main` the only live Gmail/browser runtime target.
- Port the validated Gmail/browser/runtime/translation fixes from `C:\Users\FA507\.codex\legalpdf_translate_canonical_stage1`.
- Eliminate runtime drift back to the forensic worktree and ensure fresh Gmail starts cannot inherit stale resume/checkpoint settings.

## Stage gates
1. Stage 1: converge the primary repo onto a fresh integration branch and port the validated fix set into this repo.
2. Stage 2: break the native-host drift loop and repoint all machine entrypoints to this repo only.
3. Stage 3: hard-block noncanonical live Gmail and make canonical restart authoritative.
4. Stage 4: force deterministic fresh Gmail starts and isolate Gmail-scoped checkpoints.
5. Stage 5: validate the real Gmail click path end to end, including point 10 recovery and Gmail-scoped artifacts.

## Safety notes
- Preserve the pre-port dirty state as a forensic patch before overwriting files.
- Do not reset or discard the prior worktree state; keep it available for rollback comparison.
- Stop after each stage and publish a stage packet with exact continuation token format.

## Acceptance highlights
- Live listener on `8877/8765` reports `main` from `C:\Users\FA507\.codex\legalpdf_translate`.
- Gmail native-host wrapper and loaded extension stay pinned to this repo.
- Fresh Gmail `Auto.pdf` runs use `resume=false`, `keep_intermediates=true`, Gmail-scoped run dirs, and no stale `Auto_FR_run`.
- Page 4 uses recovery and final French point 10 includes `498,03 €`.

## Execution log

### Stage 1 completed
- Saved the pre-port dirty state to `docs/assistant/forensic_snapshots/2026-04-08_pre_single_path_canonical_recovery.patch`.
- Ported the validated Gmail/browser/runtime/translation fixes from `C:\Users\FA507\.codex\legalpdf_translate_canonical_stage1` into the primary repo.
- Updated `docs/assistant/runtime/CANONICAL_BUILD.json` so the primary repo declares itself as the canonical worktree with `allow_noncanonical_by_flag = false`.
- Validation: focused regression slice passed with `231 passed`.

### Stage 2 completed
- Added a native-host registration guard in `src/legalpdf_translate/gmail_focus_host.py` so noncanonical runtimes do not rewrite AppData native-host wrapper or manifest state to themselves.
- Added Stage 2 regression coverage in `tests/test_gmail_focus_host.py` for `canonical_restart_required` registration and inspection behavior.
- Moved the porting worktree off `main`, switched the primary repo to `main`, and regenerated the real machine entrypoints from this repo:
  - `C:\Users\FA507\Desktop\LegalPDF Browser App (Live).cmd`
  - `%APPDATA%\LegalPDFTranslate\native_messaging\LegalPDFGmailFocusHost.cmd`
  - `%APPDATA%\LegalPDFTranslate\native_messaging\com.legalpdf.gmail_focus.edge.json`
  - loaded Edge Gmail intake extension copy
- Restarted the live browser listener from the primary repo. Verified `GET /api/runtime/ready?mode=live&workspace=gmail-intake` reports `branch = main`, `is_canonical = true`, and worktree `C:\Users\FA507\.codex\legalpdf_translate`.
- Validation: Stage 2 targeted slice passed with `99 passed`.

### Stage 3 completed
- Added a noncanonical live-Gmail bridge guard in `src/legalpdf_translate/browser_gmail_bridge.py` so a noncanonical listener does not auto-register the native host, start the Gmail bridge, or present itself as bridge-ready.
- Added a backend noncanonical live-Gmail block in `src/legalpdf_translate/shadow_web/app.py` for preview and prepare operations, and made shell bridge snapshots report `canonical_restart_required` instead of a healthy handoff state when the live runtime is noncanonical.
- Added the new prepare-reason catalog entry in `src/legalpdf_translate/gmail_browser_service.py` for canonical-restart-required live Gmail blocking.
- Expanded regression coverage in:
  - `tests/test_browser_gmail_bridge.py`
  - `tests/test_shadow_web_api.py`
- Validation: Stage 3 targeted slice passed with `99 passed`.
- Restarted the live listener so localhost serves the Stage 3 code. Verified:
  - `GET /api/runtime/ready?mode=live&workspace=gmail-intake` reports `branch = main`, `is_canonical = true`, and worktree `C:\Users\FA507\.codex\legalpdf_translate`
  - ports `8877` and `8765` are owned by the fresh listener PID
  - served Gmail HTML includes `gmail-restart-canonical-runtime`
  - served Gmail HTML does not include any `gmail-continue-noncanonical-runtime` override path

### Stage 4 completed
- Patched `src/legalpdf_translate/shadow_web/static/translation.js` so a fresh Gmail prepare replaces stale terminal workspace job bindings before seeding the new prepared launch, instead of leaving `New Job` stuck on the prior failed/completed run.
- Reused the same workspace-reset path for Gmail redo and fresh Gmail prepare so `currentJob`, `currentJobId`, save-row binding, completion drawer state, and stale upload state are cleared consistently before the prepared attachment is rendered.
- Expanded browser-state regression coverage in `tests/test_translation_browser_state.py` to prove:
  - a stale failed Gmail job is present before prepare
  - a fresh Gmail prepare clears that stale job binding
  - the prepared Gmail card becomes visible again with the new attachment scope
- Revalidated the server-side fresh Gmail defaults and Gmail-scoped checkpoint isolation remain intact with:
  - `tests/test_translation_service_gmail_context.py`
  - `tests/test_output_handling.py`
  - `tests/test_checkpoint_resume.py`
  - `tests/test_gmail_review_state.py`
  - focused `tests/test_gmail_intake.py` prepared/browser workspace slice
- Validation:
  - `tests/test_translation_browser_state.py`: `1 passed`
  - `tests/test_translation_service_gmail_context.py tests/test_output_handling.py tests/test_checkpoint_resume.py`: `21 passed`
  - `tests/test_gmail_review_state.py`: `1 passed`
  - `tests/test_gmail_intake.py -k "browser_workspace or background or prepare"`: `1 passed`
- Restarted the live listener from the primary repo after the Stage 4 patch. Verified `GET /api/runtime/ready?mode=live&workspace=gmail-intake` reports:
  - worktree `C:\Users\FA507\.codex\legalpdf_translate`
  - branch `main`
  - `is_canonical = true`
  - listener PID `28444`
  - `asset_version = 4510699b7b21`

### Stage 5 completed
- Ran the browser-automation environment provenance workflow and confirmed local Playwright/Edge automation was available via `dart tooling/automation_preflight.dart`.
- Forced a true cold start by shutting down the live listener, verifying ports `8877` and `8765` were clear, then invoking the real native-host/browser handoff path through `legalpdf_translate.gmail_focus_host.prepare_gmail_intake(request_focus=True, include_token=True)`.
- Posted the actual Gmail thread/message `19d0080b090c41af` into the live Gmail bridge on port `8765` and verified the canonical listener on `main` accepted the intake session for `Auto.pdf`.
- Used a headed CLI Playwright session against `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake` to exercise the real UI flow:
  - selected `Auto.pdf`
  - selected target language `FR`
  - clicked `Prepare selected`
  - verified `New Job` shows the prepared Gmail attachment instead of the stale failed-job state
  - verified prepared settings show `Images: auto`, `OCR: auto / local_then_api`, `Resume: off`, and `Keep intermediates: on`
  - clicked `Start Translate`
- Verified the actual live translation job `tx-f0bbc6987c74` started with the fresh Gmail config:
  - `resume = false`
  - `keep_intermediates = true`
  - `image_mode = auto`
  - `ocr_mode = auto`
  - `ocr_engine = local_then_api`
- Polled the live job to completion and generated the run report. Final artifacts:
  - DOCX: `C:\Users\FA507\Downloads\Auto_FR_20260408_133410.docx`
  - Gmail-scoped run dir: `C:\Users\FA507\Downloads\Auto_FR_gmail_a7b429ee1468_p1_e489e566e90a_run`
  - `run_summary.json`, `run_state.json`, `run_events.jsonl`, and `run_report.md` all align on run id `20260408_133410`
- Verified page 4 used the recovery path in `run_state.json`:
  - `source_route = ocr`
  - `source_route_reason = visual_recovery_crop_merged`
  - `ocr_request_reason = required`
  - `extraction_integrity_suspect = true`
  - `vector_gap_count = 38`
  - `visual_recovery_used = true`
- Verified the final DOCX contains point 10 with `498,03 €`:
  - `10. La dernière rémunération enregistrée s’élève à 498,03 € (quatre cent quatre-vingt-dix-huit euros et trois centimes).`
- Final live runtime proof after acceptance:
  - worktree `C:\Users\FA507\.codex\legalpdf_translate`
  - branch `main`
  - `is_canonical = true`
  - listener PID `45044`
  - `asset_version = 4510699b7b21`
