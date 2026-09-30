# Reproducible Windows development workstation — 2026-09-30

## Subsequent user authorization

The original implementation-only scope below is preserved historical evidence. After local delivery, the user explicitly selected **Both**: publish/merge the files and apply setup on this PC. Current work follows the [publication/application plan](2026-09-30_workstation_publication_and_application.md); its exact receipts supersede earlier uncommitted/no-install status only after the corresponding operation succeeds. No additional continuation token is required for the approved lifecycle.

## Goal and non-goals

Make the existing Windows development tool baseline discoverable and repeatable without replacing Python 3.11.9, uv 0.12.20 or the locked Python environment. Deliver a tailored WinGet configuration, read-only readiness checks, pinned Node/Dart CI inputs and concise setup guidance. No installation, service activation, live Gmail, native Word launch, provider dispatch, publication or dependency upgrade is authorized.

## Scope

In: workstation tool metadata/configuration, readiness script and regression tests, CI version inputs, touched setup/validation/architecture/handoff documentation. Out: application behavior/contracts, Python environment setup semantics, OS settings, WSL/Docker provisioning, secrets and private data.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/worktrees/reproducible-workstation/legalpdf_translate`
- Branch: `feat/reproducible-workstation-20260930`
- Base branch: `main`
- Base SHA: `90485237c00b95aa9744b32aa4684d16ec06e100`
- Approved-base floor: `4e9d20e`, verified ancestor before branching.
- Eventual integration target: `main`; publication is outside this task.
- Status: noncanonical development worktree; no application services will be launched.

## Interfaces and contracts

New workstation checking/configuration interfaces only. Python pins, `uv.lock`, existing setup/recovery behavior, app routes/payloads/select values, Gmail/native contracts and safe rendering remain unchanged. WinGet package/resource capabilities and exact version availability must be supported by official primary sources; absent tools require explicit manual guidance rather than invented package/version support.

## Implementation steps

1. Verify official WinGet resource/version semantics and exact package availability; record sources and limitations.
2. Add Node/Dart version files for the observed working baseline (24.14.0/3.11.0), machine-tool configuration and a bounded read-only readiness script.
3. Pin CI Node/Dart inputs without changing required job/shard contracts; add realistic sandbox checks for success, missing tools, mismatch and native failures.
4. Update README, architecture, validation, handoff and external-source guidance only within setup scope; preserve replaced documentation beforeimages.
5. Run targeted setup checks, configuration validation, standard development checks and selected Full. Retain evidence in ignored worktree `tmp/` and close the plan after completion.

## Tests and acceptance criteria

- Static configuration/schema/pin coherence checks and official package evidence, without applying WinGet or downloading/installing processors.
- Read-only actual tool checks and script regressions with recording fake executables; no installer, network, service or live-state mutation can occur.
- Existing Python setup/recovery tests still pass.
- Node/Dart pinned versions execute relevant existing checks; required selected Full and docs/hygiene complete with the known direct-Dart fallback recorded if needed.
- Existing `.python-version`, Python setup script, `uv.lock` and canonical checkout remain unchanged.

## Rollout and fallback

Delivery remains as uncommitted isolated worktree files. Readiness checks are safe entry points; actual workstation provisioning remains a separately authorized operation. Existing Python setup remains canonical. An older workstation may report version differences; no readiness check repairs or upgrades it.

## Risks and mitigations

- WinGet configurations may install processors or packages: only offline/local structural checks run here; document apply-time effects.
- Exact historic packages can disappear: record verification date and retain explicit manual source alternatives; never fall back silently to latest.
- Word/Gmail native dependencies cannot be reconstructed by Linux containers: document Windows/Word/manual prerequisites separately.
- Existing Dart wrapper fault: retain and use its direct-SDK fallback, without reinstalling tooling.
- CI hosting is untested locally: distinguish local checks from future hosted CI.

## Assumptions and defaults

The observed tool versions are a compatibility baseline, not recommendations to upgrade every tool. No stages involving external execution/publication are requested; this bounded tooling change has no live-state or provider risk requiring continuation tokens. Existing canonical Python is used read-only from the worktree when necessary, with worktree source precedence and isolated test data.

## Progress and validation

- Initial repository/instruction review complete; canonical `main` clean at the base SHA.
- Managed worktree created and feature branch established.
- Official package manifests and published DSC 1.12.440 resource/module contracts verified; six exact package mappings are available. PowerShell and Python remain deliberate manual prerequisites. The project WinGet floor is conservatively 1.12.440, distinct from Microsoft's feature floor.
- Added `.node-version`, `.dart-version`, baseline JSON, JSON-compatible YAML recipe, read-only checker, sandbox/CI tests and setup guidance. Existing Python pins, lock and setup/recovery code are unchanged.
- Peer review corrected the schema URL to actual Microsoft schema 0.2 and prevented both discovered and explicitly selected Flutter batch wrappers from bootstrapping during readiness checks. Existing direct SDKs are selected before execution. Native fake SDK tests verify those boundaries.
- All 35 workstation sandbox cases and seven CI-coherence cases passed together (42 in 47.79 seconds); all 22 existing Python setup/recovery regressions passed (13.24 seconds). No tools are invoked in configuration-only mode, required failures are nonzero, optional differences are advisory, and temporary fixture/environment bytes are preserved.
- Actual readiness passes (PowerShell 7.6.5 advisory); built-in PowerShell Test-Json passes against the downloaded official Microsoft schema. No online WinGet processor/catalog validation or installation was performed.
- Standard validation passed 249 tests (56.43 seconds). Required selected Full passed 1,389 executions with nine expected intake deselections: 249+2+5+239+191+157+117+429. Its two formatting workers passed 105/86 cases with complete collection/execution/JUnit receipts. Compilation and docs/hygiene passed using the direct-Dart fallback after retained AOT wrapper exit 255 events. All agent-docs and seven hygiene validator tests passed.
- Source/test/workflow/configuration hashes were frozen during Full and are checked at closeout. Canonical Python was reused through a temporary ignored worktree junction, with bytecode disabled, worktree source precedence and child-only offscreen fonts; setup/recreation was never invoked against that link. Remove the temporary link after validation without following its target.
- Scoped documentation beforeimages, logs, official schema and preservation/validation receipts are retained under `tmp/workstation-beforeimages/` and `tmp/workstation-validation/`. No installed tools, live services/environment, credentials, Gmail, Word or provider state were changed by this task. No commit, push, merge or deployment was performed.
- Delivery is complete as uncommitted isolated worktree files. Hosted CI, provisioning success and canonical adoption remain outside this request.
