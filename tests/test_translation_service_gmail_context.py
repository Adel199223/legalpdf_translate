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
