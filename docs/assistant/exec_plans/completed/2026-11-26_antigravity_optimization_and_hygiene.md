# ExecPlan: Complete Antigravity Global Optimization, Repo Hygiene, and Safe Worktree/Scratch Cleanup

## 1. Title
Complete Antigravity global plugin optimization, workspace watcher/search exclusions, legacy git/worktree documentation refresh, and safe scratch/worktree cleanup.

## 2. Goal and non-goals
- **Goal**:
  - Free Antigravity context budget by disabling 13 unrelated/heavyweight global plugins in `C:\Users\FA507\.gemini\config\config.json` (with exact backup preserved) so the built-in `browser` subagent and session tools remain available on fresh turns.
  - Exclude heavyweight runtime/archive directories (`.venv311`, `.playwright-cli`, `.playwright-mcp`, `tmp`, `docs/assistant/history`, `docs/assistant/exec_plans/completed`) from editor file watchers and search indexing via `.vscode/settings.json` and `docs/assistant/PERFORMANCE_BASELINES.md`.
  - Align `docs/assistant/WORKFLOW_GIT_AI.md` and `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md` with Antigravity and `.venv311\Scripts\python.exe`.
  - Safely archive ignored untracked root scratch artifacts outside the workspace and prune only verified-clean, verified-merged git worktrees (`51 -> 40`).
- **Non-goals**:
  - Do not refactor `src/` mega-files (`qt_gui/dialogs.py`, `workflow.py`, `shadow_web/app.py`, etc.); keep refactoring incremental per subsystem task.
  - Do not remove or modify any of the 39 dirty/unmerged worktrees or delete local branch refs.
  - Do not touch `bootstrap_harness_kit/`, `docs/assistant/exec_plans/active/`, `docs/assistant/HANDOFF.md`, `docs/assistant/runtime/CANONICAL_BUILD.json`, or `~/.gemini/config/plugins/migrated-settings/`.
  - Do not push to `origin` without explicit user authorization.

## 3. Scope (in/out)
- **In scope**:
  - Global Antigravity config optimization (`C:\Users\FA507\.gemini\config\config.json` + backup `config.json.bak_20261126`).
  - Exact pre-edit beforeimages under `docs/assistant/history/2026-11-26_antigravity_hygiene_before/`.
  - `.vscode/settings.json`, `docs/assistant/PERFORMANCE_BASELINES.md`, `docs/assistant/WORKFLOW_GIT_AI.md`, `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`, and `tests/tooling/test_antigravity_workspace_config.py`.
  - Archiving 7 ignored root scratch items to `C:\Users\FA507\.codex\_archive\legalpdf_root_scratch_20261126\` and removing 11 verified-clean, verified-merged worktrees + `git worktree prune`.
- **Out of scope**:
  - Remote `git push`, PR creation, branch deletion, or live Gmail/Word/OpenAI API calls.

## 4. Worktree provenance
- **Worktree path**: `C:/Users/FA507/.codex/legalpdf_translate`
- **Branch name**: `main`
- **Base branch**: `main`
- **Base SHA**: `6d478de831280114377a097204431fafce280acf` (contains `approved_base_head_floor` `4e9d20e` from `docs/assistant/runtime/CANONICAL_BUILD.json`)
- **Target integration branch**: `main`
- **Canonical build status or intended noncanonical override**: Canonical runnable build on `main`; docs/excludes/tooling tests only, zero `src/` changes, local commit only (unpushed pending explicit user remote-publication approval).
- **Lifecycle note**: Bare `commit` means full pending-tree triage plus logical grouped commits, and bare `push` means Push+PR+Merge+Cleanup; any narrower commit/push override must be recorded explicitly. This task records one clean scoped local hygiene/docs/test commit atop `6d478de` while leaving the three preexisting dirty items untouched.

## 5. Interfaces/types/contracts affected
- Preserve all 7 required watcher/search exclusion patterns enforced by `tooling/validate_workspace_hygiene.dart` (`**/.venv/**`, `**/__pycache__/**`, `**/.pytest_cache/**`, `**/.mypy_cache/**`, `**/build/**`, `**/dist/**`, `**/*_run/**`).
- Preserve all required phrases in `docs/assistant/PERFORMANCE_BASELINES.md` (`single source-of-truth`, `do not duplicate exclusion/policy tables`, `outside workspace root`).
- Preserve all 6 required user-guide headings and canonical deference links (`APP_KNOWLEDGE.md`, `git worktree list`) in `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`.

## 6. File-by-file implementation steps
1. Back up `C:\Users\FA507\.gemini\config\config.json` to `config.json.bak_20261126` and set `"enabled": false` on 13 unrelated plugins while keeping `chrome-devtools-plugin`, `modern-web-guidance-plugin`, `swarm`, Google Workspace connectors (`gcalendar`, `gdocs`, `gdrive`, `gmail`, `gsheets`, `gslides`), `migrated-settings`, and `windows-desktop-control` active (`google-developer-knowledge` kept disabled).
2. Snapshot pre-edit beforeimages under `docs/assistant/history/2026-11-26_antigravity_hygiene_before/`.
3. Update `.vscode/settings.json`, `docs/assistant/PERFORMANCE_BASELINES.md`, `docs/assistant/WORKFLOW_GIT_AI.md`, `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`, and `tests/tooling/test_antigravity_workspace_config.py`.
4. Archive 7 ignored root scratch items to `C:\Users\FA507\.codex\_archive\legalpdf_root_scratch_20261126\`, remove 11 verified-clean, verified-merged worktrees, and run `git worktree prune`.
5. Run all docs, hygiene, and Python tooling/quick validators, record outcomes here, and create the local commit.

## 7. Tests and acceptance criteria
- `validate_agent_docs.dart`, `validate_agent_docs_test.dart`, `validate_workspace_hygiene.dart`, `validate_workspace_hygiene_test.dart`, `pytest -q tests/tooling/test_harness_tools.py tests/tooling/test_antigravity_workspace_config.py`, and `scripts/validate_dev.ps1 -Quick` all exit `0`.
- `git worktree list` drops from `51` to `40` (main + 39 preserved dirty/unmerged worktrees).
- Preexisting protected dirty docs retain identical SHA256 hashes (`CACHE_COMPATIBILITY_ASSESSMENT.md`, `EXTERNAL_SOURCE_REGISTRY.md`).

## 8. Rollout and fallback
- Global plugins: restore `C:\Users\FA507\.gemini\config\config.json.bak_20261126` or re-enable individual plugins in Antigravity Settings.
- Root scratch items: stored intact in `C:\Users\FA507\.codex\_archive\legalpdf_root_scratch_20261126\`.
- Repo changes: reversible via `docs/assistant/history/2026-11-26_antigravity_hygiene_before/` or `git revert`.

## 9. Risks and mitigations
- Disabling an unintended plugin -> kept all Google Workspace, `chrome-devtools-plugin`, `modern-web-guidance-plugin`, `swarm`, `migrated-settings`, and `windows-desktop-control` enabled, plus backup file saved.
- Removing dirty/unmerged worktrees -> verified `dirty=0`, `merged=True`, `ahead=0`, `locked=False` immediately before every removal; all 39 others left untouched and no branch refs deleted.

## 10. Assumptions/defaults
- A fresh Antigravity conversation/reload reads the updated `C:\Users\FA507\.gemini\config\config.json` plugin state.
- User approved all global optimization, doc/exclude hygiene, scratch archiving, and safe worktree pruning steps in this session.

## 11. Completion & Validation Outcomes (2026-11-26)
- **Global plugins (`config.json`)**:
  - Backup created at `C:\Users\FA507\.gemini\config\config.json.bak_20261126`.
  - Disabled 13 unrelated/heavyweight plugins (`android-cli-plugin`, `chemistry`, `data-agent-kit-plugin`, `figma`, `flutter`, `gemini-api`, `genomics`, `google-antigravity-sdk`, `google_maps_platform`, `science-overview`, `scientific-literature`, `structural-biology`, `supabase`; `google-developer-knowledge` remained disabled).
  - Kept 9 explicit entries enabled (`chrome-devtools-plugin`, `gcalendar`, `gdocs`, `gdrive`, `gmail`, `gsheets`, `gslides`, `modern-web-guidance-plugin`, `swarm`) plus default-enabled `migrated-settings` and `windows-desktop-control`.
- **Root scratch archive (`C:\Users\FA507\.codex\_archive\legalpdf_root_scratch_20261126\`)**:
  - Moved 7 ignored untracked items: `6a330e92-744d-4579-847b-6bace4fa38d2_temp_FR_run`, `6a330e92-744d-4579-847b-6bace4fa38d2_temp_FR_20260211_000727.docx`, `rg_glossary_builder_hotspots.txt`, `rg_prompt_hotspots.txt`, `rg_qt_glossary_builder_hotspots.txt`, `.playwright-cli`, `.playwright-mcp`.
- **Worktree cleanup (`git worktree list`: `51 -> 40`)**:
  - Removed 11 verified-clean, verified-merged worktrees (`legalpdf_translate_arabic_acceptance`, `legalpdf_translate_formatting`, `legalpdf_translate_new_runs`, `legalpdf_translate_structured_activation`, `editor-busy-read-20261017`, `email-retest-oct15`, `email-validation-base-oct15`, `gmail-formatting-readiness`, `oct15-source-line-restoration`, `translation-structure-20261108`, `legalpdf-uv`) and ran `git worktree prune`; kept all 39 dirty/unmerged worktrees and all branch refs untouched.
- **Validation executed**:
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> `PASS: agent docs validation succeeded.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/validate_agent_docs_test.dart` -> `All agent docs validator tests passed.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> `PASS: workspace hygiene validation succeeded.` (exit 0)
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/validate_workspace_hygiene_test.dart` -> `All workspace hygiene validator tests passed (7 cases).` (exit 0)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/tooling/test_harness_tools.py tests/tooling/test_antigravity_workspace_config.py` -> `11 passed in 0.77s` (exit 0)
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick` -> `100 passed, 2 deselected in 11.89s`, `compileall -q src tests tooling` passed, triggered `dart run tooling/validate_agent_docs.dart` passed, and `dart run tooling/validate_workspace_hygiene.dart` passed (exit 0; `-Quick` is distinct from `-Full` and complete repo pytest).
