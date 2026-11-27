# ExecPlan: Adapt `legalpdf_translate` Workspace for Antigravity

## 1. Title
Adapt `legalpdf_translate` governance docs, capability inventories, workspace skills, and dev validation trigger for Antigravity.

## 2. Goal and non-goals
- **Goal**: Make the `legalpdf_translate` repository cleanly adapted for day-to-day engineering, validation, browser UI review (`mode=shadow`), Word/DOCX visual review, and safe Git lifecycle work inside Antigravity while preserving all existing validator contracts, application runtime behavior, and Codex compatibility where validators require it.
- **Non-goals**:
  - Do not modify `src/` (including frozen `codex_ai_test_review` schema in `src/legalpdf_translate/acceptance_review.py`), `extensions/`, `docs/assistant/HANDOFF.md`, `docs/assistant/runtime/CANONICAL_BUILD.json`, `docs/assistant/templates/*`, `.gitignore`, or `.vscode/settings.json`.
  - Do not modify files outside this workspace (leave `~/.gemini/config/plugins/migrated-settings/` untouched).
  - Do not create a duplicate `GEMINI.md` (Antigravity auto-loads root `AGENTS.md`).
  - Do not create `.agents/hooks.json` (intentional decision to avoid synchronous Windows `cmd /c` hook overhead on every tool call; deterministic validation is provided via `.agents/skills/` and `scripts/validate_dev.ps1`).
  - Do not relocate `C:/Users/FA507/.codex/legalpdf_translate`, commit/push, run live Gmail/Word/OpenAI paid operations, or alter preexisting uncommitted files (`docs/assistant/CACHE_COMPATIBILITY_ASSESSMENT.md`, `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`, `.codex-remote-attachments/`).

## 3. Scope (in/out)
- **In scope**:
  - Preserve exact pre-edit beforeimages and SHA256 manifest in `docs/assistant/history/2026-11-26_antigravity_adaptation_before/`.
  - Update `AGENTS.md`, `agent.md`, `README.md`, `CLAUDE.md`, `docs/assistant/LOCAL_CAPABILITIES.md`, `docs/assistant/CODEX_ENVIRONMENT.md`, `docs/assistant/GMAIL_LIVE_TESTING.md`, and `docs/assistant/INDEX.md`.
  - Add 4 lightweight Antigravity workspace skills under `.agents/skills/`:
    - `.agents/skills/legalpdf-validate/SKILL.md`
    - `.agents/skills/legalpdf-browser-review/SKILL.md`
    - `.agents/skills/legalpdf-word-review/SKILL.md`
    - `.agents/skills/legalpdf-commit-publish/SKILL.md`
  - Update `Test-DocsValidationTriggered` in `scripts/validate_dev.ps1` to also trigger docs validation for `AGENTS.md`, `agent.md`, and `.agents/*`.
  - Add offline regression test `tests/tooling/test_antigravity_workspace_config.py`.
- **Out of scope**:
  - Any product source code, extension, build launcher, schema, or live service state changes.
  - Any commit, PR, merge, push, or remote action (remains gated on explicit user approval).

## 4. Worktree provenance
- **Worktree path**: `C:/Users/FA507/.codex/legalpdf_translate`
- **Branch name**: `main`
- **Base branch**: `main`
- **Base SHA**: `d5e6d6ff8c89fc89d1ed9cb8c244131c6b53937a` (contains `approved_base_head_floor` `4e9d20e` from `docs/assistant/runtime/CANONICAL_BUILD.json`)
- **Target integration branch**: `main`
- **Canonical build status or intended noncanonical override**: Canonical runnable build on `main`; edits remain local working-tree updates scoped to workspace docs, `.agents/skills/`, `scripts/validate_dev.ps1`, and `tests/tooling/test_antigravity_workspace_config.py` without changing product code or running servers.
- **Note on lifecycle rules**: Per `docs/assistant/exec_plans/PLANS.md`, bare `commit` means full pending-tree triage plus logical grouped commits, and bare `push` means Push+PR+Merge+Cleanup; any narrower commit/push override must be recorded explicitly. This task performs local edits only and makes no commit or push. Working directly on `main` here is an explicit user-authorized local adaptation scope rather than a multi-file `src/` product feature branch, and acceptance does not auto-publish.

## 5. Interfaces/types/contracts affected
- Preserve all `tooling/validate_agent_docs.dart` and `tooling/validate_workspace_hygiene.dart` contracts, including required markers in `AGENTS.md`, `agent.md`, `README.md`, `docs/assistant/LOCAL_CAPABILITIES.md`, and retention of `docs/assistant/CODEX_ENVIRONMENT.md`.
- Preserve `AGENTS.md` size strictly under Antigravity's 24,000-byte per-file rule cap.
- Conform `.agents/skills/<name>/SKILL.md` frontmatter (`name` matching folder name, non-empty `description`) to Antigravity's customization specification.
- Extend `Test-DocsValidationTriggered` in `scripts/validate_dev.ps1` to cover `.agents/`, `AGENTS.md`, and `agent.md`.

## 6. File-by-file implementation steps
1. Capture baseline SHA256 hashes of preexisting modified docs and copy exact pre-edit beforeimages into `docs/assistant/history/2026-11-26_antigravity_adaptation_before/`.
2. Edit `AGENTS.md` and `agent.md` to generalize coding-agent references to Antigravity + other agents, add explicit guardrails against unauthorized use of Antigravity's `gmail` plugin or `browser` subagent/Playwright/Chrome DevTools against live Gmail, align tool/model routing with Antigravity, and preserve all AD020/AD026/AD037/AD038/AD039/AD045/AD046 markers.
3. Update `docs/assistant/GMAIL_LIVE_TESTING.md`, `docs/assistant/LOCAL_CAPABILITIES.md`, `docs/assistant/CODEX_ENVIRONMENT.md`, `README.md`, `docs/assistant/INDEX.md`, and prepend a non-destructive legacy notice to `CLAUDE.md`.
4. Create `.agents/skills/{legalpdf-validate,legalpdf-browser-review,legalpdf-word-review,legalpdf-commit-publish}/SKILL.md` wrapping canonical workflows without duplicating them.
5. Update `scripts/validate_dev.ps1` (`Test-DocsValidationTriggered`) and add `tests/tooling/test_antigravity_workspace_config.py`.
6. Run Dart validators, Dart validator tests, Python tooling tests, `scripts/validate_dev.ps1 -Quick`, and `scripts/check_dev_workstation.ps1 -ConfigurationOnly`; close and archive this ExecPlan to `docs/assistant/exec_plans/completed/`, then re-verify affected checks and protected hashes.

## 7. Tests and acceptance criteria
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` exits 0 (`PASS`).
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart --scope localization` exits 0 (`PASS`).
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/validate_agent_docs_test.dart` exits 0.
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` exits 0 (`PASS`).
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/validate_workspace_hygiene_test.dart` exits 0.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/tooling/test_harness_tools.py tests/tooling/test_antigravity_workspace_config.py` exits 0.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick` exits 0 and runs docs validation automatically on the modified working tree.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1 -ConfigurationOnly` exits 0.
- Protected preexisting dirty docs retain identical SHA256 hashes before and after execution.

## 8. Rollout and fallback
- Reversible purely via git working-tree restore or restoring exact beforeimages from `docs/assistant/history/2026-11-26_antigravity_adaptation_before/`.
- If any `validate_agent_docs.dart` rule rejects an edit, inspect the failing `AD*` rule ID and restore the required marker without relaxing validator assertions.

## 9. Risks and mitigations
- **Validator regressions** (`AD020`, `AD037`, `AD038`, `AD039`, `AD043`, `AD045`, `AD046`): Mitigated by preserving all checked markers verbatim and re-running full Dart validators + Dart unit tests.
- **`AGENTS.md` size bloat**: Mitigated by keeping `AGENTS.md` well under 24,000 bytes and offloading task runbooks to `.agents/skills/`.
- **Live-state or preexisting edit contamination**: Mitigated by zero live Gmail/Word/API launches and SHA256 before/after verification of protected dirty files.

## 10. Assumptions/defaults
- Antigravity discovers root `AGENTS.md` and `.agents/skills/*/SKILL.md` natively in this workspace.
- Windows PowerShell 5.1, `.venv311\Scripts\python.exe` (3.11.9), and direct Dart executable (`C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe`) are available on this host.
- Standing Docs Sync authorization (2026-09-16) and explicit user approval in this session cover the doc, skill, validation script, and test updates.

## 11. Completion & Validation Outcomes (2026-11-26)
- **Status**: Complete (two scoped local commits recorded on `main`, atop `d5e6d6ff8c89fc89d1ed9cb8c244131c6b53937a`; unpushed to `origin/main` pending explicit remote-publication approval).
- **Files created**:
  - `.agents/skills/legalpdf-validate/SKILL.md`
  - `.agents/skills/legalpdf-browser-review/SKILL.md`
  - `.agents/skills/legalpdf-word-review/SKILL.md`
  - `.agents/skills/legalpdf-commit-publish/SKILL.md`
  - `tests/tooling/test_antigravity_workspace_config.py`
  - `docs/assistant/history/2026-11-26_antigravity_adaptation_before/` (8 pre-edit snapshots + `manifest.json`)
  - This completed ExecPlan archived under `docs/assistant/exec_plans/completed/2026-11-26_antigravity_adaptation.md`
- **Files updated**:
  - `AGENTS.md` (9,233 bytes, strictly under Antigravity's 24,000-byte cap)
  - `agent.md`
  - `README.md`
  - `CLAUDE.md` (prepended legacy/superseded notice; original text retained)
  - `docs/assistant/LOCAL_CAPABILITIES.md`
  - `docs/assistant/CODEX_ENVIRONMENT.md`
  - `docs/assistant/GMAIL_LIVE_TESTING.md`
  - `docs/assistant/INDEX.md`
  - `scripts/validate_dev.ps1` (`Test-DocsValidationTriggered`)
- **Validation executed**:
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> `PASS: agent docs validation succeeded.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart --scope localization` -> `PASS (localization scope): agent docs validation succeeded.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/validate_agent_docs_test.dart` -> `All agent docs validator tests passed.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> `PASS: workspace hygiene validation succeeded.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/validate_workspace_hygiene_test.dart` -> `All workspace hygiene validator tests passed (7 cases).` (exit 0)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/tooling/test_harness_tools.py tests/tooling/test_antigravity_workspace_config.py` -> `10 passed in 0.78s` (exit 0)
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick` -> `100 passed, 2 deselected in 13.12s`, `compileall -q src tests tooling` passed, triggered `dart run tooling/validate_agent_docs.dart` passed, and `dart run tooling/validate_workspace_hygiene.dart` passed (exit 0; note `-Quick` intentionally excludes 2 DOM integration tests and is not `-Full` or complete repo pytest).
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` -> `267 passed in 45.16s` (Standard browser/API tier), `compileall -q src tests tooling` passed, triggered `dart run tooling/validate_agent_docs.dart` passed, and `dart run tooling/validate_workspace_hygiene.dart` passed (exit 0).
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1 -ConfigurationOnly` -> `configuration pass` (exit 0)
- **Protected preexisting dirty state verified unchanged (SHA256)**:
  - `docs/assistant/CACHE_COMPATIBILITY_ASSESSMENT.md`: `21ab65efecb9be18318eb1337b3efeb4dc82cf9fcc2c22d10261259404fdac95`
  - `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`: `86cc5a7700993514fc138320610fa7c25a105482515fed3a7185d41d2645ae28`
  - `.codex-remote-attachments/`: untouched.
