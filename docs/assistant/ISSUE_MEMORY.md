# Issue Memory

## Purpose
Use this file as the human-readable registry for repeated workflow or product issues that should influence:
- project-level Assistant Docs Sync decisions
- `update codex bootstrap` / `UCBS` decisions about generalized harness lessons

Keep entries concise. This is not a thread transcript or a full incident report.

## Capture Rule
Capture or update an issue entry when either of these happens:

- operational trigger:
  - wrong app/build/worktree launched
  - accepted feature stranded on a side branch
  - repeated docs/governance correction for the same failure class
  - repeated host/auth/tool preflight failure
  - repeated branch-lineage or launch-identity mistake
  - repeated UI mismatch/back-and-forth loop
  - same workaround required more than once
  - same fix fails and the issue returns
- wording trigger:
  - `back and forth`
  - `difficult`
  - `complex`
  - `again`
  - `same mistake`
  - `took too long`
  - `not working`

Operational signals take priority. Wording alone should only create or update an entry when it points to a real repeatable failure class.

## Update Rule
When an issue entry is updated:
- increment `repeat_count` if the same class happened again
- update `last_seen_timestamp`
- record the new evidence refs
- if an earlier accepted fix failed, set status to `regressed`
- if a mitigation exists but has not held long enough, use `mitigated` instead of `resolved`

## Docs Sync Rule
Assistant Docs Sync should consult `ISSUE_MEMORY.md` and `ISSUE_MEMORY.json` before broadening project docs updates.

Use issue memory to decide:
- whether current touched-scope docs need to reflect a repeated issue
- which workflows/playbooks should be updated
- whether the docs sync should record that it changed docs because of a current issue-memory entry

`DOCS_REFRESH_NOTES.md` remains deferred evidence/history. `ISSUE_MEMORY` is the reusable problem registry.

## Bootstrap Rule
`update codex bootstrap` / `UCBS` should only consider entries whose bootstrap relevance is:
- `possible`
- `required`

Prioritize entries that have:
- `repeat_count >= 2`
- high workflow cost
- regression after a prior accepted fix

Do not promote one-off local/project-specific issues into the global Codex bootstrap unless they generalize cleanly.

## Status Vocabulary
- `open`: no durable mitigation yet
- `mitigated`: a fix exists, but it has not yet proved stable enough to treat as resolved
- `resolved`: accepted fix is holding
- `regressed`: the issue returned after a prior accepted fix

## Entry Template
- Issue ID
- Title
- First seen timestamp
- Last seen timestamp
- Repeat count
- Status
- Trigger source
- Symptoms
- Likely root cause
- Attempted fix history
- Accepted fix
- Regressed after accepted fix
- Affected workflows/docs
- Bootstrap relevance
- Docs-sync relevance
- Evidence refs

## Active Entries

### workflow-wrong-build-under-test
- Title: Wrong app/build under test because of mixed branches/worktrees and noncanonical launch
- First seen timestamp: `2026-03-06T00:00:00Z`
- Last seen timestamp: `2026-03-07T10:33:19Z`
- Repeat count: `4`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - the wrong `LegalPDF Translate` window was opened for testing
  - accepted functionality appeared to be missing because it lived only on a side branch or the wrong worktree was launched
  - repeated user-visible confusion during Gemini/Gmail/UI follow-up testing
- Likely root cause:
  - feature work progressed on side branches after acceptance
  - the approved base was not promoted immediately
  - multiple runnable worktrees existed without strong enough canonical-build enforcement
- Attempted fix history:
  - `2026-03-07T00:00:00Z` — added worktree baseline discipline docs; outcome: insufficient on its own
  - `2026-03-07T00:00:00Z` — added Qt build identity helper and noncanonical build markers; outcome: reduced ambiguity but did not solve accepted-feature promotion drift by itself
- Accepted fix:
  - `2026-03-07T10:33:19Z` — canonical build enforcement + approved-base promotion discipline + launcher identity packet gating + noncanonical launch override rules
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md`
  - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
- Bootstrap relevance: `required`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - worktree/build identity governance
    - approved-base promotion rules
    - canonical launch/default test target guidance
- Evidence refs:
  - ExecPlan: `docs/assistant/exec_plans/active/2026-03-07_worktree_baseline_docs_sync.md`
  - ExecPlan: `docs/assistant/exec_plans/active/2026-03-07_qt_build_identity_hardening.md`
  - ExecPlan: `docs/assistant/exec_plans/active/2026-03-07_accepted_feature_promotion_canonical_enforcement.md`
  - Branch: `feat/ai-docs-bootstrap`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_integration`

### harness-live-state-contamination
- Title: Tests or harness cleanup reused live user state or user-facing ports and contaminated real runtime checks
- First seen timestamp: `2026-03-08T00:00:00Z`
- Last seen timestamp: `2026-03-08T09:27:00Z`
- Repeat count: `2`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - the expected localhost listener belonged to `pytest` or another non-user runtime instead of the visible app
  - tests reused live roaming/profile settings or bridge configuration
  - the browser showed a successful handoff while the visible app stayed idle
- Likely root cause:
  - tests and ad hoc debugging reused live `%APPDATA%`, live settings, or default user-facing ports instead of isolated temp state
- Attempted fix history:
  - `2026-03-08T00:00:00Z` — isolated pytest APPDATA and stopped bridge tests from using the live Gmail port; outcome: partial_only
- Accepted fix:
  - `2026-03-08T09:27:00Z` — project guidance now requires temp env/filesystem isolation, non-live or ephemeral test ports, explicit teardown, and visible listener-conflict status
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
  - `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/LOCAL_ENV_PROFILE.local.md`
  - `docs/assistant/LOCAL_CAPABILITIES.md`
- Bootstrap relevance: `required`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - test isolation defaults
    - listener ownership guidance
    - visible runtime conflict handling
- Evidence refs:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_intake`
  - Template: `docs/assistant/templates/BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md`
  - Template: `docs/assistant/templates/BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md`

### workflow-fragmented-multi-surface-diagnostics
- Title: Fragmented diagnostics across handoff, per-run execution, and finalization slowed root-cause analysis
- First seen timestamp: `2026-03-08T00:00:00Z`
- Last seen timestamp: `2026-03-08T09:27:00Z`
- Repeat count: `2`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - browser banners, app bridge state, run reports, and finalization/draft failures had to be correlated manually
  - repeated debugging required back-and-forth between transient UI evidence and durable run artifacts
  - support packets were inconsistent across handoff, execution, and finalization failures
- Likely root cause:
  - project docs did not yet encode one support-packet order or one durable app-owned session-artifact pattern for multi-surface workflows
- Attempted fix history:
  - `2026-03-08T00:00:00Z` — feature-specific Gmail diagnostics were added; outcome: partial_only
- Accepted fix:
  - `2026-03-08T09:27:00Z` — project guidance now routes multi-surface debugging through per-run artifacts first, additive workflow context when needed, one app-owned session artifact, and a fixed support-packet order
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
- Bootstrap relevance: `required`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - session-artifact layering guidance
    - support-packet order
    - multi-surface troubleshooting workflow routing
- Evidence refs:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_intake`
  - Template: `docs/assistant/templates/BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md`
  - File: `C:\Users\FA507\Downloads\run_report.md`
