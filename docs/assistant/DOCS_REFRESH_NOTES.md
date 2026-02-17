# Docs Refresh Notes

Use this file when updating docs/assistant/* is deferred.
Append an entry whenever `src/` or `tests/` change and the user did NOT request a docs refresh.

## Template (copy for new entries)
## YYYY-MM-DD — <branch> (<commit>)
- Files changed:
  - <path>
- Key symbols / entrypoints changed:
  - <file>::<symbol>
- User-visible behavior:
  - <bullet>
- Tests:
  - python -m pytest -q
  - python -m compileall src tests


## Entries

## 2026-02-17 — fix/qt-settings-claude-guardrails (eb6f84e)
- Files changed:
  - CLAUDE.md
  - src/legalpdf_translate/qt_gui/app_window.py
  - src/legalpdf_translate/qt_gui/dialogs.py
  - tests/test_qt_app_state.py
- Key symbols / entrypoints changed:
  - src/legalpdf_translate/qt_gui/app_window.py::_FuturisticCanvas
  - src/legalpdf_translate/qt_gui/dialogs.py::_StudyCandidateWorker
  - tests/test_qt_app_state.py::test_schedule_save_settings_starts_timer
- User-visible behavior:
  - Qt settings UI/app-state behavior adjusted (see commit eb6f84e).
  - Coding-agent guardrails updated in CLAUDE.md (token efficiency + triggers + safety/validation).
- Tests:
  - python -m pytest -q (443 passed)
  - python -m compileall src tests (success)

