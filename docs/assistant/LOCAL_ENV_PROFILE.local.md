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
- launching the Qt app for visible end-user testing
- validating Gmail draft creation through Windows `gog`
- using browser/account-linked tooling that must share auth state with the desktop app
- debugging desktop-window behavior, focus, or visible UI issues

### Prefer WSL When
- the task is pure code/docs/tooling without Windows-only GUI or auth coupling
- shell tooling is faster or more reliable in Linux than in PowerShell
- validator/test automation does not depend on a visible Windows desktop session

### Same-Host Rule
If the feature depends on local auth state, browser state, or desktop runtime state, validate it on the same host where the app runs.

Examples in this repo:
- Gmail draft creation through Windows `gog`
- visible Qt app testing
- browser/account-linked local tooling

## Performance and Tolerance Guidance
- This machine can tolerate local Qt/UI testing, OCR validation, and moderate local automation work.
- GPU-backed or visually heavy checks are reasonable locally when the stack supports them.
- Heavy cloud/API evaluation should still prefer cloud-first workflows with a local acceptance gate.

## No Secrets Rule
- Do not store API keys, OAuth client secrets, account passwords, or bearer tokens in this file.
- Record only non-secret operational facts and routing guidance.
