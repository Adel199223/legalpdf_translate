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
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from openai import OpenAI
from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
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
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from legalpdf_translate.config import (
    DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS,
    DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS,
    OPENAI_MODEL,
)
from legalpdf_translate.glossary import (
    GlossaryEntry,
    build_consistency_glossary_markdown,
    builtin_glossary_json,
    coerce_glossary_tier,
    coerce_source_lang,
    default_ar_entries,
    load_glossary_from_text,
    normalize_enabled_tiers_by_target_lang,
    normalize_glossaries,
    serialize_glossaries,
    supported_target_langs,
    valid_glossary_tiers,
    valid_source_langs,
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
    choose_court_email_suggestion,
    extract_pdf_header_metadata_priority_pages,
    extract_photo_metadata_from_image,
    metadata_config_from_settings,
    rank_court_email_suggestions,
)
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.pdf_text_order import extract_ordered_page_text, get_page_count
from legalpdf_translate.qt_gui.guarded_inputs import NoWheelComboBox
from legalpdf_translate.review_export import export_review_queue
from legalpdf_translate.secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
    set_openai_key,
    set_ocr_key,
)
from legalpdf_translate.study_glossary import (
    StudyCandidate,
    StudyGlossaryEntry,
    apply_subsumption_suppression,
    build_study_glossary_markdown,
    build_entry_from_candidate,
    compute_non_overlapping_tier_assignment,
    create_candidate_stats,
    compute_next_review_date,
    finalize_study_candidates,
    filter_candidates_by_thresholds,
    fill_translations_for_entry,
    merge_study_entries,
    normalize_study_entries,
    serialize_study_entries,
    supported_learning_langs,
    tokenize_page_for_mode,
    update_candidate_stats_from_page,
)
from legalpdf_translate.user_settings import app_data_dir, load_joblog_settings, save_gui_settings, save_joblog_settings

JOBLOG_COLUMNS = [
    "translation_date",
    "case_number",
    "court_email",
    "run_id",
    "job_type",
    "case_entity",
    "case_city",
    "service_entity",
    "service_city",
    "service_date",
    "lang",
    "target_lang",
    "pages",
    "word_count",
    "total_tokens",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "estimated_api_cost",
    "quality_risk_score",
    "profit",
]

JOBLOG_COLUMN_LABELS = {
    "translation_date": "Date",
    "case_number": "Case #",
    "court_email": "Court Email",
    "run_id": "Run ID",
    "job_type": "Job Type",
    "case_entity": "Case Entity",
    "case_city": "Case City",
    "service_entity": "Service Entity",
    "service_city": "Service City",
    "service_date": "Service Date",
    "lang": "Lang",
    "target_lang": "Target",
    "pages": "Pages",
    "word_count": "Words",
    "total_tokens": "Total Tokens",
    "rate_per_word": "Rate/Word",
    "expected_total": "Expected",
    "amount_paid": "Paid",
    "api_cost": "API Cost",
    "estimated_api_cost": "Est. API Cost",
    "quality_risk_score": "Risk Score",
    "profit": "Profit",
}


@dataclass(slots=True)
class JobLogSeed:
    completed_at: str
    translation_date: str
    job_type: str
    case_number: str
    court_email: str
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
    run_id: str
    target_lang: str
    total_tokens: int | None
    estimated_api_cost: float | None
    quality_risk_score: float | None
    profit: float
    pdf_path: Path


_WORD_XML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_DOCX_WORD_SEPARATOR_TAGS = {"tab", "br", "cr"}


def count_words_from_pages_dir(pages_dir: Path) -> int:
    total = 0
    for page_file in sorted(pages_dir.glob("page_*.txt")):
        text = page_file.read_text(encoding="utf-8")
        total += len(text.split())
    return total


def _extract_visible_text_from_docx(docx_path: Path) -> str:
    if not docx_path.exists() or not docx_path.is_file():
        return ""
    try:
        with ZipFile(docx_path) as archive:
            raw_xml = archive.read("word/document.xml")
    except (OSError, KeyError):
        return ""
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return ""

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", _WORD_XML_NS):
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t":
                if node.text:
                    parts.append(node.text)
            elif tag in _DOCX_WORD_SEPARATOR_TAGS:
                parts.append(" ")
        paragraph_text = "".join(parts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)
    return "\n".join(paragraphs)


def count_words_from_docx(docx_path: Path | None) -> int:
    if docx_path is None:
        return 0
    text = _extract_visible_text_from_docx(docx_path)
    return len(text.split()) if text else 0


def count_words_from_output_artifacts(
    *,
    output_docx: Path | None,
    partial_docx: Path | None,
    pages_dir: Path | None,
) -> int:
    final_count = count_words_from_docx(output_docx)
    if final_count > 0:
        return final_count
    partial_count = count_words_from_docx(partial_docx)
    if partial_count > 0:
        return partial_count
    if pages_dir is None:
        return 0
    return count_words_from_pages_dir(pages_dir)


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
    output_docx: Path | None,
    partial_docx: Path | None,
    pages_dir: Path | None,
    completed_pages: int,
    completed_at: str,
    default_rate_per_word: float,
    api_cost: float = 0.0,
) -> JobLogSeed:
    word_count = count_words_from_output_artifacts(
        output_docx=output_docx,
        partial_docx=partial_docx,
        pages_dir=pages_dir,
    )
    expected_total = round(float(default_rate_per_word) * float(word_count), 2)
    return JobLogSeed(
        completed_at=completed_at,
        translation_date=_date_from_completed_at(completed_at),
        job_type="Translation",
        case_number="",
        court_email="",
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
        run_id="",
        target_lang=lang,
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
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
        case_form.addWidget(QLabel("Court Email"), 1, 3)
        self.court_email_combo = QComboBox()
        self.court_email_combo.setEditable(True)
        self.court_email_combo.addItems(list(self._settings["vocab_court_emails"]))
        self.court_email_combo.setCurrentText(self._seed.court_email)
        case_form.addWidget(self.court_email_combo, 1, 4, 1, 2)
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

        metrics_group = QGroupBox("Run Metrics (auto-filled)")
        metrics_form = QGridLayout(metrics_group)
        metrics_form.addWidget(QLabel("Run ID"), 0, 0)
        self.run_id_edit = QLineEdit(self._seed.run_id)
        metrics_form.addWidget(self.run_id_edit, 0, 1)
        metrics_form.addWidget(QLabel("Target lang"), 0, 2)
        self.target_lang_edit = QLineEdit(self._seed.target_lang)
        metrics_form.addWidget(self.target_lang_edit, 0, 3)
        metrics_form.addWidget(QLabel("Total tokens"), 1, 0)
        self.total_tokens_edit = QLineEdit(
            "" if self._seed.total_tokens is None else str(int(self._seed.total_tokens))
        )
        metrics_form.addWidget(self.total_tokens_edit, 1, 1)
        metrics_form.addWidget(QLabel("Est. API cost"), 1, 2)
        self.estimated_api_cost_edit = QLineEdit(
            "" if self._seed.estimated_api_cost is None else f"{float(self._seed.estimated_api_cost):.2f}"
        )
        metrics_form.addWidget(self.estimated_api_cost_edit, 1, 3)
        metrics_form.addWidget(QLabel("Quality risk score"), 2, 0)
        self.quality_risk_score_edit = QLineEdit(
            "" if self._seed.quality_risk_score is None else f"{float(self._seed.quality_risk_score):.4f}"
        )
        metrics_form.addWidget(self.quality_risk_score_edit, 2, 1)
        metrics_form.setColumnStretch(1, 1)
        metrics_form.setColumnStretch(3, 1)
        root.addWidget(metrics_group)

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
        self._fill_combo(self.court_email_combo, list(self._settings["vocab_court_emails"]))

    def _set_court_email_from_context(self, *, exact_email: str | None = None, force: bool = False) -> None:
        if not force and exact_email is None and self.court_email_combo.currentText().strip():
            return
        suggestion = choose_court_email_suggestion(
            exact_email=exact_email,
            case_entity=self.case_entity_combo.currentText().strip(),
            case_city=self.case_city_combo.currentText().strip(),
            vocab_court_emails=list(self._settings["vocab_court_emails"]),
        )
        if suggestion:
            self.court_email_combo.setCurrentText(suggestion)

    def _on_case_fields_changed(self) -> None:
        self._case_entity_user_set = True
        self._case_city_user_set = True
        if self.service_same_check.isChecked():
            self._sync_service_with_case()
        self._set_court_email_from_context()

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
        ranked = rank_court_email_suggestions(
            exact_email=suggestion.court_email,
            case_entity=self.case_entity_combo.currentText().strip(),
            case_city=self.case_city_combo.currentText().strip(),
            vocab_court_emails=list(self._settings["vocab_court_emails"]),
        )
        if ranked:
            self.court_email_combo.setCurrentText(ranked[0])

    def _autofill_from_pdf_header(self) -> None:
        suggestion = extract_pdf_header_metadata_priority_pages(
            self._seed.pdf_path,
            vocab_cities=list(self._settings["vocab_cities"]),
            config=self._metadata_config,
        )
        if not any(
            (
                suggestion.case_entity,
                suggestion.case_city,
                suggestion.case_number,
                suggestion.court_email,
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

    def _parse_optional_int(self, value: str, label: str) -> int | None:
        cleaned = value.strip()
        if cleaned == "":
            return None
        try:
            return int(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer.") from exc

    def _parse_optional_float(self, value: str, label: str) -> float | None:
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return None
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
            total_tokens = self._parse_optional_int(self.total_tokens_edit.text(), "Total tokens")
            estimated_api_cost = self._parse_optional_float(
                self.estimated_api_cost_edit.text(),
                "Estimated API cost",
            )
            quality_risk_score = self._parse_optional_float(
                self.quality_risk_score_edit.text(),
                "Quality risk score",
            )
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
            "court_email": self.court_email_combo.currentText().strip(),
            "case_entity": case_entity,
            "case_city": case_city,
            "service_entity": service_entity,
            "service_city": service_city,
            "service_date": service_date,
            "lang": self._seed.lang,
            "target_lang": self.target_lang_edit.text().strip() or self._seed.target_lang,
            "run_id": self.run_id_edit.text().strip(),
            "pages": int(self._seed.pages),
            "word_count": int(self._seed.word_count),
            "total_tokens": total_tokens,
            "rate_per_word": rate,
            "expected_total": expected_total,
            "amount_paid": amount_paid,
            "api_cost": api_cost,
            "estimated_api_cost": estimated_api_cost,
            "quality_risk_score": quality_risk_score,
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
        if payload["court_email"]:
            self._ensure_in_vocab("vocab_court_emails", str(payload["court_email"]))

        save_joblog_settings(
            {
                "vocab_case_entities": self._settings["vocab_case_entities"],
                "vocab_service_entities": self._settings["vocab_service_entities"],
                "vocab_cities": self._settings["vocab_cities"],
                "vocab_job_types": self._settings["vocab_job_types"],
                "vocab_court_emails": self._settings["vocab_court_emails"],
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


REVIEW_QUEUE_COLUMNS = [
    "page_number",
    "score",
    "status",
    "reasons",
    "recommended_action",
]

REVIEW_QUEUE_COLUMN_LABELS = {
    "page_number": "Page",
    "score": "Score",
    "status": "Status",
    "reasons": "Reasons",
    "recommended_action": "Action",
}


def _coerce_queue_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return default
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return default
    return default


def _coerce_queue_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _coerce_queue_text(value: object) -> str:
    return str(value or "").strip()


def normalize_review_queue_entries(review_queue: object) -> list[dict[str, object]]:
    if not isinstance(review_queue, list):
        return []
    entries: list[dict[str, object]] = []
    for raw_item in review_queue:
        if not isinstance(raw_item, dict):
            continue
        page_number = _coerce_queue_int(raw_item.get("page_number", 0), 0)
        if page_number <= 0:
            continue
        reasons_raw = raw_item.get("reasons", [])
        reasons: list[str] = []
        if isinstance(reasons_raw, list):
            for reason in reasons_raw:
                reason_text = _coerce_queue_text(reason)
                if reason_text:
                    reasons.append(reason_text)
        entries.append(
            {
                "page_number": int(page_number),
                "score": round(min(1.0, max(0.0, _coerce_queue_float(raw_item.get("score", 0.0), 0.0))), 4),
                "status": _coerce_queue_text(raw_item.get("status", "")),
                "reasons": reasons,
                "recommended_action": _coerce_queue_text(raw_item.get("recommended_action", "")),
                "retry_reason": _coerce_queue_text(raw_item.get("retry_reason", "")),
            }
        )
    entries.sort(
        key=lambda item: (
            -_coerce_queue_float(item.get("score", 0.0), 0.0),
            _coerce_queue_int(item.get("page_number", 0), 0),
        )
    )
    return entries


def build_review_queue_markdown(entries: list[dict[str, object]]) -> str:
    lines: list[str] = []
    lines.append("# Review Queue")
    lines.append("")
    if not entries:
        lines.append("No flagged pages were found for the current run.")
        lines.append("")
        return "\n".join(lines)
    lines.append("| Page | Score | Status | Action | Reasons |")
    lines.append("|------|-------|--------|--------|---------|")
    for entry in entries:
        reasons = entry.get("reasons", [])
        reason_text = " | ".join(reasons) if isinstance(reasons, list) else str(reasons or "")
        lines.append(
            f"| {entry.get('page_number', '')} | {entry.get('score', '')} "
            f"| {entry.get('status', '') or '-'} | {entry.get('recommended_action', '') or '-'} "
            f"| {reason_text or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


class QtReviewQueueDialog(QDialog):
    """Review queue panel for flagged pages from latest run summary."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        review_queue: object,
        run_dir: Path | None,
        run_summary_path: Path | None,
        open_path_callback: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Queue")
        self.resize(980, 560)
        self._entries = normalize_review_queue_entries(review_queue)
        self._run_dir = run_dir.expanduser().resolve() if isinstance(run_dir, Path) else None
        self._run_summary_path = (
            run_summary_path.expanduser().resolve() if isinstance(run_summary_path, Path) else None
        )
        self._open_path_callback = open_path_callback
        self._build_ui()
        self._populate_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.table = QTableWidget(0, len(REVIEW_QUEUE_COLUMNS), self)
        self.table.setHorizontalHeaderLabels([REVIEW_QUEUE_COLUMN_LABELS[col] for col in REVIEW_QUEUE_COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("Export...")
        self.copy_btn = QPushButton("Copy list")
        self.open_page_btn = QPushButton("Open page file")
        self.close_btn = QPushButton("Close")
        actions.addWidget(self.export_btn)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.open_page_btn)
        actions.addStretch(1)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.export_btn.clicked.connect(self._export_queue)
        self.copy_btn.clicked.connect(self._copy_queue)
        self.open_page_btn.clicked.connect(self._open_selected_page_file)
        self.close_btn.clicked.connect(self.accept)

    def _populate_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for entry in self._entries:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            reasons = entry.get("reasons", [])
            reason_text = " | ".join(reasons) if isinstance(reasons, list) else str(reasons or "")
            values = {
                "page_number": str(int(_coerce_queue_int(entry.get("page_number", 0), 0))),
                "score": f"{_coerce_queue_float(entry.get('score', 0.0), 0.0):.4f}",
                "status": _coerce_queue_text(entry.get("status", "")),
                "reasons": reason_text,
                "recommended_action": _coerce_queue_text(entry.get("recommended_action", "")),
            }
            for col_idx, col in enumerate(REVIEW_QUEUE_COLUMNS):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(values[col]))
        self.table.setSortingEnabled(True)
        if self.table.rowCount() > 0:
            self.table.sortItems(1, Qt.SortOrder.DescendingOrder)
            self.summary_label.setText(f"Flagged pages: {self.table.rowCount()} (sorted by score).")
        else:
            self.summary_label.setText("No flagged pages found for this run.")

    def _selected_entry(self) -> dict[str, object] | None:
        row = self.table.currentRow()
        if row < 0:
            selection_model = self.table.selectionModel()
            if selection_model is not None:
                selected_rows = selection_model.selectedRows()
                if selected_rows:
                    row = int(selected_rows[0].row())
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _copy_queue(self) -> None:
        markdown = build_review_queue_markdown(self._entries)
        QApplication.clipboard().setText(markdown)
        QMessageBox.information(self, "Review Queue", "Review queue copied to clipboard.")

    def _export_queue(self) -> None:
        if self._run_summary_path is None:
            QMessageBox.warning(self, "Review Queue", "Run summary path is unavailable for export.")
            return
        default_base = self._run_summary_path.parent / "review_queue"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Export review queue",
            str(default_base),
            "All Files (*.*)",
        )
        if not selected:
            return
        try:
            csv_path, markdown_path, count = export_review_queue(
                self._run_summary_path,
                Path(selected),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Review Queue", f"Failed to export review queue:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Review Queue",
            f"Exported {count} item(s).\n\nCSV: {csv_path}\nMarkdown: {markdown_path}",
        )

    def _open_selected_page_file(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Review Queue", "Select one row first.")
            return
        if self._run_dir is None:
            QMessageBox.warning(self, "Review Queue", "Run folder is unavailable.")
            return
        page_number = _coerce_queue_int(entry.get("page_number", 0), 0)
        page_file = self._run_dir / "pages" / f"page_{page_number:04d}.txt"
        if not page_file.exists():
            QMessageBox.warning(self, "Review Queue", f"Page file not found:\n{page_file}")
            return
        if self._open_path_callback is not None:
            self._open_path_callback(page_file)
            return
        QMessageBox.information(self, "Review Queue", f"Page file:\n{page_file}")


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


class _StudyTranslationWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        entries: list[StudyGlossaryEntry],
        supported_langs: list[str],
        lemma_effort: str = "medium",
    ) -> None:
        super().__init__()
        self._entries = list(entries)
        self._supported_langs = list(supported_langs)
        self._lemma_effort = lemma_effort

    def run(self) -> None:
        try:
            client = OpenAIResponsesClient()
            updated: list[StudyGlossaryEntry] = []
            total = max(1, len(self._entries))
            for index, entry in enumerate(self._entries, start=1):
                self.progress.emit(
                    int(((index - 1) / float(total)) * 100.0),
                    f"Refreshing translations for '{entry.term_pt}' ({index}/{total})",
                )
                updated.append(
                    fill_translations_for_entry(
                        entry,
                        supported_langs=self._supported_langs,
                        client=client,
                        fill_only_missing=False,
                        effort=self._lemma_effort,
                    )
                )
            self.progress.emit(100, "Translation refresh complete.")
            self.finished.emit(updated)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class _StudyCandidateWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    cancelled = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        source_mode: str,
        run_dirs: list[str],
        pdf_paths: list[str],
        mode: str,
        include_snippets: bool,
        snippet_max_chars: int,
    ) -> None:
        super().__init__()
        self._source_mode = str(source_mode or "run_folders").strip().lower()
        self._run_dirs = list(run_dirs)
        self._pdf_paths = list(pdf_paths)
        self._mode = mode
        self._include_snippets = bool(include_snippets)
        self._snippet_max_chars = int(snippet_max_chars)
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def _iter_page_numbers_from_state(self, state_payload: dict[str, object]) -> list[int]:
        page_numbers: list[int] = []
        pages_payload = state_payload.get("pages")
        if isinstance(pages_payload, dict):
            for key in pages_payload.keys():
                try:
                    value = int(str(key))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    page_numbers.append(value)
        if page_numbers:
            return sorted(set(page_numbers))
        try:
            start = int(state_payload.get("selection_start_page", 1))
            end = int(state_payload.get("selection_end_page", start))
        except (TypeError, ValueError):
            start = 1
            end = 1
        if end < start:
            return []
        return list(range(start, end + 1))

    def _resolve_pdf_path(self, run_dir: Path, state_payload: dict[str, object]) -> Path | None:
        pdf_path_raw = str(state_payload.get("pdf_path", "") or "").strip()
        if pdf_path_raw == "":
            return None
        pdf_path = Path(pdf_path_raw).expanduser()
        if not pdf_path.is_absolute():
            pdf_path = (run_dir / pdf_path).resolve()
        if not pdf_path.exists() or not pdf_path.is_file():
            return None
        return pdf_path

    def _ordered_page_text(self, pdf_path: Path, page_number: int) -> str:
        try:
            ordered = extract_ordered_page_text(pdf_path, page_number - 1)
        except Exception:  # noqa: BLE001
            return ""
        if ordered.extraction_failed:
            return ""
        return str(ordered.text or "")

    def _ingest_page_text(
        self,
        *,
        doc_id: str,
        page_number: int,
        page_text: str,
        stats: dict[str, object],
        pages_tokens: list[list[str]],
    ) -> bool:
        if page_text.strip() == "":
            return False
        page_tokens = tokenize_page_for_mode(
            page_text,
            self._mode if self._mode in {"full_text", "headers_only"} else "full_text",  # type: ignore[arg-type]
        )
        if page_tokens:
            pages_tokens.append(page_tokens)
        update_candidate_stats_from_page(
            doc_id=doc_id,
            page_number=page_number,
            text=page_text,
            mode=self._mode,  # type: ignore[arg-type]
            include_snippets=self._include_snippets,
            snippet_max_chars=self._snippet_max_chars,
            stats=stats,
        )
        return True

    def _scan_pdf_source(
        self,
        *,
        pdf_path: Path,
        doc_id: str,
        stats: dict[str, object],
        pages_tokens: list[list[str]],
    ) -> tuple[int, bool]:
        try:
            page_count = int(get_page_count(pdf_path))
        except Exception:  # noqa: BLE001
            return (0, False)
        if page_count <= 0:
            return (0, False)
        pages_scanned = 0
        for page_number in range(1, page_count + 1):
            if self._cancel_requested:
                return (pages_scanned, True)
            page_text = self._ordered_page_text(pdf_path, page_number)
            if self._ingest_page_text(
                doc_id=doc_id,
                page_number=page_number,
                page_text=page_text,
                stats=stats,
                pages_tokens=pages_tokens,
            ):
                pages_scanned += 1
        return (pages_scanned, False)

    def run(self) -> None:
        try:
            stats = create_candidate_stats()
            pages_tokens: list[list[str]] = []
            total_pages_scanned = 0
            sources_processed = 0
            source_mode = self._source_mode if self._source_mode in {
                "run_folders",
                "current_pdf",
                "select_pdfs",
                "joblog_runs",
            } else "run_folders"

            if source_mode == "run_folders":
                total_sources = max(1, len(self._run_dirs))
                for source_index, raw_dir in enumerate(self._run_dirs, start=1):
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return
                    run_dir = Path(raw_dir).expanduser().resolve()
                    run_state_path = run_dir / "run_state.json"
                    if not run_state_path.exists():
                        sources_processed += 1
                        self.progress.emit(
                            int((sources_processed / float(total_sources)) * 100.0),
                            f"Skipping {run_dir.name}: run_state.json not found ({source_index}/{total_sources}).",
                        )
                        continue
                    try:
                        state_payload = json.loads(run_state_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        sources_processed += 1
                        self.progress.emit(
                            int((sources_processed / float(total_sources)) * 100.0),
                            f"Skipping {run_dir.name}: invalid run_state.json ({source_index}/{total_sources}).",
                        )
                        continue
                    if not isinstance(state_payload, dict):
                        sources_processed += 1
                        continue
                    doc_id = run_dir.name
                    page_numbers = self._iter_page_numbers_from_state(state_payload)
                    pages_dir = run_dir / "pages"
                    pdf_path = self._resolve_pdf_path(run_dir, state_payload)
                    for page_number in page_numbers:
                        if self._cancel_requested:
                            self.cancelled.emit()
                            return
                        page_text = ""
                        page_file = pages_dir / f"page_{page_number:04d}.txt"
                        if page_file.exists():
                            try:
                                page_text = page_file.read_text(encoding="utf-8")
                            except OSError:
                                page_text = ""
                        if page_text.strip() == "" and pdf_path is not None:
                            page_text = self._ordered_page_text(pdf_path, page_number)
                        if self._ingest_page_text(
                            doc_id=doc_id,
                            page_number=page_number,
                            page_text=page_text,
                            stats=stats,
                            pages_tokens=pages_tokens,
                        ):
                            total_pages_scanned += 1
                        if total_pages_scanned > 0 and total_pages_scanned % 10 == 0:
                            source_progress = int(((source_index - 1) / float(total_sources)) * 100.0)
                            self.progress.emit(
                                source_progress,
                                f"Processing {run_dir.name}: {total_pages_scanned} pages scanned.",
                            )
                    sources_processed += 1
                    self.progress.emit(
                        int((sources_processed / float(total_sources)) * 100.0),
                        f"Processed {sources_processed}/{total_sources} sources; pages scanned: {total_pages_scanned}.",
                    )
            else:
                total_sources = max(1, len(self._pdf_paths))
                for source_index, raw_pdf in enumerate(self._pdf_paths, start=1):
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return
                    pdf_path = Path(raw_pdf).expanduser().resolve()
                    if not pdf_path.exists() or not pdf_path.is_file():
                        sources_processed += 1
                        self.progress.emit(
                            int((sources_processed / float(total_sources)) * 100.0),
                            f"Skipping missing PDF ({source_index}/{total_sources}): {pdf_path.name}",
                        )
                        continue
                    scanned, was_cancelled = self._scan_pdf_source(
                        pdf_path=pdf_path,
                        doc_id=pdf_path.stem,
                        stats=stats,
                        pages_tokens=pages_tokens,
                    )
                    if was_cancelled:
                        self.cancelled.emit()
                        return
                    total_pages_scanned += scanned
                    sources_processed += 1
                    self.progress.emit(
                        int((sources_processed / float(total_sources)) * 100.0),
                        f"Processed {sources_processed}/{total_sources} PDFs; pages scanned: {total_pages_scanned}.",
                    )

            candidates = finalize_study_candidates(stats)
            self.finished.emit(
                {
                    "candidates": candidates,
                    "pages_tokens": pages_tokens,
                    "run_folders_processed": int(sources_processed),
                    "total_pages_scanned": int(total_pages_scanned),
                    "source_mode": source_mode,
                }
            )
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class QtSettingsDialog(QDialog):
    """Qt equivalent of the Tk settings dialog."""

    def __init__(
        self,
        *,
        parent: QWidget | None,
        settings: dict[str, object],
        apply_callback: Callable[[dict[str, object], bool], None],
        collect_debug_paths: Callable[[], list[Path]],
        current_pdf_path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(980, 700)
        self.setMinimumSize(780, 560)

        self._settings = dict(settings)
        self._apply_callback = apply_callback
        self._collect_debug_paths = collect_debug_paths
        self._study_current_pdf_path: Path | None = current_pdf_path
        self._glossaries_by_lang: dict[str, list[GlossaryEntry]] = normalize_glossaries({}, supported_target_langs())
        self._enabled_glossary_tiers_by_lang: dict[str, list[int]] = normalize_enabled_tiers_by_target_lang(
            {},
            supported_target_langs(),
        )
        self._glossary_current_lang: str | None = None
        self._glossary_selected_tier: int = 1
        self._glossary_search_text: str = ""
        self._glossary_view_keys: list[tuple[str, str, str, str, int]] = []
        self._glossary_seed_version: int = 2
        self._glossary_populating: bool = False
        self._study_supported_langs: list[str] = supported_learning_langs()
        self._study_entries: list[StudyGlossaryEntry] = normalize_study_entries([], self._study_supported_langs)
        self._study_candidate_rows: list[StudyCandidate] = []
        self._study_candidate_keys: list[str] = []
        self._study_entry_view_terms: list[str] = []
        self._study_search_text: str = ""
        self._study_filters: dict[str, str] = {"category": "all", "status": "all", "coverage_tier": "all"}
        self._study_corpus_source: str = "run_folders"
        self._study_pdf_paths: list[str] = []
        self._study_quiz_index: int = 0
        self._study_last_run_folders_processed: int = 0
        self._study_last_total_pages_scanned: int = 0
        self._study_candidate_thread: QThread | None = None
        self._study_candidate_worker: _StudyCandidateWorker | None = None
        self._study_translation_thread: QThread | None = None
        self._study_translation_worker: _StudyTranslationWorker | None = None
        self._build_ui()
        self._set_values_from_settings(self._settings)
        self._refresh_key_status()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        _scroll_area = QScrollArea()
        _scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        _scroll_area.setWidgetResizable(True)
        _scroll_content = QWidget()
        scroll_layout = QVBoxLayout(_scroll_content)
        scroll_layout.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget(self)
        scroll_layout.addWidget(self.tabs, 1)

        self.tab_keys = QWidget(self)
        self.tab_ocr = QWidget(self)
        self.tab_appearance = QWidget(self)
        self.tab_behaviour = QWidget(self)
        self.tab_glossary = QWidget(self)
        self.tab_study = QWidget(self)
        self.tab_diag = QWidget(self)
        self.tabs.addTab(self.tab_keys, "Keys & Providers")
        self.tabs.addTab(self.tab_ocr, "OCR Defaults")
        self.tabs.addTab(self.tab_appearance, "Appearance")
        self.tabs.addTab(self.tab_behaviour, "Behaviour & Performance")
        self.tabs.addTab(self.tab_glossary, "Glossary")
        self.tabs.addTab(self.tab_study, "Study Glossary")
        self.tabs.addTab(self.tab_diag, "Diagnostics")

        self._build_tab_keys()
        self._build_tab_ocr_defaults()
        self._build_tab_appearance()
        self._build_tab_behaviour()
        self._build_tab_glossary()
        self._build_tab_study()
        self._build_tab_diagnostics()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.apply_btn = QPushButton("Apply")
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        scroll_layout.addLayout(buttons)

        _scroll_area.setWidget(_scroll_content)
        root.addWidget(_scroll_area)

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
        self.ocr_mode_default_combo = NoWheelComboBox()
        self.ocr_mode_default_combo.addItems(["off", "auto", "always"])
        self.ocr_engine_default_combo = NoWheelComboBox()
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

        self.default_lang_combo = NoWheelComboBox(); self.default_lang_combo.addItems(["EN", "FR", "AR"])
        self.default_effort_combo = NoWheelComboBox(); self.default_effort_combo.addItems(["high", "xhigh"])
        self.default_effort_policy_combo = NoWheelComboBox(); self.default_effort_policy_combo.addItems(["adaptive", "fixed_high", "fixed_xhigh"])
        self.lemma_effort_combo = NoWheelComboBox(); self.lemma_effort_combo.addItems(["medium", "high", "xhigh"])
        self.default_images_combo = NoWheelComboBox(); self.default_images_combo.addItems(["off", "auto", "always"])
        self.default_workers_combo = NoWheelComboBox(); self.default_workers_combo.addItems(["1", "2", "3", "4", "5", "6"])
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
        grid.addWidget(QLabel("Translation effort"), row, 0); grid.addWidget(self.default_effort_combo, row, 1); row += 1
        grid.addWidget(QLabel("Translation effort policy"), row, 0); grid.addWidget(self.default_effort_policy_combo, row, 1); row += 1
        grid.addWidget(QLabel("Lemma / utility effort"), row, 0); grid.addWidget(self.lemma_effort_combo, row, 1); row += 1
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
        top.addWidget(QLabel("View tier"))
        self.glossary_tier_combo = QComboBox()
        for tier in valid_glossary_tiers():
            self.glossary_tier_combo.addItem(f"Tier {tier}", tier)
        self.glossary_tier_combo.setCurrentIndex(0)
        top.addWidget(self.glossary_tier_combo)
        self.glossary_tier_counts_label = QLabel("")
        top.addWidget(self.glossary_tier_counts_label, 1)
        top.addStretch(1)
        layout.addLayout(top)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.glossary_search_edit = QLineEdit()
        self.glossary_search_edit.setPlaceholderText("Filter source phrase or preferred translation...")
        search_row.addWidget(self.glossary_search_edit, 1)
        layout.addLayout(search_row)
        self._glossary_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.tab_glossary)
        self._glossary_search_shortcut.activated.connect(self._focus_glossary_search)
        self._shortcut_add_row_ctrl_n = QShortcut(QKeySequence("Ctrl+N"), self.tab_glossary)
        self._shortcut_add_row_ctrl_n.activated.connect(self._add_glossary_row_and_focus)
        self._shortcut_add_row_insert = QShortcut(QKeySequence("Insert"), self.tab_glossary)
        self._shortcut_add_row_insert.activated.connect(self._add_glossary_row_and_focus)

        active_tiers_row = QHBoxLayout()
        active_tiers_row.addWidget(QLabel("Active tiers for prompt"))
        self._glossary_active_tier_checks: dict[int, QCheckBox] = {}
        for tier in valid_glossary_tiers():
            check = QCheckBox(f"T{tier}")
            self._glossary_active_tier_checks[tier] = check
            active_tiers_row.addWidget(check)
        active_tiers_row.addStretch(1)
        layout.addLayout(active_tiers_row)

        self.glossary_table = QTableWidget(0, 5, self.tab_glossary)
        self.glossary_table.setHorizontalHeaderLabels(
            ["Source phrase (PDF text)", "Preferred translation", "Match", "Source lang", "Tier"]
        )
        self.glossary_table.verticalHeader().setVisible(False)
        self.glossary_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.glossary_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.glossary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header = self.glossary_table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.glossary_table.setColumnWidth(2, 110)  # Match
        self.glossary_table.setColumnWidth(3, 90)   # Source lang
        self.glossary_table.setColumnWidth(4, 60)   # Tier
        layout.addWidget(self.glossary_table, 1)

        add_row_inline = QHBoxLayout()
        self.glossary_add_row_top_btn = QPushButton("+")
        self.glossary_add_row_top_btn.setFixedWidth(36)
        self.glossary_add_row_top_btn.setToolTip("Add glossary row (Ctrl+N)")
        add_row_inline.addWidget(self.glossary_add_row_top_btn)
        add_row_inline.addStretch(1)
        layout.addLayout(add_row_inline)

        actions = QHBoxLayout()
        self.glossary_remove_rows_btn = QPushButton("Remove selected")
        self.glossary_export_btn = QPushButton("Export...")
        actions.addWidget(self.glossary_remove_rows_btn)
        actions.addWidget(self.glossary_export_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.glossary_hygiene_hint_label = QLabel(
            "Glossary hygiene:\n"
            "1) Add entries for repeated headers/titles/section labels.\n"
            "2) Add entries for ambiguous phrases needing consistency.\n"
            "3) Add entries where legal tone/formality must be stable.\n"
            "4) Add entries for legal formula/boilerplate phrases.\n"
            "Avoid obvious single-word dictionary items. Prefer Exact for short phrases."
        )
        self.glossary_hygiene_hint_label.setWordWrap(True)
        layout.addWidget(self.glossary_hygiene_hint_label)

        self.glossary_warning_label = QLabel("")
        self.glossary_warning_label.setWordWrap(True)
        layout.addWidget(self.glossary_warning_label)

        self.glossary_lang_combo.currentTextChanged.connect(self._on_glossary_language_changed)
        self.glossary_tier_combo.currentIndexChanged.connect(self._on_glossary_tier_changed)
        self.glossary_search_edit.textChanged.connect(self._on_glossary_search_changed)
        self.glossary_add_row_top_btn.clicked.connect(self._add_glossary_row_and_focus)
        self.glossary_remove_rows_btn.clicked.connect(self._remove_selected_glossary_rows)
        self.glossary_export_btn.clicked.connect(self._export_consistency_glossary_markdown)
        for tier, check in self._glossary_active_tier_checks.items():
            check.toggled.connect(lambda checked, tier=tier: self._on_glossary_active_tier_changed(tier, checked))

        self._glossary_auto_save_timer = QTimer(self)
        self._glossary_auto_save_timer.setSingleShot(True)
        self._glossary_auto_save_timer.setInterval(500)
        self._glossary_auto_save_timer.timeout.connect(self._persist_glossary_to_disk)
        self.glossary_table.cellChanged.connect(self._on_glossary_cell_changed)

    def _new_glossary_match_combo(self, selected: str = "exact") -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("GlossaryTableCombo")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
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

    def _new_glossary_source_lang_combo(self, selected: str = "AUTO") -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("GlossaryTableCombo")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for value in valid_source_langs():
            combo.addItem(value, value)
        selected_clean = coerce_source_lang(selected, default="AUTO")
        combo.setCurrentText(selected_clean)
        return combo

    def _new_glossary_tier_combo(self, selected: int = 2) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("GlossaryTableCombo")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for value in valid_glossary_tiers():
            combo.addItem(f"T{value}", value)
        selected_tier = coerce_glossary_tier(selected, default=2)
        if hasattr(combo, "setCurrentData"):
            combo.setCurrentData(selected_tier)
        else:
            idx = combo.findData(selected_tier) if hasattr(combo, "findData") else -1
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    def _glossary_source_lang_value(self, combo: object | None) -> str:
        if combo is None:
            return "AUTO"
        value = combo.currentData() if hasattr(combo, "currentData") else None
        if isinstance(value, str):
            return coerce_source_lang(value, default="AUTO")
        text = combo.currentText().strip().upper() if hasattr(combo, "currentText") else ""
        return coerce_source_lang(text, default="AUTO")

    def _glossary_tier_value(self, combo: object | None) -> int:
        if combo is None:
            return 2
        value = combo.currentData() if hasattr(combo, "currentData") else None
        if value is not None:
            return coerce_glossary_tier(value, default=2)
        text = combo.currentText().strip() if hasattr(combo, "currentText") else ""
        if text.startswith("T"):
            text = text[1:]
        return coerce_glossary_tier(text, default=2)

    def _glossary_entry_key(self, entry: GlossaryEntry) -> tuple[str, str, str, str, int]:
        return (
            entry.source_text,
            entry.preferred_translation,
            entry.match_mode,
            entry.source_lang,
            int(entry.tier),
        )

    def _visible_glossary_rows(self, lang: str) -> list[GlossaryEntry]:
        entries = self._glossaries_by_lang.get(lang, [])
        selected_tier = int(self._glossary_selected_tier)
        search = self._glossary_search_text.strip().casefold()
        filtered = [entry for entry in entries if int(entry.tier) == selected_tier]
        if search:
            filtered = [
                entry
                for entry in filtered
                if search in entry.source_text.casefold() or search in entry.preferred_translation.casefold()
            ]
        return filtered

    def _set_active_tier_checks(self, tiers: list[int]) -> None:
        tier_set = {coerce_glossary_tier(value, default=1) for value in tiers}
        if not tier_set:
            tier_set = {1, 2}
        for tier, check in self._glossary_active_tier_checks.items():
            check.blockSignals(True)
            check.setChecked(tier in tier_set)
            check.blockSignals(False)

    def _read_active_tier_checks(self) -> list[int]:
        tiers = [tier for tier, check in self._glossary_active_tier_checks.items() if check.isChecked()]
        if not tiers:
            tiers = [1, 2]
        return sorted({coerce_glossary_tier(value, default=1) for value in tiers})

    def _refresh_glossary_tier_counts(self) -> None:
        lang = self._glossary_current_lang or "EN"
        counts = {tier: 0 for tier in valid_glossary_tiers()}
        for entry in self._glossaries_by_lang.get(lang, []):
            counts[coerce_glossary_tier(entry.tier, default=2)] += 1
        active = self._enabled_glossary_tiers_by_lang.get(lang, [1, 2])
        counts_text = " | ".join(f"T{tier}:{counts[tier]}" for tier in valid_glossary_tiers())
        active_text = ",".join(f"T{tier}" for tier in sorted(active))
        self.glossary_tier_counts_label.setText(f"{counts_text}   Active: {active_text}")

    def _update_glossary_warning_label(self, rows: list[GlossaryEntry]) -> None:
        warnings: list[str] = []
        for entry in rows:
            source = entry.source_text.strip()
            words = [part for part in source.split() if part]
            if entry.match_mode == "contains" and (len(source) < 10 or len(words) < 2):
                warnings.append("Contains on short phrases may overmatch.")
            if len(words) == 1 and int(entry.tier) <= 2:
                warnings.append("Tier 1-2 should be reserved for high-impact phrases (headers/ambiguous/formulas).")
        if not warnings:
            self.glossary_warning_label.setText("No glossary hygiene warnings for visible rows.")
            return
        unique_warnings = list(dict.fromkeys(warnings))
        self.glossary_warning_label.setText("Warning: " + " ".join(unique_warnings))

    def _refresh_glossary_table_view(self) -> None:
        lang = self._glossary_current_lang or "EN"
        rows = self._visible_glossary_rows(lang)
        self._set_glossary_table_rows(rows)
        self._refresh_glossary_tier_counts()
        self._update_glossary_warning_label(rows)

    def _focus_glossary_search(self) -> None:
        self.glossary_search_edit.setFocus()
        self.glossary_search_edit.selectAll()

    def _set_glossary_table_rows(self, rows: list[GlossaryEntry]) -> None:
        self._glossary_populating = True
        try:
            self.glossary_table.setRowCount(0)
            self._glossary_view_keys = [self._glossary_entry_key(entry) for entry in rows]
            for entry in rows:
                row = self.glossary_table.rowCount()
                self.glossary_table.insertRow(row)
                self.glossary_table.setItem(row, 0, QTableWidgetItem(entry.source_text))
                self.glossary_table.setItem(row, 1, QTableWidgetItem(entry.preferred_translation))
                match_c = self._new_glossary_match_combo(entry.match_mode)
                self.glossary_table.setCellWidget(row, 2, match_c)
                src_c = self._new_glossary_source_lang_combo(entry.source_lang)
                self.glossary_table.setCellWidget(row, 3, src_c)
                tier_c = self._new_glossary_tier_combo(entry.tier)
                self.glossary_table.setCellWidget(row, 4, tier_c)
                match_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
                src_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
                tier_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        finally:
            self._glossary_populating = False

    def _read_glossary_table_rows(self) -> list[GlossaryEntry]:
        rows: list[dict[str, str]] = []
        for row in range(self.glossary_table.rowCount()):
            source_item = self.glossary_table.item(row, 0)
            target_item = self.glossary_table.item(row, 1)
            source = source_item.text().strip() if source_item else ""
            target = target_item.text().strip() if target_item else ""
            if source and not target:
                target = "..."
            match = self._glossary_match_value(self.glossary_table.cellWidget(row, 2))
            source_lang = self._glossary_source_lang_value(self.glossary_table.cellWidget(row, 3))
            tier = self._glossary_tier_value(self.glossary_table.cellWidget(row, 4))
            rows.append(
                {
                    "source_text": source,
                    "preferred_translation": target,
                    "match_mode": match,
                    "source_lang": source_lang,
                    "tier": str(int(tier)),
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
        lang = self._glossary_current_lang
        existing_rows = list(self._glossaries_by_lang.get(lang, []))
        view_key_set = set(self._glossary_view_keys)
        preserved_rows = [entry for entry in existing_rows if self._glossary_entry_key(entry) not in view_key_set]
        merged_rows = preserved_rows + self._read_glossary_table_rows()
        normalized = normalize_glossaries({lang: merged_rows}, [lang])
        self._glossaries_by_lang[lang] = normalized.get(lang, [])
        self._enabled_glossary_tiers_by_lang[lang] = self._read_active_tier_checks()
        self._glossary_view_keys = [self._glossary_entry_key(e) for e in self._read_glossary_table_rows()]

    def _on_glossary_tier_changed(self, _: int) -> None:
        self._save_current_glossary_language_rows()
        current = self.glossary_tier_combo.currentData()
        self._glossary_selected_tier = coerce_glossary_tier(current, default=1)
        self._refresh_glossary_table_view()

    def _on_glossary_search_changed(self, text: str) -> None:
        self._save_current_glossary_language_rows()
        self._glossary_search_text = str(text or "")
        self._refresh_glossary_table_view()

    def _on_glossary_active_tier_changed(self, tier: int, checked: bool) -> None:
        _ = checked
        if self._glossary_current_lang is None:
            return
        tiers = self._read_active_tier_checks()
        if not tiers:
            check = self._glossary_active_tier_checks.get(tier)
            if check is not None:
                check.blockSignals(True)
                check.setChecked(True)
                check.blockSignals(False)
            tiers = [coerce_glossary_tier(tier, default=1)]
        self._enabled_glossary_tiers_by_lang[self._glossary_current_lang] = sorted(tiers)
        self._refresh_glossary_tier_counts()
        self._schedule_glossary_auto_save()

    def _on_glossary_language_changed(self, lang_text: str) -> None:
        next_lang = str(lang_text or "").strip().upper()
        if next_lang == "":
            return
        self._save_current_glossary_language_rows()
        self._glossary_current_lang = next_lang
        self._set_active_tier_checks(self._enabled_glossary_tiers_by_lang.get(next_lang, [1, 2]))
        self._refresh_glossary_table_view()

    def _set_glossaries_from_settings(self, settings: dict[str, object]) -> None:
        langs = supported_target_langs()
        raw_personal = settings.get("personal_glossaries_by_lang", settings.get("glossaries_by_lang"))
        self._glossaries_by_lang = normalize_glossaries(raw_personal, langs)
        self._enabled_glossary_tiers_by_lang = normalize_enabled_tiers_by_target_lang(
            settings.get("enabled_glossary_tiers_by_target_lang"),
            langs,
        )
        seed_raw = settings.get("glossary_seed_version", 2)
        try:
            self._glossary_seed_version = max(2, int(seed_raw))  # type: ignore[arg-type]
        except Exception:
            self._glossary_seed_version = 2
        preferred = str(settings.get("default_lang", "EN") or "EN").strip().upper()
        if preferred not in langs:
            preferred = langs[0]

        self.glossary_lang_combo.blockSignals(True)
        self.glossary_lang_combo.clear()
        self.glossary_lang_combo.addItems(langs)
        self.glossary_lang_combo.setCurrentText(preferred)
        self.glossary_lang_combo.blockSignals(False)
        self._glossary_current_lang = preferred
        tier_data = self.glossary_tier_combo.currentData()
        self._glossary_selected_tier = coerce_glossary_tier(tier_data, default=1)
        self._glossary_search_text = ""
        self.glossary_search_edit.clear()
        self._set_active_tier_checks(self._enabled_glossary_tiers_by_lang.get(preferred, [1, 2]))
        self._refresh_glossary_table_view()

    def _add_glossary_row(self) -> None:
        row = self.glossary_table.rowCount()
        self.glossary_table.insertRow(row)
        self.glossary_table.setItem(row, 0, QTableWidgetItem(""))
        self.glossary_table.setItem(row, 1, QTableWidgetItem(""))
        match_c = self._new_glossary_match_combo("exact")
        self.glossary_table.setCellWidget(row, 2, match_c)
        src_c = self._new_glossary_source_lang_combo("PT")
        self.glossary_table.setCellWidget(row, 3, src_c)
        tier_c = self._new_glossary_tier_combo(self._glossary_selected_tier)
        self.glossary_table.setCellWidget(row, 4, tier_c)
        match_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        src_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        tier_c.currentIndexChanged.connect(self._schedule_glossary_auto_save)
        self._schedule_glossary_auto_save()

    def _add_glossary_row_and_focus(self) -> None:
        self._add_glossary_row()
        new_row = self.glossary_table.rowCount() - 1
        self.glossary_table.scrollToItem(self.glossary_table.item(new_row, 0))
        self.glossary_table.setCurrentCell(new_row, 0)
        self.glossary_table.editItem(self.glossary_table.item(new_row, 0))

    def _remove_selected_glossary_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.glossary_table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return
        for row in selected_rows:
            self.glossary_table.removeRow(row)
        self._update_glossary_warning_label(self._read_glossary_table_rows())
        self._schedule_glossary_auto_save()

    def _on_glossary_cell_changed(self, row: int, column: int) -> None:
        _ = row, column
        if self._glossary_populating:
            return
        self._schedule_glossary_auto_save()

    def _schedule_glossary_auto_save(self, *_args: object) -> None:
        if self._glossary_populating:
            return
        timer = getattr(self, "_glossary_auto_save_timer", None)
        if timer is not None:
            timer.start()

    def _commit_glossary_cell_editor(self) -> None:
        """Force any active glossary cell editor to commit its data."""
        # Moving focus away from the table causes the delegate's editor
        # to lose focus, which triggers commitData automatically in Qt.
        if hasattr(self, "apply_btn"):
            self.apply_btn.setFocus()

    def _persist_glossary_to_disk(self) -> None:
        """Save only glossary keys to disk (no full settings validation)."""
        self._commit_glossary_cell_editor()
        timer = getattr(self, "_glossary_auto_save_timer", None)
        if timer is not None:
            timer.stop()
        self._save_current_glossary_language_rows()
        self._propagate_glossary_source_phrases()
        normalized = normalize_glossaries(self._glossaries_by_lang, supported_target_langs())
        norm_tiers = normalize_enabled_tiers_by_target_lang(
            self._enabled_glossary_tiers_by_lang,
            supported_target_langs(),
        )
        glossary_values: dict[str, object] = {
            "personal_glossaries_by_lang": serialize_glossaries(normalized),
            "glossaries_by_lang": serialize_glossaries(normalized),
            "enabled_glossary_tiers_by_target_lang": {
                lang: list(norm_tiers.get(lang, [1, 2]))
                for lang in supported_target_langs()
            },
            "glossary_seed_version": max(2, int(self._glossary_seed_version)),
        }
        try:
            save_gui_settings(glossary_values)
        except Exception:  # noqa: BLE001
            pass  # silent fail on auto-save; user can still Save explicitly

    def _propagate_glossary_source_phrases(self) -> None:
        """Ensure each source phrase exists in all target languages' glossaries."""
        langs = supported_target_langs()

        def _norm_key(text: str) -> str:
            return " ".join(text.strip().casefold().split())

        by_lang: dict[str, dict[str, GlossaryEntry]] = {}
        for lang in langs:
            seen: dict[str, GlossaryEntry] = {}
            for entry in self._glossaries_by_lang.get(lang, []):
                key = _norm_key(entry.source_text)
                if key and key not in seen:
                    seen[key] = entry
            by_lang[lang] = seen

        changed = False
        for lang in langs:
            existing = by_lang[lang]
            additions: list[GlossaryEntry] = []
            for other in langs:
                if other == lang:
                    continue
                for key, entry in by_lang[other].items():
                    if key not in existing:
                        additions.append(
                            GlossaryEntry(
                                source_text=entry.source_text,
                                preferred_translation="...",
                                match_mode=entry.match_mode,
                                source_lang=entry.source_lang,
                                tier=entry.tier,
                            )
                        )
                        existing[key] = additions[-1]
            if additions:
                self._glossaries_by_lang[lang] = list(self._glossaries_by_lang.get(lang, [])) + additions
                changed = True

        if changed:
            for lang in langs:
                norm = normalize_glossaries({lang: self._glossaries_by_lang.get(lang, [])}, [lang])
                self._glossaries_by_lang[lang] = norm.get(lang, [])

    def _export_consistency_glossary_markdown(self) -> None:
        self._save_current_glossary_language_rows()
        normalized_glossaries = normalize_glossaries(self._glossaries_by_lang, supported_target_langs())
        if not any(normalized_glossaries.get(lang) for lang in supported_target_langs()):
            QMessageBox.information(self, "Glossary", "No glossary entries to export.")
            return
        markdown = build_consistency_glossary_markdown(
            normalized_glossaries,
            enabled_tiers_by_lang=self._enabled_glossary_tiers_by_lang,
            generated_at_iso=datetime.now().replace(microsecond=0).isoformat(),
            title="AI Glossary",
        )
        default_name = f"AI_Glossary_{datetime.now().date().isoformat()}.md"
        default_path = (app_data_dir() / default_name).expanduser().resolve()
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AI Glossary",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not selected_path:
            return
        target = Path(selected_path).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Glossary", f"Unable to save export file:\n{target}\n{exc}")
            return
        QMessageBox.information(self, "Glossary", f"Exported:\n{target}")

    def _build_tab_study(self) -> None:
        layout = QVBoxLayout(self.tab_study)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.study_search_edit = QLineEdit()
        self.study_search_edit.setPlaceholderText("Filter PT term or any translation...")
        search_row.addWidget(self.study_search_edit, 1)
        layout.addLayout(search_row)
        self._study_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.tab_study)
        self._study_search_shortcut.activated.connect(self._focus_study_search)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Category"))
        self.study_category_filter_combo = QComboBox()
        self.study_category_filter_combo.addItems(
            ["all", "headers", "roles", "procedure", "evidence", "reasoning", "decision_costs", "other"]
        )
        filter_row.addWidget(self.study_category_filter_combo)
        filter_row.addWidget(QLabel("Status"))
        self.study_status_filter_combo = QComboBox()
        self.study_status_filter_combo.addItems(["all", "new", "learning", "known", "hard"])
        filter_row.addWidget(self.study_status_filter_combo)
        filter_row.addWidget(QLabel("Coverage tier"))
        self.study_coverage_filter_combo = QComboBox()
        self.study_coverage_filter_combo.addItems(["all", "core80", "next15", "long_tail"])
        filter_row.addWidget(self.study_coverage_filter_combo)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        builder = QGroupBox("Builder")
        builder_layout = QGridLayout(builder)
        builder_layout.addWidget(QLabel("Corpus source"), 0, 0)
        self.study_corpus_source_combo = QComboBox()
        self.study_corpus_source_combo.addItem("Run folders (recommended for large corpora)", "run_folders")
        self.study_corpus_source_combo.addItem("Current PDF only", "current_pdf")
        self.study_corpus_source_combo.addItem("Select PDFs...", "select_pdfs")
        self.study_corpus_source_combo.addItem("From Job Log runs (unavailable in this version)", "joblog_runs")
        self.study_corpus_source_combo.setToolTip(
            "Job Log source is intentionally unavailable in this version (no run/pdf path tracking migration)."
        )
        builder_layout.addWidget(self.study_corpus_source_combo, 0, 1)
        self.study_current_pdf_label = QLabel("Current PDF: not available")
        self.study_current_pdf_label.setWordWrap(True)
        builder_layout.addWidget(self.study_current_pdf_label, 0, 2, 1, 2)

        builder_layout.addWidget(QLabel("Run folders"), 1, 0)
        self.study_run_dirs_list = QListWidget()
        self.study_run_dirs_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        builder_layout.addWidget(self.study_run_dirs_list, 2, 0, 4, 1)
        run_btns = QVBoxLayout()
        self.study_add_run_dir_btn = QPushButton("Add run folder")
        self.study_remove_run_dir_btn = QPushButton("Remove selected")
        self.study_clear_run_dirs_btn = QPushButton("Clear")
        run_btns.addWidget(self.study_add_run_dir_btn)
        run_btns.addWidget(self.study_remove_run_dir_btn)
        run_btns.addWidget(self.study_clear_run_dirs_btn)
        run_btns.addStretch(1)
        run_btn_wrap = QWidget()
        run_btn_wrap.setLayout(run_btns)
        builder_layout.addWidget(run_btn_wrap, 2, 1, 4, 1)

        builder_layout.addWidget(QLabel("Selected PDFs"), 6, 0)
        self.study_pdf_paths_list = QListWidget()
        self.study_pdf_paths_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        builder_layout.addWidget(self.study_pdf_paths_list, 7, 0, 3, 1)
        pdf_btns = QVBoxLayout()
        self.study_add_pdf_btn = QPushButton("Add PDF(s)")
        self.study_remove_pdf_btn = QPushButton("Remove selected")
        self.study_clear_pdf_btn = QPushButton("Clear")
        pdf_btns.addWidget(self.study_add_pdf_btn)
        pdf_btns.addWidget(self.study_remove_pdf_btn)
        pdf_btns.addWidget(self.study_clear_pdf_btn)
        pdf_btns.addStretch(1)
        pdf_btn_wrap = QWidget()
        pdf_btn_wrap.setLayout(pdf_btns)
        builder_layout.addWidget(pdf_btn_wrap, 7, 1, 3, 1)

        builder_layout.addWidget(QLabel("Mode"), 1, 2)
        self.study_mode_combo = QComboBox()
        self.study_mode_combo.addItem("Full text", "full_text")
        self.study_mode_combo.addItem("Headers only", "headers_only")
        builder_layout.addWidget(self.study_mode_combo, 1, 3)

        builder_layout.addWidget(QLabel("Coverage target (%)"), 2, 2)
        self.study_coverage_spin = QSpinBox()
        self.study_coverage_spin.setRange(50, 95)
        self.study_coverage_spin.setValue(80)
        builder_layout.addWidget(self.study_coverage_spin, 2, 3)

        self.study_include_snippets_check = QCheckBox("Store snippets (privacy-sensitive; capped)")
        builder_layout.addWidget(self.study_include_snippets_check, 3, 2, 1, 2)

        builder_layout.addWidget(QLabel("Snippet max chars"), 4, 2)
        self.study_snippet_chars_spin = QSpinBox()
        self.study_snippet_chars_spin.setRange(40, 300)
        self.study_snippet_chars_spin.setValue(120)
        builder_layout.addWidget(self.study_snippet_chars_spin, 4, 3)

        self.study_generate_btn = QPushButton("Generate")
        self.study_cancel_generate_btn = QPushButton("Cancel")
        self.study_cancel_generate_btn.setEnabled(False)
        self.study_progress = QProgressBar()
        self.study_progress.setRange(0, 100)
        self.study_progress.setValue(0)
        self.study_summary_label = QLabel("No candidates generated yet.")
        builder_layout.addWidget(self.study_generate_btn, 5, 2)
        cancel_progress_row = QHBoxLayout()
        cancel_progress_row.addWidget(self.study_cancel_generate_btn)
        cancel_progress_row.addWidget(self.study_progress, 1)
        cancel_progress_wrap = QWidget()
        cancel_progress_wrap.setLayout(cancel_progress_row)
        builder_layout.addWidget(cancel_progress_wrap, 5, 3)
        builder_layout.addWidget(self.study_summary_label, 10, 0, 1, 4)
        builder_layout.setColumnStretch(0, 2)
        builder_layout.setColumnStretch(3, 1)
        layout.addWidget(builder)

        suggestions_group = QGroupBox("Suggestions")
        suggestions_layout = QVBoxLayout(suggestions_group)
        self.study_candidates_table = QTableWidget(0, 8, self.tab_study)
        self.study_candidates_table.setHorizontalHeaderLabels(
            ["Use", "Portuguese (PT)", "TF", "Pages", "Category", "Coverage", "Confidence", "Snippet"]
        )
        self.study_candidates_table.verticalHeader().setVisible(False)
        self.study_candidates_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.study_candidates_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.study_candidates_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        suggestions_layout.addWidget(self.study_candidates_table, 1)
        self.study_add_selected_btn = QPushButton("Add selected to Study Glossary")
        suggestions_layout.addWidget(self.study_add_selected_btn)
        layout.addWidget(suggestions_group)

        entries_group = QGroupBox("Study Glossary")
        entries_layout = QVBoxLayout(entries_group)
        self.study_entries_table = QTableWidget(0, 0, self.tab_study)
        self.study_entries_table.verticalHeader().setVisible(False)
        self.study_entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.study_entries_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        entries_layout.addWidget(self.study_entries_table, 1)

        entries_actions = QHBoxLayout()
        self.study_refresh_translations_btn = QPushButton("Refresh translations")
        self.study_export_btn = QPushButton("Export...")
        self.study_copy_to_ai_btn = QPushButton("Copy selected to AI Glossary...")
        self.study_quiz_btn = QPushButton("Quiz me")
        self.study_stats_label = QLabel("")
        entries_actions.addWidget(self.study_refresh_translations_btn)
        entries_actions.addWidget(self.study_export_btn)
        entries_actions.addWidget(self.study_copy_to_ai_btn)
        entries_actions.addWidget(self.study_quiz_btn)
        entries_actions.addWidget(self.study_stats_label, 1)
        entries_layout.addLayout(entries_actions)
        layout.addWidget(entries_group, 1)

        self.study_search_edit.textChanged.connect(self._on_study_search_changed)
        self.study_category_filter_combo.currentTextChanged.connect(self._on_study_filters_changed)
        self.study_status_filter_combo.currentTextChanged.connect(self._on_study_filters_changed)
        self.study_coverage_filter_combo.currentTextChanged.connect(self._on_study_filters_changed)
        self.study_corpus_source_combo.currentTextChanged.connect(self._on_study_corpus_source_changed)
        self.study_add_run_dir_btn.clicked.connect(self._add_study_run_folder)
        self.study_remove_run_dir_btn.clicked.connect(self._remove_selected_study_run_folders)
        self.study_clear_run_dirs_btn.clicked.connect(self._clear_study_run_folders)
        self.study_add_pdf_btn.clicked.connect(self._add_study_pdf_files)
        self.study_remove_pdf_btn.clicked.connect(self._remove_selected_study_pdf_files)
        self.study_clear_pdf_btn.clicked.connect(self._clear_study_pdf_files)
        self.study_generate_btn.clicked.connect(self._generate_study_candidates)
        self.study_cancel_generate_btn.clicked.connect(self._cancel_study_generation)
        self.study_add_selected_btn.clicked.connect(self._add_selected_candidates_to_study_glossary)
        self.study_refresh_translations_btn.clicked.connect(self._refresh_selected_study_translations)
        self.study_export_btn.clicked.connect(self._export_study_glossary_markdown)
        self.study_copy_to_ai_btn.clicked.connect(self._copy_selected_study_to_ai_glossary)
        self.study_quiz_btn.clicked.connect(self._quiz_study_entry)

    def _focus_study_search(self) -> None:
        self.study_search_edit.setFocus()
        self.study_search_edit.selectAll()

    def _study_entry_key(self, term_pt: str) -> str:
        return str(term_pt or "").strip().casefold()

    def _collect_study_run_dirs(self) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for idx in range(self.study_run_dirs_list.count()):
            item = self.study_run_dirs_list.item(idx)
            if item is None:
                continue
            cleaned = item.text().strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(cleaned)
        return values

    def _set_study_run_dirs(self, run_dirs: list[str]) -> None:
        self.study_run_dirs_list.clear()
        seen: set[str] = set()
        for raw in run_dirs:
            cleaned = str(raw or "").strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            self.study_run_dirs_list.addItem(cleaned)

    def _add_study_run_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select run folder")
        if not selected:
            return
        candidate = str(Path(selected).expanduser().resolve())
        existing = {item.casefold() for item in self._collect_study_run_dirs()}
        if candidate.casefold() in existing:
            return
        self.study_run_dirs_list.addItem(candidate)

    def _remove_selected_study_run_folders(self) -> None:
        for item in self.study_run_dirs_list.selectedItems():
            row = self.study_run_dirs_list.row(item)
            self.study_run_dirs_list.takeItem(row)

    def _clear_study_run_folders(self) -> None:
        self.study_run_dirs_list.clear()

    def _collect_study_pdf_paths(self) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for idx in range(self.study_pdf_paths_list.count()):
            item = self.study_pdf_paths_list.item(idx)
            if item is None:
                continue
            cleaned = item.text().strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(cleaned)
        return values

    def _set_study_pdf_paths(self, pdf_paths: list[str]) -> None:
        self.study_pdf_paths_list.clear()
        seen: set[str] = set()
        for raw in pdf_paths:
            cleaned = str(raw or "").strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            self.study_pdf_paths_list.addItem(cleaned)
        self._study_pdf_paths = self._collect_study_pdf_paths()

    def _add_study_pdf_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF files",
            "",
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not selected:
            return
        existing = {item.casefold() for item in self._collect_study_pdf_paths()}
        for raw in selected:
            cleaned = str(Path(raw).expanduser().resolve())
            if cleaned.casefold() in existing:
                continue
            self.study_pdf_paths_list.addItem(cleaned)
            existing.add(cleaned.casefold())
        self._study_pdf_paths = self._collect_study_pdf_paths()

    def _remove_selected_study_pdf_files(self) -> None:
        for item in self.study_pdf_paths_list.selectedItems():
            row = self.study_pdf_paths_list.row(item)
            self.study_pdf_paths_list.takeItem(row)
        self._study_pdf_paths = self._collect_study_pdf_paths()

    def _clear_study_pdf_files(self) -> None:
        self.study_pdf_paths_list.clear()
        self._study_pdf_paths = []

    def _current_study_corpus_source(self) -> str:
        raw = self.study_corpus_source_combo.currentData()
        value = str(raw or self.study_corpus_source_combo.currentText() or "").strip().lower()
        if value not in {"run_folders", "current_pdf", "select_pdfs", "joblog_runs"}:
            return "run_folders"
        return value

    def _refresh_study_corpus_source_controls(self) -> None:
        mode = self._current_study_corpus_source()
        self._study_corpus_source = mode
        run_enabled = mode == "run_folders"
        pdf_enabled = mode == "select_pdfs"
        self.study_run_dirs_list.setEnabled(run_enabled)
        self.study_add_run_dir_btn.setEnabled(run_enabled)
        self.study_remove_run_dir_btn.setEnabled(run_enabled)
        self.study_clear_run_dirs_btn.setEnabled(run_enabled)
        self.study_pdf_paths_list.setEnabled(pdf_enabled)
        self.study_add_pdf_btn.setEnabled(pdf_enabled)
        self.study_remove_pdf_btn.setEnabled(pdf_enabled)
        self.study_clear_pdf_btn.setEnabled(pdf_enabled)
        if self._study_current_pdf_path is not None and self._study_current_pdf_path.exists():
            self.study_current_pdf_label.setText(f"Current PDF: {self._study_current_pdf_path}")
        else:
            self.study_current_pdf_label.setText("Current PDF: not available")
        if mode == "joblog_runs":
            self.study_current_pdf_label.setText(
                "Current PDF: unavailable for this source mode. Job Log run/pdf mapping is not enabled."
            )

    def _on_study_corpus_source_changed(self, _value: str) -> None:
        self._refresh_study_corpus_source_controls()

    def _resolve_study_corpus_inputs(self) -> tuple[str, list[str], list[str]] | None:
        source_mode = self._current_study_corpus_source()
        run_dirs = self._collect_study_run_dirs()
        pdf_paths: list[str] = []
        if source_mode == "run_folders":
            if not run_dirs:
                QMessageBox.warning(self, "Study Glossary", "Select at least one run folder.")
                return None
            return (source_mode, run_dirs, [])
        if source_mode == "current_pdf":
            current_pdf = self._study_current_pdf_path
            if current_pdf is None or (not current_pdf.exists()) or (not current_pdf.is_file()):
                QMessageBox.warning(self, "Study Glossary", "No active PDF is available. Select a PDF in the main window first.")
                return None
            return (source_mode, [], [str(current_pdf)])
        if source_mode == "select_pdfs":
            pdf_paths = self._collect_study_pdf_paths()
            if not pdf_paths:
                QMessageBox.warning(self, "Study Glossary", "Select one or more PDF files.")
                return None
            return (source_mode, [], pdf_paths)
        QMessageBox.information(
            self,
            "Study Glossary",
            "Job Log source is unavailable in this version (requires run/pdf path tracking in Job Log DB).",
        )
        return None

    def _visible_study_entries(self) -> list[StudyGlossaryEntry]:
        search = self._study_search_text.strip().casefold()
        category = self._study_filters.get("category", "all")
        status = self._study_filters.get("status", "all")
        coverage_tier = self._study_filters.get("coverage_tier", "all")
        visible: list[StudyGlossaryEntry] = []
        for entry in self._study_entries:
            if category != "all" and entry.category != category:
                continue
            if status != "all" and entry.status != status:
                continue
            if coverage_tier != "all" and entry.coverage_tier != coverage_tier:
                continue
            if search:
                haystack = [entry.term_pt]
                haystack.extend(entry.translations_by_lang.get(lang, "") for lang in self._study_supported_langs)
                if not any(search in str(value or "").casefold() for value in haystack):
                    continue
            visible.append(entry)
        return visible

    def _set_study_entries_table_rows(self, rows: list[StudyGlossaryEntry]) -> None:
        headers = ["Portuguese (PT)"] + self._study_supported_langs + [
            "TF",
            "Pages",
            "Docs",
            "Category",
            "Status",
            "Next review",
            "Coverage",
            "Snippet",
        ]
        self.study_entries_table.setColumnCount(len(headers))
        self.study_entries_table.setHorizontalHeaderLabels(headers)
        self.study_entries_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for lang_index in range(len(self._study_supported_langs)):
            self.study_entries_table.horizontalHeader().setSectionResizeMode(
                1 + lang_index,
                QHeaderView.ResizeMode.Stretch,
            )
        self.study_entries_table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        self.study_entries_table.setRowCount(0)
        self._study_entry_view_terms = [entry.term_pt for entry in rows]
        for entry in rows:
            row = self.study_entries_table.rowCount()
            self.study_entries_table.insertRow(row)
            self.study_entries_table.setItem(row, 0, QTableWidgetItem(entry.term_pt))
            for lang_index, lang in enumerate(self._study_supported_langs):
                self.study_entries_table.setItem(
                    row,
                    1 + lang_index,
                    QTableWidgetItem(entry.translations_by_lang.get(lang, "")),
                )
            offset = 1 + len(self._study_supported_langs)
            self.study_entries_table.setItem(row, offset + 0, QTableWidgetItem(str(int(entry.tf))))
            self.study_entries_table.setItem(row, offset + 1, QTableWidgetItem(str(int(entry.df_pages))))
            self.study_entries_table.setItem(row, offset + 2, QTableWidgetItem(str(int(entry.df_docs))))
            self.study_entries_table.setItem(row, offset + 3, QTableWidgetItem(entry.category))
            self.study_entries_table.setItem(row, offset + 4, QTableWidgetItem(entry.status))
            self.study_entries_table.setItem(row, offset + 5, QTableWidgetItem(entry.next_review_date or ""))
            self.study_entries_table.setItem(row, offset + 6, QTableWidgetItem(entry.coverage_tier))
            snippet = entry.sample_snippets[0] if entry.sample_snippets else ""
            self.study_entries_table.setItem(row, offset + 7, QTableWidgetItem(snippet))

    def _read_study_entries_table_rows(self) -> list[StudyGlossaryEntry]:
        rows: list[dict[str, object]] = []
        lang_count = len(self._study_supported_langs)
        for row in range(self.study_entries_table.rowCount()):
            term_item = self.study_entries_table.item(row, 0)
            term_pt = term_item.text().strip() if term_item else ""
            translations: dict[str, str] = {}
            for lang_index, lang in enumerate(self._study_supported_langs):
                item = self.study_entries_table.item(row, 1 + lang_index)
                translations[lang] = item.text().strip() if item else ""
            offset = 1 + lang_count
            tf_item = self.study_entries_table.item(row, offset + 0)
            df_item = self.study_entries_table.item(row, offset + 1)
            docs_item = self.study_entries_table.item(row, offset + 2)
            category_item = self.study_entries_table.item(row, offset + 3)
            status_item = self.study_entries_table.item(row, offset + 4)
            review_item = self.study_entries_table.item(row, offset + 5)
            coverage_item = self.study_entries_table.item(row, offset + 6)
            snippet_item = self.study_entries_table.item(row, offset + 7)
            rows.append(
                {
                    "term_pt": term_pt,
                    "translations_by_lang": translations,
                    "tf": (tf_item.text().strip() if tf_item else "0"),
                    "df_pages": (df_item.text().strip() if df_item else "0"),
                    "df_docs": (docs_item.text().strip() if docs_item else "0"),
                    "category": (category_item.text().strip() if category_item else "other"),
                    "status": (status_item.text().strip() if status_item else "new"),
                    "next_review_date": (review_item.text().strip() if review_item else ""),
                    "coverage_tier": (coverage_item.text().strip() if coverage_item else "long_tail"),
                    "sample_snippets": [snippet_item.text().strip()] if snippet_item and snippet_item.text().strip() else [],
                }
            )
        return normalize_study_entries(rows, self._study_supported_langs)

    def _save_current_study_table_rows(self) -> None:
        visible_rows = self._read_study_entries_table_rows()
        key_to_visible = {self._study_entry_key(entry.term_pt): entry for entry in visible_rows}
        visible_keys = {self._study_entry_key(term) for term in self._study_entry_view_terms}
        hidden = [
            entry
            for entry in self._study_entries
            if self._study_entry_key(entry.term_pt) not in visible_keys
        ]
        merged = hidden + list(key_to_visible.values())
        self._study_entries = normalize_study_entries(
            serialize_study_entries(merged, self._study_supported_langs),
            self._study_supported_langs,
        )

    def _refresh_study_entries_table(self) -> None:
        rows = self._visible_study_entries()
        self._set_study_entries_table_rows(rows)
        self._refresh_study_stats_label()

    def _refresh_study_stats_label(self) -> None:
        total = len(self._study_entries)
        visible = len(self._visible_study_entries())
        self.study_stats_label.setText(f"Entries: {visible}/{total}")

    def _on_study_search_changed(self, text: str) -> None:
        self._save_current_study_table_rows()
        self._study_search_text = str(text or "")
        self._refresh_study_entries_table()

    def _on_study_filters_changed(self, _value: str) -> None:
        self._save_current_study_table_rows()
        self._study_filters["category"] = self.study_category_filter_combo.currentText().strip().lower() or "all"
        self._study_filters["status"] = self.study_status_filter_combo.currentText().strip().lower() or "all"
        self._study_filters["coverage_tier"] = self.study_coverage_filter_combo.currentText().strip().lower() or "all"
        self._refresh_study_entries_table()

    def _set_study_candidates_table_rows(self, rows: list[StudyCandidate], selected_terms: set[str]) -> None:
        self.study_candidates_table.setRowCount(0)
        self._study_candidate_keys = []
        for candidate in rows:
            row = self.study_candidates_table.rowCount()
            self.study_candidates_table.insertRow(row)
            check = QCheckBox()
            check.setChecked(self._study_entry_key(candidate.term_pt) in selected_terms)
            self.study_candidates_table.setCellWidget(row, 0, check)
            self.study_candidates_table.setItem(row, 1, QTableWidgetItem(candidate.term_pt))
            self.study_candidates_table.setItem(row, 2, QTableWidgetItem(str(int(candidate.tf))))
            self.study_candidates_table.setItem(row, 3, QTableWidgetItem(str(int(candidate.df_pages))))
            self.study_candidates_table.setItem(row, 4, QTableWidgetItem(candidate.category))
            self.study_candidates_table.setItem(row, 5, QTableWidgetItem(candidate.coverage_tier))
            self.study_candidates_table.setItem(row, 6, QTableWidgetItem(f"{float(candidate.confidence):.3f}"))
            snippet = candidate.sample_snippets[0] if candidate.sample_snippets else ""
            self.study_candidates_table.setItem(row, 7, QTableWidgetItem(snippet))
            self._study_candidate_keys.append(self._study_entry_key(candidate.term_pt))

    def _set_study_generation_controls_busy(self, busy: bool) -> None:
        enabled = not busy
        self.study_generate_btn.setEnabled(enabled)
        self.study_corpus_source_combo.setEnabled(enabled)
        self.study_mode_combo.setEnabled(enabled)
        self.study_include_snippets_check.setEnabled(enabled)
        self.study_snippet_chars_spin.setEnabled(enabled)
        self.study_coverage_spin.setEnabled(enabled)
        self.study_cancel_generate_btn.setEnabled(busy)
        if enabled:
            self._refresh_study_corpus_source_controls()
        else:
            self.study_run_dirs_list.setEnabled(False)
            self.study_add_run_dir_btn.setEnabled(False)
            self.study_remove_run_dir_btn.setEnabled(False)
            self.study_clear_run_dirs_btn.setEnabled(False)
            self.study_pdf_paths_list.setEnabled(False)
            self.study_add_pdf_btn.setEnabled(False)
            self.study_remove_pdf_btn.setEnabled(False)
            self.study_clear_pdf_btn.setEnabled(False)

    def _generate_study_candidates(self) -> None:
        if self._study_candidate_thread is not None:
            return
        resolved = self._resolve_study_corpus_inputs()
        if resolved is None:
            return
        source_mode, run_dirs, pdf_paths = resolved
        mode = self.study_mode_combo.currentData()
        mode_value = str(mode or "full_text")
        include_snippets = bool(self.study_include_snippets_check.isChecked())
        snippet_max_chars = int(self.study_snippet_chars_spin.value())
        self._set_study_generation_controls_busy(True)
        self.study_progress.setValue(0)
        self.study_summary_label.setText("Generating study glossary candidates...")
        thread = QThread(self)
        worker = _StudyCandidateWorker(
            source_mode=source_mode,
            run_dirs=run_dirs,
            pdf_paths=pdf_paths,
            mode=mode_value,
            include_snippets=include_snippets,
            snippet_max_chars=snippet_max_chars,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_study_candidate_progress)
        worker.finished.connect(self._on_study_candidate_finished)
        worker.cancelled.connect(self._on_study_candidate_cancelled)
        worker.error.connect(self._on_study_candidate_error)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)
        self._study_candidate_thread = thread
        self._study_candidate_worker = worker
        thread.start()

    def _cancel_study_generation(self) -> None:
        worker = self._study_candidate_worker
        if worker is None:
            return
        worker.cancel()
        self.study_cancel_generate_btn.setEnabled(False)
        self.study_summary_label.setText("Cancelling generation...")

    def _on_study_candidate_progress(self, value: int, message: str) -> None:
        self.study_progress.setValue(max(0, min(100, int(value))))
        self.study_summary_label.setText(message)

    def _on_study_candidate_finished(self, payload: object) -> None:
        self._set_study_generation_controls_busy(False)
        data = payload if isinstance(payload, dict) else {}
        candidates_raw = data.get("candidates")
        candidates = candidates_raw if isinstance(candidates_raw, list) else []
        pages_tokens_raw = data.get("pages_tokens")
        pages_tokens: list[list[str]] = []
        if isinstance(pages_tokens_raw, list):
            for page in pages_tokens_raw:
                if not isinstance(page, list):
                    continue
                normalized_page = [str(token).strip().casefold() for token in page if str(token).strip()]
                if normalized_page:
                    pages_tokens.append(normalized_page)
        filtered = filter_candidates_by_thresholds(
            [candidate for candidate in candidates if isinstance(candidate, StudyCandidate)]
        )
        coverage_target = max(50, min(95, int(self.study_coverage_spin.value()))) / 100.0
        tiered = compute_non_overlapping_tier_assignment(
            filtered,
            pages_tokens,
            coverage_target=coverage_target,
            next_target=0.95,
        )
        filtered_for_display = apply_subsumption_suppression(
            tiered,
            pages_tokens,
            threshold=0.80,
        )
        selected_keys = {
            self._study_entry_key(candidate.term_pt)
            for candidate in filtered_for_display
            if candidate.coverage_tier == "core80"
        }
        self._study_candidate_rows = filtered_for_display
        self._set_study_candidates_table_rows(filtered_for_display, selected_keys)
        self._study_last_run_folders_processed = int(data.get("run_folders_processed", 0) or 0)
        self._study_last_total_pages_scanned = int(data.get("total_pages_scanned", 0) or 0)
        source_mode = str(data.get("source_mode", self._study_corpus_source) or "run_folders")
        source_label = "folders" if source_mode == "run_folders" else "sources"
        self.study_progress.setValue(100)
        core_count = len([item for item in filtered_for_display if item.coverage_tier == "core80"])
        self.study_summary_label.setText(
            f"Candidates: {len(filtered_for_display)} | {source_label}: {self._study_last_run_folders_processed} | "
            f"pages: {self._study_last_total_pages_scanned} | core {int(coverage_target * 100)}%: {core_count}."
        )
        self._study_candidate_thread = None
        self._study_candidate_worker = None

    def _on_study_candidate_cancelled(self) -> None:
        self._set_study_generation_controls_busy(False)
        self.study_summary_label.setText("Generation cancelled. Existing study glossary is unchanged.")
        self.study_progress.setValue(0)
        self._study_candidate_thread = None
        self._study_candidate_worker = None

    def _on_study_candidate_error(self, message: str) -> None:
        self._set_study_generation_controls_busy(False)
        self.study_summary_label.setText("Generation failed.")
        self.study_progress.setValue(0)
        self._study_candidate_thread = None
        self._study_candidate_worker = None
        QMessageBox.critical(self, "Study Glossary", message or "Failed to generate study glossary candidates.")

    def _add_selected_candidates_to_study_glossary(self) -> None:
        if not self._study_candidate_rows:
            return
        selected: list[StudyCandidate] = []
        for row in range(self.study_candidates_table.rowCount()):
            check = self.study_candidates_table.cellWidget(row, 0)
            checked = bool(check.isChecked()) if isinstance(check, QCheckBox) else False
            if not checked:
                continue
            if row < len(self._study_candidate_rows):
                selected.append(self._study_candidate_rows[row])
        if not selected:
            QMessageBox.information(self, "Study Glossary", "No candidate selected.")
            return
        new_entries = [
            build_entry_from_candidate(candidate, supported_langs=self._study_supported_langs)
            for candidate in selected
        ]
        self._save_current_study_table_rows()
        self._study_entries = merge_study_entries(
            self._study_entries,
            new_entries,
            supported_langs=self._study_supported_langs,
        )
        self._refresh_study_entries_table()

    def _selected_study_entries_from_table(self) -> list[StudyGlossaryEntry]:
        selected_rows = sorted({index.row() for index in self.study_entries_table.selectedIndexes()})
        if not selected_rows:
            return []
        visible_rows = self._visible_study_entries()
        selected_entries: list[StudyGlossaryEntry] = []
        for row in selected_rows:
            if 0 <= row < len(visible_rows):
                selected_entries.append(visible_rows[row])
        return selected_entries

    def _count_study_to_ai_conflicts(self, selected_entries: list[StudyGlossaryEntry]) -> int:
        supported_langs = supported_target_langs()
        normalized = normalize_glossaries(self._glossaries_by_lang, supported_langs)
        conflicts = 0
        for entry in selected_entries:
            source_text = entry.term_pt.strip()
            if source_text == "":
                continue
            for target_lang in supported_langs:
                preferred = entry.translations_by_lang.get(target_lang, "").strip()
                if preferred == "":
                    continue
                duplicate = any(
                    row.source_text == source_text
                    and row.preferred_translation == preferred
                    and row.match_mode == "exact"
                    and row.source_lang == "PT"
                    and int(row.tier) == 2
                    for row in normalized.get(target_lang, [])
                )
                if duplicate:
                    continue
                has_conflict = any(
                    row.source_text == source_text
                    and row.match_mode == "exact"
                    and row.source_lang == "PT"
                    and int(row.tier) == 2
                    and row.preferred_translation != preferred
                    for row in normalized.get(target_lang, [])
                )
                if has_conflict:
                    conflicts += 1
        return conflicts

    def _merge_study_entries_into_ai_glossary(
        self,
        selected_entries: list[StudyGlossaryEntry],
        *,
        replace_conflicts: bool,
    ) -> tuple[int, int, int]:
        supported_langs = supported_target_langs()
        normalized = normalize_glossaries(self._glossaries_by_lang, supported_langs)
        added = 0
        skipped = 0
        conflicts = 0
        for entry in selected_entries:
            source_text = entry.term_pt.strip()
            if source_text == "":
                continue
            for target_lang in supported_langs:
                preferred = entry.translations_by_lang.get(target_lang, "").strip()
                if preferred == "":
                    continue
                bucket = list(normalized.get(target_lang, []))
                candidate = GlossaryEntry(
                    source_text=source_text,
                    preferred_translation=preferred,
                    match_mode="exact",
                    source_lang="PT",
                    tier=2,
                )
                duplicate = any(
                    row.source_text == candidate.source_text
                    and row.preferred_translation == candidate.preferred_translation
                    and row.match_mode == candidate.match_mode
                    and row.source_lang == candidate.source_lang
                    and int(row.tier) == int(candidate.tier)
                    for row in bucket
                )
                if duplicate:
                    skipped += 1
                    continue
                conflict_indexes = [
                    index
                    for index, row in enumerate(bucket)
                    if row.source_text == candidate.source_text
                    and row.match_mode == candidate.match_mode
                    and row.source_lang == candidate.source_lang
                    and int(row.tier) == int(candidate.tier)
                    and row.preferred_translation != candidate.preferred_translation
                ]
                if conflict_indexes:
                    conflicts += 1
                    if not replace_conflicts:
                        skipped += 1
                        continue
                    for index in reversed(conflict_indexes):
                        bucket.pop(index)
                bucket.append(candidate)
                normalized[target_lang] = normalize_glossaries({target_lang: bucket}, [target_lang]).get(target_lang, [])
                added += 1
        self._glossaries_by_lang = normalize_glossaries(normalized, supported_langs)
        return (added, skipped, conflicts)

    def _copy_selected_study_to_ai_glossary(self) -> None:
        self._save_current_study_table_rows()
        self._save_current_glossary_language_rows()
        selected_entries = self._selected_study_entries_from_table()
        if not selected_entries:
            QMessageBox.information(self, "Study Glossary", "Select one or more Study Glossary rows first.")
            return
        conflicts = self._count_study_to_ai_conflicts(selected_entries)
        replace_conflicts = False
        if conflicts > 0:
            choice = QMessageBox.question(
                self,
                "Copy to AI Glossary",
                (
                    "Conflicts were detected for the default mapping "
                    "(Exact + PT + Tier 2).\n\n"
                    "Yes: replace conflicting AI glossary rows.\n"
                    "No: skip conflicting rows.\n"
                    "Cancel: abort."
                ),
                buttons=(
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                ),
                defaultButton=QMessageBox.StandardButton.No,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            replace_conflicts = choice == QMessageBox.StandardButton.Yes
        else:
            choice = QMessageBox.question(
                self,
                "Copy to AI Glossary",
                (
                    "Copy selected study entries into AI Glossary?\n\n"
                    "Defaults: match=exact, source_lang=PT, tier=2.\n"
                    "Targets: all non-empty target-language translations."
                ),
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.Yes,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        added, skipped, conflict_count = self._merge_study_entries_into_ai_glossary(
            selected_entries,
            replace_conflicts=replace_conflicts,
        )
        self._refresh_glossary_table_view()
        QMessageBox.information(
            self,
            "Copy to AI Glossary",
            f"Added: {added}\nSkipped: {skipped}\nConflicts encountered: {conflict_count}",
        )

    def _refresh_selected_study_translations(self) -> None:
        self._save_current_study_table_rows()
        selected_entries = self._selected_study_entries_from_table()
        if not selected_entries:
            QMessageBox.information(self, "Study Glossary", "Select one or more study rows first.")
            return
        self.study_refresh_translations_btn.setEnabled(False)
        self.study_progress.setValue(0)
        self.study_summary_label.setText("Refreshing translations...")
        thread = QThread(self)
        _lemma_effort = str(self._settings.get("openai_reasoning_effort_lemma", "high") or "high")
        worker = _StudyTranslationWorker(
            entries=selected_entries, supported_langs=self._study_supported_langs, lemma_effort=_lemma_effort,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_study_translation_progress)
        worker.finished.connect(self._on_study_translation_finished)
        worker.error.connect(self._on_study_translation_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)
        self._study_translation_thread = thread
        self._study_translation_worker = worker
        thread.start()

    def _on_study_translation_progress(self, value: int, message: str) -> None:
        self.study_progress.setValue(max(0, min(100, int(value))))
        self.study_summary_label.setText(message)

    def _on_study_translation_finished(self, updated_rows: object) -> None:
        entries = updated_rows if isinstance(updated_rows, list) else []
        keyed_updates = {
            self._study_entry_key(entry.term_pt): entry
            for entry in entries
            if isinstance(entry, StudyGlossaryEntry)
        }
        merged: list[StudyGlossaryEntry] = []
        for entry in self._study_entries:
            key = self._study_entry_key(entry.term_pt)
            merged.append(keyed_updates.get(key, entry))
        self._study_entries = normalize_study_entries(
            serialize_study_entries(merged, self._study_supported_langs),
            self._study_supported_langs,
        )
        self.study_refresh_translations_btn.setEnabled(True)
        self.study_progress.setValue(100)
        self.study_summary_label.setText("Translation refresh complete.")
        self._refresh_study_entries_table()
        self._study_translation_thread = None
        self._study_translation_worker = None

    def _on_study_translation_error(self, message: str) -> None:
        self.study_refresh_translations_btn.setEnabled(True)
        self.study_summary_label.setText("Translation refresh failed.")
        self.study_progress.setValue(0)
        self._study_translation_thread = None
        self._study_translation_worker = None
        QMessageBox.critical(self, "Study Glossary", message or "Failed to refresh translations.")

    def _export_study_glossary_markdown(self) -> None:
        self._save_current_study_table_rows()
        if not self._study_entries:
            QMessageBox.information(self, "Study Glossary", "No study glossary entries to export.")
            return

        chooser = QMessageBox(self)
        chooser.setWindowTitle("Export Study Glossary")
        chooser.setText("Choose export scope.")
        current_btn = chooser.addButton("Current filter (Recommended)", QMessageBox.ButtonRole.AcceptRole)
        all_btn = chooser.addButton("All entries", QMessageBox.ButtonRole.ActionRole)
        chooser.addButton(QMessageBox.StandardButton.Cancel)
        chooser.exec()
        clicked = chooser.clickedButton()
        if clicked is None or clicked == chooser.button(QMessageBox.StandardButton.Cancel):
            return
        if clicked == current_btn:
            export_rows = self._visible_study_entries()
            scope_label = "Current filter"
        else:
            export_rows = list(self._study_entries)
            scope_label = "All entries"
        if not export_rows:
            QMessageBox.information(self, "Study Glossary", "No entries match the selected export scope.")
            return

        generated_at_iso = datetime.now().replace(microsecond=0).isoformat()
        markdown = build_study_glossary_markdown(
            export_rows,
            generated_at_iso=generated_at_iso,
            run_folders_count=self._study_last_run_folders_processed,
            total_pages_scanned=self._study_last_total_pages_scanned,
            include_snippets=bool(self.study_include_snippets_check.isChecked()),
            snippet_max_chars=int(self.study_snippet_chars_spin.value()),
            scope_label=scope_label,
            supported_langs=self._study_supported_langs,
        )
        default_name = f"Study_Glossary_{datetime.now().date().isoformat()}.md"
        default_path = (app_data_dir() / default_name).expanduser().resolve()
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Study Glossary",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not selected_path:
            return
        target = Path(selected_path).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Study Glossary", f"Unable to save export file:\n{target}\n{exc}")
            return
        QMessageBox.information(self, "Study Glossary", f"Exported:\n{target}")

    def _quiz_study_entry(self) -> None:
        self._save_current_study_table_rows()
        rows = self._visible_study_entries() or list(self._study_entries)
        if not rows:
            QMessageBox.information(self, "Study Glossary", "No study entries available.")
            return
        entry = rows[self._study_quiz_index % len(rows)]
        self._study_quiz_index = (self._study_quiz_index + 1) % max(1, len(rows))
        QMessageBox.information(self, "Study Quiz", f"Portuguese term:\n{entry.term_pt}")
        translations = "\n".join(
            f"{lang}: {entry.translations_by_lang.get(lang, '').strip() or '—'}"
            for lang in self._study_supported_langs
        )
        quiz = QMessageBox(self)
        quiz.setWindowTitle("Study Quiz")
        quiz.setText(f"Translations:\n{translations}\n\nHow well do you know this term?")
        known_btn = quiz.addButton("Known", QMessageBox.ButtonRole.AcceptRole)
        learning_btn = quiz.addButton("Learning", QMessageBox.ButtonRole.ActionRole)
        hard_btn = quiz.addButton("Hard", QMessageBox.ButtonRole.DestructiveRole)
        quiz.addButton(QMessageBox.StandardButton.Cancel)
        quiz.exec()
        clicked = quiz.clickedButton()
        if clicked is None or clicked == quiz.button(QMessageBox.StandardButton.Cancel):
            return
        if clicked == known_btn:
            new_status = "known"
        elif clicked == hard_btn:
            new_status = "hard"
        else:
            new_status = "learning"
        key = self._study_entry_key(entry.term_pt)
        updated_entries: list[StudyGlossaryEntry] = []
        for existing in self._study_entries:
            if self._study_entry_key(existing.term_pt) != key:
                updated_entries.append(existing)
                continue
            updated_entries.append(
                StudyGlossaryEntry(
                    term_pt=existing.term_pt,
                    translations_by_lang=dict(existing.translations_by_lang),
                    tf=existing.tf,
                    df_pages=existing.df_pages,
                    sample_snippets=list(existing.sample_snippets),
                    category=existing.category,
                    status=new_status,  # type: ignore[arg-type]
                    next_review_date=compute_next_review_date(new_status),  # type: ignore[arg-type]
                    coverage_tier=existing.coverage_tier,
                    confidence=existing.confidence,
                )
            )
        self._study_entries = updated_entries
        self._refresh_study_entries_table()

    def _set_study_from_settings(self, settings: dict[str, object]) -> None:
        self._study_supported_langs = supported_learning_langs()
        self._study_entries = normalize_study_entries(
            settings.get("study_glossary_entries"),
            self._study_supported_langs,
        )
        self.study_include_snippets_check.setChecked(bool(settings.get("study_glossary_include_snippets", False)))
        try:
            snippet_max = int(settings.get("study_glossary_snippet_max_chars", 120))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            snippet_max = 120
        try:
            coverage_percent = int(settings.get("study_glossary_default_coverage_percent", 80))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            coverage_percent = 80
        self.study_snippet_chars_spin.setValue(max(40, min(300, snippet_max)))
        self.study_coverage_spin.setValue(max(50, min(95, coverage_percent)))
        run_dirs_raw = settings.get("study_glossary_last_run_dirs")
        run_dirs = [str(item).strip() for item in run_dirs_raw] if isinstance(run_dirs_raw, list) else []
        source_raw = str(settings.get("study_glossary_corpus_source", "run_folders") or "").strip().lower()
        if source_raw not in {"run_folders", "current_pdf", "select_pdfs", "joblog_runs"}:
            source_raw = "run_folders"
        self._study_corpus_source = source_raw
        pdf_paths_raw = settings.get("study_glossary_pdf_paths")
        pdf_paths = [str(item).strip() for item in pdf_paths_raw] if isinstance(pdf_paths_raw, list) else []
        self._set_study_run_dirs(run_dirs)
        self._set_study_pdf_paths(pdf_paths)
        self.study_corpus_source_combo.blockSignals(True)
        for idx in range(self.study_corpus_source_combo.count()):
            if str(self.study_corpus_source_combo.itemData(idx) or "").strip().lower() == source_raw:
                self.study_corpus_source_combo.setCurrentIndex(idx)
                break
        self.study_corpus_source_combo.blockSignals(False)
        self._study_search_text = ""
        self.study_search_edit.clear()
        self.study_category_filter_combo.setCurrentText("all")
        self.study_status_filter_combo.setCurrentText("all")
        self.study_coverage_filter_combo.setCurrentText("all")
        self._study_filters = {"category": "all", "status": "all", "coverage_tier": "all"}
        self._study_candidate_rows = []
        self._study_quiz_index = 0
        self._study_last_run_folders_processed = 0
        self._study_last_total_pages_scanned = 0
        self.study_candidates_table.setRowCount(0)
        self.study_progress.setValue(0)
        self.study_summary_label.setText("No candidates generated yet.")
        self._set_study_generation_controls_busy(False)
        self._refresh_study_corpus_source_controls()
        self._refresh_study_entries_table()

    def _collect_study_settings_values(self) -> dict[str, object]:
        self._save_current_study_table_rows()
        return {
            "study_glossary_entries": serialize_study_entries(self._study_entries, self._study_supported_langs),
            "study_glossary_include_snippets": bool(self.study_include_snippets_check.isChecked()),
            "study_glossary_snippet_max_chars": int(self.study_snippet_chars_spin.value()),
            "study_glossary_last_run_dirs": self._collect_study_run_dirs(),
            "study_glossary_corpus_source": self._current_study_corpus_source(),
            "study_glossary_pdf_paths": self._collect_study_pdf_paths(),
            "study_glossary_default_coverage_percent": int(self.study_coverage_spin.value()),
        }

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
        self.lemma_effort_combo.setCurrentText(str(settings.get("openai_reasoning_effort_lemma", "high")))
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
        self.timeout_text_edit.setText(
            str(settings.get("perf_timeout_text_seconds", DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS))
        )
        self.timeout_image_edit.setText(
            str(settings.get("perf_timeout_image_seconds", DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS))
        )
        self.allow_xhigh_check.setChecked(bool(settings.get("allow_xhigh_escalation", False)))
        self.diag_cost_summary_check.setChecked(bool(settings.get("diagnostics_show_cost_summary", True)))
        self.diag_verbose_meta_check.setChecked(bool(settings.get("diagnostics_verbose_metadata_logs", False)))
        self.diag_admin_mode_check.setChecked(bool(settings.get("diagnostics_admin_mode", True)))
        self.diag_snippets_check.setChecked(bool(settings.get("diagnostics_include_sanitized_snippets", False)))
        self.diag_snippets_check.setEnabled(self.diag_admin_mode_check.isChecked())
        self._set_glossaries_from_settings(settings)
        self._set_study_from_settings(settings)

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
        self.lemma_effort_combo.setCurrentText("high")
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
        self._glossary_seed_version = 2
        self._set_glossaries_from_settings(
            {
                "default_lang": "EN",
                "glossaries_by_lang": serialize_glossaries(self._glossaries_by_lang),
                "glossary_seed_version": self._glossary_seed_version,
            }
        )
        self._set_study_from_settings(
            {
                "study_glossary_entries": [],
                "study_glossary_include_snippets": False,
                "study_glossary_snippet_max_chars": 120,
                "study_glossary_last_run_dirs": [],
                "study_glossary_corpus_source": "run_folders",
                "study_glossary_pdf_paths": [],
                "study_glossary_default_coverage_percent": 80,
            }
        )
        self.ocr_mode_default_combo.setCurrentText("auto")
        self.ocr_engine_default_combo.setCurrentText("local_then_api")
        self.retries_edit.setText("4")
        self.backoff_cap_edit.setText("12.0")
        self.timeout_text_edit.setText(str(DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS))
        self.timeout_image_edit.setText(str(DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS))
        self.allow_xhigh_check.setChecked(False)

    def _collect_values(self) -> dict[str, object]:
        self._commit_glossary_cell_editor()
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
        normalized_enabled_tiers = normalize_enabled_tiers_by_target_lang(
            self._enabled_glossary_tiers_by_lang,
            supported_target_langs(),
        )

        return {
            "ui_theme": self.ui_theme_combo.currentText().strip(),
            "ui_scale": ui_scale,
            "default_lang": self.default_lang_combo.currentText().strip().upper(),
            "default_effort": self.default_effort_combo.currentText().strip().lower(),
            "default_effort_policy": self.default_effort_policy_combo.currentText().strip().lower(),
            "openai_reasoning_effort_lemma": self.lemma_effort_combo.currentText().strip().lower(),
            "default_images_mode": self.default_images_combo.currentText().strip().lower(),
            "default_workers": _to_int(self.default_workers_combo.currentText(), field="Default workers", min_value=1, max_value=6),
            "default_resume": bool(self.default_resume_check.isChecked()),
            "default_keep_intermediates": bool(self.default_keep_check.isChecked()),
            "default_page_breaks": bool(self.default_breaks_check.isChecked()),
            "default_start_page": default_start,
            "default_end_page": default_end,
            "default_outdir": self.default_outdir_edit.text().strip(),
            "personal_glossaries_by_lang": serialize_glossaries(normalized_glossaries),
            "glossaries_by_lang": serialize_glossaries(normalized_glossaries),
            "enabled_glossary_tiers_by_target_lang": {
                lang: list(normalized_enabled_tiers.get(lang, [1, 2]))
                for lang in supported_target_langs()
            },
            "glossary_seed_version": max(2, int(self._glossary_seed_version)),
            "glossary_file_path": self.glossary_file_edit.text().strip(),
            **self._collect_study_settings_values(),
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

    def reject(self) -> None:
        """Commit any pending cell edit and auto-save glossary before closing."""
        self._commit_glossary_cell_editor()
        timer = getattr(self, "_glossary_auto_save_timer", None)
        if timer is not None:
            timer.stop()
        self._persist_glossary_to_disk()
        super().reject()

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
