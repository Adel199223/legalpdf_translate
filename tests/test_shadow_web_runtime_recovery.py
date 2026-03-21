from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _run_api_probe() -> dict[str, dict[str, object]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for shadow web recovery coverage.")

    module_url = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "api.js"
    ).as_uri()

    script = f"""
const apiModule = await import({json.dumps(module_url)});

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
"""

    completed = subprocess.run(
        [node, "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    return {entry["name"]: entry for entry in payload}


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
