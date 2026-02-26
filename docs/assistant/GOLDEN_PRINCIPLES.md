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
8. Docs sync updates only relevant touched-scope docs.
9. If user requests parity/inspiration with named products/sites/apps, run reference discovery workflow before implementation decisions.
10. For support/non-technical explanations, route through user guides first.

## Enforcement Hooks
- `tooling/validate_agent_docs.dart`
- `tooling/validate_workspace_hygiene.dart`
- CI workflow checks in `.github/workflows/python-package.yml`
