# Assistant Docs Index

## Use when you need canonical architecture/status
- `APP_KNOWLEDGE.md`: canonical app architecture and status.
- `docs/assistant/APP_KNOWLEDGE.md`: short bridge for fast routing.

## Use when you need governance rules
- `agent.md`: operational runbook.
- `AGENTS.md`: compatibility shim.
- `docs/assistant/SESSION_RESUME.md`: first resume stop for `resume master plan` and fresh-session roadmap continuity.
- `docs/assistant/GOLDEN_PRINCIPLES.md`: enforceable rule source-of-truth.
- `docs/assistant/exec_plans/PLANS.md`: ExecPlan format and lifecycle.
- `docs/assistant/runtime/CANONICAL_BUILD.json`: canonical runnable build policy for Qt launch handoffs.
- `docs/assistant/ISSUE_MEMORY.md`: reusable per-project registry for repeated workflow/product issues.
- `docs/assistant/ISSUE_MEMORY.json`: machine-readable issue memory used by docs sync and bootstrap maintenance.
- `docs/assistant/LOCAL_ENV_PROFILE.local.md`: tracked local host/runtime profile for this repo.
- `docs/assistant/LOCAL_CAPABILITIES.md`: current machine/tool/skill capability inventory for this repo.

## Use when you need user-facing explanations
- `docs/assistant/features/APP_USER_GUIDE.md`: beginner support guide covering OCR advisor, review queue, job log save, and queue runs.
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`: primary workflow guide covering cost guardrails, review export, OCR advisor, and queue runner behavior.
- `docs/assistant/features/PRIMARY_FEATURE_USER_GUIDE.md`: compatibility shim to primary workflow guide.
- `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`: plain-language guide for the saved multi-root VS Code workspace and the active LegalPDF Git worktrees on this machine.

## Use when you need workflow routing
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`
- `docs/assistant/workflows/LOCALIZATION_WORKFLOW.md`
- `docs/assistant/workflows/PERFORMANCE_WORKFLOW.md`
- `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md`
- `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`
- `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`
- `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md`
- `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`
- `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`
- `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`
- `docs/assistant/workflows/CI_REPO_WORKFLOW.md`
- `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
- `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
- `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
- `docs/assistant/workflows/FEATURE_WORKFLOW.md` (compat shim)
- `docs/assistant/workflows/DATA_WORKFLOW.md` (compat shim)

## Use when you need source-backed external decisions
- `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`

## Use when you need audit packets and roadmap outputs
- `docs/assistant/audits/AUDIT_USAGE_PACKET_2026-03-05.md`
- `docs/assistant/audits/AUDIT_USAGE_PACKET_2026-03-05.json`
- `docs/assistant/audits/BOOTSTRAP_APPLICATION_AUDIT_2026-03-09.md`
- `docs/assistant/audits/PROJECT_HARNESS_ALIGNMENT_AUDIT_2026-03-09.md`
- `docs/assistant/audits/SIMILAR_APP_BENCHMARK_2026-03-05.md`
- `docs/assistant/audits/GAP_OPPORTUNITY_MAP_2026-03-05.md`
- `docs/assistant/audits/TOP5_UPGRADE_SPECS_2026-03-05.md`
- `docs/assistant/audits/ROADMAP_30_60_90_2026-03-05.md`
- `docs/assistant/audits/RELIABILITY_SIGNOFF_2026-03-05.md`: live final signoff packet for the 2026-03-05 staged implementation set.

## Use when you need validation
- `tooling/validate_agent_docs.dart`
- `tooling/validate_workspace_hygiene.dart`
- `tooling/automation_preflight.dart`
- `tooling/cloud_eval_preflight.dart`
- `tooling/qt_render_review.py` (deterministic wide/medium/narrow Qt renders for reference-locked UI review)
- `tooling/launch_qt_build.py` (canonical multi-worktree Qt launch helper that emits a build identity packet)
- `tooling/ocr_translation_probe.py` (small-slice OCR-heavy translation probe and safe-run packet)
- `test/tooling/validate_agent_docs_test.dart`
- `test/tooling/validate_workspace_hygiene_test.dart`
- `test/tooling/automation_preflight_test.dart`
- `test/tooling/cloud_eval_preflight_test.dart`

## Use when local Python is broken
- `scripts/setup_python311_env.ps1`: rebuilds a clean `.venv311` with project dependencies.

## Legacy supplemental deep docs
- `docs/assistant/API_PROMPTS.md`
- `docs/assistant/PROMPTS_KNOWLEDGE.md`
- `docs/assistant/QT_UI_KNOWLEDGE.md` (current Qt dashboard shell, launch path, and responsive invariants)
- `docs/assistant/QT_UI_PLAYBOOK.md` (Qt dashboard change recipes, deterministic render checks, and verification checklist)
- `docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md`
- `docs/assistant/WORKFLOW_GIT_AI.md`

## Template Read Policy
`docs/assistant/templates/*` is read-on-demand only.
Project-local harness application may read vendored templates when the user explicitly invokes `implement the template files` / `sync project harness`, but that flow must not edit the template folder.
