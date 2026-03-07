# Workflow Hardening for Qt UI and OCR Triage

## Goal and non-goals
- Goal: convert the recent Qt UI replication and OCR-heavy translation debugging lessons into reusable docs and lightweight tooling.
- Non-goal: change product-facing translation behavior or add new app features.

## Scope (in/out)
- In: assistant workflow docs, routing docs, manifest/index discoverability, lightweight Qt render tooling, lightweight OCR triage tooling, validation coverage.
- Out: prompt rewrites, OCR engine/provider behavior changes, Qt feature redesign, schema changes.

## Interfaces/types/contracts affected
- Assistant workflow routing in `docs/assistant/manifest.json`
- Assistant workflow documentation under `docs/assistant/workflows/`
- Internal-only helper CLIs in `tooling/`

## File-by-file implementation steps
1. Add reusable workflow docs for reference-locked Qt UI work and OCR-heavy translation triage.
2. Update routing docs (`APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, `docs/assistant/INDEX.md`, `docs/assistant/QT_UI_PLAYBOOK.md`, `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`, `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`).
3. Add deterministic helper scripts for Qt render review and OCR-heavy probe runs.
4. Add tests for the new helper tooling and validator discoverability rules.
5. Run docs/workspace validators and targeted Python tests.

## Tests and acceptance criteria
- New workflow docs are routed from both `INDEX.md` and `manifest.json`.
- Qt render helper produces deterministic wide/medium/narrow captures.
- OCR probe helper emits a stable packet and safe runbook command path.
- Docs validators pass and targeted helper tests pass.

## Rollout and fallback
- Keep changes internal-only and local-first.
- If the new helper tooling proves too invasive, retain the workflow docs and reduce helper scope to non-executing probe/report output.

## Risks and mitigations
- Risk: new workflow docs drift from validator-required structure. Mitigation: follow existing workflow headings and update validator tests where needed.
- Risk: helper tooling collides with active product work on the branch. Mitigation: keep edits in docs/tooling paths and avoid product modules unless imported read-only.

## Assumptions/defaults
- Windows-native GUI launch remains canonical.
- Desktop exactness is the authoritative UI acceptance mode.
- OCR-heavy triage should begin with small-page acceptance, not a full-document retry.
