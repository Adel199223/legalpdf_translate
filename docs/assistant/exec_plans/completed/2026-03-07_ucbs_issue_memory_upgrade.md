# UCBS Upgrade: Default Issue Memory and Automatic Build-Identity Safeguards

## Summary
Upgrade the Codex bootstrap so:
- every generated or upgraded project gets issue memory by default
- runnable app/GUI or explicit multi-worktree-risk projects automatically inherit worktree/build-identity safeguards

This is a bootstrap-system change only. It should not preseed fake incidents into generated project issue memory.

## Problem
- issue memory exists in the source project, but the bootstrap does not yet generate it as a default subsystem
- worktree/build identity guidance exists, but it is not yet auto-activated for the project classes that most need it
- the repeated wrong-build/window issue should influence the generated prevention rules, not be copied as a fake incident into new projects

## Files To Update
- `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md`
- `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
- `docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md`
- `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
- `docs/assistant/templates/BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md`
- `docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`
- `tooling/validate_agent_docs.dart`
- `test/tooling/validate_agent_docs_test.dart`

## Required Outcome
- issue memory is a default generated subsystem for new projects
- worktree/build identity safeguards auto-activate for runnable app/GUI or multi-worktree-risk projects
- validators fail if the template system stops generating or routing those rules

## Validation Gate
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
