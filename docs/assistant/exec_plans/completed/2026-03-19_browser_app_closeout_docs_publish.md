# Browser App Closeout, Docs Sync, Publish, and Continuity

## Goal and Non-Goals
- Goal:
  - close out the browser-app feature work on `codex/beginner-first-primary-flow-ux`
  - make one implementation commit and one docs-sync commit
  - publish through the normal push/PR/merge/cleanup flow
  - leave the unrelated dirty `main` worktree untouched
  - install a strong fresh-session anchor for continued browser-app-first development
- Non-goals:
  - do not edit `docs/assistant/templates/*`
  - do not repair or clean the unrelated dirty `main` worktree
  - do not widen docs sync beyond touched browser-app, routing, continuity, and reusable issue-memory scope

## Scope (In / Out)
- In:
  - feature worktree git triage
  - browser-app implementation commit
  - scoped Assistant Docs Sync
  - session-resume / issue-memory / manifest / guide updates for the browser-app system
  - active/completed ExecPlan lifecycle cleanup for the completed browser-app wave
  - push, PR, merge, and feature-worktree cleanup
- Out:
  - template-folder synchronization
  - unrelated product changes on `main`
  - direct post-merge repair on `main` unless merge flow itself requires it

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status or intended noncanonical override:
  - current worktree is a noncanonical feature worktree
  - intended outcome is merge into canonical `main`, then clean feature-branch closeout

## Interfaces / Types / Contracts Affected
- Assistant docs routing/continuity contracts:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/manifest.json`
  - `docs/assistant/INDEX.md`
  - `docs/assistant/SESSION_RESUME.md`
- Reusable issue-memory / workflow contracts for browser-app live-vs-isolated mode and browser-owned Gmail bridge:
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/ISSUE_MEMORY.json`
  - touched workflow/user-guide docs only if needed to make the new browser-app system discoverable and durable
- Git lifecycle contracts:
  - active/completed ExecPlan inventory
  - PR merge / cleanup state for the feature branch

## File-by-File Implementation Steps
1. Triage the feature worktree:
   - keep browser-app/product/test/tooling changes
   - keep browser-parity ExecPlans and closeout ExecPlan
   - exclude scratch artifacts such as `.playwright-cli/` and `output/playwright/*`
2. Make the implementation commit:
   - stage product, test, tooling, and implementation-plan files only
   - leave docs-sync surfaces unstaged for the second commit
3. Run Assistant Docs Sync:
   - update canonical architecture/status to browser-app-first daily-use guidance
   - update routing/index/manifest and user-guide continuity for live mode vs isolated test mode
   - update issue memory / reusable workflow guidance so later template sync can reuse the pattern
   - update `SESSION_RESUME.md` to anchor fresh sessions in the browser-app era
4. Make the docs-sync commit:
   - docs-only staged set
   - validate agent docs and workspace hygiene as needed
5. Close branch lifecycle before merge:
   - archive completed browser-parity ExecPlans into `completed/`
   - remove scratch outputs
   - confirm clean feature worktree
6. Publish:
   - push branch
   - create or update PR
   - wait for checks
   - merge into `main`
   - prune branch/worktree state
   - confirm remote and feature worktree are clean

## Tests and Acceptance Criteria
- Implementation commit gate:
  - targeted tests for touched browser-app / Gmail-bridge / server slices still pass
  - `python -m compileall src tests`
  - scratch artifacts are not staged
- Docs-sync commit gate:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart` if touched docs require it
  - docs clearly describe:
    - browser app as preferred daily-use local surface
    - `live` mode vs isolated test mode
    - browser-owned live Gmail bridge and extension handoff
    - browser dashboard / Extension Lab / parity surface
    - deferred template-sync note
- Publish/cleanup gate:
  - PR is green and merged
  - feature worktree is clean
  - `main` dirty worktree is explicitly left untouched
  - `SESSION_RESUME.md` is sufficient for a fresh chat handoff

## Rollout and Fallback
- Preferred rollout:
  - merge feature branch cleanly into `main`
  - keep browser app as the documented day-to-day local entry surface
- Fallback:
  - if checks or merge block, stop at the cleanest published point and report the blocker
  - do not bypass by direct edits on `main`

## Risks and Mitigations
- Risk: scratch artifacts get swept into the implementation commit.
  - Mitigation: explicit path staging and pre-commit `git diff --cached --name-only`.
- Risk: docs remain Qt-primary and future sessions drift.
  - Mitigation: update canonical, bridge, index, manifest, session-resume, and user-guide routing in the same docs pass.
- Risk: completed active plans remain in `active/` and continuity drifts again.
  - Mitigation: archive completed browser-parity plans before merge and verify active inventory.
- Risk: user interprets “clean repos” as cleaning the unrelated dirty `main` worktree.
  - Mitigation: preserve the explicit leave-main-alone contract in the closeout notes and final verification.

## Assumptions / Defaults
- The browser app is now the preferred day-to-day local interface.
- `live` mode is the normal user-facing mode; isolated test mode remains an explicit development/testing surface.
- The real Gmail extension stays canonical, but it now hands off into the browser app.
- Template-folder sync is intentionally deferred to a later explicit request.
