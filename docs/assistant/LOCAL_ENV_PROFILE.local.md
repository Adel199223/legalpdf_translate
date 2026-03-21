# Local Environment Profile

## Purpose
This file records the host/runtime facts that materially affect work in this repo.

It is intentionally tracked here because this repo is a personal harness and the contents are operationally useful but non-secret.

## Current Host Profile
- Host OS: Windows 11 Home 64-bit
- Host topology: dual-host workflow (`Windows + WSL`)
- CPU: AMD Ryzen 9 7940HS
- Memory: 32 GB RAM
- GPU 1: NVIDIA RTX 4070 Laptop GPU
- GPU 2: AMD Radeon 780M

## Routing Rules
### Prefer Windows When
- launching the local browser app in `live` mode for real user work
- validating browser-app Gmail bridge ownership and extension handoff
- launching the Qt app for visible end-user testing
- validating Gmail draft creation through Windows `gog`
- validating the Arabic DOCX Word review gate or `Align Right + Save`
- using browser/account-linked tooling that must share auth state with the desktop app
- debugging desktop-window behavior, focus, or visible UI issues

### Prefer WSL When
- the task is pure code/docs/tooling without Windows-only GUI or auth coupling
- shell tooling is faster or more reliable in Linux than in PowerShell
- validator/test automation does not depend on a visible Windows desktop session

### Same-Host Rule
If the feature depends on local auth state, browser state, or desktop runtime state, validate it on the same host where the app runs.

Examples in this repo:
- browser-app `live` mode, Gmail bridge ownership, and extension handoff
- browser-app `shadow` mode when a risky isolated test should not touch live data
- Gmail draft creation through Windows `gog`
- visible Qt app testing
- Arabic DOCX review through Windows Word / PowerShell COM automation
- browser/account-linked local tooling
- browser-app live daily-use URL: `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job`
- browser-app isolated test URL: `http://127.0.0.1:8877/?mode=shadow&workspace=workspace-1#new-job`
- browser-app Gmail handoff URL: `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
- fixed browser review-preview URL: `http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job`

Before browser/app or bridge triage on Windows, verify any required localhost listener is owned by the expected process. Unexpected listener ownership is a preflight `unavailable` condition, not a product failure.

For browser-shell review work, keep `8877` for the normal daily browser app and `8888` for the fixed feature-preview contract. If an old cached preview tab shows fetch failures on `8888`, relaunch the preview instead of treating it as a product-runtime regression on the daily app.

For the Arabic DOCX review gate, WSL-only validation is insufficient because Word automation, visible Word editing, and save-detection behavior are Windows-host runtime facts.

## Performance and Tolerance Guidance
- This machine can tolerate local Qt/UI testing, OCR validation, and moderate local automation work.
- GPU-backed or visually heavy checks are reasonable locally when the stack supports them.
- Heavy cloud/API evaluation should still prefer cloud-first workflows with a local acceptance gate.

## No Secrets Rule
- Do not store API keys, OAuth client secrets, account passwords, or bearer tokens in this file.
- Record only non-secret operational facts and routing guidance.
