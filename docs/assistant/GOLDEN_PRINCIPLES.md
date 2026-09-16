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
7. Standing user authorization (2026-09-16) permits useful Docs Sync without renewed approval; do not ask again.
8. Update only relevant touched-scope docs; no blanket rewrites or template application.
9. Keep current guidance concise and preserve exact dated evidence before replacing historical detail.
10. Defer maintenance only when it is unnecessary or conflicts with an active scoped freeze, then record the remaining work.
11. Docs Sync does not authorize publication, destructive actions, live Gmail or additional paid/native operations.
12. If user requests parity/inspiration with named products/sites/apps, run reference discovery workflow before implementation decisions.
13. For support/non-technical explanations, route through user guides first.
14. For OpenAI products/APIs or unstable external facts, use official primary sources and include explicit verification date (`YYYY-MM-DD`).
15. For risk-triggered complex work, use staged execution and its `NEXT_STAGE_X` gates when applicable. Current explicit user authorization takes precedence; do not renew already satisfied gates or treat historical tokens as new restrictions.
16. For browser automation tasks, enforce workspace provenance lock, host fallback semantics (`unavailable|failed`), restricted-page fallback, and binary provenance packet fields.
17. For cloud-heavy machine evaluation, enforce cloud-first heavy runs, local human acceptance before apply, and no-auto-apply defaults.

## Enforcement Hooks
- `tooling/validate_agent_docs.dart`
- `tooling/validate_workspace_hygiene.dart`
- `tooling/automation_preflight.dart`
- `tooling/cloud_eval_preflight.dart`
- CI workflow checks in `.github/workflows/python-package.yml`
