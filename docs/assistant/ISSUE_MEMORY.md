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
- Last seen timestamp: `2026-03-19T06:51:00Z`
- Repeat count: `6`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - the wrong `LegalPDF Translate` window was opened for testing
  - accepted functionality appeared to be missing because it lived only on a side branch or the wrong worktree was launched
  - repeated user-visible confusion during Gemini/Gmail/UI follow-up testing
  - the user also needed extra support guidance about which sibling folder or workspace file should be the normal daily entry point
- Likely root cause:
  - feature work progressed on side branches after acceptance
  - the approved base was not promoted immediately
  - multiple runnable worktrees existed without strong enough canonical-build enforcement
- Attempted fix history:
  - `2026-03-07T00:00:00Z` — added worktree baseline discipline docs; outcome: insufficient on its own
  - `2026-03-07T00:00:00Z` — added Qt build identity helper and noncanonical build markers; outcome: reduced ambiguity but did not solve accepted-feature promotion drift by itself
  - `2026-03-09T01:00:00Z` — added a saved multi-root VS Code workspace guide and archived a stale broken sibling folder out of the daily view; outcome: partial_only because it reduces navigation confusion but does not replace canonical build identity enforcement
  - `2026-03-19T06:51:00Z` — promoted the local browser app to the preferred daily-use surface, added explicit `live` versus isolated `shadow` mode routing, and documented the canonical live browser URL plus detached launcher; outcome: partial_only because it gives one stable human entrypoint, but branch/publish discipline still matters
- Accepted fix:
  - `2026-03-19T06:51:00Z` — canonical build enforcement plus approved-base promotion discipline, launcher identity packet gating, noncanonical launch override rules, and one browser-app-first daily entrypoint with explicit `live` versus isolated `shadow` semantics
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md`
  - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/SESSION_RESUME.md`
- Bootstrap relevance: `required`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - worktree/build identity governance
    - approved-base promotion rules
    - canonical launch/default test target guidance
    - plain-language local workspace entry guidance
  - Evidence refs:
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-07_worktree_baseline_docs_sync.md`
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-07_qt_build_identity_hardening.md`
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-07_accepted_feature_promotion_canonical_enforcement.md`
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-09_worktree_workspace_organization.md`
  - Branch: `feat/ai-docs-bootstrap`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate`
  - Workspace: `C:\Users\FA507\.codex\legalpdf_translate-worktrees.code-workspace`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_integration`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`

### harness-live-state-contamination
- Title: Tests or harness cleanup reused live user state or user-facing ports and contaminated real runtime checks
- First seen timestamp: `2026-03-08T00:00:00Z`
- Last seen timestamp: `2026-03-19T06:51:00Z`
- Repeat count: `3`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - the expected localhost listener belonged to `pytest` or another non-user runtime instead of the visible app
  - tests reused live roaming/profile settings or bridge configuration
  - the browser showed a successful handoff while the visible app stayed idle
  - browser validation needed an explicit isolated browser `shadow` mode because real Gmail bridge ownership and real user data could not safely share the same default runtime state
- Likely root cause:
  - tests and ad hoc debugging reused live `%APPDATA%`, live settings, or default user-facing ports instead of isolated temp state
- Attempted fix history:
  - `2026-03-08T00:00:00Z` — isolated pytest APPDATA and stopped bridge tests from using the live Gmail port; outcome: partial_only
  - `2026-03-19T06:51:00Z` — added explicit browser-app `live` versus isolated `shadow` mode, separate runtime roots, browser-owned live Gmail bridge ownership, and clearer diagnostics for active mode, data root, and listener owner; outcome: stronger_mitigation
- Accepted fix:
  - `2026-03-19T06:51:00Z` — project guidance now requires temp env/filesystem isolation, non-live or ephemeral test ports, explicit teardown, visible listener-conflict status, and a first-class browser-app split between real-work `live` mode and isolated `shadow` mode
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
  - `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/LOCAL_ENV_PROFILE.local.md`
  - `docs/assistant/LOCAL_CAPABILITIES.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/SESSION_RESUME.md`
- Bootstrap relevance: `required`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - test isolation defaults
    - listener ownership guidance
    - visible runtime conflict handling
- Evidence refs:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_intake`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
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

### product-arabic-docx-word-right-alignment
- Title: Arabic DOCX right alignment in Word could not be solved durably with OOXML-only writer changes
- First seen timestamp: `2026-03-08T00:00:00Z`
- Last seen timestamp: `2026-03-08T20:45:00Z`
- Repeat count: `4`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - Arabic DOCX output still opened left-aligned in Word even though the text itself remained RTL
  - some attempted fixes worsened mixed Arabic/Portuguese line ordering or misplaced Latin fragments
  - source-side XML/test changes could appear correct while the real Word-rendered document still required manual right alignment
- Likely root cause:
  - mixed RTL/LTR Word layout is not reliably controlled by the current OOXML writer path alone, so writer-only fixes were not durable enough for shipped user-visible behavior
- Attempted fix history:
  - `2026-03-08T00:00:00Z` — switched RTL paragraph handling toward left-justified bidi semantics; outcome: insufficient because mixed Arabic/Portuguese ordering got worse
  - `2026-03-08T00:00:00Z` — kept `jc=right` while removing paragraph bidi/rtl; outcome: insufficient because mixed ordering improved but Word still did not visually align the page to the right
  - `2026-03-08T00:00:00Z` — tried a bidi-only paragraph shape with build/delivery verification; outcome: insufficient because it was not durable enough as a shipped fix in the real host/build path
- Accepted fix:
  - `2026-03-08T20:45:00Z` — added an Arabic-only Word review gate with `Align Right + Save`, automatic save detection, and manual fallback actions before Save to Job Log / Gmail continuation
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/LOCAL_CAPABILITIES.md`
  - `docs/assistant/LOCAL_ENV_PROFILE.local.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Bootstrap relevance: `possible`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - Arabic Word review gate behavior
    - Windows Word + PowerShell same-host requirement
    - durable memory of failed OOXML-only fixes without presenting them as current behavior
- Evidence refs:
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-08_arabic_docx_review_gate.md`
  - File: `src/legalpdf_translate/word_automation.py`
  - File: `src/legalpdf_translate/qt_gui/dialogs.py`
  - File: `tests/test_word_automation.py`
  - File: `tests/test_qt_app_state.py`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate`

### workflow-gmail-post-save-finalization-regression
- Title: Gmail batch post-save continuation changes regressed behavior when special-casing the last saved item
- First seen timestamp: `2026-03-08T00:00:00Z`
- Last seen timestamp: `2026-03-08T20:45:00Z`
- Repeat count: `1`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - a same-day change to make `Save` continue Gmail finalization made the flow worse and had to be rolled back
  - Gmail batch post-save behavior became harder to reason about because final-item behavior diverged from the conservative continuation path
- Likely root cause:
  - Gmail batch post-save continuation is stateful and fragile, so special-casing the last item without full host validation can regress user-visible flow quickly
- Attempted fix history:
  - `2026-03-08T00:00:00Z` — added a last-item post-save finalization helper and related tests; outcome: insufficient because the behavior regressed and the change was rolled back
- Accepted fix:
  - `2026-03-08T20:45:00Z` — reverted to the previous conservative `_start_next_gmail_batch_translation()` post-save path and raised the change bar to full-file green plus manual host validation before touching Gmail post-save continuation again
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Bootstrap relevance: `possible`
- Docs-sync relevance:
  - Priority: `medium`
  - Targets:
    - Gmail batch post-save continuation caution
    - require stronger validation before changing final-item save behavior again
- Evidence refs:
  - File: `src/legalpdf_translate/qt_gui/app_window.py`
  - File: `tests/test_qt_app_state.py`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate`

### workflow-post-merge-continuity-cleanup-drift
- Title: Post-merge cleanup drift left stale roadmap continuity and scratch artifacts behind
- First seen timestamp: `2026-03-09T23:30:00Z`
- Last seen timestamp: `2026-03-09T23:30:00Z`
- Repeat count: `1`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - `docs/assistant/SESSION_RESUME.md` still pointed to a deleted feature branch after merge
  - `docs/assistant/exec_plans/active/` still held clearly completed or dead-branch plans
  - a docs-only continuity repair was needed on `main` after the merge was already complete
  - deterministic Qt render-review outputs showed up as untracked Source Control noise
- Likely root cause:
  - branch cleanup did not require roadmap closeout, resume-anchor updates, and scratch-output cleanup to be decision-complete before merge
- Attempted fix history:
  - `2026-03-09T23:30:00Z` — merged the feature thread first and repaired continuity state afterward on `main`; outcome: partial_only because the cleanup succeeded but too much of the logic still lived in thread memory
- Accepted fix:
  - `2026-03-09T23:30:00Z` — added dormant-roadmap support for `SESSION_RESUME.md`, archived deterministically stale plans, hardened commit/publish and docs-maintenance workflows, moved Qt render-review scratch output under ignored `tmp/`, and added validator coverage for stale resume branches and legacy scratch-path guidance
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/UPDATE_POLICY.md`
  - `docs/assistant/SESSION_RESUME.md`
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Bootstrap relevance: `possible`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - stale roadmap continuity repair
    - active/completed ExecPlan lifecycle hygiene
    - post-merge cleanup guardrails
    - ignored scratch-output defaults for assistant tooling
- Evidence refs:
  - File: `docs/assistant/SESSION_RESUME.md`
  - File: `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - File: `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - File: `tooling/qt_render_review.py`
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-09_cleanup_continuity_hardening.md`
  - Branch: `main`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate`

### desktop-qt-honorarios-export-reliability
- Title: Honorários PDF export and focus-sensitive Qt dialogs felt unstable because host-bound work blocked the UI and modal state leaked across paths
- First seen timestamp: `2026-03-12T00:00:00Z`
- Last seen timestamp: `2026-03-12T18:05:00Z`
- Repeat count: `2`
- Status: `mitigated`
- Trigger source: `both`
- Symptoms:
  - the visible LegalPDF window could show `No responde` while Word PDF export tried to launch or timed out
  - PDF failure warnings dumped raw PowerShell/COM text inline and could cascade into an extra Gmail missing-PDF warning
  - focus-sensitive Qt tests around Return/Delete shortcuts could fail intermittently because leaked dialogs or stale focus changed the active target
- Likely root cause:
  - host-bound Word PDF export originally ran on the GUI thread and failure handling spanned too many modal layers
  - the Qt harness did not yet enforce deterministic popup cleanup, activation, and shortcut targeting for focus-sensitive dialog tests
- Attempted fix history:
  - `2026-03-12T00:00:00Z` — added synchronous honorários DOCX-to-PDF export through Word automation; outcome: insufficient because the UI could freeze and the failure diagnostics were too noisy
- Accepted fix:
  - `2026-03-12T18:05:00Z` — moved honorários PDF export to a worker thread, replaced raw command dumps with concise warnings plus expandable details, added one retry/select-existing-PDF/local-only recovery flow, reduced duplicate warning cascades, and hardened Qt popup cleanup plus explicit activation for focus-sensitive dialog tests
- Regressed after accepted fix: `no`
- Affected workflows/docs:
  - `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Bootstrap relevance: `possible`
- Docs-sync relevance:
  - Priority: `high`
  - Targets:
    - non-blocking host automation for user-facing desktop flows
    - concise user-facing failure text with expandable diagnostics
    - single recovery flow for partial-success exports
    - explicit activation and leaked-popup cleanup for focus-sensitive Qt tests
- Evidence refs:
  - ExecPlan: `docs/assistant/exec_plans/completed/2026-03-12_desktop_stability_honorarios_qt.md`
  - File: `src/legalpdf_translate/qt_gui/dialogs.py`
  - File: `src/legalpdf_translate/qt_gui/worker.py`
  - File: `src/legalpdf_translate/word_automation.py`
  - File: `tests/conftest.py`
  - File: `tests/test_qt_app_state.py`
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate`
