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
    operatorMode: stateModule.appState.operatorMode,
    href: window.location.href,
    uiDataset: document.body.dataset.uiVariant || "",
    workspaceDataset: document.body.dataset.workspaceId || "",
    shellMode: document.body.dataset.shellMode || "",
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
installWindow("http://127.0.0.1:8887/?mode=live&workspace=gmail-intake#gmail-intake");
stateModule.initializeRouteState(config);
results.push(capture("gmail-intake-hash"));
window.location.hash = "#settings";
stateModule.syncActiveViewFromLocation();
results.push(capture("hashchange-settings"));
installWindow("http://127.0.0.1:8887/?mode=shadow&workspace=workspace-qt&operator=1");
stateModule.initializeRouteState(config);
results.push(capture("qt-operator"));
stateModule.setOperatorMode(false);
results.push(capture("operator-disabled"));

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


def _shadow_web_stylesheet() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "style.css"
    ).read_text(encoding="utf-8")


def test_shadow_web_route_state_defaults_follow_ui_variant() -> None:
    results = _run_route_state_probe()

    assert results["qt-default"]["activeView"] == "new-job"
    assert results["qt-default"]["href"].endswith("#new-job")
    assert results["qt-default"]["uiVariant"] == "qt"
    assert results["qt-default"]["uiDataset"] == "qt"
    assert results["qt-default"]["workspaceId"] == "workspace-qt"
    assert results["qt-default"]["workspaceDataset"] == "workspace-qt"
    assert results["qt-default"]["operatorMode"] is False
    assert results["qt-default"]["shellMode"] == "standard"

    assert results["legacy-default"]["activeView"] == "dashboard"
    assert results["legacy-default"]["href"].endswith("ui=legacy#dashboard")
    assert results["legacy-default"]["uiVariant"] == "legacy"
    assert results["legacy-default"]["uiDataset"] == "legacy"
    assert results["legacy-default"]["shellMode"] == "standard"


def test_shadow_web_route_state_invalid_views_and_hash_sync() -> None:
    results = _run_route_state_probe()

    assert results["qt-invalid-fallback"]["activeView"] == "new-job"
    assert results["qt-invalid-fallback"]["href"].endswith("#new-job")

    assert results["legacy-invalid-fallback"]["activeView"] == "dashboard"
    assert results["legacy-invalid-fallback"]["href"].endswith("ui=legacy#dashboard")

    assert results["explicit-hash"]["activeView"] == "recent-jobs"
    assert results["explicit-hash"]["href"].endswith("#recent-jobs")
    assert results["explicit-hash"]["shellMode"] == "standard"

    assert results["gmail-intake-hash"]["activeView"] == "gmail-intake"
    assert results["gmail-intake-hash"]["href"].endswith("workspace=gmail-intake#gmail-intake")
    assert results["gmail-intake-hash"]["shellMode"] == "gmail-focus"

    assert results["hashchange-settings"]["activeView"] == "settings"
    assert results["hashchange-settings"]["href"].endswith("#settings")
    assert results["hashchange-settings"]["shellMode"] == "standard"

    assert results["qt-operator"]["operatorMode"] is True
    assert "operator=1" in results["qt-operator"]["href"]

    assert results["operator-disabled"]["operatorMode"] is False
    assert "operator=1" not in results["operator-disabled"]["href"]


def test_shadow_web_stylesheet_keeps_gmail_focus_shell_overrides_last() -> None:
    stylesheet = _shadow_web_stylesheet()

    generic_shell_selector = 'body[data-ui-variant="qt"] .app-shell'
    generic_hero_selector = 'body[data-ui-variant="qt"] [data-view="gmail-intake"].qt-workspace-view .workspace-hero'
    generic_panel_selector = 'body[data-ui-variant="qt"] [data-view="gmail-intake"].qt-workspace-view .workspace-panel-gmail'
    focus_shell_selector = 'body[data-ui-variant="qt"][data-shell-mode="gmail-focus"] .app-shell'
    focus_view_selector = 'body[data-ui-variant="qt"][data-shell-mode="gmail-focus"] [data-view="gmail-intake"].qt-workspace-view'
    focus_frame_selector = 'body[data-ui-variant="qt"][data-shell-mode="gmail-focus"] [data-view="gmail-intake"].qt-workspace-view::before'
    focus_hero_selector = 'body[data-ui-variant="qt"][data-shell-mode="gmail-focus"] [data-view="gmail-intake"].qt-workspace-view .workspace-hero'
    focus_panel_selector = 'body[data-ui-variant="qt"][data-shell-mode="gmail-focus"] [data-view="gmail-intake"].qt-workspace-view .workspace-panel-gmail'

    focus_shell_index = stylesheet.index(focus_shell_selector)
    focus_view_index = stylesheet.index(focus_view_selector)
    focus_frame_index = stylesheet.index(focus_frame_selector)
    focus_hero_index = stylesheet.index(focus_hero_selector)
    focus_panel_index = stylesheet.index(focus_panel_selector)

    assert focus_shell_index > stylesheet.rindex(generic_shell_selector)
    assert focus_hero_index > stylesheet.rindex(generic_hero_selector)
    assert focus_panel_index > stylesheet.rindex(generic_panel_selector)

    assert "grid-template-columns: minmax(0, 1fr);" in stylesheet[focus_shell_index:stylesheet.index("}", focus_shell_index)]
    assert "grid-template-columns: minmax(0, 1fr);" in stylesheet[focus_view_index:stylesheet.index("}", focus_view_index)]
    assert "display: none;" in stylesheet[focus_frame_index:stylesheet.index("}", focus_frame_index)]
    assert "display: none;" in stylesheet[focus_hero_index:stylesheet.index("}", focus_hero_index)]
    assert "max-width: 980px;" in stylesheet[focus_panel_index:stylesheet.index("}", focus_panel_index)]
