# Bootstrap Application Audit

Verification date: 2026-03-09

## Scope
- Source of truth for this audit:
  - `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md`
  - `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
  - `docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md`
  - `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
  - `docs/assistant/templates/BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md`
  - `docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`
  - `docs/assistant/templates/BOOTSTRAP_CAPABILITY_DISCOVERY.md`
  - `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
- Local project evidence:
  - `agent.md`
  - `docs/assistant/INDEX.md`
  - `docs/assistant/manifest.json`
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/ISSUE_MEMORY.json`
  - `docs/assistant/LOCAL_ENV_PROFILE.local.md`
  - `docs/assistant/LOCAL_CAPABILITIES.md`
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
  - `docs/assistant/workflows/*.md`

## Verdict
Current bootstrap-defined relevant layers appear to be applied in this repo.
No current `missing_from_project` rows were found among the bootstrap-defined layers audited here.

The requested continuity system is not present in the committed bootstrap:
- no routed `SESSION_RESUME.md`
- no bootstrap-defined `MASTER_PLAN.md`
- no current-roadmap file contract
- no anchor-file or anchor-routing contract in the templates or local manifest

That continuity requirement should therefore be treated as `missing_from_bootstrap`, not as a project-local application failure.

## Applied-vs-Missing Matrix
| Bootstrap source module or contract | Project-local instantiation files | Status | Evidence note |
|---|---|---|---|
| Core required outputs | `README.md`, `AGENTS.md`, `agent.md`, `APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, `docs/assistant/INDEX.md`, `docs/assistant/manifest.json`, `docs/assistant/GOLDEN_PRINCIPLES.md`, `docs/assistant/exec_plans/PLANS.md`, validator tooling/tests | `applied` | All required core files listed by `BOOTSTRAP_CORE_CONTRACT.md` are present. |
| Beginner Layer | `docs/assistant/features/APP_USER_GUIDE.md`, `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`, support routing in `agent.md` and `INDEX.md` | `applied` | Plain-language user guides and support routing are present for non-technical help. |
| Localization + Performance | `docs/assistant/LOCALIZATION_GLOSSARY.md`, `docs/assistant/PERFORMANCE_BASELINES.md`, corresponding workflows and manifest routing | `applied` | The project carries both localization and workspace-performance sources of truth expected by the trigger matrix. |
| Issue Memory System | `docs/assistant/ISSUE_MEMORY.md`, `docs/assistant/ISSUE_MEMORY.json`, issue-memory routing in `manifest.json` and docs-maintenance guidance | `applied` | The project has the paired human + machine registry and bootstrap-promotion filtering language. |
| Local Environment Overlay | `docs/assistant/LOCAL_ENV_PROFILE.local.md` | `applied` | The repo carries a tracked project-local environment profile rather than pushing machine facts into universal docs. |
| Capability Discovery | `docs/assistant/LOCAL_CAPABILITIES.md` | `applied` | The project has a durable local capability inventory matching the bootstrap discovery model. |
| Worktree / Build Identity | `docs/assistant/runtime/CANONICAL_BUILD.json`, `tooling/launch_qt_build.py`, `agent.md`, worktree workflow docs | `applied` | The repo encodes approved-base locking, canonical build identity, and handoff provenance. |
| Host Integration Preflight | `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`, local env/capability docs | `applied` | Same-host install/auth/preflight guidance is present and routed. |
| Harness Isolation + Diagnostics | `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`, manifest isolation/diagnostics policies | `applied` | Listener ownership, live-state isolation, and durable session-diagnostics rules are present. |
| Staged Execution | `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`, stage-gate policy in `agent.md` and `manifest.json` | `applied` | Stage packets and exact continuation-token guidance are present. |
| Reference Discovery | `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md`, routing in `agent.md` and `manifest.json` | `applied` | Named-product parity work is explicitly routed. |
| OpenAI Docs + Citation | `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`, freshness/citation policy in `agent.md` and `manifest.json` | `applied` | Unstable OpenAI facts are explicitly routed through official docs. |
| Browser Automation + Environment Provenance | `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`, manifest policies | `applied` | Browser automation reliability/provenance workflow is present and routed. |
| Cloud Machine Evaluation + Local Acceptance | `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`, manifest policies | `applied` | Cloud-heavy evaluation guidance and local acceptance split are present. |
| Bootstrap Update Policy | none expected in generated project-local harness | `not_applicable` | This module governs edits to `docs/assistant/templates/*`, not normal project-local harness outputs. |
| Master plan / session resume / anchor continuity system | None in templates, manifest, or routed local docs | `missing_from_bootstrap` | No template file, template-map entry, manifest contract, or local routed file defines this subsystem. |

## Project-Only Extras (Not Bootstrap Continuity)
These files exist in the repo, but they do not satisfy the requested continuity requirement because the bootstrap does not define them as always-on cross-session planning artifacts:

| Local file | Why it does not satisfy the requested system |
|---|---|
| `docs/assistant/audits/ROADMAP_30_60_90_2026-03-05.md` | Historical dated roadmap output, not a bootstrap-required current master plan. |
| `docs/assistant/audits/RELIABILITY_SIGNOFF_2026-03-05.md` | Historical signoff packet, not a resume file. |
| Active/completed `docs/assistant/exec_plans/*.md` | Task-scoped execution plans, not a single repo-wide continuity file. |
| `docs/assistant/ISSUE_MEMORY.*` | Reusable issue registry, not a session-resume or anchor document. |

## Continuity Verdict
- `ExecPlans` solve task-level continuity only.
- `ISSUE_MEMORY` solves repeated-problem memory only.
- Stage packets solve staged handoff continuity only.
- Existing roadmap/audit outputs are historical and dated, not canonical continuity surfaces.
- The committed bootstrap currently lacks a generic master-plan + session-resume + anchor-file subsystem.

If that system is desired, it should be added through a separate bootstrap-maintenance pass, not patched in locally as if it were already part of the bootstrap.
