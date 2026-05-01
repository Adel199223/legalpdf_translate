# ExecPlan: Bootstrap Template Refactor and Hardening

## Problem
The bootstrap system is still a single large prompt file. It preserves strong contracts, but it does not scale well and it does not yet encode the most reusable lessons from recent work:
- approved-baseline and worktree/build identity discipline,
- host-bound integration preflight,
- optional local machine overlays,
- dynamic skill/MCP/tool discovery,
- dated OpenAI/Codex assumptions routed through official docs.

## Goal
Refactor `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md` into a small orchestrator plus read-on-demand sub-bootstrap files, then add validator coverage so the template system cannot silently drift.

## Scope
- Create a template map in `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
- Add these sub-bootstrap files:
  - `BOOTSTRAP_CORE_CONTRACT.md`
  - `BOOTSTRAP_MODULES_AND_TRIGGERS.md`
  - `BOOTSTRAP_LOCAL_ENV_OVERLAY.md`
  - `BOOTSTRAP_CAPABILITY_DISCOVERY.md`
  - `BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md`
  - `BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md`
- Slim the main bootstrap prompt into an orchestrator
- Extend `tooling/validate_agent_docs.dart`
- Extend `test/tooling/validate_agent_docs_test.dart`

## Non-Goals
- No product/app feature changes
- No manifest routing changes outside what the validator already enforces
- No blanket governance rewrite outside the bootstrap/template surface

## Validation
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`

## Notes
- Machine-specific facts belong in the local environment overlay, not the universal core contract.
- OpenAI/Codex guidance must be recorded as dated assumptions with official-doc routing, not timeless product facts.
