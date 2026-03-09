# Worktree Workspace Guide

## Use This Guide When
- You want one VS Code window that shows the main repo plus the active side-branch worktrees.
- You are unsure which LegalPDF folder should be your normal starting point.
- You want a plain explanation of how the sibling folders fit together.

## Do Not Use This Guide For
- Git history repair or branch surgery.
- Deep architecture questions about the app itself.
- Build, packaging, or test troubleshooting.

## For Agents: Support Interaction Contract
Use this sequence:
1. Start from the saved workspace file.
2. Tell the user which folder is the normal default.
3. Explain worktrees in plain language before using Git terms heavily.
4. Warn the user not to manually move active worktree folders.

## Canonical Deference Rule
This guide explains the local folder/workspace setup in plain language. For current app architecture and runtime truth, defer to `APP_KNOWLEDGE.md`. For the actual active worktree list on this machine, `git worktree list` is final truth.

## Quick Start (No Technical Background)
1. Open VS Code.
2. Open `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`.
3. Use `01 Main - legalpdf_translate` for normal day-to-day work unless you intentionally need one of the side branches.
4. Leave the sibling worktree folders where they are on disk.

## Terms in Plain English
- Workspace: One VS Code file that opens several folders together in one window.
- Worktree: Another folder connected to the same Git repository, usually for a different branch.
- Main folder: The default folder you should reach for first, which is `/mnt/c/Users/FA507/.codex/legalpdf_translate`.
- Side branch worktree: A sibling folder kept for a specific feature branch so it does not interfere with the main one.
- Archive: A safe holding area for stale or broken folders that should not stay in the daily workspace.

## Default Folder
- Your default main folder is `/mnt/c/Users/FA507/.codex/legalpdf_translate`.
- Treat that as the primary repo unless you intentionally need one of the side-branch worktrees.

## Open The Saved Workspace
- Open this file in VS Code: `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`
- It shows these active worktrees in order:
  - `01 Main - legalpdf_translate`
  - `02 Mail Drafts - legalpdf_translate_gmail`
  - `03 Gmail Intake - legalpdf_translate_gmail_intake`
  - `04 Integration - legalpdf_translate_integration`

## What A Worktree Means Here
- These folders are not random copies.
- They are linked Git worktrees for different branches of the same repository.
- That lets you keep separate feature branches open at the same time without constantly switching branches in one folder.

## Important Warning
- Do not manually move or rename the active worktree folders.
- If an old folder looks stale or broken, archive it instead of mixing it into the active workspace.
- If you are unsure which folder to use, use `legalpdf_translate` first.
