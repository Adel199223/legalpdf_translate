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


def test_app_profile_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "buildActionFailureFeedback" in app_source
    assert "function applyActionFailureFeedback" in app_source
    for fallback in [
        "Profile import failed.",
        "New profile failed.",
        "Profile save failed.",
        "Set-primary failed.",
        "Profile delete failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("profile", "bad", error.message ||' not in app_source
    assert 'setDiagnostics("profile", error, { hint: error.message ||' not in app_source


def test_app_recent_work_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyActionFailureFeedback" in app_source
    for fallback in [
        "Saved work delete failed.",
        "History reload failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("recent-jobs", "bad", error.message ||' not in app_source


def test_app_extension_lab_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyActionFailureFeedback" in app_source
    for fallback in [
        "Extension diagnostics refresh failed.",
        "Simulator request failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("extension", "bad", error.message ||' not in app_source
    assert 'setPanelStatus("simulator", "bad", error.message ||' not in app_source


def test_app_autofill_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyActionFailureFeedback" in app_source
    for fallback in [
        "Notification autofill failed.",
        "Photo autofill failed.",
        "Google Photos connection failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("autofill", "bad", error.message ||' not in app_source
    assert 'setDiagnostics("autofill", error, { hint: error.message ||' not in app_source


def test_app_form_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyActionFailureFeedback" in app_source
    assert app_source.count("recoverInterpretationValidationError(error);") >= 2
    for fallback in [
        "Save failed.",
        "Export failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"


def test_app_runtime_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyActionFailureFeedback" in app_source
    for fallback in [
        "Browser shell refresh failed.",
        "Runtime refresh failed.",
        "Runtime mode change failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("runtime", "bad", error.message || "Browser shell refresh failed."' not in app_source
    assert 'setPanelStatus("runtime", "bad", error.message || "Runtime refresh failed."' not in app_source
    assert 'setPanelStatus("runtime", "bad", error.message || "Runtime mode change failed."' not in app_source
