from __future__ import annotations

import os
import sys
from pathlib import Path

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox

from legalpdf_translate.glossary_builder import GlossaryBuilderSuggestion
from legalpdf_translate.qt_gui.guarded_inputs import NoWheelComboBox, NoWheelSpinBox
from legalpdf_translate.qt_gui.tools_dialogs import QtCalibrationAuditDialog, QtGlossaryBuilderDialog
from legalpdf_translate.types import RunConfig, TargetLang


def _config_for(tmp_path: Path) -> RunConfig:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")
    return RunConfig(
        pdf_path=pdf_path,
        output_dir=tmp_path,
        target_lang=TargetLang.EN,
    )


def test_glossary_builder_dialog_uses_guarded_controls_and_primary_actions(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "builder.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% builder test pdf\n")
    dialog = QtGlossaryBuilderDialog(
        parent=None,
        settings={"diagnostics_admin_mode": True, "openai_reasoning_effort_lemma": "high"},
        current_pdf_path=pdf_path,
        current_output_dir=tmp_path,
        default_target_lang="FR",
        save_settings_callback=lambda _values: None,
    )
    try:
        assert isinstance(dialog.source_combo, NoWheelComboBox)
        assert isinstance(dialog.target_lang_combo, NoWheelComboBox)
        assert isinstance(dialog.mode_combo, NoWheelComboBox)
        assert isinstance(dialog.lemma_effort_combo, NoWheelComboBox)
        assert dialog.source_combo.isEditable() is False
        assert dialog.target_lang_combo.isEditable() is False
        assert dialog.mode_combo.isEditable() is False
        assert dialog.lemma_effort_combo.isEditable() is False

        assert dialog.generate_btn.objectName() == "PrimaryButton"
        assert dialog.apply_btn.objectName() == "PrimaryButton"
        assert dialog.remove_run_dir_btn.objectName() == "DangerButton"
        assert dialog.clear_run_dirs_btn.objectName() == "DangerButton"
        assert dialog.remove_pdf_btn.objectName() == "DangerButton"
        assert dialog.clear_pdf_btn.objectName() == "DangerButton"

        dialog._suggestions = [
            GlossaryBuilderSuggestion(
                source_term="acusacao",
                target_lang="FR",
                occurrences_doc=5,
                occurrences_corpus=8,
                df_pages=3,
                df_docs=2,
                suggested_translation="accusation",
                confidence=0.75,
                recommended_scope="project",
            )
        ]
        dialog._populate_table()
        scope_widget = dialog.table.cellWidget(0, 7)
        assert isinstance(scope_widget, QComboBox)
        assert not isinstance(scope_widget, NoWheelComboBox)
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_calibration_audit_dialog_uses_guarded_spins_and_primary_actions(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    dialog = QtCalibrationAuditDialog(
        parent=None,
        settings={},
        build_config_callback=lambda: _config_for(tmp_path),
        save_settings_callback=lambda _values: None,
    )
    try:
        assert isinstance(dialog.sample_pages_spin, NoWheelSpinBox)
        assert isinstance(dialog.excerpt_chars_spin, NoWheelSpinBox)
        assert dialog.run_btn.objectName() == "PrimaryButton"
        assert dialog.apply_btn.objectName() == "PrimaryButton"

        dialog._populate_glossary_suggestions(
            [
                {
                    "source_text": "acusacao",
                    "preferred_translation": "accusation",
                    "target_lang": "FR",
                    "source_lang": "PT",
                    "match_mode": "exact",
                    "tier": 2,
                    "page_number": 1,
                }
            ]
        )
        scope_widget = dialog.glossary_suggestions_table.cellWidget(0, 7)
        assert isinstance(scope_widget, QComboBox)
        assert not isinstance(scope_widget, NoWheelComboBox)
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()
