# Project Rules

- Minimal diffs only — no refactors unless explicitly asked.
- Do not change the translation provider or model unless explicitly asked.
- Prefer Qt GUI as the active UI.
- Never print or store secrets (API keys).

## Validation (always run)

```
python -m pytest -q
python -m compileall src tests
```
