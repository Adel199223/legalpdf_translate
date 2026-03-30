# Stabilize the Web App End to End for Gmail Intake and Translation

## Goal and non-goals
- Goal: make the browser app the reliable operator path for Gmail handoff in live mode by stabilizing runtime readiness, listener provenance, and Gmail workspace warmup behavior before web-side credential recovery and full end-to-end hardening.
- Non-goals for Stage 1:
  - do not add browser-side key save/clear/test flows yet
  - do not redesign Gmail review UX
  - do not change translation runtime behavior beyond the shell/handoff contract needed to stabilize launch/readiness

## Scope (in/out)
- In scope for Stage 1:
  - add `GET /api/bootstrap/shell` as the fast extension-facing readiness route
  - improve runtime metadata truthfulness after the server is actually bound
  - expose bounded Gmail workspace pending/warmup state
  - replace Gmail view auto-refresh loops with bounded warmup polling
- In scope for Stage 2:
  - browser-first credential save/clear/test for translation and OCR
  - browser-side auth recovery copy and provider recovery flows
- Deferred to Stage 3:
  - final extension/browser readiness hardening across the full Gmail workflow
  - acceptance-level end-to-end validation from cold app launch through translation and batch finalization

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical working branch on top of the approved-base floor declared in `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- New route: `GET /api/bootstrap/shell`
- Additive Gmail bootstrap fields:
  - `pending_status`
  - `pending_intake_context`
  - `pending_review_open`
- Runtime metadata refresh semantics for `shadow_runtime.json`
- Gmail browser UI refresh policy changes from open-ended focus refresh to bounded warmup polling

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_browser_service.py`
  - track pending Gmail intake/warmup state per workspace
  - surface additive pending fields in `build_bootstrap`
- `src/legalpdf_translate/shadow_web/app.py`
  - add minimal `/api/bootstrap/shell`
  - refresh persisted runtime metadata when listener ownership changes materially
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - replace aggressive focus/visibility refresh behavior with bounded polling keyed to warmup state
- `tests/test_gmail_browser_service.py`
  - cover pending warmup state and cleanup behavior
- `tests/test_shadow_web_api.py`
  - cover `/api/bootstrap/shell`
  - cover runtime metadata refresh behavior

## Tests and acceptance criteria
- `GET /api/bootstrap/shell` returns a fast readiness payload with listener ownership, Gmail bridge sync state, and Gmail workspace readiness state
- Gmail bootstrap exposes pending warmup state while a bridge intake is in flight
- Live runtime metadata is rewritten after bind so listener ownership reflects the actual browser server process
- Gmail UI no longer needs focus/visibility-driven endless refreshes after a stable load

## Rollout and fallback
- Stage 1 stops at the runtime/handoff stabilization boundary
- Stage 2 adds browser-side credential recovery instead of relying on Qt/CLI
- Stage 3 will harden the full cold-start Gmail flow and validate end to end on Windows

## Stage 2 implementation notes
- Added secure browser routes for translation-key and OCR-key save/clear plus safe provider-state refresh payloads.
- Translation auth recovery is now browser-first in the web UI copy and diagnostics.
- OpenAI-backed OCR now recognizes a stored OpenAI translation key as a fallback credential source when no dedicated OCR key is stored.
- Browser-safe provider metadata now distinguishes:
  - translation stored key configured vs effective source
  - OCR stored key configured vs translation-key fallback availability
  - OCR effective source including `openai_api_key_fallback`

## Stage 3 implementation notes
- Hardened the browser-owned Gmail handoff path with single-flight launch semantics:
  - native host reports `launch_in_progress` instead of triggering repeated browser-open attempts
  - browser-owned handoffs now include `browser_open_owned_by=extension`
  - extension-side settle logic no longer creates a second browser window/tab while the same handoff is warming
- Made live Gmail intake idempotent for exact-message replays:
  - duplicate bridge posts for the same exact Gmail message now reuse the current workspace state
  - `review_event_id` and `message_signature` remain stable across duplicate same-message handoffs
  - stable loaded workspaces no longer restart passive Gmail refresh loops on focus/visibility churn
- Fixed browser-side provider recovery so the live app can actually run with credentials already present on this machine:
  - translation auth preflight now uses a valid OpenAI probe (`max_output_tokens=16`)
  - OCR provider test now uses the same valid probe budget and no longer crashes with a 500 on the browser route
  - translation now falls back to the stored OpenAI OCR credential when no dedicated translation key is stored
  - browser provider state/UI now surfaces that fallback as `ocr_api_key_fallback`
- Live runtime verification on the restarted `127.0.0.1:8877` server:
  - `/api/bootstrap/shell` returns `200` with `shell.ready=true`, `owner_kind=browser_app`, and `browser_open_owned_by=extension`
  - `/api/settings/translation-test` returns `ok` via `credential_source={"kind":"stored","name":"ocr_api_key_fallback"}`
  - `/api/settings/ocr-test` returns `ok` via the stored OCR key instead of crashing
  - a real one-page translation run completed successfully in live mode from the previously failing Gmail PDF source path
  - duplicate live Gmail bridge handoffs for message `19d0bf7e8dccffc0` remained stable with unchanged `review_event_id` and `message_signature`
- Known local validation constraint:
  - the Dart-based browser automation preflight on this machine is currently broken (`Unable to find AOT snapshot for dartdev`), so browser automation provenance remained in the existing `preferred_host_status=unavailable` state during this pass

## Risks and mitigations
- Risk: a lightweight shell route accidentally triggers heavy bootstrap work
  - Mitigation: build the shell payload directly and pass explicit `capability_flags`
- Risk: pending warmup state could get stuck
  - Mitigation: clear pending fields on success, reset, and unexpected failure paths
- Risk: Gmail UI polling could still loop
  - Mitigation: bound polling by status and timeout, and stop on stable loaded/failed/idle states

## Assumptions/defaults
- The current environment key for OpenAI remains unauthorized and will be addressed in Stage 2 via browser credential recovery
- The browser app is the primary live operator surface
- Stage-gate continuation tokens are required:
  - after Stage 1: `NEXT_STAGE_2`
  - after Stage 2: `NEXT_STAGE_3`
