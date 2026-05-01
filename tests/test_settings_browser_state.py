from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def _probe_results() -> dict[str, object]:
    script = """
const settingsModule = await import(__SETTINGS_MODULE_URL__);

const summary = {
  ui_theme: "system",
  default_lang: "FR",
  default_outdir: "C:/work/output",
  ocr_mode_default: "auto",
  ocr_engine_default: "local_then_api",
  ocr_api_provider_default: "openai",
  gmail_intake_bridge_enabled: true,
  gmail_intake_port: 8765,
  settings_path: "C:/work/settings.json",
  job_log_db_path: "C:/work/job_log.sqlite3",
  outputs_dir: "C:/work/outputs",
};

const readyProviderState = {
  translation: { credentials_configured: true },
  ocr: { api_configured: true, local_available: false },
  gmail_draft: { ready: true },
  word_pdf_export: { finalization_ready: true },
  native_host: { ready: true },
};

const notReadyProviderState = {
  translation: { credentials_configured: false },
  ocr: { api_configured: false, local_available: false },
  gmail_draft: { ready: false },
  word_pdf_export: { finalization_ready: false, export_canary: { message: "Word unavailable" } },
  native_host: { ready: false },
};

const readySummaryItems = settingsModule.buildSettingsSummaryItems(summary, readyProviderState);
const readyStatus = settingsModule.buildSettingsStatusPresentation(readyProviderState);
const notReadyStatus = settingsModule.buildSettingsStatusPresentation(notReadyProviderState);
const capabilityCards = settingsModule.buildSettingsCapabilityCards({
  normalized_payload: {
    settings_admin: {
      provider_state: readyProviderState,
    },
  },
});

const helperText = [
  JSON.stringify(readySummaryItems),
  JSON.stringify(readyStatus),
  JSON.stringify(notReadyStatus),
  JSON.stringify(capabilityCards),
].join(" ");

console.log(JSON.stringify({
  readySummaryItems,
  readyStatus,
  notReadyStatus,
  capabilityCards,
  helperText,
}));
"""
    return run_browser_esm_json_probe(
        script,
        {"__SETTINGS_MODULE_URL__": "settings_presentation.js"},
        timeout_seconds=20,
    )


def test_settings_presentation_helper_uses_beginner_setup_copy() -> None:
    payload = _probe_results()

    summary_items = payload["readySummaryItems"]
    assert [item["label"] for item in summary_items] == [
        "Theme",
        "Default language",
        "Default output folder",
        "Translation provider",
        "OCR defaults",
        "Gmail intake",
        "Settings file",
        "Saved work database",
        "Output folder",
    ]
    assert summary_items[2]["value"] == "C:/work/output"
    assert summary_items[3]["value"] == "Configured"
    assert summary_items[5]["value"] == "Enabled on 8765"
    assert summary_items[7]["value"] == "C:/work/job_log.sqlite3"

    ready_status = payload["readyStatus"]
    assert ready_status["tone"] == "ok"
    assert ready_status["message"] == (
        "Settings loaded. Translation provider is configured, OCR is ready, "
        "Gmail replies are ready, and Word/PDF output is ready."
    )

    not_ready_status = payload["notReadyStatus"]
    assert not_ready_status["tone"] == "warn"
    assert not_ready_status["message"] == (
        "Settings loaded. Translation provider is not configured, OCR is not ready, "
        "Gmail replies are not ready, and Word/PDF output is degraded."
    )

    cards = payload["capabilityCards"]
    assert [card["title"] for card in cards] == [
        "Translation provider",
        "OCR tools",
        "Gmail replies",
        "Browser helper",
        "Word/PDF output",
    ]
    assert all(card["status"] == "ok" for card in cards)

    helper_text = payload["helperText"]
    assert "Gmail Bridge" not in helper_text
    assert "Job Log DB" not in helper_text
    assert "runtime summary" not in helper_text
    assert "admin controls" not in helper_text
