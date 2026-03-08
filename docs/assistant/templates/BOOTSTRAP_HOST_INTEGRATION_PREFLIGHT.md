# Bootstrap Host Integration Preflight

## What This Module Is For
This module covers integrations that depend on local host state, local installations, local auth, or desktop/browser-coupled tooling.

The purpose is to stop teams from building a feature before proving the environment can actually support it.

## Activation Rule
Enable this module when the project involves integrations such as:
- authenticated local CLIs
- browser/account-linked tooling
- desktop-specific automation
- same-host runtime dependencies

## Preflight Sequence
Before building the integration, verify in this order:
1. tool installation exists on the target host
2. auth/account state is available
3. the app and the integration run in the same host/runtime environment when required
4. if a localhost listener is required, verify the port is owned by the expected process and not by a stale or unrelated test/runtime process
5. a live smoke check succeeds before feature implementation proceeds

## Same-Host Validation Rule
If the app will run on Windows, and the integration depends on Windows-local auth or desktop state, validate it on Windows.
If the app will run inside WSL or Linux, validate the integration there.

Do not assume that a tool working on one host means it works in the host where the app runs.

## Failure Classification
- `unavailable`: install/auth/host preflight failed
- `unavailable`: localhost bind conflict or unexpected listener ownership blocked the real integration host
- `failed`: the integration ran, but the feature behavior itself failed

## Listener Ownership Rule
If a localhost listener is required:
- verify the port is owned by the expected process before declaring the integration healthy
- classify bind conflicts or unexpected listeners as `unavailable`
- make listener-startup conflicts visible instead of leaving them as silent logs

## Example Pattern
A Gmail draft feature backed by a local authenticated CLI is just one example.
The reusable rule is broader:
- verify installation
- verify account auth
- verify the app host can access the same auth
- run a minimal real smoke test before building the full feature
