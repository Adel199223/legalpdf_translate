"""Qt dialogs for settings and job log flows."""

from __future__ import annotations

import json
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from openai import OpenAI
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from legalpdf_translate.config import OPENAI_MODEL
from legalpdf_translate.glossary import (
    GlossaryEntry,
    builtin_glossary_json,
    default_ar_entries,
    load_glossary_from_text,
    normalize_glossaries,
    serialize_glossaries,
    supported_target_langs,
)
from legalpdf_translate.joblog_db import (
    insert_job_run,
    list_job_runs,
    open_job_log,
    update_joblog_visible_columns,
)
from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    MetadataSuggestion,
    apply_service_case_default_rule,
    extract_pdf_header_metadata,
    extract_photo_metadata_from_image,
    metadata_config_from_settings,
)
from legalpdf_translate.secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
    set_openai_key,
    set_ocr_key,
)
from legalpdf_translate.user_settings import app_data_dir, load_joblog_settings, save_joblog_settings

JOBLOG_COLUMNS = [
    "translation_date",
    "case_number",
    "job_type",
    "case_entity",
    "case_city",
    "service_entity",
    "service_city",
    "service_date",
    "lang",
    "pages",
    "word_count",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "profit",
]

JOBLOG_COLUMN_LABELS = {
    "translation_date": "Date",
    "case_number": "Case #",
    "job_type": "Job Type",
    "case_entity": "Case Entity",
    "case_city": "Case City",
    "service_entity": "Service Entity",
    "service_city": "Service City",
    "service_date": "Service Date",
    "lang": "Lang",
    "pages": "Pages",
    "word_count": "Words",
    "rate_per_word": "Rate/Word",
    "expected_total": "Expected",
    "amount_paid": "Paid",
    "api_cost": "API Cost",
    "profit": "Profit",
}


@dataclass(slots=True)
class JobLogSeed:
    completed_at: str
    translation_date: str
    job_type: str
    case_number: str
    case_entity: str
    case_city: str
    service_entity: str
    service_city: str
    service_date: str
    lang: str
    pages: int
    word_count: int
    rate_per_word: float
    expected_total: float
    amount_paid: float
    api_cost: float
    profit: float
    pdf_path: Path


def count_words_from_pages_dir(pages_dir: Path) -> int:
    total = 0
    for page_file in sorted(pages_dir.glob("page_*.txt")):
        text = page_file.read_text(encoding="utf-8")
        total += len(text.split())
    return total


def _date_from_completed_at(completed_at: str) -> str:
    cleaned = completed_at.strip()
    if cleaned == "":
        return ""
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return cleaned[:10]


def build_seed_from_run(
    *,
    pdf_path: Path,
    lang: str,
    pages_dir: Path,
    completed_pages: int,
    completed_at: str,
    default_rate_per_word: float,
    api_cost: float = 0.0,
) -> JobLogSeed:
    word_count = count_words_from_pages_dir(pages_dir)
    expected_total = round(float(default_rate_per_word) * float(word_count), 2)
    return JobLogSeed(
        completed_at=completed_at,
        translation_date=_date_from_completed_at(completed_at),
        job_type="Translation",
        case_number="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date=_date_from_completed_at(completed_at),
        lang=lang,
        pages=int(completed_pages),
        word_count=int(word_count),
        rate_per_word=float(default_rate_per_word),
        expected_total=expected_total,
        amount_paid=0.0,
        api_cost=float(api_cost),
        profit=round(expected_total - float(api_cost), 2),
        pdf_path=pdf_path,
    )


class QtSaveToJobLogDialog(QDialog):
    """Qt equivalent of save-to-joblog flow."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        db_path: Path,
        seed: JobLogSeed,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save to Job Log")
        self.resize(980, 660)

        self._db_path = db_path
        self._seed = seed
        self._on_saved = on_saved
        self._saved = False
        self._settings = load_joblog_settings()
        self._metadata_config: MetadataAutofillConfig = metadata_config_from_settings(self._settings)
        self._case_entity_user_set = False
        self._case_city_user_set = False

        self._build_ui()
        self._refresh_service_mirror_state()
        self._refresh_photo_controls()

    @property
    def saved(self) -> bool:
        return self._saved

    def _fill_combo(self, combo: QComboBox, values: list[str]) -> None:
        current = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        combo.setCurrentText(current)
        combo.blockSignals(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QFrame()
        top_grid = QGridLayout(top)
        top_grid.addWidget(QLabel("Job type"), 0, 0)
        self.job_type_combo = QComboBox()
        self.job_type_combo.setEditable(True)
        self.job_type_combo.addItems(list(self._settings["vocab_job_types"]))
        self.job_type_combo.setCurrentText(self._seed.job_type or "Translation")
        top_grid.addWidget(self.job_type_combo, 0, 1)
        top_grid.addWidget(QLabel(f"Translation date: {self._seed.translation_date}"), 0, 2)
        top_grid.addWidget(
            QLabel(f"Lang: {self._seed.lang} | Pages: {self._seed.pages} | Words: {self._seed.word_count}"),
            0,
            3,
        )
        top_grid.setColumnStretch(1, 1)
        top_grid.setColumnStretch(3, 1)
        root.addWidget(top)

        case_group = QGroupBox("CASE (belongs to)")
        case_form = QGridLayout(case_group)
        case_form.addWidget(QLabel("Case entity"), 0, 0)
        self.case_entity_combo = QComboBox()
        self.case_entity_combo.setEditable(True)
        self.case_entity_combo.addItems(list(self._settings["vocab_case_entities"]))
        self.case_entity_combo.setCurrentText(self._seed.case_entity)
        case_form.addWidget(self.case_entity_combo, 0, 1)
        self.add_case_entity_btn = QPushButton("Add...")
        case_form.addWidget(self.add_case_entity_btn, 0, 2)

        case_form.addWidget(QLabel("Case city"), 0, 3)
        self.case_city_combo = QComboBox()
        self.case_city_combo.setEditable(True)
        self.case_city_combo.addItems(list(self._settings["vocab_cities"]))
        self.case_city_combo.setCurrentText(self._seed.case_city)
        case_form.addWidget(self.case_city_combo, 0, 4)
        self.add_case_city_btn = QPushButton("Add...")
        case_form.addWidget(self.add_case_city_btn, 0, 5)

        case_form.addWidget(QLabel("Case number"), 1, 0)
        self.case_number_edit = QLineEdit(self._seed.case_number)
        case_form.addWidget(self.case_number_edit, 1, 1, 1, 2)
        case_form.setColumnStretch(1, 1)
        case_form.setColumnStretch(4, 1)
        root.addWidget(case_group)

        service_group = QGroupBox("SERVICE (provided to)")
        service_grid = QGridLayout(service_group)
        self.service_same_check = QCheckBox("Service same as Case")
        self.service_same_check.setChecked(bool(self._settings["service_equals_case_by_default"]))
        service_grid.addWidget(self.service_same_check, 0, 0, 1, 2)

        service_grid.addWidget(QLabel("Service entity"), 1, 0)
        self.service_entity_combo = QComboBox()
        self.service_entity_combo.setEditable(True)
        self.service_entity_combo.addItems(list(self._settings["vocab_service_entities"]))
        self.service_entity_combo.setCurrentText(self._seed.service_entity)
        service_grid.addWidget(self.service_entity_combo, 1, 1)
        self.add_service_entity_btn = QPushButton("Add...")
        service_grid.addWidget(self.add_service_entity_btn, 1, 2)

        service_grid.addWidget(QLabel("Service city"), 1, 3)
        self.service_city_combo = QComboBox()
        self.service_city_combo.setEditable(True)
        self.service_city_combo.addItems(list(self._settings["vocab_cities"]))
        self.service_city_combo.setCurrentText(self._seed.service_city)
        service_grid.addWidget(self.service_city_combo, 1, 4)
        self.add_service_city_btn = QPushButton("Add...")
        service_grid.addWidget(self.add_service_city_btn, 1, 5)

        service_grid.addWidget(QLabel("Service date (YYYY-MM-DD)"), 2, 0)
        self.service_date_edit = QLineEdit(self._seed.service_date)
        service_grid.addWidget(self.service_date_edit, 2, 1)
        service_grid.setColumnStretch(1, 1)
        service_grid.setColumnStretch(4, 1)
        root.addWidget(service_group)

        autofill_row = QHBoxLayout()
        self.autofill_header_btn = QPushButton("Autofill from PDF header")
        self.autofill_photo_btn = QPushButton("Autofill from photo...")
        self.photo_translation_check = QCheckBox("Usually for Interpretation; enable anyway")
        self.photo_hint = QLabel("")
        autofill_row.addWidget(self.autofill_header_btn)
        autofill_row.addWidget(self.autofill_photo_btn)
        autofill_row.addWidget(self.photo_translation_check)
        autofill_row.addStretch(1)
        autofill_row.addWidget(self.photo_hint)
        root.addLayout(autofill_row)

        finance_group = QGroupBox("Amounts (EUR)")
        finance_form = QGridLayout(finance_group)
        finance_form.addWidget(QLabel("Rate/word"), 0, 0)
        self.rate_edit = QLineEdit(f"{self._seed.rate_per_word:.4f}")
        finance_form.addWidget(self.rate_edit, 0, 1)
        finance_form.addWidget(QLabel("Expected total"), 0, 2)
        self.expected_total_edit = QLineEdit(f"{self._seed.expected_total:.2f}")
        finance_form.addWidget(self.expected_total_edit, 0, 3)
        finance_form.addWidget(QLabel("Amount paid"), 1, 0)
        self.amount_paid_edit = QLineEdit(f"{self._seed.amount_paid:.2f}")
        finance_form.addWidget(self.amount_paid_edit, 1, 1)
        finance_form.addWidget(QLabel("API cost"), 1, 2)
        self.api_cost_edit = QLineEdit(f"{self._seed.api_cost:.2f}")
        finance_form.addWidget(self.api_cost_edit, 1, 3)
        finance_form.addWidget(QLabel("Profit"), 2, 0)
        self.profit_edit = QLineEdit(f"{self._seed.profit:.2f}")
        finance_form.addWidget(self.profit_edit, 2, 1)
        finance_form.setColumnStretch(1, 1)
        finance_form.setColumnStretch(3, 1)
        root.addWidget(finance_group)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.save_btn)
        root.addLayout(actions)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._save)
        self.job_type_combo.currentTextChanged.connect(self._refresh_photo_controls)
        self.photo_translation_check.toggled.connect(self._refresh_photo_controls)
        self.case_entity_combo.currentTextChanged.connect(self._on_case_fields_changed)
        self.case_city_combo.currentTextChanged.connect(self._on_case_fields_changed)
        self.service_entity_combo.currentTextChanged.connect(self._on_service_fields_changed)
        self.service_city_combo.currentTextChanged.connect(self._on_service_fields_changed)
        self.service_same_check.toggled.connect(self._on_service_same_toggled)
        self.autofill_header_btn.clicked.connect(self._autofill_from_pdf_header)
        self.autofill_photo_btn.clicked.connect(self._autofill_from_photo)
        self.add_case_entity_btn.clicked.connect(lambda: self._add_value("Case entity", "vocab_case_entities", self.case_entity_combo))
        self.add_service_entity_btn.clicked.connect(lambda: self._add_value("Service entity", "vocab_service_entities", self.service_entity_combo))
        self.add_case_city_btn.clicked.connect(lambda: self._add_value("City", "vocab_cities", self.case_city_combo))
        self.add_service_city_btn.clicked.connect(lambda: self._add_value("City", "vocab_cities", self.service_city_combo))

    def _add_value(self, title: str, key: str, combo: QComboBox) -> None:
        value, ok = QInputDialog.getText(self, f"Add {title}", f"{title}:")
        if not ok:
            return
        cleaned = value.strip()
        if cleaned == "":
            return
        self._ensure_in_vocab(key, cleaned)
        combo.setCurrentText(cleaned)

    def _ensure_in_vocab(self, key: str, value: str) -> None:
        cleaned = value.strip()
        if cleaned == "":
            return
        bucket = list(self._settings[key])
        lowered = {item.casefold() for item in bucket}
        if cleaned.casefold() in lowered:
            return
        bucket.append(cleaned)
        self._settings[key] = bucket
        self._refresh_vocab_widgets()

    def _refresh_vocab_widgets(self) -> None:
        self._fill_combo(self.case_entity_combo, list(self._settings["vocab_case_entities"]))
        self._fill_combo(self.service_entity_combo, list(self._settings["vocab_service_entities"]))
        self._fill_combo(self.case_city_combo, list(self._settings["vocab_cities"]))
        self._fill_combo(self.service_city_combo, list(self._settings["vocab_cities"]))
        self._fill_combo(self.job_type_combo, list(self._settings["vocab_job_types"]))

    def _on_case_fields_changed(self) -> None:
        self._case_entity_user_set = True
        self._case_city_user_set = True
        if self.service_same_check.isChecked():
            self._sync_service_with_case()

    def _on_service_fields_changed(self) -> None:
        self._apply_non_court_default_rule()

    def _on_service_same_toggled(self) -> None:
        self._refresh_service_mirror_state()
        self._settings["service_equals_case_by_default"] = bool(self.service_same_check.isChecked())

    def _sync_service_with_case(self) -> None:
        self.service_entity_combo.setCurrentText(self.case_entity_combo.currentText().strip())
        self.service_city_combo.setCurrentText(self.case_city_combo.currentText().strip())

    def _refresh_service_mirror_state(self) -> None:
        same = self.service_same_check.isChecked()
        if same:
            self._sync_service_with_case()
        self.service_entity_combo.setEnabled(not same)
        self.service_city_combo.setEnabled(not same)

    def _refresh_photo_controls(self) -> None:
        photo_enabled = bool(self._settings["metadata_photo_enabled"])
        job_type = self.job_type_combo.currentText().strip()
        if not photo_enabled:
            self.autofill_photo_btn.setEnabled(False)
            self.photo_translation_check.setEnabled(False)
            self.photo_hint.setText("Photo metadata disabled in settings.")
            return
        if job_type == "Interpretation":
            self.autofill_photo_btn.setEnabled(True)
            self.photo_translation_check.setEnabled(False)
            self.photo_hint.setText("Interpretation mode.")
            return
        self.photo_translation_check.setEnabled(True)
        enabled = self.photo_translation_check.isChecked()
        self.autofill_photo_btn.setEnabled(enabled)
        self.photo_hint.setText("Usually Interpretation.")

    def _apply_header_suggestion(self, suggestion: MetadataSuggestion) -> None:
        if suggestion.case_entity:
            self._ensure_in_vocab("vocab_case_entities", suggestion.case_entity)
            self.case_entity_combo.setCurrentText(suggestion.case_entity)
        if suggestion.case_city:
            self._ensure_in_vocab("vocab_cities", suggestion.case_city)
            self.case_city_combo.setCurrentText(suggestion.case_city)
        if suggestion.case_number:
            self.case_number_edit.setText(suggestion.case_number)
        if self.service_same_check.isChecked():
            self._sync_service_with_case()
        else:
            if suggestion.service_entity and not self.service_entity_combo.currentText().strip():
                self._ensure_in_vocab("vocab_service_entities", suggestion.service_entity)
                self.service_entity_combo.setCurrentText(suggestion.service_entity)
            if suggestion.service_city and not self.service_city_combo.currentText().strip():
                self._ensure_in_vocab("vocab_cities", suggestion.service_city)
                self.service_city_combo.setCurrentText(suggestion.service_city)
        self._apply_non_court_default_rule()

    def _autofill_from_pdf_header(self) -> None:
        suggestion = extract_pdf_header_metadata(
            self._seed.pdf_path,
            vocab_cities=list(self._settings["vocab_cities"]),
            config=self._metadata_config,
            page_number=1,
        )
        if not any(
            (
                suggestion.case_entity,
                suggestion.case_city,
                suggestion.case_number,
                suggestion.service_entity,
                suggestion.service_city,
            )
        ):
            QMessageBox.warning(self, "Autofill", "No header text could be extracted.")
            return
        self._apply_header_suggestion(suggestion)

    def _autofill_from_photo(self) -> None:
        if not bool(self._settings["metadata_photo_enabled"]):
            QMessageBox.warning(self, "Photo autofill", "Photo autofill is disabled in settings.")
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select photo",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*.*)",
        )
        if not selected:
            return
        suggestion = extract_photo_metadata_from_image(
            Path(selected),
            vocab_cities=list(self._settings["vocab_cities"]),
            config=self._metadata_config,
        )
        if suggestion.service_city:
            self._ensure_in_vocab("vocab_cities", suggestion.service_city)
            self.service_city_combo.setCurrentText(suggestion.service_city)
        if suggestion.service_date:
            self.service_date_edit.setText(suggestion.service_date)
        if suggestion.case_number and not self.case_number_edit.text().strip():
            self.case_number_edit.setText(suggestion.case_number)
        self._apply_non_court_default_rule()

    def _apply_non_court_default_rule(self) -> None:
        case_entity, case_city = apply_service_case_default_rule(
            case_entity=self.case_entity_combo.currentText().strip(),
            case_city=self.case_city_combo.currentText().strip(),
            service_entity=self.service_entity_combo.currentText().strip(),
            service_city=self.service_city_combo.currentText().strip(),
            case_entity_user_set=self._case_entity_user_set,
            case_city_user_set=self._case_city_user_set,
            non_court_service_entities=list(self._settings["non_court_service_entities"]),
        )
        if case_entity is not None and case_entity != self.case_entity_combo.currentText().strip():
            self.case_entity_combo.setCurrentText(case_entity)
            self._ensure_in_vocab("vocab_case_entities", case_entity)
        if case_city is not None and case_city != self.case_city_combo.currentText().strip():
            self.case_city_combo.setCurrentText(case_city)
            self._ensure_in_vocab("vocab_cities", case_city)

    def _parse_float(self, value: str, label: str) -> float:
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return 0.0
        try:
            return float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric.") from exc

    def _save(self) -> None:
        try:
            rate = self._parse_float(self.rate_edit.text(), "Rate/word")
            expected_total = self._parse_float(self.expected_total_edit.text(), "Expected total")
            amount_paid = self._parse_float(self.amount_paid_edit.text(), "Amount paid")
            api_cost = self._parse_float(self.api_cost_edit.text(), "API cost")
            profit = self._parse_float(self.profit_edit.text(), "Profit")
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid values", str(exc))
            return

        if expected_total == 0.0 and rate > 0:
            expected_total = round(rate * float(self._seed.word_count), 2)
        if profit == 0.0:
            if amount_paid > 0:
                profit = round(amount_paid - api_cost, 2)
            else:
                profit = round(expected_total - api_cost, 2)

        service_date = self.service_date_edit.text().strip()
        if service_date:
            try:
                datetime.strptime(service_date, "%Y-%m-%d")
            except ValueError:
                QMessageBox.critical(self, "Invalid date", "Service date must be YYYY-MM-DD.")
                return

        case_entity = self.case_entity_combo.currentText().strip()
        case_city = self.case_city_combo.currentText().strip()
        service_entity = self.service_entity_combo.currentText().strip()
        service_city = self.service_city_combo.currentText().strip()
        if self.service_same_check.isChecked():
            service_entity = case_entity
            service_city = case_city

        payload = {
            "completed_at": self._seed.completed_at,
            "translation_date": self._seed.translation_date,
            "job_type": self.job_type_combo.currentText().strip() or "Translation",
            "case_number": self.case_number_edit.text().strip(),
            "case_entity": case_entity,
            "case_city": case_city,
            "service_entity": service_entity,
            "service_city": service_city,
            "service_date": service_date,
            "lang": self._seed.lang,
            "pages": int(self._seed.pages),
            "word_count": int(self._seed.word_count),
            "rate_per_word": rate,
            "expected_total": expected_total,
            "amount_paid": amount_paid,
            "api_cost": api_cost,
            "profit": profit,
        }

        with closing(open_job_log(self._db_path)) as conn:
            insert_job_run(conn, payload)

        self._ensure_in_vocab("vocab_job_types", payload["job_type"])
        if case_entity:
            self._ensure_in_vocab("vocab_case_entities", case_entity)
        if service_entity:
            self._ensure_in_vocab("vocab_service_entities", service_entity)
        if case_city:
            self._ensure_in_vocab("vocab_cities", case_city)
        if service_city:
            self._ensure_in_vocab("vocab_cities", service_city)

        save_joblog_settings(
            {
                "vocab_case_entities": self._settings["vocab_case_entities"],
                "vocab_service_entities": self._settings["vocab_service_entities"],
                "vocab_cities": self._settings["vocab_cities"],
                "vocab_job_types": self._settings["vocab_job_types"],
                "default_rate_per_word": self._settings["default_rate_per_word"],
                "joblog_visible_columns": self._settings["joblog_visible_columns"],
                "metadata_ai_enabled": self._settings["metadata_ai_enabled"],
                "metadata_photo_enabled": self._settings["metadata_photo_enabled"],
                "service_equals_case_by_default": bool(self.service_same_check.isChecked()),
                "non_court_service_entities": self._settings["non_court_service_entities"],
                "ocr_mode": self._settings["ocr_mode"],
                "ocr_engine": self._settings["ocr_engine"],
                "ocr_api_base_url": self._settings["ocr_api_base_url"],
                "ocr_api_model": self._settings["ocr_api_model"],
                "ocr_api_key_env_name": self._settings["ocr_api_key_env_name"],
            }
        )
        self._saved = True
        if self._on_saved is not None:
            self._on_saved()
        self.accept()


class QtJobLogWindow(QDialog):
    """Qt job log table window."""

    def __init__(self, *, parent: QWidget | None, db_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Job Log")
        self.resize(1280, 520)

        self._db_path = db_path
        self._settings = load_joblog_settings()
        self._visible_columns = update_joblog_visible_columns(self._settings["joblog_visible_columns"])
        if not self._visible_columns:
            self._visible_columns = ["translation_date", "case_number", "job_type"]

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.columns_btn = QPushButton("Columns...")
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.columns_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.table = QTableWidget(0, len(JOBLOG_COLUMNS), self)
        self.table.setHorizontalHeaderLabels([JOBLOG_COLUMN_LABELS[col] for col in JOBLOG_COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.refresh_btn.clicked.connect(self.refresh_rows)
        self.columns_btn.clicked.connect(self._open_columns_dialog)
        self._apply_visible_columns()
        self.refresh_rows()

    def _apply_visible_columns(self) -> None:
        visible = set(self._visible_columns)
        for idx, col in enumerate(JOBLOG_COLUMNS):
            self.table.setColumnHidden(idx, col not in visible)

    def refresh_rows(self) -> None:
        self.table.setRowCount(0)
        with closing(open_job_log(self._db_path)) as conn:
            rows = list_job_runs(conn, limit=1000)
        for row in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            for col_idx, col in enumerate(JOBLOG_COLUMNS):
                raw = row[col] if col in row.keys() else ""
                text = "" if raw is None else str(raw)
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(text))

    def _open_columns_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Visible Columns")
        layout = QVBoxLayout(dialog)
        checks: dict[str, QCheckBox] = {}
        for col in JOBLOG_COLUMNS:
            check = QCheckBox(JOBLOG_COLUMN_LABELS[col], dialog)
            check.setChecked(col in self._visible_columns)
            checks[col] = check
            layout.addWidget(check)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel", dialog)
        apply_btn = QPushButton("Apply", dialog)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(apply_btn)
        layout.addLayout(button_row)
        cancel_btn.clicked.connect(dialog.reject)

        def apply_columns() -> None:
            selected = [col for col in JOBLOG_COLUMNS if checks[col].isChecked()]
            selected = update_joblog_visible_columns(selected)
            if not selected:
                QMessageBox.warning(dialog, "Columns", "Select at least one column.")
                return
            self._visible_columns = selected
            self._settings["joblog_visible_columns"] = list(selected)
            save_joblog_settings({"joblog_visible_columns": list(selected)})
            self._apply_visible_columns()
            dialog.accept()

        apply_btn.clicked.connect(apply_columns)
        dialog.exec()


def _validate_url_or_blank(value: str) -> bool:
    cleaned = value.strip()
    if cleaned == "":
        return True
    parsed = urlparse(cleaned)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _to_int(value: str, *, field: str, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{field} must be between {min_value} and {max_value}.")
    return parsed


def _to_float(value: str, *, field: str, min_value: float, max_value: float) -> float:
    cleaned = value.strip().replace(",", ".")
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{field} must be between {min_value} and {max_value}.")
    return parsed


class QtGlossaryEditorDialog(QDialog):
    """Simple JSON editor for glossary content."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        initial_text: str,
        source_label: str,
        initial_path: Path | None,
        default_save_path: Path,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossary Editor")
        self.resize(860, 560)

        self._current_path = initial_path
        self._default_save_path = default_save_path.expanduser().resolve()
        self.saved_path: Path | None = None

        layout = QVBoxLayout(self)
        source = source_label.strip() or "Built-in glossary"
        self.source_label = QLabel(f"Source: {source}")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        self.json_edit = QPlainTextEdit()
        self.json_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.json_edit.setPlainText(initial_text)
        layout.addWidget(self.json_edit, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.validate_btn = QPushButton("Validate")
        self.save_btn = QPushButton("Save")
        self.save_as_btn = QPushButton("Save As...")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.validate_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.save_as_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.validate_btn.clicked.connect(self._validate)
        self.save_btn.clicked.connect(self._save)
        self.save_as_btn.clicked.connect(self._save_as)
        self.cancel_btn.clicked.connect(self.reject)

    @staticmethod
    def _validated_text(text: str, *, source: str) -> str:
        load_glossary_from_text(text, source=source)
        return text

    @staticmethod
    def _write_text_atomically(path: Path, text: str) -> Path:
        target = path.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(f"{target.suffix}.tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(target)
        return target

    def _validate(self) -> None:
        text = self.json_edit.toPlainText()
        source = str(self._current_path) if self._current_path is not None else "editor"
        try:
            self._validated_text(text, source=source)
        except ValueError as exc:
            QMessageBox.critical(self, "Glossary", str(exc))
            return
        QMessageBox.information(self, "Glossary", "Glossary JSON is valid.")

    def _save_to(self, path: Path) -> bool:
        text = self.json_edit.toPlainText()
        target = path.expanduser().resolve()
        try:
            self._validated_text(text, source=str(target))
            written = self._write_text_atomically(target, text)
        except ValueError as exc:
            QMessageBox.critical(self, "Glossary", str(exc))
            return False
        except OSError as exc:
            QMessageBox.critical(self, "Glossary", f"Unable to save glossary file: {target}\n{exc}")
            return False
        self._current_path = written
        self.saved_path = written
        return True

    def _save(self) -> None:
        target = self._current_path if self._current_path is not None else self._default_save_path
        if self._save_to(target):
            self.accept()

    def _save_as(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save glossary JSON",
            str(self._current_path or self._default_save_path),
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not selected:
            return
        if self._save_to(Path(selected)):
            self.accept()


class QtSettingsDialog(QDialog):
    """Qt equivalent of the Tk settings dialog."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        settings: dict[str, object],
        apply_callback: Callable[[dict[str, object], bool], None],
        collect_debug_paths: Callable[[], list[Path]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(980, 700)

        self._settings = dict(settings)
        self._apply_callback = apply_callback
        self._collect_debug_paths = collect_debug_paths
        self._glossaries_by_lang: dict[str, list[GlossaryEntry]] = normalize_glossaries({}, supported_target_langs())
        self._glossary_current_lang: str | None = None
        self._glossary_seed_version: int = 1
        self._build_ui()
        self._set_values_from_settings(self._settings)
        self._refresh_key_status()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs, 1)

        self.tab_keys = QWidget(self)
        self.tab_ocr = QWidget(self)
        self.tab_appearance = QWidget(self)
        self.tab_behaviour = QWidget(self)
        self.tab_glossary = QWidget(self)
        self.tab_diag = QWidget(self)
        self.tabs.addTab(self.tab_keys, "Keys & Providers")
        self.tabs.addTab(self.tab_ocr, "OCR Defaults")
        self.tabs.addTab(self.tab_appearance, "Appearance")
        self.tabs.addTab(self.tab_behaviour, "Behaviour & Performance")
        self.tabs.addTab(self.tab_glossary, "Glossary")
        self.tabs.addTab(self.tab_diag, "Diagnostics")

        self._build_tab_keys()
        self._build_tab_ocr_defaults()
        self._build_tab_appearance()
        self._build_tab_behaviour()
        self._build_tab_glossary()
        self._build_tab_diagnostics()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.apply_btn = QPushButton("Apply")
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        root.addLayout(buttons)

        self.apply_btn.clicked.connect(self._apply)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _build_tab_keys(self) -> None:
        layout = QVBoxLayout(self.tab_keys)
        openai_group = QGroupBox("OpenAI (Translation)")
        openai_layout = QGridLayout(openai_group)
        openai_layout.addWidget(QLabel("API key"), 0, 0)
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        openai_layout.addWidget(self.openai_key_edit, 0, 1)
        self.openai_toggle_btn = QPushButton("Show")
        self.openai_save_btn = QPushButton("Save")
        self.openai_clear_btn = QPushButton("Clear")
        self.openai_test_btn = QPushButton("Test")
        openai_layout.addWidget(self.openai_toggle_btn, 0, 2)
        openai_layout.addWidget(self.openai_save_btn, 0, 3)
        openai_layout.addWidget(self.openai_clear_btn, 0, 4)
        openai_layout.addWidget(self.openai_test_btn, 0, 5)
        self.openai_status_label = QLabel("Not stored")
        openai_layout.addWidget(self.openai_status_label, 1, 0, 1, 6)
        openai_layout.setColumnStretch(1, 1)
        layout.addWidget(openai_group)

        ocr_group = QGroupBox("OCR API (Fallback)")
        ocr_layout = QGridLayout(ocr_group)
        ocr_layout.addWidget(QLabel("API key"), 0, 0)
        self.ocr_key_edit = QLineEdit()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ocr_layout.addWidget(self.ocr_key_edit, 0, 1)
        self.ocr_toggle_btn = QPushButton("Show")
        self.ocr_save_btn = QPushButton("Save")
        self.ocr_clear_btn = QPushButton("Clear")
        self.ocr_test_btn = QPushButton("Test")
        ocr_layout.addWidget(self.ocr_toggle_btn, 0, 2)
        ocr_layout.addWidget(self.ocr_save_btn, 0, 3)
        ocr_layout.addWidget(self.ocr_clear_btn, 0, 4)
        ocr_layout.addWidget(self.ocr_test_btn, 0, 5)
        self.ocr_status_label = QLabel("Not stored")
        ocr_layout.addWidget(self.ocr_status_label, 1, 0, 1, 6)
        ocr_layout.setColumnStretch(1, 1)
        layout.addWidget(ocr_group)

        provider_group = QGroupBox("Provider Settings")
        provider_form = QFormLayout(provider_group)
        self.ocr_base_url_edit = QLineEdit()
        self.ocr_model_edit = QLineEdit()
        self.ocr_env_edit = QLineEdit()
        self.provider_summary_label = QLabel("")
        provider_form.addRow("OCR base URL", self.ocr_base_url_edit)
        provider_form.addRow("OCR model", self.ocr_model_edit)
        provider_form.addRow("OCR env var name", self.ocr_env_edit)
        provider_form.addRow("Summary", self.provider_summary_label)
        layout.addWidget(provider_group)
        layout.addStretch(1)

        self.openai_toggle_btn.clicked.connect(self._toggle_openai_key)
        self.ocr_toggle_btn.clicked.connect(self._toggle_ocr_key)
        self.openai_save_btn.clicked.connect(self._save_openai_key)
        self.openai_clear_btn.clicked.connect(self._clear_openai_key)
        self.openai_test_btn.clicked.connect(self._test_openai_key)
        self.ocr_save_btn.clicked.connect(self._save_ocr_key)
        self.ocr_clear_btn.clicked.connect(self._clear_ocr_key)
        self.ocr_test_btn.clicked.connect(self._test_ocr_key)

    def _build_tab_ocr_defaults(self) -> None:
        form = QFormLayout(self.tab_ocr)
        self.ocr_mode_default_combo = QComboBox()
        self.ocr_mode_default_combo.addItems(["off", "auto", "always"])
        self.ocr_engine_default_combo = QComboBox()
        self.ocr_engine_default_combo.addItems(["local", "local_then_api", "api"])
        self.min_chars_edit = QLineEdit()
        form.addRow("Default OCR mode", self.ocr_mode_default_combo)
        form.addRow("Default OCR engine", self.ocr_engine_default_combo)
        form.addRow("Min chars to accept OCR", self.min_chars_edit)

    def _build_tab_appearance(self) -> None:
        form = QFormLayout(self.tab_appearance)
        self.ui_theme_combo = QComboBox()
        self.ui_theme_combo.addItems(["dark_futuristic", "dark_simple"])
        self.ui_scale_combo = QComboBox()
        self.ui_scale_combo.addItems(["1.00", "1.10", "1.25"])
        form.addRow("Theme", self.ui_theme_combo)
        form.addRow("UI scale", self.ui_scale_combo)

    def _build_tab_behaviour(self) -> None:
        layout = QVBoxLayout(self.tab_behaviour)
        grid = QGridLayout()
        row = 0

        self.default_lang_combo = QComboBox(); self.default_lang_combo.addItems(["EN", "FR", "AR"])
        self.default_effort_combo = QComboBox(); self.default_effort_combo.addItems(["high", "xhigh"])
        self.default_effort_policy_combo = QComboBox(); self.default_effort_policy_combo.addItems(["adaptive", "fixed_high", "fixed_xhigh"])
        self.default_images_combo = QComboBox(); self.default_images_combo.addItems(["off", "auto", "always"])
        self.default_workers_combo = QComboBox(); self.default_workers_combo.addItems(["1", "2", "3", "4", "5", "6"])
        self.default_start_edit = QLineEdit()
        self.default_end_edit = QLineEdit()
        self.default_outdir_edit = QLineEdit()
        self.default_outdir_btn = QPushButton("Browse")
        self.glossary_file_edit = QLineEdit()
        self.glossary_file_btn = QPushButton("Browse")
        self.glossary_edit_btn = QPushButton("View/Edit...")
        self.glossary_builtin_btn = QPushButton("Use built-in")
        self.default_resume_check = QCheckBox("Default resume ON")
        self.default_keep_check = QCheckBox("Default keep intermediates ON")
        self.default_breaks_check = QCheckBox("Default page breaks ON")
        self.retries_edit = QLineEdit()
        self.backoff_cap_edit = QLineEdit()
        self.timeout_text_edit = QLineEdit()
        self.timeout_image_edit = QLineEdit()
        self.allow_xhigh_check = QCheckBox("Allow xhigh escalation (adaptive, image + short text only)")
        self.restore_defaults_btn = QPushButton("Restore defaults")

        grid.addWidget(QLabel("Default language"), row, 0); grid.addWidget(self.default_lang_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default effort"), row, 0); grid.addWidget(self.default_effort_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default effort policy"), row, 0); grid.addWidget(self.default_effort_policy_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default images mode"), row, 0); grid.addWidget(self.default_images_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default workers"), row, 0); grid.addWidget(self.default_workers_combo, row, 1); row += 1
        grid.addWidget(QLabel("Default start page"), row, 0); grid.addWidget(self.default_start_edit, row, 1); row += 1
        grid.addWidget(QLabel("Default end page"), row, 0); grid.addWidget(self.default_end_edit, row, 1); row += 1

        outdir_row = QHBoxLayout()
        outdir_row.addWidget(self.default_outdir_edit, 1)
        outdir_row.addWidget(self.default_outdir_btn)
        outdir_wrap = QWidget()
        outdir_wrap.setLayout(outdir_row)
        grid.addWidget(QLabel("Default output folder"), row, 0)
        grid.addWidget(outdir_wrap, row, 1)
        row += 1

        glossary_row = QHBoxLayout()
        glossary_row.addWidget(self.glossary_file_edit, 1)
        glossary_row.addWidget(self.glossary_file_btn)
        glossary_row.addWidget(self.glossary_edit_btn)
        glossary_row.addWidget(self.glossary_builtin_btn)
        glossary_wrap = QWidget()
        glossary_wrap.setLayout(glossary_row)
        grid.addWidget(QLabel("Glossary JSON file"), row, 0)
        grid.addWidget(glossary_wrap, row, 1)
        row += 1

        grid.addWidget(self.default_resume_check, row, 0, 1, 2); row += 1
        grid.addWidget(self.default_keep_check, row, 0, 1, 2); row += 1
        grid.addWidget(self.default_breaks_check, row, 0, 1, 2); row += 1

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        grid.addWidget(separator, row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Transport retries"), row, 0); grid.addWidget(self.retries_edit, row, 1); row += 1
        grid.addWidget(QLabel("Backoff cap (seconds)"), row, 0); grid.addWidget(self.backoff_cap_edit, row, 1); row += 1
        grid.addWidget(QLabel("Text timeout (seconds)"), row, 0); grid.addWidget(self.timeout_text_edit, row, 1); row += 1
        grid.addWidget(QLabel("Image timeout (seconds)"), row, 0); grid.addWidget(self.timeout_image_edit, row, 1); row += 1
        grid.addWidget(self.allow_xhigh_check, row, 0, 1, 2); row += 1
        grid.addWidget(self.restore_defaults_btn, row, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

        self.default_outdir_btn.clicked.connect(self._pick_default_outdir)
        self.glossary_file_btn.clicked.connect(self._pick_glossary_file)
        self.glossary_edit_btn.clicked.connect(self._open_glossary_editor)
        self.glossary_builtin_btn.clicked.connect(self._use_builtin_glossary)
        self.restore_defaults_btn.clicked.connect(self._restore_defaults)

    def _build_tab_glossary(self) -> None:
        layout = QVBoxLayout(self.tab_glossary)
        top = QHBoxLayout()
        top.addWidget(QLabel("Target language"))
        self.glossary_lang_combo = QComboBox()
        self.glossary_lang_combo.addItems(supported_target_langs())
        top.addWidget(self.glossary_lang_combo)
        top.addStretch(1)
        layout.addLayout(top)

        self.glossary_table = QTableWidget(0, 3, self.tab_glossary)
        self.glossary_table.setHorizontalHeaderLabels(["Source text", "Preferred translation", "Match"])
        self.glossary_table.verticalHeader().setVisible(False)
        self.glossary_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.glossary_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.glossary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.glossary_table, 1)

        actions = QHBoxLayout()
        self.glossary_add_row_btn = QPushButton("Add row")
        self.glossary_remove_rows_btn = QPushButton("Remove selected")
        actions.addWidget(self.glossary_add_row_btn)
        actions.addWidget(self.glossary_remove_rows_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        hint = QLabel("Glossary rows are per target language and used as preferred translation guidance.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.glossary_lang_combo.currentTextChanged.connect(self._on_glossary_language_changed)
        self.glossary_add_row_btn.clicked.connect(self._add_glossary_row)
        self.glossary_remove_rows_btn.clicked.connect(self._remove_selected_glossary_rows)

    def _new_glossary_match_combo(self, selected: str = "exact") -> QComboBox:
        combo = QComboBox()
        combo.addItem("Exact", "exact")
        combo.addItem("Contains", "contains")
        selected_clean = selected.strip().lower()
        if selected_clean == "contains":
            combo.setCurrentIndex(1)
        else:
            combo.setCurrentIndex(0)
        return combo

    def _glossary_match_value(self, combo: object | None) -> str:
        if combo is None:
            return "exact"
        value = combo.currentData() if hasattr(combo, "currentData") else None
        if isinstance(value, str) and value in {"exact", "contains"}:
            return value
        text = combo.currentText().strip().lower() if hasattr(combo, "currentText") else ""
        return "contains" if text == "contains" else "exact"

    def _set_glossary_table_rows(self, rows: list[GlossaryEntry]) -> None:
        self.glossary_table.setRowCount(0)
        for entry in rows:
            row = self.glossary_table.rowCount()
            self.glossary_table.insertRow(row)
            self.glossary_table.setItem(row, 0, QTableWidgetItem(entry.source))
            self.glossary_table.setItem(row, 1, QTableWidgetItem(entry.target))
            self.glossary_table.setCellWidget(row, 2, self._new_glossary_match_combo(entry.match))

    def _read_glossary_table_rows(self) -> list[GlossaryEntry]:
        rows: list[dict[str, str]] = []
        for row in range(self.glossary_table.rowCount()):
            source_item = self.glossary_table.item(row, 0)
            target_item = self.glossary_table.item(row, 1)
            source = source_item.text().strip() if source_item else ""
            target = target_item.text().strip() if target_item else ""
            match = self._glossary_match_value(self.glossary_table.cellWidget(row, 2))
            rows.append(
                {
                    "source": source,
                    "target": target,
                    "match": match,
                }
            )
        normalized = normalize_glossaries(
            {self._glossary_current_lang or "EN": rows},
            [self._glossary_current_lang or "EN"],
        )
        return normalized.get(self._glossary_current_lang or "EN", [])

    def _save_current_glossary_language_rows(self) -> None:
        if self._glossary_current_lang is None:
            return
        self._glossaries_by_lang[self._glossary_current_lang] = self._read_glossary_table_rows()

    def _on_glossary_language_changed(self, lang_text: str) -> None:
        next_lang = str(lang_text or "").strip().upper()
        if next_lang == "":
            return
        self._save_current_glossary_language_rows()
        self._glossary_current_lang = next_lang
        self._set_glossary_table_rows(self._glossaries_by_lang.get(next_lang, []))

    def _set_glossaries_from_settings(self, settings: dict[str, object]) -> None:
        langs = supported_target_langs()
        self._glossaries_by_lang = normalize_glossaries(settings.get("glossaries_by_lang"), langs)
        seed_raw = settings.get("glossary_seed_version", 1)
        try:
            self._glossary_seed_version = max(1, int(seed_raw))  # type: ignore[arg-type]
        except Exception:
            self._glossary_seed_version = 1
        preferred = str(settings.get("default_lang", "EN") or "EN").strip().upper()
        if preferred not in langs:
            preferred = langs[0]

        self.glossary_lang_combo.blockSignals(True)
        self.glossary_lang_combo.clear()
        self.glossary_lang_combo.addItems(langs)
        self.glossary_lang_combo.setCurrentText(preferred)
        self.glossary_lang_combo.blockSignals(False)
        self._glossary_current_lang = preferred
        self._set_glossary_table_rows(self._glossaries_by_lang.get(preferred, []))

    def _add_glossary_row(self) -> None:
        row = self.glossary_table.rowCount()
        self.glossary_table.insertRow(row)
        self.glossary_table.setItem(row, 0, QTableWidgetItem(""))
        self.glossary_table.setItem(row, 1, QTableWidgetItem(""))
        self.glossary_table.setCellWidget(row, 2, self._new_glossary_match_combo("exact"))

    def _remove_selected_glossary_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.glossary_table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return
        for row in selected_rows:
            self.glossary_table.removeRow(row)

    def _build_tab_diagnostics(self) -> None:
        layout = QVBoxLayout(self.tab_diag)
        self.diag_cost_summary_check = QCheckBox("Show cost summary")
        self.diag_verbose_meta_check = QCheckBox("Verbose metadata logs")
        self.diag_admin_mode_check = QCheckBox("Admin diagnostics mode")
        self.diag_snippets_check = QCheckBox("Include small sanitized snippets (first 200 chars per page)")
        self.create_bundle_btn = QPushButton("Create debug bundle")
        hint = QLabel("Bundle excludes page text files and all credentials.")
        layout.addWidget(self.diag_cost_summary_check)
        layout.addWidget(self.diag_verbose_meta_check)
        layout.addWidget(self.diag_admin_mode_check)
        layout.addWidget(self.diag_snippets_check)
        layout.addWidget(self.create_bundle_btn)
        layout.addWidget(hint)
        layout.addStretch(1)
        self.diag_admin_mode_check.toggled.connect(self.diag_snippets_check.setEnabled)
        self.create_bundle_btn.clicked.connect(self._create_debug_bundle)

    def _set_values_from_settings(self, settings: dict[str, object]) -> None:
        self.ui_theme_combo.setCurrentText(str(settings.get("ui_theme", "dark_futuristic")))
        self.ui_scale_combo.setCurrentText(f"{float(settings.get('ui_scale', 1.0)):.2f}")
        self.default_lang_combo.setCurrentText(str(settings.get("default_lang", "EN")))
        self.default_effort_combo.setCurrentText(str(settings.get("default_effort", "high")))
        self.default_effort_policy_combo.setCurrentText(str(settings.get("default_effort_policy", "adaptive")))
        self.default_images_combo.setCurrentText(str(settings.get("default_images_mode", "off")))
        self.default_workers_combo.setCurrentText(str(settings.get("default_workers", 3)))
        self.default_resume_check.setChecked(bool(settings.get("default_resume", True)))
        self.default_keep_check.setChecked(bool(settings.get("default_keep_intermediates", True)))
        self.default_breaks_check.setChecked(bool(settings.get("default_page_breaks", True)))
        self.default_start_edit.setText(str(settings.get("default_start_page", 1)))
        default_end = settings.get("default_end_page")
        self.default_end_edit.setText("" if default_end in (None, "") else str(default_end))
        self.default_outdir_edit.setText(str(settings.get("default_outdir", "")))
        self.glossary_file_edit.setText(str(settings.get("glossary_file_path", "")))
        self.ocr_mode_default_combo.setCurrentText(str(settings.get("ocr_mode_default", "auto")))
        self.ocr_engine_default_combo.setCurrentText(str(settings.get("ocr_engine_default", "local_then_api")))
        self.min_chars_edit.setText(str(settings.get("min_chars_to_accept_ocr", 200)))
        self.ocr_base_url_edit.setText(str(settings.get("ocr_api_base_url", "")))
        self.ocr_model_edit.setText(str(settings.get("ocr_api_model", "")))
        self.ocr_env_edit.setText(str(settings.get("ocr_api_key_env_name", "DEEPSEEK_API_KEY")))
        self.retries_edit.setText(str(settings.get("perf_max_transport_retries", 4)))
        self.backoff_cap_edit.setText(str(settings.get("perf_backoff_cap_seconds", 12.0)))
        self.timeout_text_edit.setText(str(settings.get("perf_timeout_text_seconds", 90)))
        self.timeout_image_edit.setText(str(settings.get("perf_timeout_image_seconds", 120)))
        self.allow_xhigh_check.setChecked(bool(settings.get("allow_xhigh_escalation", False)))
        self.diag_cost_summary_check.setChecked(bool(settings.get("diagnostics_show_cost_summary", True)))
        self.diag_verbose_meta_check.setChecked(bool(settings.get("diagnostics_verbose_metadata_logs", False)))
        self.diag_admin_mode_check.setChecked(bool(settings.get("diagnostics_admin_mode", True)))
        self.diag_snippets_check.setChecked(bool(settings.get("diagnostics_include_sanitized_snippets", False)))
        self.diag_snippets_check.setEnabled(self.diag_admin_mode_check.isChecked())
        self._set_glossaries_from_settings(settings)

    def _pick_default_outdir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose default output folder")
        if chosen:
            self.default_outdir_edit.setText(chosen)

    def _pick_glossary_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select glossary JSON file",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if selected:
            self.glossary_file_edit.setText(selected)

    def _resolve_glossary_path(self) -> Path | None:
        raw = self.glossary_file_edit.text().strip()
        if raw == "":
            return None
        return Path(raw).expanduser().resolve()

    def _default_glossary_save_path(self) -> Path:
        return (app_data_dir() / "glossary.json").expanduser().resolve()

    def _load_glossary_editor_text(self, glossary_path: Path | None) -> tuple[str, str]:
        if glossary_path is None:
            return builtin_glossary_json(indent=2), "Built-in glossary"
        try:
            raw = glossary_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Unable to read glossary file: {glossary_path}") from exc
        return raw, str(glossary_path)

    def _open_glossary_editor(self) -> None:
        glossary_path = self._resolve_glossary_path()
        try:
            initial_text, source_label = self._load_glossary_editor_text(glossary_path)
        except ValueError as exc:
            QMessageBox.critical(self, "Glossary", str(exc))
            return

        editor = QtGlossaryEditorDialog(
            parent=self,
            initial_text=initial_text,
            source_label=source_label,
            initial_path=glossary_path,
            default_save_path=self._default_glossary_save_path(),
        )
        if editor.exec() == QDialog.DialogCode.Accepted and editor.saved_path is not None:
            self.glossary_file_edit.setText(str(editor.saved_path))

    def _use_builtin_glossary(self) -> None:
        if self.glossary_file_edit.text().strip() == "":
            QMessageBox.information(self, "Glossary", "Built-in glossary is already active.")
            return
        confirm = QMessageBox.question(
            self,
            "Use built-in glossary",
            "Clear custom glossary path and use built-in glossary rules?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Ok:
            return
        self.glossary_file_edit.clear()
        QMessageBox.information(self, "Glossary", "Using built-in glossary rules.")

    def _toggle_openai_key(self) -> None:
        if self.openai_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            confirm = QMessageBox.question(
                self,
                "Reveal OpenAI key",
                "Reveal stored OpenAI API key in plain text?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Ok:
                return
            try:
                stored = get_openai_key()
            except RuntimeError as exc:
                QMessageBox.critical(self, "Settings", str(exc))
                return
            if not stored:
                QMessageBox.warning(self, "Settings", "OpenAI key is not stored.")
                self._refresh_key_status()
                return
            self.openai_key_edit.setText(stored)
            self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.openai_toggle_btn.setText("Hide")
        else:
            self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.openai_toggle_btn.setText("Show")

    def _toggle_ocr_key(self) -> None:
        if self.ocr_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            confirm = QMessageBox.question(
                self,
                "Reveal OCR key",
                "Reveal stored OCR API key in plain text?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Ok:
                return
            try:
                stored = get_ocr_key()
            except RuntimeError as exc:
                QMessageBox.critical(self, "Settings", str(exc))
                return
            if not stored:
                QMessageBox.warning(self, "Settings", "OCR key is not stored.")
                self._refresh_key_status()
                return
            self.ocr_key_edit.setText(stored)
            self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.ocr_toggle_btn.setText("Hide")
        else:
            self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.ocr_toggle_btn.setText("Show")

    def _refresh_key_status(self) -> None:
        try:
            openai_stored = bool(get_openai_key())
            ocr_stored = bool(get_ocr_key())
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            openai_stored = False
            ocr_stored = False
        self.openai_status_label.setText("Stored" if openai_stored else "Not stored")
        self.ocr_status_label.setText("Stored" if ocr_stored else "Not stored")
        self.openai_toggle_btn.setEnabled(openai_stored)
        self.ocr_toggle_btn.setEnabled(ocr_stored)
        if not openai_stored:
            self.openai_key_edit.clear()
            self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.openai_toggle_btn.setText("Show")
        if not ocr_stored:
            self.ocr_key_edit.clear()
            self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.ocr_toggle_btn.setText("Show")
        self.provider_summary_label.setText(
            "Provider mode: OpenAI credentials "
            f"{'present' if openai_stored else 'missing'}, OCR credentials {'present' if ocr_stored else 'missing'}."
        )

    def _save_openai_key(self) -> None:
        key = self.openai_key_edit.text().strip()
        if not key:
            QMessageBox.critical(self, "Settings", "OpenAI API key cannot be empty.")
            return
        try:
            set_openai_key(key)
            if not get_openai_key():
                raise RuntimeError("Secure credential storage is unavailable on this system.")
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.openai_key_edit.clear()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_toggle_btn.setText("Show")
        self._refresh_key_status()
        QMessageBox.information(self, "Settings", "Saved")

    def _clear_openai_key(self) -> None:
        try:
            delete_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.openai_key_edit.clear()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_toggle_btn.setText("Show")
        self._refresh_key_status()

    def _save_ocr_key(self) -> None:
        key = self.ocr_key_edit.text().strip()
        if not key:
            QMessageBox.critical(self, "Settings", "OCR API key cannot be empty.")
            return
        try:
            set_ocr_key(key)
            if not get_ocr_key():
                raise RuntimeError("Secure credential storage is unavailable on this system.")
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.ocr_key_edit.clear()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_toggle_btn.setText("Show")
        self._refresh_key_status()
        QMessageBox.information(self, "Settings", "Saved")

    def _clear_ocr_key(self) -> None:
        try:
            delete_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.ocr_key_edit.clear()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_toggle_btn.setText("Show")
        self._refresh_key_status()

    def _test_openai_key(self) -> None:
        try:
            key = get_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        if not key:
            QMessageBox.warning(self, "Key Test", "OpenAI key is not stored.")
            return
        started = time.perf_counter()
        try:
            client = OpenAI(api_key=key)
            client.responses.create(
                model=OPENAI_MODEL,
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                max_output_tokens=8,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Key Test", f"OpenAI key test failed: {type(exc).__name__}")
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        QMessageBox.information(self, "Key Test", f"OpenAI test passed ({latency_ms} ms).")

    def _test_ocr_key(self) -> None:
        try:
            key = get_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        if not key:
            QMessageBox.warning(self, "Key Test", "OCR key is not stored.")
            return
        base_url = self.ocr_base_url_edit.text().strip()
        model = self.ocr_model_edit.text().strip() or "gpt-4o-mini"
        started = time.perf_counter()
        if base_url == "":
            latency_ms = int((time.perf_counter() - started) * 1000)
            QMessageBox.information(self, "Key Test", f"OCR key is present ({latency_ms} ms).")
            return
        try:
            client = OpenAI(api_key=key, base_url=base_url)
            client.responses.create(
                model=model,
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                max_output_tokens=8,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Key Test", f"OCR key test failed: {type(exc).__name__}")
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        QMessageBox.information(self, "Key Test", f"OCR test passed ({latency_ms} ms).")

    def _restore_defaults(self) -> None:
        self.default_lang_combo.setCurrentText("EN")
        self.default_effort_combo.setCurrentText("high")
        self.default_effort_policy_combo.setCurrentText("adaptive")
        self.default_images_combo.setCurrentText("off")
        self.default_workers_combo.setCurrentText("3")
        self.default_resume_check.setChecked(True)
        self.default_keep_check.setChecked(True)
        self.default_breaks_check.setChecked(True)
        self.default_start_edit.setText("1")
        self.default_end_edit.setText("")
        self.default_outdir_edit.setText("")
        self.glossary_file_edit.setText("")
        self._glossaries_by_lang = normalize_glossaries({}, supported_target_langs())
        self._glossaries_by_lang["AR"] = default_ar_entries()
        self._glossary_seed_version = 1
        self._set_glossaries_from_settings(
            {
                "default_lang": "EN",
                "glossaries_by_lang": serialize_glossaries(self._glossaries_by_lang),
                "glossary_seed_version": self._glossary_seed_version,
            }
        )
        self.ocr_mode_default_combo.setCurrentText("auto")
        self.ocr_engine_default_combo.setCurrentText("local_then_api")
        self.retries_edit.setText("4")
        self.backoff_cap_edit.setText("12.0")
        self.timeout_text_edit.setText("90")
        self.timeout_image_edit.setText("120")
        self.allow_xhigh_check.setChecked(False)

    def _collect_values(self) -> dict[str, object]:
        base_url = self.ocr_base_url_edit.text().strip()
        if not _validate_url_or_blank(base_url):
            raise ValueError("OCR base URL must be a valid http/https URL.")

        default_end_text = self.default_end_edit.text().strip()
        if default_end_text == "":
            default_end = None
        else:
            default_end = _to_int(default_end_text, field="Default end page", min_value=1, max_value=100000)
        default_start = _to_int(self.default_start_edit.text(), field="Default start page", min_value=1, max_value=100000)
        if default_end is not None and default_start > default_end:
            raise ValueError("Default start page must be <= default end page.")

        ui_scale = _to_float(self.ui_scale_combo.currentText(), field="UI scale", min_value=1.0, max_value=1.25)
        if ui_scale not in (1.0, 1.1, 1.25):
            raise ValueError("UI scale must be one of 1.00, 1.10, or 1.25.")

        self._save_current_glossary_language_rows()
        normalized_glossaries = normalize_glossaries(self._glossaries_by_lang, supported_target_langs())

        return {
            "ui_theme": self.ui_theme_combo.currentText().strip(),
            "ui_scale": ui_scale,
            "default_lang": self.default_lang_combo.currentText().strip().upper(),
            "default_effort": self.default_effort_combo.currentText().strip().lower(),
            "default_effort_policy": self.default_effort_policy_combo.currentText().strip().lower(),
            "default_images_mode": self.default_images_combo.currentText().strip().lower(),
            "default_workers": _to_int(self.default_workers_combo.currentText(), field="Default workers", min_value=1, max_value=6),
            "default_resume": bool(self.default_resume_check.isChecked()),
            "default_keep_intermediates": bool(self.default_keep_check.isChecked()),
            "default_page_breaks": bool(self.default_breaks_check.isChecked()),
            "default_start_page": default_start,
            "default_end_page": default_end,
            "default_outdir": self.default_outdir_edit.text().strip(),
            "glossaries_by_lang": serialize_glossaries(normalized_glossaries),
            "glossary_seed_version": max(1, int(self._glossary_seed_version)),
            "glossary_file_path": self.glossary_file_edit.text().strip(),
            "ocr_mode_default": self.ocr_mode_default_combo.currentText().strip().lower(),
            "ocr_engine_default": self.ocr_engine_default_combo.currentText().strip().lower(),
            "ocr_api_base_url": base_url,
            "ocr_api_model": self.ocr_model_edit.text().strip(),
            "ocr_api_key_env_name": self.ocr_env_edit.text().strip() or "DEEPSEEK_API_KEY",
            "perf_max_transport_retries": _to_int(self.retries_edit.text(), field="Transport retries", min_value=0, max_value=12),
            "perf_backoff_cap_seconds": _to_float(self.backoff_cap_edit.text(), field="Backoff cap", min_value=1.0, max_value=120.0),
            "perf_timeout_text_seconds": _to_int(self.timeout_text_edit.text(), field="Text timeout", min_value=5, max_value=600),
            "perf_timeout_image_seconds": _to_int(self.timeout_image_edit.text(), field="Image timeout", min_value=5, max_value=1200),
            "allow_xhigh_escalation": bool(self.allow_xhigh_check.isChecked()),
            "adaptive_effort_enabled": self.default_effort_policy_combo.currentText().strip().lower() == "adaptive",
            "adaptive_effort_xhigh_only_when_image_or_validator_fail": bool(self.allow_xhigh_check.isChecked()),
            "diagnostics_show_cost_summary": bool(self.diag_cost_summary_check.isChecked()),
            "diagnostics_verbose_metadata_logs": bool(self.diag_verbose_meta_check.isChecked()),
            "diagnostics_admin_mode": bool(self.diag_admin_mode_check.isChecked()),
            "diagnostics_include_sanitized_snippets": bool(self.diag_snippets_check.isChecked()),
            "min_chars_to_accept_ocr": _to_int(self.min_chars_edit.text(), field="Min chars to accept OCR", min_value=20, max_value=10000),
        }

    def _apply(self) -> None:
        try:
            values = self._collect_values()
        except ValueError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self._apply_callback(values, False)

    def _save(self) -> None:
        try:
            values = self._collect_values()
        except ValueError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self._apply_callback(values, True)
        QMessageBox.information(self, "Settings", "Saved")

    def _create_debug_bundle(self) -> None:
        try:
            snapshot = self._collect_values()
        except ValueError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save debug bundle", "", "Zip archive (*.zip)")
        if not save_path:
            return
        output = Path(save_path).expanduser().resolve()
        metadata_paths = self._collect_debug_paths()
        try:
            with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
                for path in metadata_paths:
                    if not path.exists() or not path.is_file():
                        continue
                    archive.write(path, arcname=path.name)
                archive.writestr("settings_snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Settings", f"Failed to create debug bundle: {exc}")
            return
        QMessageBox.information(self, "Settings", f"Debug bundle created:\n{output}")
