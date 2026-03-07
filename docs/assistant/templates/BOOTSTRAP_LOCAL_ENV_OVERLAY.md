# Bootstrap Local Environment Overlay

## What This Module Is For
This is an optional machine-local overlay for personal harnesses.

Use it to teach a new project about the host it is being developed on without polluting the universal core contract for all users.

## Current Discovered Host Profile (2026-03-07)
- Host OS: Windows 11 Home 64-bit
- Dual-host workflow: Windows + WSL
- CPU: AMD Ryzen 9 7940HS
- RAM: 32 GB class system memory
- GPU 1: NVIDIA RTX 4070 Laptop GPU
- GPU 2: AMD Radeon 780M

## Design Rule
Treat this as a personal overlay only.
Generated projects should not assume every future user has this hardware or this host topology.

## Recommended Generated Files For New Projects
- `docs/assistant/LOCAL_ENV_PROFILE.local.md` for machine-local/private runtime facts
- optionally a tracked example/reference file if the repo needs to explain how to populate the local overlay

## Host Routing Guidance
### Prefer Windows When
- launching GUI desktop apps for visible end-user testing
- using Windows-only CLIs or auth flows
- browser/account integrations must share the same host/runtime environment as the app

### Prefer WSL/Linux When
- the task is pure code/docs/tooling and does not depend on Windows-only GUI or host auth state
- Linux-native tooling is more reliable than Windows shell usage for the task

### Same-Host Rule
If a feature depends on local auth state or GUI binding, the tool must be validated on the same OS/runtime environment as the app that will consume it.

Examples:
- Gmail or other desktop/browser-authenticated CLI integrations
- local browser profile or extension automation
- desktop-window control or UI-driving tools

## Performance and Tolerance Guidance
- This host can tolerate local OCR/desktop/UI testing and moderate local automation work.
- GPU-accelerated or visually heavy work is reasonable locally when the stack supports it.
- For heavy cloud/API evaluation or large expensive runs, prefer cloud-first workflows with local acceptance gates.
- New repos should encode these as routing hints, not as global always-on defaults.
