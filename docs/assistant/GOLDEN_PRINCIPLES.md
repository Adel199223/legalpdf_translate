# Golden Principles

This file is the single source-of-truth for enforceable mechanical rules.

## Rule Precedence
1. Source code is final truth.
2. `APP_KNOWLEDGE.md` is canonical for app-level architecture/status.
3. Bridge docs and user guides defer to canonical technical docs.

## Mechanical Rules
1. Never execute commit/publish blindly; use commit workflow.
2. Keep `main` stable; major work starts on `feat/*`.
3. Use worktree isolation for parallel streams.
4. Major/multi-file changes require ExecPlans.
5. Keep localization terminology centralized in `docs/assistant/LOCALIZATION_GLOSSARY.md`.
6. Keep workspace performance defaults centralized in `docs/assistant/PERFORMANCE_BASELINES.md`.
7. After significant changes, ask exactly:
   - "Would you like me to run Assistant Docs Sync for this change now?"
8. Ask that prompt only when relevant touched-scope docs still remain unsynced; do not ask it again after the same-pass sync already happened.
9. Docs sync updates only relevant touched-scope docs.
10. If user requests parity/inspiration with named products/sites/apps, run reference discovery workflow before implementation decisions.
11. For support/non-technical explanations, route through user guides first.
12. For OpenAI products/APIs or unstable external facts, use official primary sources and include explicit verification date (`YYYY-MM-DD`).
13. For risk-triggered complex work, enforce staged execution and require exact continuation token format `NEXT_STAGE_X`.
14. For browser automation tasks, enforce workspace provenance lock, host fallback semantics (`unavailable|failed`), restricted-page fallback, and binary provenance packet fields.
15. For cloud-heavy machine evaluation, enforce cloud-first heavy runs, local human acceptance before apply, and no-auto-apply defaults.

## Enforcement Hooks
- `tooling/validate_agent_docs.dart`
- `tooling/validate_workspace_hygiene.dart`
- `tooling/automation_preflight.dart`
- `tooling/cloud_eval_preflight.dart`
- CI workflow checks in `.github/workflows/python-package.yml`
