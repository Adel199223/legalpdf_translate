from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from legalpdf_translate.qt_gui.app_window import QtMainWindow, _load_advisor_recommendation


class _FakeEdit:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def text(self) -> str:
        return self._value


class _FakeCombo:
    def __init__(self, value: str) -> None:
        self._value = value

    def currentText(self) -> str:
        return self._value


class _FakeSpin:
    def __init__(self, value: int) -> None:
        self._value = value

    def value(self) -> int:
        return self._value


class _FakeCheck:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _FakeText:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def toPlainText(self) -> str:
        return self._value


def test_load_advisor_recommendation_reads_analyze_report(tmp_path: Path) -> None:
    report_path = tmp_path / "analyze_report.json"
    report_path.write_text(
        json.dumps(
            {
                "recommended_ocr_mode": "auto",
                "recommended_image_mode": "always",
                "recommendation_reasons": ["ar_layout_or_text_quality_requires_ocr"],
                "confidence": 0.83,
                "advisor_track": "ar",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = _load_advisor_recommendation(report_path)

    assert payload is not None
    assert payload["recommended_ocr_mode"] == "auto"
    assert payload["recommended_image_mode"] == "always"
    assert payload["advisor_track"] == "ar"
    assert payload["confidence"] == 0.83


def test_apply_and_ignore_advisor_set_expected_run_scope_state() -> None:
    logs: list[str] = []
    calls = {"refreshed": 0, "updated": 0}
    fake = SimpleNamespace(
        _advisor_recommendation={
            "recommended_ocr_mode": "always",
            "recommended_image_mode": "auto",
            "advisor_track": "enfr",
            "confidence": 0.79,
        },
        _advisor_recommendation_applied=None,
        _advisor_override_ocr_mode=None,
        _advisor_override_image_mode=None,
        _append_log=lambda msg: logs.append(msg),
        _refresh_advisor_banner=lambda: calls.__setitem__("refreshed", calls["refreshed"] + 1),
        _update_controls=lambda: calls.__setitem__("updated", calls["updated"] + 1),
    )

    QtMainWindow._apply_advisor_recommendation(fake)
    assert fake._advisor_recommendation_applied is True
    assert fake._advisor_override_ocr_mode == "always"
    assert fake._advisor_override_image_mode == "auto"

    QtMainWindow._ignore_advisor_recommendation(fake)
    assert fake._advisor_recommendation_applied is False
    assert fake._advisor_override_ocr_mode is None
    assert fake._advisor_override_image_mode is None
    assert calls == {"refreshed": 2, "updated": 2}
    assert any("Advisor applied for next run only" in item for item in logs)
    assert any("Advisor recommendation ignored for next run." in item for item in logs)


def test_build_config_uses_advisor_modes_for_run_only(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    outdir = tmp_path / "out"
    outdir.mkdir()

    fake = SimpleNamespace(
        pdf_edit=_FakeEdit(str(pdf_path)),
        outdir_edit=_FakeEdit(str(outdir)),
        lang_combo=_FakeCombo("EN"),
        effort_combo=_FakeCombo("high"),
        effort_policy_combo=_FakeCombo("adaptive"),
        images_combo=_FakeCombo("off"),
        ocr_mode_combo=_FakeCombo("off"),
        ocr_engine_combo=_FakeCombo("local_then_api"),
        start_edit=_FakeEdit("1"),
        end_edit=_FakeEdit(""),
        max_edit=_FakeEdit(""),
        workers_spin=_FakeSpin(1),
        resume_check=_FakeCheck(False),
        breaks_check=_FakeCheck(True),
        keep_check=_FakeCheck(True),
        context_file_edit=_FakeEdit(""),
        context_text=_FakeText(""),
        _defaults={
            "allow_xhigh_escalation": False,
            "ocr_api_base_url": "",
            "ocr_api_model": "",
            "ocr_api_key_env_name": "DEEPSEEK_API_KEY",
            "diagnostics_admin_mode": True,
            "diagnostics_include_sanitized_snippets": False,
            "glossary_file_path": "",
        },
        _advisor_recommendation_applied=True,
        _advisor_override_ocr_mode="auto",
        _advisor_override_image_mode="always",
        _advisor_recommendation={
            "recommended_ocr_mode": "auto",
            "recommended_image_mode": "always",
            "advisor_track": "enfr",
            "confidence": 0.88,
        },
    )

    config = QtMainWindow._build_config(fake)

    assert config.image_mode.value == "always"
    assert config.ocr_mode.value == "auto"
    assert config.advisor_recommendation_applied is True
    assert isinstance(config.advisor_recommendation, dict)
    assert config.advisor_recommendation["recommended_image_mode"] == "always"

    fake2 = SimpleNamespace(
        _advisor_recommendation_applied=True,
        _advisor_override_ocr_mode="auto",
        _advisor_override_image_mode="always",
        _refresh_advisor_banner=lambda: None,
    )
    QtMainWindow._consume_advisor_choice(fake2)
    assert fake2._advisor_recommendation_applied is None
    assert fake2._advisor_override_ocr_mode is None
    assert fake2._advisor_override_image_mode is None
