# Bootstrap Worktree and Build Identity

## What This Module Is For
This module encodes the worktree discipline required when a project may have parallel branches, multiple worktrees, or more than one runnable GUI build.

## Auto-Activation Rule
Auto-activate this module when the project has:
- a runnable app
- a GUI
- a local desktop workflow
- explicit multi-worktree or multi-build testing risk

For CLI/library projects without those characteristics, keep only the governance-level rules and do not force unnecessary launch tooling.

## Latest Approved Baseline Rule
Before starting parallel work, identify the latest approved baseline by:
- branch name
- exact base SHA

Every new branch or worktree must be created from that locked baseline, not from an older convenient branch.

## Required Worktree Provenance
Every major active ExecPlan should record:
- worktree path
- branch name
- base branch
- base SHA
- intended feature scope
- target integration branch

If a worktree is discovered to be based on the wrong branch or SHA, stop feature work and transplant/rebase before continuing.

## Canonical Runnable Build Rule
Only one build should be treated as the normal user-facing test target at a time.
Other worktrees may exist, but they should be treated as source-only unless explicitly promoted.

## Build Under Test Identity Packet
When a GUI build is opened or handed off for testing, the handoff is incomplete unless it includes:
- worktree path
- branch
- HEAD SHA
- launch command
- distinguishing feature labels

`open the app` is incomplete without that build identity packet.

## Canonical Launcher Rule
Generated repos that can have multiple runnable worktrees should include a canonical launcher/identity helper so GUI launches are deterministic instead of ad hoc.

## Accepted-Feature Promotion Rule
Generated repos in this class should treat merge-immediately-after-acceptance as the default lifecycle:
1. branch from the latest approved base
2. build and test the feature
3. once the user accepts the feature, merge it into the approved base immediately
4. prune/delete the obsolete source branch
5. start the next feature from the updated approved base

An accepted feature living only on a side branch should be treated as a workflow violation in projects that use this module.
