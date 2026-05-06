from __future__ import annotations

from pathlib import Path

from .browser_esm_probe import run_browser_esm_json_probe


def test_action_feedback_presentation_builds_failure_feedback() -> None:
    script = """
const feedbackModule = await import(__ACTION_FEEDBACK_MODULE_URL__);

const directError = feedbackModule.buildActionFailureFeedback(
  { message: "Settings failed <img src=x onerror=alert(1)>" },
  "Fallback should not win",
  { panelSlot: "settings", diagnosticsSlot: "settings-admin" },
);
const fallbackError = feedbackModule.buildActionFailureFeedback(
  { message: "" },
  "Fallback <script>bad()</script>",
  { panelSlot: "power-tools", diagnosticsSlot: "power-tools-builder" },
);
const nullError = feedbackModule.buildActionFailureFeedback(
  null,
  "Null fallback",
);

console.log(JSON.stringify({
  exportType: typeof feedbackModule.buildActionFailureFeedback,
  directError,
  fallbackError,
  nullError,
}));
"""
    payload = run_browser_esm_json_probe(
        script,
        {"__ACTION_FEEDBACK_MODULE_URL__": "action_feedback_presentation.js"},
        timeout_seconds=20,
    )

    assert payload["exportType"] == "function"
    assert payload["directError"] == {
        "panelSlot": "settings",
        "diagnosticsSlot": "settings-admin",
        "tone": "bad",
        "message": "Settings failed <img src=x onerror=alert(1)>",
        "diagnosticsHint": "Settings failed <img src=x onerror=alert(1)>",
        "diagnosticsOpen": True,
    }
    assert payload["fallbackError"] == {
        "panelSlot": "power-tools",
        "diagnosticsSlot": "power-tools-builder",
        "tone": "bad",
        "message": "Fallback <script>bad()</script>",
        "diagnosticsHint": "Fallback <script>bad()</script>",
        "diagnosticsOpen": True,
    }
    assert payload["nullError"] == {
        "panelSlot": "",
        "diagnosticsSlot": "",
        "tone": "bad",
        "message": "Null fallback",
        "diagnosticsHint": "Null fallback",
        "diagnosticsOpen": True,
    }


def test_power_tools_delegates_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    feedback_source = (static_dir / "action_feedback_presentation.js").read_text(encoding="utf-8")
    power_tools_source = (static_dir / "power-tools.js").read_text(encoding="utf-8")

    assert "export function buildActionFailureFeedback" in feedback_source
    assert 'from "./action_feedback_presentation.js"' in power_tools_source
    assert "buildActionFailureFeedback" in power_tools_source
    assert "function applyActionFailureFeedback" in power_tools_source
    assert 'setPanelStatus("settings", "bad", error.message ||' not in power_tools_source
    assert 'setPanelStatus("power-tools", "bad", error.message ||' not in power_tools_source
    assert "setDiagnostics(\"settings-admin\", error, { hint: error.message ||" not in power_tools_source
    assert "setDiagnostics(\"settings-test\", error, { hint: error.message ||" not in power_tools_source
    assert "error.message || \"Glossary save failed.\"" not in power_tools_source
    assert "error.message || \"Build suggestions failed.\"" not in power_tools_source
    assert "error.message || \"Create troubleshooting bundle failed.\"" not in power_tools_source
