from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def _run_api_probe() -> dict[str, dict[str, object]]:
    script = """
const apiModule = await import(__API_MODULE_URL__);

async function captureNetworkCase(name, url, bootstrap, state) {{
  globalThis.window = {{
    location: new URL(url),
    LEGALPDF_BROWSER_BOOTSTRAP: bootstrap,
  }};
  globalThis.fetch = async () => {{
    throw new TypeError("Failed to fetch");
  }};
  try {{
    await apiModule.fetchJson("/api/bootstrap", state);
    return {{ name, status: "ok" }};
  }} catch (error) {{
    const details = apiModule.describeLocalServerUnavailable(error);
    return {{
      name,
      status: "failed",
      message: error.message,
      diagnosticsError: error.payload?.diagnostics?.error || "",
      isLocalServerUnavailable: Boolean(apiModule.isLocalServerUnavailableError(error)),
      title: details.title,
      recommendedUrl: details.recommendedUrl,
      launcherCommand: details.launcherCommand,
      workspaceId: details.workspaceId,
      port: details.port,
    }};
  }}
}}

async function captureBackendCase() {{
  globalThis.window = {{
    location: new URL("http://127.0.0.1:8877/?mode=shadow&workspace=workspace-alpha#new-job"),
    LEGALPDF_BROWSER_BOOTSTRAP: {{
      shadowHost: "127.0.0.1",
      shadowPort: 8877,
      defaultRuntimeMode: "shadow",
      defaultWorkspaceId: "workspace-alpha",
      defaultUiVariant: "qt",
    }},
  }};
  globalThis.fetch = async () => {{
    return {{
      ok: false,
      status: 422,
      async text() {{
        return JSON.stringify({{
          status: "failed",
          diagnostics: {{
            error: "Backend says no.",
          }},
        }});
      }},
    }};
  }};
  try {{
    await apiModule.fetchJson("/api/bootstrap", {{
      runtimeMode: "shadow",
      workspaceId: "workspace-alpha",
    }});
    return {{ name: "backend", status: "ok" }};
  }} catch (error) {{
    return {{
      name: "backend",
      status: "failed",
      message: error.message,
      isLocalServerUnavailable: Boolean(apiModule.isLocalServerUnavailableError(error)),
      diagnosticsError: error.payload?.diagnostics?.error || "",
    }};
  }}
}}

const results = [];
results.push(await captureNetworkCase(
  "preview",
  "http://127.0.0.1:8888/?mode=shadow&workspace=workspace-old#dashboard",
  {{
    shadowHost: "127.0.0.1",
    shadowPort: 8888,
    defaultRuntimeMode: "shadow",
    defaultWorkspaceId: "workspace-old",
    defaultUiVariant: "qt",
  }},
  {{
    runtimeMode: "shadow",
    workspaceId: "workspace-old",
  }},
));
results.push(await captureNetworkCase(
  "daily",
  "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job",
  {{
    shadowHost: "127.0.0.1",
    shadowPort: 8877,
    defaultRuntimeMode: "live",
    defaultWorkspaceId: "workspace-1",
    defaultUiVariant: "qt",
  }},
  {{
    runtimeMode: "live",
    workspaceId: "workspace-1",
  }},
));
results.push(await captureBackendCase());
console.log(JSON.stringify(results));
""".replace("{{", "{").replace("}}", "}")
    payload = run_browser_esm_json_probe(
        script,
        {"__API_MODULE_URL__": "api.js"},
        timeout_seconds=20,
    )
    return {entry["name"]: entry for entry in payload}


def _run_bootstrap_hydration_probe() -> dict[str, dict[str, object]]:
    script = """
const hydrationModule = await import(__BOOTSTRAP_HYDRATION_MODULE_URL__);

const initial = hydrationModule.buildInitialClientReadyState({{
  href: "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
  defaultRuntimeMode: "live",
  defaultWorkspaceId: "gmail-intake",
  defaultUiVariant: "qt",
  buildSha: "5c9842e",
}});

const retryEvents = [];
let gmailFullAttempts = 0;
const stagedGmail = await hydrationModule.runStagedBootstrap({{
  routeContext: {{
    workspaceId: "gmail-intake",
    activeView: "gmail-intake",
  }},
  fetchShell: async () => ({{ shell: "ready" }}),
  fetchFull: async () => {{
    gmailFullAttempts += 1;
    if (gmailFullAttempts < 3) {{
      throw new Error(`warmup-${{gmailFullAttempts}}`);
    }}
    return {{ status: "ok", attempts: gmailFullAttempts }};
  }},
  sleep: async () => undefined,
  onRetry: (event) => retryEvents.push({{
    attempt: event.attempt,
    maxAttempts: event.maxAttempts,
    delayMs: event.delayMs,
    message: event.error.message,
  }}),
}});

let standardFullAttempts = 0;
const stagedStandard = await hydrationModule.runStagedBootstrap({{
  routeContext: {{
    workspaceId: "workspace-1",
    activeView: "new-job",
  }},
  fetchShell: async () => ({{ shell: "ready" }}),
  fetchFull: async () => {{
    standardFullAttempts += 1;
    return {{ status: "ok", attempts: standardFullAttempts }};
  }},
  sleep: async () => undefined,
}});

console.log(JSON.stringify({{
  initial,
  stagedGmail,
  retryEvents,
  stagedStandard,
}}));
""".replace("{{", "{").replace("}}", "}")
    return run_browser_esm_json_probe(
        script,
        {"__BOOTSTRAP_HYDRATION_MODULE_URL__": "bootstrap_hydration.js"},
        timeout_seconds=20,
    )


def test_shadow_web_fetch_json_normalizes_dead_preview_and_daily_ports() -> None:
    results = _run_api_probe()

    preview = results["preview"]
    assert preview["status"] == "failed"
    assert preview["isLocalServerUnavailable"] is True
    assert preview["diagnosticsError"] == "local_server_unavailable"
    assert preview["title"] == "Review preview unavailable"
    assert preview["port"] == 8888
    assert preview["workspaceId"] == "workspace-preview"
    assert preview["recommendedUrl"] == "http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job"
    assert "--workspace workspace-preview --port 8888" in str(preview["launcherCommand"])

    daily = results["daily"]
    assert daily["status"] == "failed"
    assert daily["isLocalServerUnavailable"] is True
    assert daily["diagnosticsError"] == "local_server_unavailable"
    assert daily["title"] == "Browser app unavailable"
    assert daily["port"] == 8877
    assert daily["workspaceId"] == "workspace-1"
    assert daily["recommendedUrl"] == "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job"
    assert str(daily["launcherCommand"]).endswith("tooling\\launch_browser_app_live_detached.py")


def test_shadow_web_fetch_json_preserves_backend_failures() -> None:
    results = _run_api_probe()

    backend = results["backend"]
    assert backend["status"] == "failed"
    assert backend["message"] == "Backend says no."
    assert backend["isLocalServerUnavailable"] is False
    assert backend["diagnosticsError"] == "Backend says no."


def test_shadow_web_bootstrap_hydration_uses_gmail_route_defaults_and_retry_budget() -> None:
    results = _run_bootstrap_hydration_probe()

    assert results["initial"] == {
        "status": "warming",
        "runtimeMode": "live",
        "workspaceId": "gmail-intake",
        "activeView": "gmail-intake",
        "gmailHandoffState": "warming",
        "buildSha": "5c9842e",
        "assetVersion": "",
        "bootstrappedAt": None,
    }
    assert results["stagedGmail"]["attempts"] == 3
    assert results["stagedGmail"]["retries"] == 2
    assert results["stagedGmail"]["shellPayload"] == {"shell": "ready"}
    assert results["stagedGmail"]["fullPayload"] == {"status": "ok", "attempts": 3}
    assert results["retryEvents"] == [
        {
            "attempt": 1,
            "maxAttempts": 6,
            "delayMs": 200,
            "message": "warmup-1",
        },
        {
            "attempt": 2,
            "maxAttempts": 6,
            "delayMs": 350,
            "message": "warmup-2",
        },
    ]
    assert results["stagedStandard"]["attempts"] == 1
    assert results["stagedStandard"]["retries"] == 0
    assert results["stagedStandard"]["fullPayload"] == {"status": "ok", "attempts": 1}
