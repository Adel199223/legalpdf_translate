# Bootstrap Issue Memory System

## What This Module Is For
This module makes issue memory a default generated subsystem for every bootstrapped project.

The goal is to give each project a reusable problem registry that can influence:
- project-level Assistant Docs Sync
- `update codex bootstrap` / `UCBS` decisions about generalized harness lessons

Issue memory is always on by default. It should not depend on a project already having repeated issues before the files exist.

## Required Generated Files
Generate these files in every project harness:
- `docs/assistant/ISSUE_MEMORY.md`
- `docs/assistant/ISSUE_MEMORY.json`

These files are paired views of the same registry:
- Markdown: concise human-readable review surface
- JSON: machine-friendly repeat detection, docs-sync routing, and bootstrap filtering

## Generated Record Shape
Each generated project issue record must support:
- stable issue id
- first seen timestamp
- last seen timestamp
- repeat count
- status
- trigger source
- symptoms
- likely root cause
- attempted fix history
- accepted fix
- regressed-after-fix flag
- affected workflows/docs
- bootstrap relevance
- docs-sync relevance
- evidence refs

Generate an empty-but-structured registry. Do not preseed fake incidents from the bootstrap source project.

## Capture Rules
Generated projects should update issue memory when meaningful issue classes appear.

Operational triggers take priority:
- wrong app/build/worktree launched
- accepted feature stranded on a side branch
- repeated docs/governance correction for the same failure class
- repeated host/auth/tool preflight failure
- repeated test/live-state contamination involving real settings, ports, auth, or caches
- repeated branch-lineage or launch-identity mistake
- repeated fragmented diagnostics across workflow surfaces
- repeated UI mismatch/back-and-forth loop
- same workaround required more than once
- same fix fails and the issue returns

Wording triggers are secondary signals:
- `back and forth`
- `difficult`
- `complex`
- `again`
- `same mistake`
- `took too long`
- `not working`

Wording alone should only create or update an entry when it points to a real repeatable failure class.

## Docs Sync Rule
Generated repos should make Assistant Docs Sync consult issue memory before widening project docs updates.

Use issue memory to decide:
- whether current touched-scope docs should reflect a repeated issue
- which workflows/playbooks should be updated
- whether the sync should record that docs changed because of a current issue-memory entry

`DOCS_REFRESH_NOTES.md` remains evidence/history. `ISSUE_MEMORY` is the reusable problem registry.

## Bootstrap Rule
Generated repos should make `update codex bootstrap` / `UCBS` consult issue memory only for entries whose bootstrap relevance is:
- `possible`
- `required`

Prioritize:
- `repeat_count >= 2`
- high workflow cost
- regression after a prior accepted fix

Do not promote one-off project-specific issues into the global Codex bootstrap unless they generalize cleanly.

## Concision Rule
Issue memory must stay concise and structured.

Do not use it as:
- a full incident narrative
- a thread transcript
- a duplicate of ExecPlans or run reports

Long narratives belong in thread history, ExecPlans, and run/report artifacts. Issue memory should keep only the reusable problem memory.
