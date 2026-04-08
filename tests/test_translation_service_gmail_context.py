from __future__ import annotations

from pathlib import Path

from legalpdf_translate.translation_service import _build_config_from_form, _serialize_run_config


def test_build_config_from_form_preserves_gmail_batch_context(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    source_path = tmp_path / "sentenca_305.pdf"
    source_path.write_bytes(b"%PDF-1.7\n")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    config = _build_config_from_form(
        form_values={
            "source_path": str(source_path),
            "output_dir": str(output_dir),
            "target_lang": "AR",
            "start_page": 3,
            "gmail_batch_context": {
                "source": "gmail_intake",
                "session_id": "gmail_batch_123",
                "message_id": "msg-1",
                "thread_id": "thr-1",
                "attachment_id": "att-1",
                "selected_attachment_filename": "sentença 305.pdf",
                "selected_attachment_count": 2,
                "selected_target_lang": "AR",
                "selected_start_page": 3,
                "gmail_batch_session_report_path": str(tmp_path / "gmail_batch_session.json"),
            },
        },
        settings_path=settings_path,
    )

    assert config.gmail_batch_context == {
        "source": "gmail_intake",
        "session_id": "gmail_batch_123",
        "message_id": "msg-1",
        "thread_id": "thr-1",
        "attachment_id": "att-1",
        "selected_attachment_filename": "sentença 305.pdf",
        "selected_attachment_count": 2,
        "selected_target_lang": "AR",
        "selected_start_page": 3,
        "gmail_batch_session_report_path": str((tmp_path / "gmail_batch_session.json").resolve()),
    }

    serialized = _serialize_run_config(config)
    assert serialized["gmail_batch_context"] == config.gmail_batch_context


def test_build_config_from_form_applies_gmail_safe_defaults_when_fields_are_missing(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        (
            '{'
            '"image_mode":"off",'
            '"ocr_mode":"off",'
            '"ocr_engine":"local",'
            '"resume":true,'
            '"keep_intermediates":false'
            '}'
        ),
        encoding="utf-8",
    )
    source_path = tmp_path / "auto.pdf"
    source_path.write_bytes(b"%PDF-1.7\n")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    config = _build_config_from_form(
        form_values={
            "source_path": str(source_path),
            "output_dir": str(output_dir),
            "gmail_batch_context": {
                "source": "gmail_intake",
                "session_id": "gmail_batch_456",
                "message_id": "msg-2",
                "thread_id": "thr-2",
                "attachment_id": "att-2",
                "selected_attachment_filename": "Auto.pdf",
                "selected_attachment_count": 1,
                "selected_target_lang": "FR",
                "selected_start_page": 4,
                "gmail_batch_session_report_path": str(tmp_path / "gmail_batch_session.json"),
            },
        },
        settings_path=settings_path,
    )

    assert config.target_lang.value == "FR"
    assert config.start_page == 4
    assert config.image_mode.value == "auto"
    assert config.ocr_mode.value == "auto"
    assert config.ocr_engine.value == "local_then_api"
    assert config.resume is False
    assert config.keep_intermediates is True


def test_build_config_from_form_allows_explicit_gmail_overrides(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    source_path = tmp_path / "auto.pdf"
    source_path.write_bytes(b"%PDF-1.7\n")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    config = _build_config_from_form(
        form_values={
            "source_path": str(source_path),
            "output_dir": str(output_dir),
            "target_lang": "AR",
            "start_page": 2,
            "image_mode": "off",
            "ocr_mode": "off",
            "ocr_engine": "local",
            "resume": True,
            "keep_intermediates": False,
            "gmail_batch_context": {
                "source": "gmail_intake",
                "session_id": "gmail_batch_789",
                "message_id": "msg-3",
                "thread_id": "thr-3",
                "attachment_id": "att-3",
                "selected_attachment_filename": "Auto.pdf",
                "selected_attachment_count": 1,
                "selected_target_lang": "FR",
                "selected_start_page": 1,
                "gmail_batch_session_report_path": str(tmp_path / "gmail_batch_session.json"),
            },
        },
        settings_path=settings_path,
    )

    assert config.target_lang.value == "AR"
    assert config.start_page == 2
    assert config.image_mode.value == "off"
    assert config.ocr_mode.value == "off"
    assert config.ocr_engine.value == "local"
    assert config.resume is True
    assert config.keep_intermediates is False
