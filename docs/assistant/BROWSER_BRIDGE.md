# Browser Bridge

The local browser app is the primary daily-use interface for this repo. The Qt desktop shell is the fallback and secondary shell when the browser app is unavailable or cannot take ownership of the live workflow.

## Canonical URLs And Ports

- Live daily-use URL on port `8877`: `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job`
- Shadow isolated testing URL on port `8877`: `http://127.0.0.1:8877/?mode=shadow&workspace=workspace-1#new-job`
- Gmail handoff workspace URL on port `8877`: `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
- Preview and review URL on port `8888`: `http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job`

## Bridge Ownership Expectations

- The browser app owns the live Gmail bridge when it is available.
- The real Gmail extension and native host should hand off to the browser app first.
- Qt is fallback only when browser launch is unavailable and no healthy browser-owned bridge already exists.
- The preview listener on port `8888` never owns the live Gmail bridge.

## Validation Scope

- Browser bridge validation is Windows-host-bound.
- A WSL-only validation pass is not sufficient for the live Gmail bridge.
