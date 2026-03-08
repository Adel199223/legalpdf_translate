# Bootstrap Harness Isolation and Diagnostics

## What This Module Is For
This module covers projects where tests or multi-stage runtime workflows can accidentally collide with live machine state or become expensive to debug because evidence is split across too many surfaces.

The goal is to prevent false regressions caused by harness contamination and to make cross-surface incidents debuggable without reconstructing the story from thread memory.

## Activation Rule
Enable this module when the project has any of:
- a runnable app with localhost listeners, background workers, or host-owned runtime state
- a browser/app/CLI/desktop workflow that spans more than one failure surface
- tests that could accidentally reuse live settings, ports, auth state, caches, or machine-local files

## Default Isolation Rules
Generated projects should define these rules by default:
- tests must run against temporary filesystem and environment state unless a test explicitly opts into live host state
- tests must not read or write live user settings paths, caches, or roaming profile files by default
- tests must use non-live or ephemeral ports by default instead of the user-facing runtime port
- tests must tear down listeners, windows, service processes, and background workers even when a test fails
- authenticated machine state must be explicit opt-in for tests, never inherited silently

## Listener Ownership and Runtime Conflict Rules
For localhost or same-host integrations, generated projects should require:
- verifying that the expected listener port is owned by the expected process before treating the integration as healthy
- classifying port bind conflicts or unexpected listeners as `unavailable`, not as product `failed`
- showing visible runtime status when listener startup fails instead of logging silently

## Durable Session Diagnostics Rule
When a workflow spans handoff, per-item execution, and finalization:
- keep existing per-run artifacts as the main run evidence
- add an additive `workflow_context` or equivalent block when a run belongs to a larger session
- define one durable app-owned session artifact that lives with other durable outputs
- include session id, started timestamp, status, halt reason, handoff/source context, per-item run linkage, finalization state, and final output names when relevant
- do not create a separate browser or extension report file by default; browser-side evidence should remain transient UI/banner/console output unless the project has a strong reason to persist it

## Support Packet Order
Generated docs should define a compact troubleshooting packet in this order:
1. user-visible browser/banner/UI error if handoff failed before app intake
2. app build identity and visible runtime status
3. per-run report plus machine-readable run summary for the affected execution
4. app-owned session artifact for multi-stage or finalization issues

## Validation Pack Rule
Generated repos should keep a focused reliability pack for host-bound workflows:
- intake and handoff behavior
- listener ownership and bind-conflict handling
- test isolation from live settings and ports
- per-run artifact integrity
- finalization/export/draft integrity
- diagnostics rendering and report linkage

## Example Pattern
Examples vary by stack, but the reusable pattern is stable:
- pytest commonly uses temporary directories plus environment monkeypatching to isolate tests from the running user
- browser extensions commonly use action-scoped access and runtime script injection to recover stale tabs without broad permanent access

The broader harness rule is:
- isolate tests from live machine state
- make runtime ownership conflicts visible
- keep one durable app-owned session artifact for multi-surface debugging
