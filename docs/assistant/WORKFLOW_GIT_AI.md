# Workflow & Git Checklist (for AI Agents and Non-Coder Users)

## 1. State Snapshot

Run these commands before and after any change. If the AI agent has repo access, it **MUST** run the snapshot and paste outputs in its final response.

```bash
# What branch am I on? Any uncommitted changes?
git status --short

# What files changed since last commit?
git diff --name-only

# Do all tests pass?
python -m pytest -q

# Does all code compile without syntax errors?
python -m compileall src tests

# Recent commits (context for commit messages)
git log --oneline -5
```

| Command | What it tells you |
|---------|-------------------|
| `git status --short` | Uncommitted changes (M = modified, ?? = new untracked file) |
| `git diff --name-only` | List of files changed but not yet committed |
| `python -m pytest -q` | All tests pass (e.g. `420 passed in 12s`) or which failed |
| `python -m compileall src tests` | No Python syntax errors in any file |
| `git log --oneline -5` | Last 5 commit messages (follow the same style) |

## 2. Safe Change Flow

Follow this order every time. Each step depends on the previous one succeeding.

### Step 1 — Create or switch to a feature branch

```bash
# From main branch, create a new branch
git checkout main
git pull origin main
git checkout -b feat/my-change-name
```

### Step 2 — Make changes, then run tests

```bash
python -m pytest -q
python -m compileall src tests
```

If tests fail, fix them before proceeding. Never commit broken tests.

### Step 3 — Commit

```bash
# Stage specific files (not git add -A)
git add src/path/to/changed_file.py tests/test_new.py docs/assistant/updated.md

# Commit with a descriptive message
git commit -m "Add feature X: brief description"
```

### Step 4 — Push

```bash
# First push on a new branch (sets upstream tracking)
git push -u origin HEAD

# Subsequent pushes
git push
```

### Step 5 — Create PR

```bash
gh pr create --title "Short title" --body "$(cat <<'EOF'
## Summary
- What changed and why

## Verification
- python -m pytest -q -> <paste result>
- python -m compileall src tests -> success
- git diff --name-only -> <paste list>
- git status --short -> <paste status>
EOF
)"
```

### Step 6 — After merge, sync main

```bash
git checkout main
git pull origin main
```

## 3. AI Agent Rule

> **If the AI agent has repository access, it MUST run the State Snapshot (section 1) and paste all outputs in its final response to the user.** This is non-negotiable — the user relies on these outputs to verify completion.

The minimum required outputs in every final response:

```
python -m pytest -q        -> <actual result>
python -m compileall src tests -> <actual result>
git diff --name-only       -> <actual file list>
git status --short         -> <actual status>
```

## 4. Common Errors

### PowerShell `@{u}` quoting issue

**Symptom:** `git log @{u}..HEAD` fails in PowerShell because `@{}` is PowerShell syntax.

**Fix:** Wrap in quotes:
```powershell
git log '@{u}..HEAD'
```
Or use the explicit form:
```powershell
git log "origin/main..HEAD"
```

### Diverged main — safe backup + reset

**Symptom:** `git pull` says "diverged" or "refusing to merge unrelated histories".

**Fix — safe approach (backup first):**
```bash
# 1. Save current work to a backup branch
git branch backup/my-work-$(date +%Y%m%d)

# 2. Reset main to match remote
git fetch origin
git reset --hard origin/main
```

Never force-push main. If unsure, ask before running `reset --hard`.

### First push requires upstream

**Symptom:** `git push` fails with "no upstream branch".

**Fix:** Use `-u` on first push:
```bash
git push -u origin HEAD
```

After this, plain `git push` works for subsequent pushes on the same branch.

## 5. Security

- **Never** print, log, or commit API keys, tokens, or credentials.
- If a command output contains secrets, redact them before pasting.
- Do not commit `.env` files or `credentials.json`.
- Use `git diff` to review changes before committing — check for accidental secret inclusion.
