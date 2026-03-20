from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _run_route_state_probe() -> dict[str, dict[str, str]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for shadow web route-state coverage.")

    module_url = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "state.js"
    ).as_uri()

    script = f"""
const stateModule = await import({json.dumps(module_url)});

function installWindow(url) {{
  globalThis.window = {{
    location: new URL(url),
    history: {{
      replaceState(_state, _title, nextUrl) {{
        window.location = new URL(nextUrl, window.location.href);
      }},
    }},
  }};
  globalThis.document = {{
    body: {{
      dataset: {{}},
    }},
  }};
}}

function capture(name) {{
  return {{
    name,
    runtimeMode: stateModule.appState.runtimeMode,
    workspaceId: stateModule.appState.workspaceId,
    activeView: stateModule.appState.activeView,
    uiVariant: stateModule.appState.uiVariant,
    href: window.location.href,
    uiDataset: document.body.dataset.uiVariant || "",
  }};
}}

const config = {{
  defaultRuntimeMode: "shadow",
  defaultWorkspaceId: "workspace-1",
  defaultUiVariant: "qt",
}};

const results = [];

installWindow("http://127.0.0.1:8887/?mode=shadow&workspace=workspace-qt");
stateModule.initializeRouteState(config);
results.push(capture("qt-default"));
stateModule.setActiveView("unsupported-view");
results.push(capture("qt-invalid-fallback"));

installWindow("http://127.0.0.1:8887/?mode=shadow&workspace=workspace-qt&ui=legacy");
stateModule.initializeRouteState(config);
results.push(capture("legacy-default"));
stateModule.setActiveView("unsupported-view");
results.push(capture("legacy-invalid-fallback"));

installWindow("http://127.0.0.1:8887/?mode=shadow&workspace=workspace-qt#recent-jobs");
stateModule.initializeRouteState(config);
results.push(capture("explicit-hash"));
window.location.hash = "#settings";
stateModule.syncActiveViewFromLocation();
results.push(capture("hashchange-settings"));

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


def test_shadow_web_route_state_defaults_follow_ui_variant() -> None:
    results = _run_route_state_probe()

    assert results["qt-default"]["activeView"] == "new-job"
    assert results["qt-default"]["href"].endswith("#new-job")
    assert results["qt-default"]["uiVariant"] == "qt"
    assert results["qt-default"]["uiDataset"] == "qt"
    assert results["qt-default"]["workspaceId"] == "workspace-qt"

    assert results["legacy-default"]["activeView"] == "dashboard"
    assert results["legacy-default"]["href"].endswith("ui=legacy#dashboard")
    assert results["legacy-default"]["uiVariant"] == "legacy"
    assert results["legacy-default"]["uiDataset"] == "legacy"


def test_shadow_web_route_state_invalid_views_and_hash_sync() -> None:
    results = _run_route_state_probe()

    assert results["qt-invalid-fallback"]["activeView"] == "new-job"
    assert results["qt-invalid-fallback"]["href"].endswith("#new-job")

    assert results["legacy-invalid-fallback"]["activeView"] == "dashboard"
    assert results["legacy-invalid-fallback"]["href"].endswith("ui=legacy#dashboard")

    assert results["explicit-hash"]["activeView"] == "recent-jobs"
    assert results["explicit-hash"]["href"].endswith("#recent-jobs")

    assert results["hashchange-settings"]["activeView"] == "settings"
    assert results["hashchange-settings"]["href"].endswith("#settings")
