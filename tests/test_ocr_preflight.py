from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "tooling" / "ocr_preflight.py"
    spec = importlib.util.spec_from_file_location("ocr_preflight_tool", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_unavailable_when_tesseract_missing(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "which", lambda _name: None)
    payload = module.run_ocr_preflight(
        environment={"OCR_PREFLIGHT_IGNORE_STORED_KEY": "true"},
        runner=lambda _cmd: (1, "", "missing"),
    )
    assert payload["overall_status"] == "unavailable"
    assert payload["fallback_readiness"]["local_only"] == "unavailable"
    assert payload["fallback_readiness"]["local_then_api_required_only"] == "unavailable"
    assert payload["tesseract"]["required_langs_ready"] is False
    assert payload["api_fallback"]["configured"] is False


def test_preflight_degraded_without_fallback_key(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "which", lambda _name: "/usr/bin/tesseract")

    def _runner(command: list[str]) -> tuple[int, str, str]:
        if command[-1] == "--version":
            return 0, "tesseract 5.3.0\n", ""
        if command[-1] == "--list-langs":
            return 0, "List of available languages in /usr/share:\neng\nfra\npor\nara\n", ""
        return 1, "", "unknown"

    payload = module.run_ocr_preflight(
        environment={"OCR_PREFLIGHT_IGNORE_STORED_KEY": "true"},
        runner=_runner,
    )
    assert payload["overall_status"] == "available"
    assert payload["fallback_readiness"]["local_only"] == "available"
    assert payload["fallback_readiness"]["local_then_api_required_only"] == "degraded"
    assert payload["tesseract"]["required_langs"]["por"] is True
    assert payload["tesseract"]["required_langs"]["eng"] is True
    assert payload["tesseract"]["required_langs"]["fra"] is True
    assert payload["tesseract"]["required_langs"]["ara"] is True


def test_preflight_available_when_env_key_present(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "which", lambda _name: "/usr/bin/tesseract")

    def _runner(command: list[str]) -> tuple[int, str, str]:
        if command[-1] == "--version":
            return 0, "tesseract 5.3.0\n", ""
        if command[-1] == "--list-langs":
            return 0, "List of available languages in /usr/share:\neng\nfra\npor\nara\n", ""
        return 1, "", "unknown"

    payload = module.run_ocr_preflight(
        environment={
            "OCR_PREFLIGHT_IGNORE_STORED_KEY": "true",
            "OPENAI_API_KEY": "key",
        },
        runner=_runner,
    )
    assert payload["overall_status"] == "available"
    assert payload["fallback_readiness"]["local_only"] == "available"
    assert payload["fallback_readiness"]["local_then_api_required_only"] == "available"
    assert payload["api_fallback"]["configured"] is True
    assert payload["api_fallback"]["key_env_name"] == "OPENAI_API_KEY"


def test_preflight_available_when_legacy_env_key_present(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "which", lambda _name: "/usr/bin/tesseract")

    def _runner(command: list[str]) -> tuple[int, str, str]:
        if command[-1] == "--version":
            return 0, "tesseract 5.3.0\n", ""
        if command[-1] == "--list-langs":
            return 0, "List of available languages in /usr/share:\neng\nfra\npor\nara\n", ""
        return 1, "", "unknown"

    payload = module.run_ocr_preflight(
        environment={
            "OCR_PREFLIGHT_IGNORE_STORED_KEY": "true",
            "DEEPSEEK_API_KEY": "legacy-key",
        },
        runner=_runner,
    )

    assert payload["fallback_readiness"]["local_then_api_required_only"] == "available"
    assert payload["api_fallback"]["configured"] is True
    assert payload["api_fallback"]["key_env_name"] == "OPENAI_API_KEY"
    assert "DEEPSEEK_API_KEY" in payload["api_fallback"]["key_env_candidates"]


def test_preflight_uses_settings_env_name_when_no_env_override(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_configured_ocr_env_name_from_settings", lambda: "GEMINI_API_KEY")
    monkeypatch.setattr(module, "which", lambda _name: None)

    payload = module.run_ocr_preflight(
        environment={"OCR_PREFLIGHT_IGNORE_STORED_KEY": "true", "GEMINI_API_KEY": "gem-key"},
        runner=lambda _cmd: (1, "", "missing"),
    )

    assert payload["api_fallback"]["configured"] is True
    assert payload["api_fallback"]["key_env_name"] == "GEMINI_API_KEY"
    assert payload["api_fallback"]["key_env_candidates"] == ["GEMINI_API_KEY"]


def test_cli_emits_valid_json(monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "which", lambda _name: None)
    exit_code = module.main(["--compact"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["tool"] == "ocr_preflight"
