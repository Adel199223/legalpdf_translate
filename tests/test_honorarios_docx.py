from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PySide6.QtWidgets import QApplication

from legalpdf_translate.honorarios_docx import (
    FIXED_ADDRESS,
    FIXED_IBAN,
    FIXED_NAME,
    HonorariosDraft,
    build_honorarios_draft,
    build_honorarios_paragraph_texts,
    default_honorarios_filename,
    format_portuguese_date,
    generate_honorarios_docx,
)
from legalpdf_translate.joblog_db import insert_job_run, open_job_log
from legalpdf_translate.qt_gui.dialogs import (
    JobLogSeed,
    QtHonorariosExportDialog,
    QtJobLogWindow,
    QtSaveToJobLogDialog,
    _default_documents_dir,
)


def test_format_portuguese_date_uses_full_month_name() -> None:
    assert format_portuguese_date(date(2026, 3, 6)) == "06 de março de 2026"


def test_build_honorarios_paragraph_texts_uses_locked_template() -> None:
    draft = build_honorarios_draft(
        case_number="109/26.0PBBJA",
        word_count=1666,
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        today=date(2026, 3, 6),
    )

    paragraphs = build_honorarios_paragraph_texts(draft)
    assert paragraphs == [
        ("Número de processo: 109/26.0PBBJA", "left"),
        ("", "left"),
        ("Exmo. Sr procurador da república\ndo Juízo Local Criminal de Beja\nde Beja", "address"),
        ("", "left"),
        (f"Nome: {FIXED_NAME}", "left"),
        (f"Morada: {FIXED_ADDRESS}", "left"),
        ("", "left"),
        (
            "Venho por este meio requerer o pagamento dos honorários devidos, em virtude de ter sido nomeado "
            "tradutor no âmbito do processo acima identificado.",
            "left",
        ),
        ("O documento traduzido contém 1666 palavras.", "left"),
        ("Este serviço inclui a taxa IVA de 23% e não tem retenção de IRS.", "left"),
        (f"O Pagamento deverá ser efetuado para o seguinte IBAN: {FIXED_IBAN}", "left"),
        ("", "left"),
        ("Melhores cumprimentos,", "left"),
        ("", "left"),
        ("Espera deferimento,", "center"),
        ("", "left"),
        ("Beja, 06 de março de 2026", "center"),
        ("", "left"),
        (FIXED_NAME, "center"),
    ]


def test_generate_honorarios_docx_has_expected_text_and_alignment(tmp_path: Path) -> None:
    draft = HonorariosDraft(
        case_number="109/26.0PBBJA",
        word_count=1666,
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        date_pt="06 de março de 2026",
    )
    output = tmp_path / "honorarios.docx"

    generate_honorarios_docx(draft, output)

    doc = Document(output)
    paragraphs = doc.paragraphs
    assert paragraphs[0].text == "Número de processo: 109/26.0PBBJA"
    assert paragraphs[2].text == "Exmo. Sr procurador da república\ndo Juízo Local Criminal de Beja\nde Beja"
    assert paragraphs[12].text == "Melhores cumprimentos,"
    assert paragraphs[14].text == "Espera deferimento,"
    assert paragraphs[16].text == "Beja, 06 de março de 2026"
    assert paragraphs[18].text == FIXED_NAME
    assert paragraphs[14].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert paragraphs[16].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert paragraphs[18].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert paragraphs[0].runs[0].font.name == "Arial"


def test_default_honorarios_filename_sanitizes_case_number() -> None:
    assert (
        default_honorarios_filename("109/26.0PBBJA", today=date(2026, 3, 6))
        == "Requerimento_Honorarios_109_26.0PBBJA_20260306.docx"
    )


def test_honorarios_dialog_validates_required_fields(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    dialog = QtHonorariosExportDialog(
        parent=None,
        draft=HonorariosDraft("", 0, "", "", "06 de março de 2026"),
        default_directory=tmp_path,
    )
    try:
        with pytest.raises(ValueError, match="Número de processo"):
            dialog._build_draft()
        dialog.case_number_edit.setText("109/26.0PBBJA")
        dialog.case_entity_edit.setText("Juízo Local Criminal de Beja")
        dialog.case_city_edit.setText("Beja")
        with pytest.raises(ValueError, match="greater than zero"):
            dialog._build_draft()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_save_to_joblog_dialog_opens_honorarios_dialog_with_current_values(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at=datetime.now().isoformat(timespec="seconds"),
        translation_date="2026-03-06",
        job_type="Translation",
        case_number="seed-case",
        court_email="",
        case_entity="Seed Entity",
        case_city="Seed City",
        service_entity="Seed Entity",
        service_city="Seed City",
        service_date="2026-03-06",
        lang="AR",
        pages=7,
        word_count=1666,
        rate_per_word=0.09,
        expected_total=149.94,
        amount_paid=0.0,
        api_cost=0.56,
        run_id="20260306_165834",
        target_lang="AR",
        total_tokens=57126,
        estimated_api_cost=0.56,
        quality_risk_score=0.1754,
        profit=149.38,
        pdf_path=tmp_path / "sample.pdf",
        output_docx=tmp_path / "out" / "translated.docx",
    )
    seed.output_docx.parent.mkdir(parents=True)
    seed.output_docx.write_bytes(b"docx")

    captured: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            captured["parent"] = parent
            captured["draft"] = draft
            captured["default_directory"] = default_directory

        def exec(self) -> int:
            captured["exec"] = True
            return 0

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtHonorariosExportDialog", _FakeHonorariosDialog)

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.case_number_edit.setText("109/26.0PBBJA")
        dialog.case_entity_combo.setCurrentText("Juízo Local Criminal de Beja")
        dialog.case_city_combo.setCurrentText("Beja")
        dialog._open_honorarios_dialog()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()

    draft = captured["draft"]
    assert isinstance(draft, HonorariosDraft)
    assert draft.case_number == "109/26.0PBBJA"
    assert draft.word_count == 1666
    assert draft.case_entity == "Juízo Local Criminal de Beja"
    assert draft.case_city == "Beja"
    assert captured["default_directory"] == seed.output_docx.parent.resolve()
    assert captured["exec"] is True


def test_joblog_window_generates_honorarios_from_selected_row(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(
            conn,
            {
                "completed_at": "2026-03-06T16:58:34",
                "translation_date": "2026-03-06",
                "job_type": "Translation",
                "case_number": "109/26.0PBBJA",
                "court_email": "beja.judicial@tribunais.org.pt",
                "case_entity": "Juízo Local Criminal de Beja",
                "case_city": "Beja",
                "service_entity": "Juízo Local Criminal de Beja",
                "service_city": "Beja",
                "service_date": "2026-03-06",
                "lang": "AR",
                "target_lang": "AR",
                "run_id": "20260306_165834",
                "pages": 7,
                "word_count": 1666,
                "total_tokens": 57126,
                "rate_per_word": 0.09,
                "expected_total": 149.94,
                "amount_paid": 0.0,
                "api_cost": 0.56,
                "estimated_api_cost": 0.56,
                "quality_risk_score": 0.1754,
                "profit": 149.38,
            },
        )

    captured: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            captured["draft"] = draft
            captured["default_directory"] = default_directory

        def exec(self) -> int:
            captured["exec"] = True
            return 0

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtHonorariosExportDialog", _FakeHonorariosDialog)

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        assert window.honorarios_btn.isEnabled() is False
        window.table.selectRow(0)
        QApplication.processEvents()
        assert window.honorarios_btn.isEnabled() is True
        window._open_honorarios_dialog()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    draft = captured["draft"]
    assert isinstance(draft, HonorariosDraft)
    assert draft.case_number == "109/26.0PBBJA"
    assert draft.word_count == 1666
    assert draft.case_entity == "Juízo Local Criminal de Beja"
    assert draft.case_city == "Beja"
    assert captured["default_directory"] == _default_documents_dir()
    assert captured["exec"] is True
