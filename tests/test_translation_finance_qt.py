from dataclasses import replace

from PySide6.QtWidgets import QApplication

from legalpdf_translate.joblog_flow import build_seed_from_joblog_row
from legalpdf_translate.qt_gui.dialogs import QtSaveToJobLogDialog


def seed():
    return build_seed_from_joblog_row({"job_type": "Translation", "lang": "EN", "pages": 5,
        "translation_date": "2026-09-27", "case_number": "FICTIONAL", "case_city": "City",
        "word_count": 1132, "rate_per_word": .027, "expected_total": 30.56,
        "api_cost": .1648255, "estimated_api_cost": .1648255, "profit": None})


def test_qt_new_translation_uses_precise_rate_automatic_total_and_null_profit(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "jobs.sqlite", seed=seed())
    try:
        assert dialog.total_mode_combo.currentData() == "auto"
        assert dialog.expected_total_edit.isReadOnly()
        assert dialog.profit_edit.isReadOnly() and dialog.profit_edit.text() == ""
        dialog.word_count_edit.setText("1138")
        assert dialog.expected_total_edit.text() == "30.73"
        dialog.rate_edit.setText("0,03")
        assert dialog.expected_total_edit.text() == "34.14"
        payload = dialog._normalized_payload()
        assert payload["profit"] is None
        assert payload["api_cost"] == payload["estimated_api_cost"] == .1648255
        dialog.total_mode_combo.setCurrentIndex(1)
        dialog.expected_total_edit.setText("17.43")
        dialog.word_count_edit.setText("1501")
        assert dialog._normalized_payload()["expected_total"] == 17.43
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_qt_old_record_keeps_financial_history_until_explicit_calculation(tmp_path):
    app = QApplication.instance() or QApplication([])
    old = replace(seed(), rate_per_word=.08, expected_total=90.56, profit=90.4)
    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "jobs.sqlite", seed=old, edit_row_id=1)
    try:
        assert dialog.total_mode_combo.currentData() == "manual"
        payload = dialog._normalized_payload()
        assert (payload["rate_per_word"], payload["expected_total"], payload["profit"]) == (.08, 90.56, 90.4)
        dialog.total_mode_combo.setCurrentIndex(0)
        dialog.rate_edit.setText("0.027")
        dialog.word_count_edit.setText("1138")
        payload = dialog._normalized_payload()
        assert payload["expected_total"] == 30.73
        assert payload["profit"] == 90.4
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
