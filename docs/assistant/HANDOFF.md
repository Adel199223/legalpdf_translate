# LegalPDF Translate Handoff

## Current State
- Canonical repo: `C:\Users\FA507\.codex\legalpdf_translate`.
- Repository: `Adel199223/legalpdf_translate`.
- Canonical branch: `main`.
- Main after PR #49 merge: `24c30fe63d2237657e941d0cfb792e7836c62d03`.
- Primary UI: local browser app on `127.0.0.1`, normally live on port `8877`.
- Secondary UI: Qt/PySide6 shell.
- Development UI review mode: browser `shadow` mode with isolated app data.

PR #46 and the docs harness refresh PR #47 have been squash-merged into `main`. A post-merge setup pass launched the canonical-main live browser runtime and reported both `8877` and `8765` listening. Future live Gmail extension testing must happen from canonical `main`, not from feature branches.

Google Photos Interpretation import is merged and this follow-up closeout adds the accepted Review Details behavior: one selected Google Photos image imports through the Interpretation-only photo/OCR path, service-city evidence stays separate from case-city evidence, court email options are keyed to the case city, photo date can prefill service date only as an editable fallback, and distance is keyed to the effective service city. Google Photos place/location remains unavailable from the Picker API; if any testing credential was exposed during troubleshooting, rotate it before production-like use.

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
