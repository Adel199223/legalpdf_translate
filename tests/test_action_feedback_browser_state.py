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


def test_action_feedback_ui_helper_applies_status_and_diagnostics_safely() -> None:
    script = """
const feedbackModule = await import(__ACTION_FEEDBACK_MODULE_URL__);

const calls = { panel: [], diagnostics: [] };
const directFeedback = feedbackModule.applyActionFailureFeedbackToUi(
  { message: "Failure <img src=x onerror=alert(1)><script>bad()</script>" },
  {
    panelSlot: "gmail",
    diagnosticsSlot: "gmail-session",
    fallback: "Fallback should not win",
    tone: "warn",
    diagnosticsHint: (message) => `Hint ${message}`,
  },
  {
    setPanelStatus(slot, tone, message) {
      calls.panel.push({ slot, tone, message });
    },
    setDiagnostics(slot, value, options) {
      calls.diagnostics.push({
        slot,
        valueMessage: value?.message || "",
        hint: options?.hint || "",
        open: options?.open === true,
      });
    },
  },
);
const fallbackFeedback = feedbackModule.applyActionFailureFeedbackToUi(
  { message: "" },
  {
    panelSlot: "power-tools",
    fallback: "Fallback <strong>safe</strong>",
  },
  {
    setPanelStatus(slot, tone, message) {
      calls.panel.push({ slot, tone, message });
    },
    setDiagnostics(slot, value, options) {
      calls.diagnostics.push({ slot, valueMessage: value?.message || "", hint: options?.hint || "", open: options?.open === true });
    },
  },
);
const nullSinksFeedback = feedbackModule.applyActionFailureFeedbackToUi(
  null,
  { fallback: "Null fallback" },
  {},
);

console.log(JSON.stringify({
  exportType: typeof feedbackModule.applyActionFailureFeedbackToUi,
  directFeedback,
  fallbackFeedback,
  nullSinksFeedback,
  calls,
}));
"""
    payload = run_browser_esm_json_probe(
        script,
        {"__ACTION_FEEDBACK_MODULE_URL__": "action_feedback_presentation.js"},
        timeout_seconds=20,
    )

    assert payload["exportType"] == "function"
    assert payload["directFeedback"] == {
        "panelSlot": "gmail",
        "diagnosticsSlot": "gmail-session",
        "tone": "warn",
        "message": "Failure <img src=x onerror=alert(1)><script>bad()</script>",
        "diagnosticsHint": "Failure <img src=x onerror=alert(1)><script>bad()</script>",
        "diagnosticsOpen": True,
    }
    assert payload["fallbackFeedback"]["message"] == "Fallback <strong>safe</strong>"
    assert payload["nullSinksFeedback"]["message"] == "Null fallback"
    assert payload["calls"]["panel"] == [
        {
            "slot": "gmail",
            "tone": "warn",
            "message": "Failure <img src=x onerror=alert(1)><script>bad()</script>",
        },
        {
            "slot": "power-tools",
            "tone": "bad",
            "message": "Fallback <strong>safe</strong>",
        },
    ]
    assert payload["calls"]["diagnostics"] == [
        {
            "slot": "gmail-session",
            "valueMessage": "Failure <img src=x onerror=alert(1)><script>bad()</script>",
            "hint": "Hint Failure <img src=x onerror=alert(1)><script>bad()</script>",
            "open": True,
        },
    ]


def test_browser_modules_delegate_action_failure_ui_application() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    feedback_source = (static_dir / "action_feedback_presentation.js").read_text(encoding="utf-8")
    module_sources = {
        "app": (static_dir / "app.js").read_text(encoding="utf-8"),
        "gmail": (static_dir / "gmail.js").read_text(encoding="utf-8"),
        "translation": (static_dir / "translation.js").read_text(encoding="utf-8"),
        "power-tools": (static_dir / "power-tools.js").read_text(encoding="utf-8"),
    }

    assert "export function applyActionFailureFeedbackToUi" in feedback_source
    for name, source in module_sources.items():
        assert "applyActionFailureFeedbackToUi" in source, f"{name} should import the shared action feedback UI helper"
        helper_start = source.index("function applyActionFailureFeedback(")
        helper_end = source.index("\n}\n", helper_start) + 3
        helper_block = source[helper_start:helper_end]
        assert "applyActionFailureFeedbackToUi(" in helper_block, f"{name} helper should delegate"
        assert "setPanelStatus(feedback.panelSlot" not in helper_block, f"{name} helper should not repeat status plumbing"
        assert "setDiagnostics(feedback.diagnosticsSlot" not in helper_block, f"{name} helper should not repeat diagnostics plumbing"


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
    assert "applyActionFailureFeedbackToUi" in power_tools_source
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


def test_app_profile_distance_actions_delegate_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyProfileDistanceFailureStatus" in app_source
    assert "buildActionFailureFeedback(error, fallback)" in app_source
    assert "setProfileDistanceStatus(feedback.tone, feedback.message)" in app_source
    for fallback in [
        "Unable to update the distance.",
        "Unable to refresh the distance list.",
    ]:
        assert (
            f'applyProfileDistanceFailureStatus(error, "{fallback}")'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setProfileDistanceStatus("bad", error.message ||' not in app_source


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


def test_app_google_photos_picker_failure_delegates_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyGooglePhotosPickerFailureFeedback" in app_source
    assert "buildActionFailureFeedback(feedbackError, \"Google Photos import failed.\"" in app_source
    assert "GOOGLE_PHOTOS_RECONNECT_GUIDANCE" in app_source
    assert "google_photos_picker: pickerDiagnostics" in app_source
    assert "request_error: error.payload || {}" in app_source
    assert "renderGooglePhotosSummary({" in app_source
    assert "applyGooglePhotosPickerFailureFeedback(error, pickerDiagnostics)" in app_source
    assert 'error.message || "Google Photos import failed."' not in app_source
    assert 'setPanelStatus("autofill", "bad", message)' not in app_source


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


def test_app_interpretation_guard_failures_delegate_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_source = (static_dir / "app.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in app_source
    assert "function applyInterpretationGuardFailureFeedback" in app_source
    assert "buildActionFailureFeedback(error, fallback" in app_source
    assert "setPanelStatus(feedback.panelSlot, feedback.tone, feedback.message)" in app_source
    assert "setDiagnostics(feedback.diagnosticsSlot, diagnosticsValue || error, {" in app_source
    assert 'fallback: `Interpretation ${actionName} is blocked.`' in app_source
    assert 'fallback: "A positive one-way distance is required before continuing."' in app_source
    assert "applyInterpretationGuardFailureFeedback(fallbackError" in app_source
    assert "applyInterpretationGuardFailureFeedback(distanceError" in app_source
    assert 'setPanelStatus("form", "bad", fallbackError.message ||' not in app_source
    assert 'hint: fallbackError.message ||' not in app_source
    assert 'setPanelStatus("form", "bad", message)' not in app_source


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


def test_app_bootstrap_failures_delegate_action_failure_feedback() -> None:
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
    assert "function applyBootstrapFailureState" in app_source
    assert "diagnosticsHint" in app_source
    for fallback in [
        "This LegalPDF browser tab is using stale browser assets.",
        "Browser app bootstrap failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in app_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in app_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setTopbarStatus(error.message || "This LegalPDF browser tab is using stale browser assets."' not in app_source
    assert 'setTopbarStatus(error.message || "Browser app bootstrap failed."' not in app_source
    assert 'setPanelStatus("runtime", "bad", error.message || "Browser app bootstrap failed."' not in app_source
    assert 'setDiagnostics("runtime", error, { hint: error.message || "Browser app bootstrap failed."' not in app_source


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
    assert "applyActionFailureFeedbackToUi" in translation_source
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
    assert "applyActionFailureFeedbackToUi(" in translation_source
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
    assert "applyActionFailureFeedbackToUi" in gmail_source
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


def test_gmail_preview_actions_delegate_remaining_action_failure_feedback() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    gmail_source = (static_dir / "gmail.js").read_text(encoding="utf-8")

    assert 'from "./action_feedback_presentation.js"' in gmail_source
    assert "function applyActionFailureFeedback" in gmail_source
    assert "diagnosticsHint" in gmail_source
    assert "gmailFailureHint(error, message)" in gmail_source
    for fallback in [
        "Preview rendering failed.",
        "Attachment preview failed.",
        "Gmail session preparation failed.",
    ]:
        assert (
            f'fallback: "{fallback}"'
            in gmail_source
        ), f"{fallback} should be routed through shared action feedback"
        assert (
            f'error.message || "{fallback}"'
            not in gmail_source
        ), f"{fallback} should not repeat raw fallback message plumbing"
    assert 'setPanelStatus("gmail", "bad", error.message || "Attachment preview failed."' not in gmail_source
    assert 'setPanelStatus("gmail", "bad", error.message || "Gmail session preparation failed."' not in gmail_source
