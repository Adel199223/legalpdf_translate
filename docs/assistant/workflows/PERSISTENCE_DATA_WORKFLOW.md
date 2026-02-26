# PERSISTENCE_DATA_WORKFLOW

## What This Workflow Is For
Managing persistence/data concerns including joblog schema, run-state artifacts, settings schema, and migration safety.

## Expected Outputs
- Data/persistence scoped changes with migration safety.
- Verified backward compatibility for existing user data.
- Targeted migration and persistence test results.

## When To Use
- Changes to SQLite schema/migrations.
- Changes to settings schema defaults/migration logic.
- Changes to checkpoint/run artifact compatibility.

## What Not To Do
- Don't use this workflow when changing only product UX behavior.
- Instead use `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`.

## Primary Files
- `src/legalpdf_translate/joblog_db.py`
- `src/legalpdf_translate/checkpoint.py`
- `src/legalpdf_translate/user_settings.py`
- `docs/assistant/DB_DRIFT_KNOWLEDGE.md`

## Minimal Commands
```powershell
python -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_checkpoint_resume.py
python -m pytest -q tests/test_user_settings_schema.py
```

## Targeted Tests
- `tests/test_db_migration_joblog_v2.py`
- `tests/test_checkpoint_resume.py`
- `tests/test_user_settings_schema.py`

## Failure Modes and Fallback Steps
- Migration incompatibility: stop rollout, restore backup, patch migration for additive compatibility.
- Schema drift on existing installs: add compatibility migration and retest from old schema snapshots.
- Settings coercion drops user data: add roundtrip tests and restore tolerant migration path.

## Handoff Checklist
1. Document schema/settings deltas.
2. Provide migration safety notes.
3. Include targeted tests and outcomes.
4. Confirm approval gate handling for risky operations.
