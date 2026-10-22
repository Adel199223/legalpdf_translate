# Bounded multiple-image Responses client input

## Goal and non-goals
Add an explicitly selected, bounded sequence of source images to the existing Responses client. Preserve omitted/None and single-image requests exactly. This prerequisite does not implement semantic audit prompts, workflow changes, checkpoint changes or live provider acceptance.

## Scope
Only `openai_client.py`, focused offline client tests and this plan. No credentials, provider/network/native calls, package changes, app data, publication or commits.

## Worktree provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/semantic-audit-engine/legalpdf_translate`
- Branch: `feat/semantic-audit-engine-20261020`
- Base/integration branch: canonical `main`
- Base SHA and current approved task floor: `9b0ffe97` (repository floor `4e9d20e` retained)
- Noncanonical implementation checkout; no app runtime launched.

## Interfaces/types/contracts affected
Add optional `image_data_urls: list[str] | tuple[str, ...] | None` to `prepare_page_request`, `create_page_response` and `_build_page_request`. Explicit plural input accepts 1-12 base64 image data URLs and forbids simultaneous single-image input. All images use the existing `image_detail` argument. Existing response schema validation, refusal/incomplete checks, accounting and retry policies remain unchanged. The 12-image ceiling is a local application bound, not a claimed provider limit.

## File-by-file implementation
1. `src/legalpdf_translate/openai_client.py`: validate explicit plural input before dispatch and build ordered image parts through the existing request builder and accounted transport. Keep legacy branch selected when the new option is omitted or None.
2. `tests/test_openai_multi_image.py`: verify ordered payloads, invalid-input refusal, exact legacy compatibility, accounting image-count/reservation behavior and existing response/retry safety using injected offline transports only.
3. This plan: record exact targeted validation and pending root integration checks.

## Tests and acceptance criteria
Run canonical `.venv311/Scripts/python.exe` against this worktree's tests/src. Require all focused new and existing structured/legacy/accounting tests to pass. Root owns combined Standard/Full validation before integration; no independent paid or native acceptance follows.

## Rollout and fallback
Return an uncommitted patch for root review/integration. No canonical source changes or application restart. Explicit plural input uses the existing bounded path; legacy callers retain their previous path and request shape.

## Risks and mitigations
Reject generators, strings, empty/over-limit sequences, remote URLs, malformed/non-image data URLs and mixed single/plural inputs before accounting/provider dispatch. Retain accounting envelope image counts and hashed request identity for every ordered image. Do not add a direct SDK alternate.

## Assumptions/defaults
Source-page image preparation and audit policy are separate root-owned work. Reference translations must never enter provider prompts. Installed locked SDK input types support image parts with base64 data URLs; this task makes no new model/capability/pricing claim and performs no external source refresh.

## Progress
- Managed worktree created and exact base `9b0ffe97a852233ac3e6e31260f335dbde75d61d` verified.
- Implemented the additive three-entry-point option and explicit plural validation; the legacy method and existing accounting/response/retry implementations are unchanged.
- Focused tests passed 128 cases in 3.63 seconds: new multiple-image cases, structured transport, legacy transport retries, dispatch accounting and locked SDK offline serialization.
- A direct standalone interpreter import exposed the canonical editable-install path; pytest's worktree conftest inserts its own `src`, and new-argument tests already exercised the patch. An explicit worktree-source import assertion plus the same 128-case suite passed again in 2.03 seconds. That in-process invocation emitted one benign anyio assertion-rewrite warning. These repeated checks are not additive coverage.
- `git diff --check` passed. No provider/network/native calls or dependency changes occurred. Root owns patch review, combined Standard/Full, integration and wider semantic-audit acceptance; this child remains active until that disposition.


## 2026-10-21 final scoped lifecycle disposition

Disposition: **Completed bounded implementation scope**. The bounded additive multiple-image client transport is implemented; legacy single-image calls and request/accounting contracts remain preserved.

ROOT's bounded benchmark parent is complete. See the [own completed parent](2026-10-20_autonomous_draft_parity.md). ROOT's final integration gate is Full24, finished 2026-10-21 at 21:26:08 UTC and reaped with exit 0, with all 798 protected files exact in both trees at runtime `c3282f4e642fae948efdb512c2c540ebcd6a4ccd7b27b3273d244a60281b6c92` and no Full-owned process remaining. Terminal receipt SHA `3b6aafe656a6a1c44a01de5af73ebb0041a4af38b713c47e3e1e5c382e9b91a1` and ROOT closure SHA `2426d383ca23827734d90c145b44a87ac1c8f2ad4cab7182f20863162a1af0a9` bind that selected Full wrapper result; it is not a claim of the entire repository pytest collection and overlapping selections are not summed. The known Dart AOT wrapper issue was followed by successful direct-Dart docs/hygiene fallback.

All three bound benchmark outputs are accepted after causal product repairs and ordinary retained-response recovery; NOTICE acceptance SHA `e26ad64fde683c637b397dc7f3a2e5cacbc4532072540f5e49ac1c08ad7fe715` binds its final source/reference/native evidence. Earlier failed attempts and failed/superseded Full runs remain unchanged. This records the child implementation and final parent gate without rewriting the earlier author checkpoints or claiming fresh first-pass/unattended repeatability. Product `automatic_unreviewed`, historical unknown costs and separate Save/Gmail/publication/installation boundaries remain.
