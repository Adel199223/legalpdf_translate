# Project Harness Alignment Audit

Verification date: 2026-03-09

## Scope
- Source of truth:
  - current vendored templates under `docs/assistant/templates/`
- Local implementation surface:
  - `agent.md`
  - `AGENTS.md`
  - `README.md`
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/INDEX.md`
  - `docs/assistant/manifest.json`
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
  - `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
  - `docs/assistant/SESSION_RESUME.md`
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`

## Summary
The vendored template set now includes project-harness sync policy and roadmap governance.
This repo is aligning its project-local harness to that newer template floor without editing `docs/assistant/templates/*`.

This audit does not replace `docs/assistant/audits/BOOTSTRAP_APPLICATION_AUDIT_2026-03-09.md`.
That earlier audit remains historically accurate for the older committed template set that existed at the time.

## Local Implementation Targets
| Template-derived contract | Project-local implementation target |
|---|---|
| local harness apply triggers | `agent.md`, `AGENTS.md`, `README.md`, `docs/assistant/INDEX.md`, `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md` |
| vendored-template protection | `agent.md`, `AGENTS.md`, `docs/assistant/manifest.json`, `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md` |
| roadmap anchor file | `docs/assistant/SESSION_RESUME.md` |
| roadmap governance runbook | `docs/assistant/workflows/ROADMAP_WORKFLOW.md` |
| active-worktree authority | `APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, `docs/assistant/SESSION_RESUME.md` |
| validator enforcement | `tooling/validate_agent_docs.dart`, `test/tooling/validate_agent_docs_test.dart` |

## Continuity Verdict
- The continuity system requested by the user now exists in the vendored templates.
- This repo therefore needs a project-local implementation of that system rather than a bootstrap-gap report.
- `docs/assistant/SESSION_RESUME.md` is the stable fresh-session entrypoint once the local harness sync is complete.
