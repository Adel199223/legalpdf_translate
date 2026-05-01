# Rebuild Cold-Start Reliability for the Gmail-to-Browser Workflow

## Goal
- Restore reliable cold-start from the Gmail extension into the browser app and stop native-host/runtime drift from breaking the front door again.

## Stage 1
- Break the native-host import chain away from OCR/OpenAI startup dependencies.
- Add native-host self-test support and validated runtime selection.
- Make browser and Qt native-host auto-registration prefer the actual running runtime instead of blind worktree venv guessing.
- Add regression coverage for validated runtime selection and current-runtime registration.

## Stage 2
- Add browser diagnostics and repair affordances for native-host health.
- Extend shell/bootstrap payloads with native-host readiness and repair details.

### Stage 2 implementation notes
- Added a native-host inspection payload that reports registry path, manifest path, wrapper target, self-test status, and repairability without mutating registration.
- Added browser settings routes for native-host test and repair, and surfaced native-host state in provider-state/admin payloads.
- Extended shell/bootstrap and capability flags so the browser can expose native-host readiness alongside Gmail handoff readiness.
- Added focused regression coverage for provider-state hydration, shell payloads, and settings route delegation.

## Stage 3
- Validate the full cold-start flow from Gmail click through browser readiness, preview, and one-page translation.

### Stage 3 implementation notes
- Fixed Windows venv runtime identity drift in `gmail_focus_host.py` by preserving the launcher path for runtime selection, worktree discovery, wrapper parsing, and diagnostics instead of collapsing venv `python.exe` paths back to the base interpreter.
- Fixed `_merge_response(...)` so routes that already provide `capability_flags` no longer recompute the full browser capability snapshot eagerly; this removed a large hidden latency penalty from shell/bootstrap and other dynamic routes.
- Made `/api/bootstrap/shell` use lightweight native-host readiness inspection (`run_self_test=False`) instead of the full provider-state build, bringing the extension-facing shell probe back down to a fast readiness check.
- Relaxed post-launch bridge wait handling so transient `bridge_port_owner_mismatch` states during browser-app startup are treated as warmup noise instead of immediate hard failures.
- Added regression coverage for:
  - preserving runtime/worktree identity when `Path.resolve()` would collapse a venv launcher,
  - treating temp/pytest runtimes as unsafe even if resolution points elsewhere,
  - avoiding eager capability recomputation in `_merge_response(...)`,
  - tolerating transient bridge-owner mismatch during the cold-start wait loop.

### Stage 3 validation notes
- True cold-state acceptance passed from the native host:
  - `prepare_gmail_intake(...)` launched the browser app from cold state and returned `ok=true`
  - `GET /api/bootstrap/shell?mode=live&workspace=gmail-intake` returned `200` with `shell.ready=true`
  - live Gmail bridge handoff accepted the real message `19d0bf7e8dccffc0`
  - Gmail workspace loaded the real message with 2 attachments
  - inline preview succeeded for the Gmail attachment route with PDF bytes served from the browser app
  - `POST /api/settings/translation-test` returned `ok`
  - `POST /api/settings/ocr-test` returned `ok`
  - one-page live translation succeeded for `sentença 305.pdf`
- Live translation artifact from acceptance:
  - `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage3_cold_acceptance_output\sentença 305_EN_20260329_161351.docx`
- Focused regression suite after the Stage 3 fixes:
  - `tests/test_gmail_intake.py`
  - `tests/test_gmail_focus_host.py`
  - `tests/test_browser_gmail_bridge.py`
  - `tests/test_shadow_web_api.py`
  - Result: `74 passed`

## Stage 4
- Run live write-through acceptance only after explicit approval because it mutates real Gmail/job-log data.

### Stage 4 implementation notes
- Reused the already cold-started live `gmail-intake` workspace and its completed browser translation job instead of rerunning unnecessary translation work before the live mutation checks.
- Drove the write-through acceptance through the same browser API surfaces the UI uses:
  - `POST /api/translation/save-row`
  - `POST /api/gmail/batch/confirm-current`
  - `POST /api/gmail/batch/finalize`
- Used the translation job's real `save_seed` to populate the browser save form payload so the job-log mutation matched the browser UI's prefilled save flow exactly.
- Confirmed the Gmail batch attachment against the saved job-log row before finalization so the final draft request used the staged translated DOCX produced by the browser batch session.
- Finalized the Gmail batch reply with a real honorários DOCX/PDF export and a real Gmail draft creation on the original thread.

### Stage 4 validation notes
- Live job-log mutation acceptance passed:
  - `job_runs` row count increased from `45` to `46`
  - new live translation row `72` was inserted through `/api/translation/save-row`
  - row `72` retained the expected case metadata, run id `20260329_161351`, and translated DOCX path
- Live Gmail batch progression passed:
  - active session `gmail_batch_0eb05dfb205a` advanced from `prepared` to `confirmed`
  - confirmed item count advanced from `0` to `1`
  - the staged translated attachment for draft finalization was written to:
    - `C:\Users\FA507\AppData\Local\Temp\legalpdf_gmail_batch_50p9vc2k\_draft_attachments\sentença 305_EN_20260329_161351.docx`
- Live Gmail finalization passed:
  - `POST /api/gmail/batch/finalize` returned `status=ok`
  - honorários artifacts were created at:
    - `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage3_cold_acceptance_output\stage4_gmail_batch_acceptance.docx`
    - `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage3_cold_acceptance_output\stage4_gmail_batch_acceptance.pdf`
  - Gmail draft creation returned:
    - `draftId = r8514944552436371417`
    - `message.id = 19d3a3397312dd30`
    - `threadId = 19d0bf7e8dccffc0`
    - `labelIds = ["DRAFT"]`
- External Gmail verification passed on the real thread:
  - thread `19d0bf7e8dccffc0` now contains the draft reply message `19d3a3397312dd30`
  - the draft is addressed to `beja.judicial@tribunais.org.pt`
  - the draft includes:
    - `stage4_gmail_batch_acceptance.pdf`
    - `sentença 305_EN_20260329_161351.docx`

## Continuation tokens
- After Stage 1: `NEXT_STAGE_2`
- After Stage 2: `NEXT_STAGE_3`
- After Stage 3: `NEXT_STAGE_4`
