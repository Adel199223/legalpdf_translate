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
const warningError = feedbackModule.buildActionFailureFeedback(
  { message: "Warning <strong>safe</strong>" },
  "Warning fallback",
  { panelSlot: "translation-save", diagnosticsSlot: "translation-save", tone: "warn" },
);

console.log(JSON.stringify({
  exportType: typeof feedbackModule.buildActionFailureFeedback,
  directError,
  fallbackError,
  nullError,
  warningError,
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
    assert payload["warningError"] == {
        "panelSlot": "translation-save",
        "diagnosticsSlot": "translation-save",
        "tone": "warn",
        "message": "Warning <strong>safe</strong>",
        "diagnosticsHint": "Warning <strong>safe</strong>",
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
        "Interpretation validation failed.",
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
    assert 'setPanelStatus("form", "bad", error.message || "Interpretation validation failed."' not in app_source
    assert 'hint: error.message || "Interpretation validation failed."' not in app_source


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


def test_app_interpretation_reference_actions_delegate_repeated_action_failure_feedback() -> None:
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
    assert "return feedback;" in app_source
    for fallback in [
        "Unable to save the court email yet.",
        "Unable to save the city yet.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("form", "bad", error.message || "Unable to save the court email yet."' not in app_source
    assert 'setPanelStatus("form", "bad", error.message || "Unable to save the city yet."' not in app_source
    assert "recoverInterpretationValidationError(error);" in app_source


def test_translation_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    translation_source = (static_dir / "translation.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in translation_source
    assert "buildActionFailureFeedback" in translation_source
    assert "function applyActionFailureFeedback" in translation_source
    for fallback in [
        "Translation job polling failed.",
        "Source staging failed.",
        "Translation refresh failed.",
        "Analyze failed.",
        "Translation start failed.",
        "Cancellation failed.",
        "Resume failed.",
        "Rebuild failed.",
        "Review queue export failed.",
        "Run report generation failed.",
        "Translation save failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in translation_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in translation_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("translation", "bad", error.message ||' not in translation_source
    assert 'setPanelStatus("translation-save", "bad", error.message || "Translation save failed."' not in translation_source
    assert 'setDiagnostics("translation", error, { hint: error.message ||' not in translation_source
    assert 'setDiagnostics("translation-job", error, { hint: error.message ||' not in translation_source
    assert 'setDiagnostics("translation-save", error, { hint: error.message || "Translation save failed."' not in translation_source


def test_translation_save_actions_delegate_remaining_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    translation_source = (static_dir / "translation.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in translation_source
    assert "function applyActionFailureFeedback" in translation_source
    assert 'tone: "warn"' in translation_source
    for fallback in [
        "Arabic DOCX review refresh failed.",
        "Arabic DOCX review open failed.",
        "Arabic DOCX review restore failed.",
        "Translation row delete failed.",
        "Arabic DOCX review continuation failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in translation_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in translation_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("translation-save", "bad", error.message ||' not in translation_source
    assert 'setPanelStatus("translation-save", "warn", error.message ||' not in translation_source
    assert "setDiagnostics(feedback.diagnosticsSlot, error, {" in translation_source
    assert 'hint: error.message ||' not in translation_source


def test_gmail_actions_delegate_repeated_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    gmail_source = (static_dir / "gmail.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in gmail_source
    assert "buildActionFailureFeedback" in gmail_source
    assert "function applyActionFailureFeedback" in gmail_source
    for fallback in [
        "Gmail batch finalization preflight failed.",
        "Gmail message load failed.",
        "Demo Gmail review load failed.",
        "Canonical runtime restart failed.",
        "Gmail browser failure report generation failed.",
        "Gmail finalization report generation failed.",
        "Redo current attachment failed.",
        "Gmail attachment confirmation failed.",
        "Gmail batch finalization failed.",
        "Creating the Gmail reply failed.",
        "Gmail refresh failed.",
        "Gmail review reset failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in gmail_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in gmail_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("gmail", "bad", error.message || "Gmail message load failed."' not in gmail_source
    assert 'setPanelStatus("gmail-session", "bad", error.message || "Gmail attachment confirmation failed."' not in gmail_source
    assert 'setPanelStatus("gmail-batch-finalize", "bad", error.message || "Gmail batch finalization failed."' not in gmail_source
    assert 'setDiagnostics("gmail", error, { hint: error.message || "Gmail refresh failed."' not in gmail_source
    assert 'setDiagnostics("gmail-session", error, { hint: error.message || "Gmail review reset failed."' not in gmail_source
    assert 'setDiagnostics("gmail-batch-finalize", error, { hint: error.message || "Gmail finalization report generation failed."' not in gmail_source
