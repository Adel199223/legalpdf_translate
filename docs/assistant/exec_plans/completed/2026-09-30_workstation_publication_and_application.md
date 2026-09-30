# Workstation publication and application — 2026-09-30

## Goal and non-goals

The user explicitly selected **Both**: publish/merge the validated workstation files and apply the setup on this PC. Complete the normal PR, exact-head checks, merge and canonical application lifecycle, then verify the installed tool baseline. Preserve the existing Python environment, locked packages and live application data. No Gmail, Word, provider or app-default operation belongs to this task.

## Scope

In: the completed [workstation implementation](../completed/2026-09-30_reproducible_workstation_setup.md), a bounded full-version parsing correction found in final review, scoped continuity docs, GitHub publication and six pinned workstation packages. Out: Python/environment recreation, dependency upgrades, WSL/Docker activation, OS tuning and unrelated side-worktree changes.

## Worktree provenance

- Authoring path: `C:/Users/FA507/.codex/worktrees/reproducible-workstation/legalpdf_translate`
- Branch: `feat/reproducible-workstation-20260930`
- Base and integration branch: `main`
- Base SHA: `90485237c00b95aa9744b32aa4684d16ec06e100`, verified equal to freshly fetched origin/main.
- Approved floor: `4e9d20e`, verified ancestor.
- Canonical application path: `C:/Users/FA507/.codex/legalpdf_translate`, currently clean main at the same base; no listeners on the LegalPDF ports.

## Interfaces and contracts

Compare the complete reported tool version, so a prerelease cannot satisfy a stable pin. Application contracts and Python setup semantics remain unchanged. Use authenticated GitHub connector operations because the local gh credential is invalid; never expose or replace credentials.

## Implementation steps

1. Correct checker version parsing and add fictional prerelease regressions in the existing script/test files.
2. Preserve beforeimages and synchronize APP_KNOWLEDGE, HANDOFF, SESSION_RESUME and setup-guide lifecycle status.
3. Run focused checks and required Full on the frozen final tree, commit the reviewed scope, push and create a PR.
4. Wait for complete successful exact-head CI and clean review/lineage, then merge and fast-forward clean canonical main.
5. Apply the exact tracked recipe using supported WinGet tooling; if the configuration processor is unavailable, investigate and record a supported equivalent package path rather than inventing capabilities or changing versions.
6. Verify all six package versions, direct SDK readiness, preserved Python inputs/package versions, service state and clean repository state. Retain evidence before archiving the authoring worktree.

## Tests and acceptance criteria

Focused workstation/CI/recovery checks and required selected Full must pass after the parsing correction. Required hosted jobs must pass for the actual reviewed SHA before merge. Provisioning success must be verified separately from offline checks or local tests. Python pins, lock, setup code and installed package versions must remain unchanged.

## Rollout and fallback

Use standard PR flow, no force push or direct main publication. Installation targets the six pinned package identities only; already matching packages require no change. Keep historical failed validation/application attempts and report any unresolved blocker. Worktree cleanup must preserve ignored receipts and beforeimages outside the checkout before archiving.

## Risks and mitigations

Exact configuration resources can reinstall mismatched versions; targeted inventory shows five pinned packages already match, while standalone Dart is absent. WinGet 1.29.380 requires extended configuration features: initial validation reported them disabled, and the supported Store enable attempt returned E_ABORT. Preserve this failure and determine a supported fallback. Do not enable disabled administrative overrides or alter WSL/Docker.

## Assumptions and defaults

Current explicit approval covers publication and workstation application continuously; earlier implementation-only boundaries are historical. This bounded setup lifecycle needs no additional continuation token. Existing project Python is used read-only for validation, with isolated fixtures and child-only environment settings.

## Branch closeout and remaining publication gates

Local implementation and workstation application are complete. The checker retains complete version tokens and safely rejects prereleases for minimum checks; nine new fictional cases bring workstation/CI checks to 51 passing cases, alongside the existing 22 passing Python recovery cases. Independent review found no remaining issue. The final source/test/configuration tree is frozen during required selected Full revalidation; the original 1,389-pass Full remains separate evidence, and the new outcome belongs to `full-02-result.json`.

Fresh online WinGet validation passed. The exact tracked recipe then applied all six units successfully with exit 0, adding standalone Dart 3.11.0 while the other five already matched. All six installed package versions and direct standalone-Dart readiness were verified. Both processor modules are pinned to 1.12.440. All 58 currently discovered Python distributions and the protected Python pin/lock/setup inputs remain unchanged; Docker remains stopped/manual and WSL stopped/disabled. Original failed/aborted enable and agreement attempts remain preserved rather than relabeled as successful application.

This completed plan closes implementation and rollout decisions before merge; commit/PR/required exact-head CI, merge, canonical fast-forward and cleanup are the remaining authorized publication gates under COMMIT_PUBLISH_WORKFLOW. Their terminal state is owned by `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/workstation_setup_20260930_01/publication_01/publication_receipt.json`. If that receipt is complete, no action remains. Do not infer a merge from this completed local plan.

Beforeimages and original/new validation/application logs are retained under the same evidence root before worktree archival. No live app, Word, Gmail, provider, saved-default or environment recreation operation occurred.
