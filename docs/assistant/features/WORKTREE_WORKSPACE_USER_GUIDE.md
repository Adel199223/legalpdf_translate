# Worktree Workspace Guide

## Use This Guide When
- You want the simplest starting point for the LegalPDF repo in Antigravity or VS Code.
- You are unsure which LegalPDF folder should be your normal starting point.
- You want a plain explanation of how optional side worktrees fit around the main repo.

## Do Not Use This Guide For
- Git history repair or branch surgery.
- Deep architecture questions about the app itself.
- Build, packaging, or test troubleshooting.

## For Agents: Support Interaction Contract
Use this sequence:
1. Start from the main repo folder (`C:\Users\FA507\.codex\legalpdf_translate`).
2. Tell the user the main repo is the normal default.
3. Explain optional side worktrees in plain language before using Git terms heavily.
4. Warn the user not to manually move active worktree folders if they create them later.

## Canonical Deference Rule
This guide explains the local folder/workspace setup in plain language. For current app architecture and runtime truth, defer to `APP_KNOWLEDGE.md`. For the actual active worktree list on this machine, `git worktree list` is final truth.

## Quick Start (No Technical Background)
1. In **Antigravity**, open `C:\Users\FA507\.codex\legalpdf_translate` from the **Projects** sidebar as your default workspace.
2. If you use **VS Code** instead, open `C:\Users\FA507\.codex\legalpdf_translate-worktrees.code-workspace` (WSL path `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`) and select `01 Main - legalpdf_translate`.
3. Use that main folder for normal day-to-day work and live Gmail runs.
4. Only create extra sibling worktree folders when you intentionally need another branch isolated.

## Terms in Plain English
- Workspace: One project window (or a VS Code `.code-workspace` file) pointing at your repository folder.
- Worktree: Another folder connected to the same Git repository, usually for a different branch.
- Main folder: The default folder you should reach for first, which is `C:\Users\FA507\.codex\legalpdf_translate` (WSL: `/mnt/c/Users/FA507/.codex/legalpdf_translate`).
- Side branch worktree: An optional sibling folder kept for a specific feature branch so it does not interfere with the main one.
- Archive: A safe holding area (`C:\Users\FA507\.codex\_archive\`) for stale or retired files that should not clutter the daily workspace.

## Default Folder
- Your default main folder is `C:\Users\FA507\.codex\legalpdf_translate`.
- Treat that as the primary repo unless you intentionally create and use a side-branch worktree.

## Open The Saved VS Code Workspace (Optional)
- Open `C:\Users\FA507\.codex\legalpdf_translate-worktrees.code-workspace` (WSL: `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`) when working in VS Code.
- It lists `01 Main - legalpdf_translate` as the default folder.
- Add extra folders only when you intentionally create new side worktrees again.

## What A Worktree Means Here
- The main folder is the normal day-to-day repo.
- Extra worktree folders are not random copies.
- They are linked Git worktrees for different branches of the same repository.
- Use them only when you deliberately need separate feature branches open at the same time without constantly switching one folder back and forth.

## Important Warning
- Do not manually move or rename active worktree folders.
- If an old side-worktree folder looks stale or broken, remove or archive it deliberately instead of mixing it into the daily workspace.
- If you are unsure which folder to use, use `C:\Users\FA507\.codex\legalpdf_translate` first.
