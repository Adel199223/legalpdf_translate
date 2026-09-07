# LegalPDF Translate Handoff

## Current State
- Canonical repo: `C:\Users\FA507\.codex\legalpdf_translate`.
- Repository: `Adel199223/legalpdf_translate`.
- Canonical branch: `main`.
- Current product-modernization baseline: `c3ec60e57852af4ff69ba96cd0410c489a25ba69` after PR #226, `[codex] Extract Gmail prepare action presentation`.
- This historical modernization baseline is not the current head; use `git rev-parse HEAD` in the canonical repo and inspect the latest merged PR checks for current repository state.
- Primary UI: local browser app on `127.0.0.1`, normally live on port `8877`.
- Secondary UI: Qt/PySide6 shell.
- Development UI review mode: browser `shadow` mode with isolated app data.
- Formatting integration starts from `main@022b5afb54b9be0b2eba1f2c19d617ed46a10891`. Keep unfinished research in the clean local-only quality worktree at checkpoint `66a7374a2b874f59994215177af4ff48d1d5f100`; do not delete, merge or publish that combined research branch wholesale. Unrelated dependency-update PRs are outside this rollout.

## Approved Formatting Integration

The formatting-only release preserves compact editable Word output, coherent Arabic/Latin runs, real page fields, and section-specific headers/footers and source gaps when complete matching block evidence exists. Private Arabic/French rebuilds match every uncompressed DOCX package entry in the user-approved five-page/one-page Word proofs; evidence and private documents remain outside Git.

Current production requests still return TXT, so new runs gain typography/RTL/page-number defaults, not fabricated source-aware associations. Exact regions and section furniture require retained validated source/target sidecars; missing evidence remains a manual-layout-review item. Saved text, historical usage and semantic findings survive local rebuilds. No provider call is required for formatting-only rebuilds.

Translation prompts/models/efforts, OCR routing, browser/Gmail contracts and honorarios export behavior are unchanged. Terra/Sol policy promotion, complete structured production extraction/translation and unattended honorarios PDF reliability remain separate unfinished work, not accepted by this layout rollout. Translations remain DOCX.

See `docs/assistant/exec_plans/completed/2026-09-07_approved_formatting_integration.md` for validation and rollout conditions; verify the merged PR and actual canonical head rather than assuming the old modernization baseline is current.

The recent browser modernization line has been merged through PR #226. The static browser frontend is now split across focused UI/presentation modules while `app.js`, `gmail.js`, `translation.js`, and `power-tools.js` remain coordinator modules for state, API calls, routing, and side effects. This preserved the existing FastAPI/static app, route IDs, payload shapes, selectors, Gmail/native-host contracts, CLI, and PySide6 entry points.

Recent validation baseline after PR #226:
- focused Gmail prepare-action presentation/static coverage
- browser safe-rendering probe
- broad shadow-web, route-state, and translation-browser regression group
- `scripts\validate_dev.ps1 -Full`, with the known Dart wrapper AOT issue accepted only because the direct Dart fallback passed
- light shadow-mode browser smoke on `main@c3ec60e` for Dashboard, New Job, Extension Lab, and Gmail intake, without opening live Gmail/OAuth/native-host flows

## What The App Does
LegalPDF Translate is a Windows-first legal PDF translation and Gmail intake app. It translates PDFs page by page into DOCX, preserves run artifacts, supports browser and Qt workflows, records translation and interpretation work in the Job Log, and can continue from a real Gmail message through a browser extension/native-host bridge.

Important invariant: do not convert the translation workflow into one whole-document model request. Page-by-page processing, safe rendering, and Gmail/native-host contracts are core product guarantees.

## Fresh-Thread Starting Points
- App architecture and status: `APP_KNOWLEDGE.md`.
- Agent runbook: `agent.md`.
- Quick guardrails: `AGENTS.md`.
- Validation commands: `docs/assistant/VALIDATION.md`.
- Google Photos Interpretation runbook: `docs/assistant/features/GOOGLE_PHOTOS_INTERPRETATION_RUNBOOK.md`.
- Live Gmail retest guide: `docs/assistant/GMAIL_LIVE_TESTING.md`.
- PR #46 historical summary: `docs/assistant/PR46_POST_MERGE_SUMMARY.md`.
- Routing map: `docs/assistant/manifest.json`.
- Roadmap resume anchor: `docs/assistant/SESSION_RESUME.md`.

## Current Next Step
Start from clean canonical `main`. For translation-quality continuation, first inspect the preserved quality checkpoint and its ExecPlan, then isolate the next approved scope; do not reintroduce mixed research changes by merging that branch. The next consequential gap is source-associated structure in new production runs, followed by evidence-gated model evaluation/promotion and the separately deferred honorarios PDF issue. Preserve the original lifetime benchmark allowance; formatting integration adds no paid calls. Unrelated modernization remains normal small-PR work.

For live Gmail checks, use canonical `main` only:
1. Keep the primary worktree on `main`.
2. Confirm the canonical live browser runtime is running.
3. Confirm `127.0.0.1:8877` and `127.0.0.1:8765` are listening.
4. Have the user open a real Gmail email with an attachment.
5. Have the user click the LegalPDF extension once.
6. Verify attachment review opens and the live path shows the current Gmail Review/Preview polish.

Codex must not click the Gmail extension or operate the user's live Gmail mailbox unless the user explicitly asks and the task allows it.

For feature-branch Review/Preview UI checks, use `mode=shadow` and the shadow-only `Load demo attachments` affordance in the Gmail intake workspace. The demo seeds one safe PDF attachment, opens Review Attachments, and lets reviewers verify that Review/Preview drawers persist on outside click and restore without resetting the selected attachment, start page, or preview page.

## Known Caveats
- Do not switch branches in `C:\Users\FA507\.codex\legalpdf_translate` while a LegalPDF server launched from that worktree is running. Use a separate worktree for edits.
- Live Gmail extension intake requires canonical `main` at the primary repo path. Feature branches should use `mode=shadow` for browser UI review; the shadow Gmail demo fixture is safe for Review/Preview drawer testing.
- The Dart launcher can fail locally with `Unable to find AOT snapshot for dartdev`; when `scripts/validate_dev.ps1` detects this, the direct Dart fallback at `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe` is the expected path.
- Generated DOCX/PDF files must be manually reviewed before any Gmail draft is sent.
- The Google Photos validation intentionally did not generate the final honorários DOCX/PDF. Treat Google Photos `createTime` and downloaded EXIF dates as photo-date provenance only: OCR/legal text wins, and photo date is just an editable fallback when OCR has no service date. Do not claim Google Photos place/location or EXIF GPS support from the current validation.
- Numeric mismatch warnings are serious in legal workflows; do not suppress or soften them without a focused safety review.
- Do not print secrets, tokens, `.env` values, private app data, or live Gmail content in reports.

## High-Value Roadmap
- Keep canonical-main live Gmail retests focused on handoff/readiness, with screenshots or notes only from safe user-approved surfaces.
- Keep hardening Gmail failure recovery with narrow tests around bridge ownership, stale runtime metadata, and exact-message handoff.
- Continue browser-first beginner workflow polish only when it preserves route IDs, DOM IDs, payload shapes, and safe rendering.
- Expand deterministic screenshot/probe coverage for high-risk browser states that are hard to reproduce manually.
- Keep Qt Job Log and browser Recent Work behavior aligned so saved legal work remains easy to audit.
