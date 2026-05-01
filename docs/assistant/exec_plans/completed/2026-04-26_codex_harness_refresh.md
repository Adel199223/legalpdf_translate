# Codex Harness Refresh

## Goal
Refresh the repo-local agent harness after PR #46 so future Codex and ChatGPT threads can continue from repo docs instead of old chat history.

## Scope
- Update concise agent guardrails.
- Add durable handoff, validation, Gmail live-testing, and PR #46 post-merge summary docs.
- Preserve product behavior, route/API payloads, Gmail/native-host contracts, safe rendering, app data, and runtime metadata.

## Validation
- Run targeted browser/Gmail/profile/Qt delete-key tests.
- Run `scripts/validate_dev.ps1`.
- Run full validation only if non-Markdown code/test/workflow files change.

## Closeout
- Write Downloads summaries, diff, and a small review artifact ZIP.
- Commit docs-only changes and open a draft PR.

## Result
- Created durable handoff, validation, live Gmail testing, and PR #46 post-merge summary docs.
- Updated the root agent shim and README/index pointers.
- No product behavior or runtime contracts changed.
