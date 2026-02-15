"""PySide6 main window for LegalPDF Translate."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from legalpdf_translate import __version__
from legalpdf_translate.checkpoint import (
    load_run_state,
    parse_effort,
    parse_effort_policy,
    parse_image_mode,
    parse_ocr_engine_policy,
    parse_ocr_mode,
)
from legalpdf_translate.config import OPENAI_MODEL
from legalpdf_translate.joblog_db import job_log_db_path
from legalpdf_translate.metadata_autofill import (
    extract_pdf_header_metadata,
    metadata_config_from_settings,
)
from legalpdf_translate.output_paths import (
    build_output_paths,
    require_writable_output_dir_text,
)
from legalpdf_translate.pdf_text_order import get_page_count
from legalpdf_translate.qt_gui.dialogs import (
    JobLogSeed,
    QtJobLogWindow,
    QtSaveToJobLogDialog,
    QtSettingsDialog,
    build_seed_from_run,
)
from legalpdf_translate.qt_gui.tools_dialogs import QtCalibrationAuditDialog, QtGlossaryBuilderDialog
from legalpdf_translate.qt_gui.styles import apply_primary_glow, apply_soft_shadow
from legalpdf_translate.qt_gui.worker import (
    AnalyzeWorker,
    RebuildDocxWorker,
    TranslationRunWorker,
)
from legalpdf_translate.run_report import build_run_report_markdown
from legalpdf_translate.secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
)
from legalpdf_translate.types import (
    AnalyzeSummary,
    EffortPolicy,
    RunConfig,
    RunSummary,
    TargetLang,
)
from legalpdf_translate.user_settings import (
    app_data_dir,
    load_gui_settings,
    load_joblog_settings,
    save_gui_settings,
    settings_path,
)
from legalpdf_translate.workflow import TranslationWorkflow


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes"}


class _FuturisticCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RootWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.rect()
        if rect.width() <= 1 or rect.height() <= 1:
            return

        base_gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base_gradient.setColorAt(0.0, QColor(1, 9, 24))
        base_gradient.setColorAt(0.45, QColor(3, 20, 46))
        base_gradient.setColorAt(1.0, QColor(2, 10, 28))
        painter.fillRect(rect, base_gradient)

        painter.setPen(Qt.PenStyle.NoPen)
        left_glow = QRadialGradient(rect.width() * 0.18, rect.height() * 0.32, rect.width() * 0.38)
        left_glow.setColorAt(0.0, QColor(20, 158, 214, 68))
        left_glow.setColorAt(1.0, QColor(20, 158, 214, 0))
        painter.setBrush(left_glow)
        painter.drawEllipse(
            int(rect.width() * -0.12),
            int(rect.height() * 0.03),
            int(rect.width() * 0.64),
            int(rect.width() * 0.64),
        )

        right_glow = QRadialGradient(rect.width() * 0.84, rect.height() * 0.78, rect.width() * 0.34)
        right_glow.setColorAt(0.0, QColor(18, 196, 255, 48))
        right_glow.setColorAt(1.0, QColor(18, 196, 255, 0))
        painter.setBrush(right_glow)
        painter.drawEllipse(
            int(rect.width() * 0.56),
            int(rect.height() * 0.52),
            int(rect.width() * 0.52),
            int(rect.width() * 0.52),
        )

        top_bar = QLinearGradient(0.0, 0.0, float(rect.width()), 0.0)
        top_bar.setColorAt(0.0, QColor(20, 154, 204, 46))
        top_bar.setColorAt(0.5, QColor(36, 220, 255, 116))
        top_bar.setColorAt(1.0, QColor(20, 154, 204, 46))
        painter.fillRect(0, 26, rect.width(), 64, top_bar)

        frame_rect = rect.adjusted(16, 96, -16, -18)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        outer_pen = QPen(QColor(51, 205, 255, 124), 2.0)
        painter.setPen(outer_pen)
        painter.drawRoundedRect(frame_rect, 22.0, 22.0)
        inner_pen = QPen(QColor(126, 235, 255, 58), 1.0)
        painter.setPen(inner_pen)
        painter.drawRoundedRect(frame_rect.adjusted(6, 6, -6, -6), 18.0, 18.0)

        accent_pen = QPen(QColor(57, 216, 255, 140), 2.0)
        painter.setPen(accent_pen)
        corner_len = 34
        for left, top in (
            (frame_rect.left() + 16, frame_rect.top() + 16),
            (frame_rect.right() - 16, frame_rect.top() + 16),
            (frame_rect.left() + 16, frame_rect.bottom() - 16),
            (frame_rect.right() - 16, frame_rect.bottom() - 16),
        ):
            dx = corner_len if left < frame_rect.center().x() else -corner_len
            dy = corner_len if top < frame_rect.center().y() else -corner_len
            painter.drawLine(left, top, left + dx, top)
            painter.drawLine(left, top, left, top + dy)

        sweep = QLinearGradient(float(frame_rect.left()), float(frame_rect.top()), float(frame_rect.right()), float(frame_rect.top()))
        sweep.setColorAt(0.0, QColor(57, 216, 255, 0))
        sweep.setColorAt(0.5, QColor(57, 216, 255, 96))
        sweep.setColorAt(1.0, QColor(57, 216, 255, 0))
        painter.fillRect(frame_rect.left() + 24, frame_rect.top() + 18, frame_rect.width() - 48, 2, sweep)
        painter.end()
        super().paintEvent(event)


class QtMainWindow(QMainWindow):
    request_cancel = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LegalPDF Translate")
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMinimumSize(720, 540)
        self._initial_resize_done = False

        self._defaults = load_gui_settings()
        self._worker_thread: QThread | None = None
        self._worker: object | None = None
        self._last_workflow: TranslationWorkflow | None = None
        self._last_summary: RunSummary | None = None
        self._last_output_docx: Path | None = None
        self._last_run_config: RunConfig | None = None
        self._last_run_dir: Path | None = None
        self._last_joblog_seed: JobLogSeed | None = None
        self._last_run_report_path: Path | None = None
        self._joblog_window: QtJobLogWindow | None = None
        self._settings_dialog: QtSettingsDialog | None = None
        self._glossary_builder_dialog: QtGlossaryBuilderDialog | None = None
        self._calibration_dialog: QtCalibrationAuditDialog | None = None
        self._menu_actions: dict[str, QAction] = {}
        self._joblog_db_path = job_log_db_path()
        self._session_started_at = datetime.now()
        self._metadata_logs_dir = app_data_dir() / "logs"
        self._metadata_logs_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_log_file = self._metadata_logs_dir / (
            f"session_{self._session_started_at.strftime('%Y%m%d_%H%M%S')}.log"
        )
        self._busy = False
        self._running = False
        self._can_export_partial = False
        self._last_page_path: str | None = None
        self._progress_done_pages = 0
        self._progress_total_pages = 0
        self._image_pages_seen: set[int] = set()
        self._retry_pages_seen: set[int] = set()
        self._click_debug_enabled = _is_truthy_env(os.getenv("LEGALPDF_QT_CLICK_DEBUG"))
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(250)
        self._settings_save_timer.timeout.connect(self._save_settings)

        self._build_ui()
        self._install_menu()
        self._restore_settings()
        self._set_adv_visible(False)
        self._set_details_visible(False)
        self._refresh_page_count()
        self._update_controls()
        self._refresh_canvas()

    def _build_ui(self) -> None:
        root = _FuturisticCanvas(self)
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 96, 16, 18)
        outer.setSpacing(0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.viewport().setAutoFillBackground(False)
        self._scroll_area.setStyleSheet("QScrollArea{background:transparent;}")
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background:transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(18, 14, 18, 6)
        scroll_layout.setSpacing(0)
        scroll_layout.addStretch(1)

        self.content_card = QFrame(objectName="GlassCard")
        self.content_card.setMaximumWidth(1180)
        self.content_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        apply_soft_shadow(self.content_card, blur_radius=66, offset_y=16)
        scroll_layout.addWidget(self.content_card, 0, Qt.AlignmentFlag.AlignHCenter)
        scroll_layout.addStretch(1)

        self._scroll_area.setWidget(scroll_content)
        outer.addWidget(self._scroll_area, 1)

        card_shell = QVBoxLayout(self.content_card)
        card_shell.setContentsMargins(18, 16, 18, 16)
        card_shell.setSpacing(10)

        self.header_strip = QFrame(objectName="HeaderStrip")
        header = QHBoxLayout(self.header_strip)
        header.setContentsMargins(18, 12, 18, 12)
        header.setSpacing(10)
        self.title_label = QLabel("LegalPDF Translate", objectName="TitleLabel")
        self.header_status_label = QLabel("Idle", objectName="StatusHeaderLabel")
        self.header_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.header_status_label, 0)
        card_shell.addWidget(self.header_strip)

        self.main_card = QFrame(objectName="SurfacePanel")
        main_layout = QVBoxLayout(self.main_card)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.pdf_edit = QLineEdit(placeholderText="Select PDF file...")
        self.pdf_btn = QPushButton("Browse")
        self.pages_label = QLabel("Pages: -", objectName="MutedLabel")
        grid.addWidget(QLabel("PDF"), 0, 0)
        grid.addWidget(self.pdf_edit, 0, 1)
        grid.addWidget(self.pdf_btn, 0, 2)
        grid.addWidget(self.pages_label, 0, 3)

        self.lang_combo = QComboBox(); self.lang_combo.addItems(["EN", "FR", "AR"])
        self.outdir_edit = QLineEdit(placeholderText="Select output folder...")
        self.outdir_btn = QPushButton("Browse")
        grid.addWidget(QLabel("Language"), 1, 0)
        grid.addWidget(self.lang_combo, 1, 1)
        grid.addWidget(QLabel("Output Folder"), 2, 0)
        grid.addWidget(self.outdir_edit, 2, 1)
        grid.addWidget(self.outdir_btn, 2, 2)

        self.show_adv = QCheckBox("Show Advanced")
        self.settings_btn = QPushButton("Settings...")
        self.glossary_builder_btn = QPushButton("Glossary Builder...")
        self.calibration_audit_btn = QPushButton("Calibration Audit...")
        grid.addWidget(self.show_adv, 3, 0, 1, 2)
        tools_row = QWidget()
        tools_row_layout = QHBoxLayout(tools_row)
        tools_row_layout.setContentsMargins(0, 0, 0, 0)
        tools_row_layout.setSpacing(8)
        tools_row_layout.addWidget(self.glossary_builder_btn)
        tools_row_layout.addWidget(self.calibration_audit_btn)
        tools_row_layout.addWidget(self.settings_btn)
        grid.addWidget(tools_row, 3, 2, 1, 2, Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(grid)

        self.adv_frame = QFrame(objectName="SurfacePanel")
        adv = QFormLayout(self.adv_frame)
        adv.setContentsMargins(10, 10, 10, 10)
        adv.setHorizontalSpacing(12)
        adv.setVerticalSpacing(10)
        self.effort_policy_combo = QComboBox(); self.effort_policy_combo.addItems(["adaptive", "fixed_high", "fixed_xhigh"])
        self.effort_combo = QComboBox(); self.effort_combo.addItems(["high", "xhigh"])
        self.images_combo = QComboBox(); self.images_combo.addItems(["off", "auto", "always"])
        self.ocr_mode_combo = QComboBox(); self.ocr_mode_combo.addItems(["off", "auto", "always"])
        self.ocr_engine_combo = QComboBox(); self.ocr_engine_combo.addItems(["local", "local_then_api", "api"])
        self.start_edit = QLineEdit("1")
        self.end_edit = QLineEdit("")
        self.max_edit = QLineEdit("")
        self.workers_spin = QSpinBox(); self.workers_spin.setRange(1, 6)
        self.resume_check = QCheckBox("Resume")
        self.breaks_check = QCheckBox("Insert page breaks")
        self.keep_check = QCheckBox("Keep intermediates")
        self.context_file_edit = QLineEdit(placeholderText="Optional context file...")
        self.context_btn = QPushButton("Browse")
        cf = QWidget(); cfl = QHBoxLayout(cf); cfl.setContentsMargins(0, 0, 0, 0); cfl.setSpacing(8); cfl.addWidget(self.context_file_edit); cfl.addWidget(self.context_btn)
        self.context_text = QPlainTextEdit(); self.context_text.setFixedHeight(90); self.context_text.setPlaceholderText("Optional context text...")
        self.analyze_btn = QPushButton("Analyze")
        toggles = QWidget(); tl = QHBoxLayout(toggles); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(12); tl.addWidget(self.resume_check); tl.addWidget(self.breaks_check); tl.addWidget(self.keep_check); tl.addStretch(1)
        adv.addRow("Effort policy", self.effort_policy_combo)
        adv.addRow("Reasoning effort", self.effort_combo)
        adv.addRow("Image mode", self.images_combo)
        adv.addRow("OCR mode", self.ocr_mode_combo)
        adv.addRow("OCR engine", self.ocr_engine_combo)
        adv.addRow("Start page", self.start_edit)
        adv.addRow("End page", self.end_edit)
        adv.addRow("Max pages", self.max_edit)
        adv.addRow("Parallel workers", self.workers_spin)
        adv.addRow("Run options", toggles)
        adv.addRow("Context file", cf)
        adv.addRow("Context text", self.context_text)
        adv.addRow("", self.analyze_btn)
        main_layout.addWidget(self.adv_frame)
        card_shell.addWidget(self.main_card)

        self.details_card = QFrame(objectName="SurfacePanel")
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(10, 8, 10, 10)
        self.details_btn = QToolButton(objectName="DisclosureButton")
        self.details_btn.setCheckable(True)
        self.details_btn.setChecked(False)
        self.details_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.details_btn.setText("Show details")
        self.log_text = QPlainTextEdit(readOnly=True)
        self.log_text.setVisible(False)
        self.log_text.setMaximumBlockCount(5000)
        details_layout.addWidget(self.details_btn)
        details_layout.addWidget(self.log_text)
        card_shell.addWidget(self.details_card)

        self.footer_card = QFrame(objectName="SurfacePanel")
        self.footer_card.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        footer = QVBoxLayout(self.footer_card)
        footer.setContentsMargins(14, 10, 14, 10)
        footer.setSpacing(10)
        fp = QHBoxLayout(); fp.addWidget(QLabel("Final DOCX")); self.final_docx_edit = QLineEdit(readOnly=True); fp.addWidget(self.final_docx_edit, 1); footer.addLayout(fp)
        pr = QHBoxLayout(); self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0); self.page_label = QLabel("Page: -/-", objectName="MutedLabel"); pr.addWidget(self.progress, 1); pr.addWidget(self.page_label); footer.addLayout(pr)
        self.status_label = QLabel("Idle", objectName="PathLabel")
        self.live_counters_label = QLabel("Done 0/0 | Images 0 | Retries 0", objectName="MutedLabel")
        footer.addWidget(self.status_label)
        footer.addWidget(self.live_counters_label)

        self.translate_btn = QPushButton("Translate", objectName="PrimaryButton")
        self.cancel_btn = QPushButton("Cancel", objectName="DangerButton")
        self.new_btn = QPushButton("New Run")
        self.partial_btn = QPushButton("Export partial DOCX")
        self.rebuild_btn = QPushButton("Rebuild DOCX")
        self.open_btn = QPushButton("Open output folder")
        self.report_btn = QPushButton("Export Run Report")
        self.save_joblog_btn = QPushButton("Save to Job Log")
        self.open_joblog_btn = QPushButton("Job Log")

        btn_grid = QGridLayout()
        btn_grid.setSpacing(8)
        row0 = [self.translate_btn, self.cancel_btn, self.new_btn,
                self.partial_btn, self.rebuild_btn]
        row1 = [self.open_btn, self.report_btn, self.save_joblog_btn,
                self.open_joblog_btn]
        for col, btn in enumerate(row0):
            btn.setToolTip(btn.text())
            btn_grid.addWidget(btn, 0, col)
        for col, btn in enumerate(row1):
            btn.setToolTip(btn.text())
            btn_grid.addWidget(btn, 1, col)
        btn_grid.setColumnStretch(len(row0), 1)
        footer.addLayout(btn_grid)
        card_shell.addWidget(self.footer_card)

        apply_primary_glow(self.translate_btn, blur_radius=28)

        self.pdf_btn.clicked.connect(self._pick_pdf)
        self.outdir_btn.clicked.connect(self._pick_outdir)
        self.context_btn.clicked.connect(self._pick_context)
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        self.glossary_builder_btn.clicked.connect(self._open_glossary_builder_dialog)
        self.calibration_audit_btn.clicked.connect(self._open_calibration_audit_dialog)
        self.show_adv.toggled.connect(self._set_adv_visible)
        self.details_btn.toggled.connect(self._set_details_visible)
        self.translate_btn.clicked.connect(self._start)
        self.analyze_btn.clicked.connect(self._start_analyze)
        self.cancel_btn.clicked.connect(self._cancel)
        self.new_btn.clicked.connect(self._new_run)
        self.partial_btn.clicked.connect(self._export_partial)
        self.rebuild_btn.clicked.connect(self._start_rebuild_docx)
        self.open_btn.clicked.connect(self._open_output_folder)
        self.report_btn.clicked.connect(self._open_run_report)
        self.save_joblog_btn.clicked.connect(self._open_save_to_joblog_dialog)
        self.open_joblog_btn.clicked.connect(self._open_joblog_window)

        self.request_cancel.connect(self._dispatch_cancel)
        self.pdf_edit.textChanged.connect(self._on_form_changed)
        self.lang_combo.currentTextChanged.connect(self._on_form_changed)
        self.outdir_edit.textChanged.connect(self._on_form_changed)
        self.effort_combo.currentTextChanged.connect(self._on_form_changed)
        self.effort_policy_combo.currentTextChanged.connect(self._on_form_changed)
        self.images_combo.currentTextChanged.connect(self._on_form_changed)
        self.ocr_mode_combo.currentTextChanged.connect(self._on_form_changed)
        self.ocr_engine_combo.currentTextChanged.connect(self._on_form_changed)
        self.start_edit.textChanged.connect(self._on_form_changed)
        self.end_edit.textChanged.connect(self._on_form_changed)
        self.max_edit.textChanged.connect(self._on_form_changed)
        self.workers_spin.valueChanged.connect(self._on_form_changed)
        self.resume_check.toggled.connect(self._on_form_changed)
        self.breaks_check.toggled.connect(self._on_form_changed)
        self.keep_check.toggled.connect(self._on_form_changed)

        self._set_adv_visible(False)
        self._set_details_visible(False)
        self._refresh_canvas()

    def _restore_settings(self) -> None:
        defaults = self._defaults
        outdir = str(defaults.get("last_outdir", defaults.get("default_outdir", "")) or "").strip()
        self.outdir_edit.setText(outdir)

        lang = str(defaults.get("last_lang", defaults.get("default_lang", "EN")) or "EN").strip().upper()
        if lang not in {"EN", "FR", "AR"}:
            lang = "EN"
        self.lang_combo.setCurrentText(lang)
        self.effort_combo.setCurrentText(str(defaults.get("effort", defaults.get("default_effort", "high")) or "high"))
        self.effort_policy_combo.setCurrentText(
            str(defaults.get("effort_policy", defaults.get("default_effort_policy", "adaptive")) or "adaptive")
        )
        self.images_combo.setCurrentText(str(defaults.get("image_mode", defaults.get("default_images_mode", "off")) or "off"))
        self.ocr_mode_combo.setCurrentText(str(defaults.get("ocr_mode", defaults.get("ocr_mode_default", "auto")) or "auto"))
        self.ocr_engine_combo.setCurrentText(
            str(defaults.get("ocr_engine", defaults.get("ocr_engine_default", "local_then_api")) or "local_then_api")
        )

        start_page = defaults.get("start_page", defaults.get("default_start_page", 1))
        end_page = defaults.get("end_page", defaults.get("default_end_page", None))
        max_pages = defaults.get("max_pages", None)
        self.start_edit.setText(str(start_page if isinstance(start_page, int) and start_page > 0 else 1))
        self.end_edit.setText("" if end_page in (None, "") else str(end_page))
        self.max_edit.setText("" if max_pages in (None, "") else str(max_pages))

        workers_value = defaults.get("workers", defaults.get("default_workers", 3))
        try:
            workers = int(workers_value)  # type: ignore[arg-type]
        except Exception:
            workers = 3
        self.workers_spin.setValue(max(1, min(6, workers)))

        self.resume_check.setChecked(bool(defaults.get("resume", defaults.get("default_resume", True))))
        self.breaks_check.setChecked(bool(defaults.get("page_breaks", defaults.get("default_page_breaks", True))))
        self.keep_check.setChecked(bool(defaults.get("keep_intermediates", defaults.get("default_keep_intermediates", True))))

    def _save_settings(self) -> None:
        timer = getattr(self, "_settings_save_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

        def opt_int(text: str) -> int | None:
            cleaned = text.strip()
            if cleaned == "":
                return None
            try:
                return int(cleaned)
            except ValueError:
                return None

        start_text = self.start_edit.text().strip() or "1"
        try:
            start_page = int(start_text)
        except ValueError:
            start_page = 1
        if start_page <= 0:
            start_page = 1

        values = {
            "last_outdir": self.outdir_edit.text().strip(),
            "last_lang": self.lang_combo.currentText().strip().upper(),
            "effort": self.effort_combo.currentText().strip().lower(),
            "effort_policy": self.effort_policy_combo.currentText().strip().lower(),
            "image_mode": self.images_combo.currentText().strip().lower(),
            "ocr_mode": self.ocr_mode_combo.currentText().strip().lower(),
            "ocr_engine": self.ocr_engine_combo.currentText().strip().lower(),
            "start_page": start_page,
            "end_page": opt_int(self.end_edit.text()),
            "max_pages": opt_int(self.max_edit.text()),
            "workers": max(1, min(6, int(self.workers_spin.value()))),
            "resume": self.resume_check.isChecked(),
            "page_breaks": self.breaks_check.isChecked(),
            "keep_intermediates": self.keep_check.isChecked(),
        }
        try:
            save_gui_settings(values)
            self._defaults.update(values)
        except Exception:
            pass

    def _install_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_new = file_menu.addAction("New Run")
        file_new.triggered.connect(self._new_run)
        file_open = file_menu.addAction("Open Output Folder")
        file_open.triggered.connect(self._open_output_folder)
        file_export = file_menu.addAction("Export Partial DOCX")
        file_export.triggered.connect(self._export_partial)
        file_menu.addSeparator()
        file_exit = file_menu.addAction("Exit")
        file_exit.triggered.connect(self.close)

        tools_menu = menu_bar.addMenu("Tools")
        tools_settings = tools_menu.addAction("Settings...")
        tools_settings.triggered.connect(self._open_settings_dialog)
        tools_menu.addSeparator()
        tools_glossary_builder = tools_menu.addAction("Glossary Builder...")
        tools_glossary_builder.triggered.connect(self._open_glossary_builder_dialog)
        tools_calibration_audit = tools_menu.addAction("Calibration Audit...")
        tools_calibration_audit.triggered.connect(self._open_calibration_audit_dialog)
        tools_menu.addSeparator()
        tools_test = tools_menu.addAction("Test API Keys...")
        tools_test.triggered.connect(self._test_api_keys)
        clear_menu = tools_menu.addMenu("Clear Stored Keys...")
        clear_openai = clear_menu.addAction("OpenAI key")
        clear_openai.triggered.connect(self._clear_openai_key)
        clear_ocr = clear_menu.addAction("OCR key")
        clear_ocr.triggered.connect(self._clear_ocr_key)
        clear_both = clear_menu.addAction("Both")
        clear_both.triggered.connect(self._clear_all_keys)

        help_menu = menu_bar.addMenu("Help")
        help_about = help_menu.addAction("About")
        help_about.triggered.connect(self._show_about)
        help_logs = help_menu.addAction("Open Logs Folder")
        help_logs.triggered.connect(self._open_logs_folder)
        help_how = help_menu.addAction("How it works")
        help_how.triggered.connect(self._show_how_it_works)

        self._menu_actions = {
            "new_run": file_new,
            "open_output_folder": file_open,
            "export_partial": file_export,
            "settings": tools_settings,
            "glossary_builder": tools_glossary_builder,
            "calibration_audit": tools_calibration_audit,
            "test_api_keys": tools_test,
            "about": help_about,
            "open_logs": help_logs,
            "how_it_works": help_how,
        }

    def _set_menu_enabled(self, key: str, enabled: bool) -> None:
        action = self._menu_actions.get(key)
        if action is not None:
            action.setEnabled(enabled)

    def _clear_openai_key(self) -> None:
        try:
            delete_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Credential Manager", str(exc))
            return
        QMessageBox.information(self, "Credential Manager", "Stored OpenAI key cleared.")

    def _clear_ocr_key(self) -> None:
        try:
            delete_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Credential Manager", str(exc))
            return
        QMessageBox.information(self, "Credential Manager", "Stored OCR key cleared.")

    def _clear_all_keys(self) -> None:
        try:
            delete_openai_key()
            delete_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Credential Manager", str(exc))
            return
        QMessageBox.information(self, "Credential Manager", "Stored OpenAI and OCR keys cleared.")

    def _test_api_keys(self) -> None:
        lines: list[str] = []
        try:
            openai_key = get_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "API Key Test", str(exc))
            return
        if not openai_key:
            lines.append("OpenAI: missing key")
        else:
            started = time.perf_counter()
            try:
                client = OpenAI(api_key=openai_key)
                client.responses.create(
                    model=OPENAI_MODEL,
                    input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                    max_output_tokens=8,
                    store=False,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                lines.append(f"OpenAI: PASS ({latency_ms} ms)")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"OpenAI: FAIL ({type(exc).__name__})")

        try:
            ocr_key = get_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "API Key Test", str(exc))
            return
        if not ocr_key:
            lines.append("OCR API: missing key")
        else:
            ocr_base_url = str(self._defaults.get("ocr_api_base_url", "") or "").strip()
            ocr_model = str(self._defaults.get("ocr_api_model", "") or "").strip() or "gpt-4o-mini"
            if ocr_base_url == "":
                lines.append("OCR API: key present (base URL not set)")
            else:
                started = time.perf_counter()
                try:
                    client = OpenAI(api_key=ocr_key, base_url=ocr_base_url)
                    client.responses.create(
                        model=ocr_model,
                        input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                        max_output_tokens=8,
                        store=False,
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    lines.append(f"OCR API: PASS ({latency_ms} ms)")
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"OCR API: FAIL ({type(exc).__name__})")

        QMessageBox.information(self, "API Key Test", "\n".join(lines))

    def _show_about(self) -> None:
        build_date = datetime.fromtimestamp(Path(__file__).stat().st_mtime).strftime("%Y-%m-%d")
        QMessageBox.information(
            self,
            "About",
            f"LegalPDF Translate\nVersion: {__version__}\nBuild date: {build_date}",
        )

    def _open_logs_folder(self) -> None:
        self._metadata_logs_dir.mkdir(parents=True, exist_ok=True)
        target = self._metadata_logs_dir.expanduser().resolve()
        try:
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open logs folder", str(exc))

    def _show_how_it_works(self) -> None:
        lines = [
            "1) The app processes selected pages one by one.",
            "2) It reuses checkpoints so runs can resume safely.",
            "3) OCR is used when text is missing or poor.",
            "4) Translation is validated before page acceptance.",
            "5) Cancellation is cooperative between pages.",
            "6) Partial DOCX export is available after progress.",
            "7) Logs store metadata only, not translated content.",
            "8) API keys are stored securely in Credential Manager.",
            "9) New Run clears runtime state without app restart.",
        ]
        QMessageBox.information(self, "How it works", "\n".join(lines))

    def collect_debug_bundle_metadata_paths(self) -> list[Path]:
        paths: list[Path] = []
        settings_file = settings_path()
        if settings_file.exists():
            paths.append(settings_file)
        if self._metadata_log_file.exists():
            paths.append(self._metadata_log_file)
        if self._last_summary is not None:
            run_state_path = self._last_summary.run_dir / "run_state.json"
            if run_state_path.exists():
                paths.append(run_state_path)
            run_events_path = self._last_summary.run_dir / "run_events.jsonl"
            if run_events_path.exists():
                paths.append(run_events_path)
        if self._last_run_config is not None:
            run_paths = build_output_paths(
                self._last_run_config.output_dir,
                self._last_run_config.pdf_path,
                self._last_run_config.target_lang,
            )
            if run_paths.run_state_path.exists():
                paths.append(run_paths.run_state_path)
        return paths

    def apply_settings_from_dialog(self, values: dict[str, object], persist: bool) -> None:
        self._defaults.update(values)
        if persist:
            save_gui_settings(values)
            self._defaults = load_gui_settings()

        self.lang_combo.setCurrentText(str(self._defaults.get("default_lang", "EN")))
        self.effort_combo.setCurrentText(str(self._defaults.get("default_effort", "high")))
        self.effort_policy_combo.setCurrentText(str(self._defaults.get("default_effort_policy", "adaptive")))
        self.images_combo.setCurrentText(str(self._defaults.get("default_images_mode", "off")))
        self.resume_check.setChecked(bool(self._defaults.get("default_resume", True)))
        self.keep_check.setChecked(bool(self._defaults.get("default_keep_intermediates", True)))
        self.breaks_check.setChecked(bool(self._defaults.get("default_page_breaks", True)))
        self.start_edit.setText(str(self._defaults.get("default_start_page", 1)))
        default_end = self._defaults.get("default_end_page")
        self.end_edit.setText("" if default_end in (None, "") else str(default_end))
        try:
            default_workers = int(self._defaults.get("default_workers", 3))
        except (TypeError, ValueError):
            default_workers = 3
        self.workers_spin.setValue(max(1, min(6, default_workers)))
        default_outdir = str(self._defaults.get("default_outdir", "") or "")
        if default_outdir and not self.outdir_edit.text().strip():
            self.outdir_edit.setText(default_outdir)
        self.ocr_mode_combo.setCurrentText(str(self._defaults.get("ocr_mode_default", "auto")))
        self.ocr_engine_combo.setCurrentText(str(self._defaults.get("ocr_engine_default", "local_then_api")))
        self._update_controls()

    def _open_settings_dialog(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return

        current_pdf_path: Path | None = None
        pdf_text = self.pdf_edit.text().strip()
        if pdf_text:
            candidate = Path(pdf_text).expanduser().resolve()
            if candidate.exists() and candidate.is_file():
                current_pdf_path = candidate

        dialog = QtSettingsDialog(
            parent=self,
            settings=self._defaults,
            apply_callback=self.apply_settings_from_dialog,
            collect_debug_paths=self.collect_debug_bundle_metadata_paths,
            current_pdf_path=current_pdf_path,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_settings_dialog", None))
        self._settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _apply_aux_settings(self, values: dict[str, object]) -> None:
        save_gui_settings(values)
        self._defaults = load_gui_settings()
        self._update_controls()

    def _current_pdf_path_for_tools(self) -> Path | None:
        pdf_text = self.pdf_edit.text().strip()
        if pdf_text == "":
            return None
        candidate = Path(pdf_text).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            return None
        return candidate

    def _current_output_dir_for_tools(self) -> Path | None:
        out_text = self.outdir_edit.text().strip()
        if out_text == "":
            return None
        candidate = Path(out_text).expanduser().resolve()
        if not candidate.exists() or not candidate.is_dir():
            return None
        return candidate

    def _open_glossary_builder_dialog(self) -> None:
        if self._glossary_builder_dialog is not None and self._glossary_builder_dialog.isVisible():
            self._glossary_builder_dialog.raise_()
            self._glossary_builder_dialog.activateWindow()
            return
        dialog = QtGlossaryBuilderDialog(
            parent=self,
            settings=self._defaults,
            current_pdf_path=self._current_pdf_path_for_tools(),
            current_output_dir=self._current_output_dir_for_tools(),
            default_target_lang=self.lang_combo.currentText().strip().upper(),
            save_settings_callback=self._apply_aux_settings,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_glossary_builder_dialog", None))
        self._glossary_builder_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_calibration_audit_dialog(self) -> None:
        if self._calibration_dialog is not None and self._calibration_dialog.isVisible():
            self._calibration_dialog.raise_()
            self._calibration_dialog.activateWindow()
            return
        dialog = QtCalibrationAuditDialog(
            parent=self,
            settings=self._defaults,
            build_config_callback=self._build_config,
            save_settings_callback=self._apply_aux_settings,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_calibration_dialog", None))
        self._calibration_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _set_details_visible(self, visible: bool) -> None:
        self.log_text.setVisible(visible)
        self.details_btn.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.details_btn.setText("Hide details" if visible else "Show details")
        self._refresh_canvas()

    def _set_adv_visible(self, visible: bool) -> None:
        self.adv_frame.setVisible(visible)
        self._refresh_canvas()

    def _on_form_changed(self) -> None:
        self._schedule_save_settings()
        self._refresh_page_count()
        self._update_controls()

    def _schedule_save_settings(self) -> None:
        self._settings_save_timer.start()

    def _refresh_canvas(self) -> None:
        central = self.centralWidget()
        if central is not None:
            central.update()

    def _refresh_page_count(self) -> None:
        pdf_text = self.pdf_edit.text().strip()
        if pdf_text == self._last_page_path:
            return
        self._last_page_path = pdf_text
        if not pdf_text:
            self.pages_label.setText("Pages: -")
            return
        pdf_path = Path(pdf_text).expanduser().resolve()
        if not pdf_path.exists() or not pdf_path.is_file():
            self.pages_label.setText("Pages: -")
            return
        try:
            self.pages_label.setText(f"Pages: {get_page_count(pdf_path)}")
        except Exception:
            self.pages_label.setText("Pages: ?")
    def _pick_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf);;All Files (*.*)")
        if path:
            self.pdf_edit.setText(path)

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self.outdir_edit.setText(path)

    def _pick_context(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select context file", "", "Text Files (*.txt);;All Files (*.*)")
        if path:
            self.context_file_edit.setText(path)

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{stamp}] {message}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        if bool(self._defaults.get("diagnostics_verbose_metadata_logs", False)):
            try:
                self._metadata_log_file.parent.mkdir(parents=True, exist_ok=True)
                with self._metadata_log_file.open("a", encoding="utf-8") as fh:
                    fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
            except Exception:
                pass

    def _reset_live_counters(self) -> None:
        self._progress_done_pages = 0
        self._progress_total_pages = 0
        self._image_pages_seen.clear()
        self._retry_pages_seen.clear()
        self._update_live_counters()

    def _update_live_counters(self) -> None:
        self.live_counters_label.setText(
            "Done "
            f"{self._progress_done_pages}/{self._progress_total_pages} | "
            f"Images {len(self._image_pages_seen)} | Retries {len(self._retry_pages_seen)}"
        )

    def _warn_fixed_xhigh_for_enfr(self) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Cost/Time warning")
        dialog.setText("xhigh can multiply cost and time; recommended: adaptive or high.")
        proceed_btn = dialog.addButton("Proceed", QMessageBox.ButtonRole.AcceptRole)
        switch_btn = dialog.addButton("Switch to adaptive", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is proceed_btn:
            return "proceed"
        if clicked is switch_btn:
            return "switch"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"

    def _build_config(self) -> RunConfig:
        pdf_text = self.pdf_edit.text().strip()
        outdir_text = self.outdir_edit.text().strip()
        if not pdf_text:
            raise ValueError("PDF path is required.")
        if not outdir_text:
            raise ValueError("Output folder is required.")
        pdf = Path(pdf_text).expanduser().resolve()
        outdir = require_writable_output_dir_text(outdir_text)

        def opt_int(value: str, field: str) -> int | None:
            v = value.strip()
            if not v:
                return None
            try:
                return int(v)
            except ValueError as exc:
                raise ValueError(f"{field} must be an integer.") from exc

        start_text = self.start_edit.text().strip() or "1"
        try:
            start_page = int(start_text)
        except ValueError as exc:
            raise ValueError("Start page must be an integer.") from exc

        context_file_text = self.context_file_edit.text().strip()
        context_file = Path(context_file_text).expanduser().resolve() if context_file_text else None
        glossary_file_text = str(self._defaults.get("glossary_file_path", "") or "").strip()
        glossary_file = Path(glossary_file_text).expanduser().resolve() if glossary_file_text else None

        return RunConfig(
            pdf_path=pdf,
            output_dir=outdir,
            target_lang=TargetLang(self.lang_combo.currentText().strip().upper()),
            effort=parse_effort(self.effort_combo.currentText()),
            effort_policy=parse_effort_policy(self.effort_policy_combo.currentText()),
            allow_xhigh_escalation=bool(self._defaults.get("allow_xhigh_escalation", False)),
            image_mode=parse_image_mode(self.images_combo.currentText()),
            start_page=start_page,
            end_page=opt_int(self.end_edit.text(), "End page"),
            max_pages=opt_int(self.max_edit.text(), "Max pages"),
            workers=max(1, min(6, int(self.workers_spin.value()))),
            resume=self.resume_check.isChecked(),
            page_breaks=self.breaks_check.isChecked(),
            keep_intermediates=self.keep_check.isChecked(),
            ocr_mode=parse_ocr_mode(self.ocr_mode_combo.currentText()),
            ocr_engine=parse_ocr_engine_policy(self.ocr_engine_combo.currentText()),
            ocr_api_base_url=str(self._defaults.get("ocr_api_base_url", "") or "") or None,
            ocr_api_model=str(self._defaults.get("ocr_api_model", "") or "") or None,
            ocr_api_key_env_name=str(self._defaults.get("ocr_api_key_env_name", "DEEPSEEK_API_KEY") or "DEEPSEEK_API_KEY"),
            context_file=context_file,
            context_text=self.context_text.toPlainText().strip() or None,
            glossary_file=glossary_file,
            diagnostics_admin_mode=bool(self._defaults.get("diagnostics_admin_mode", True)),
            diagnostics_include_sanitized_snippets=bool(
                self._defaults.get("diagnostics_include_sanitized_snippets", False)
            ),
        )

    def _can_start(self) -> bool:
        if self._busy:
            return False
        pdf = self.pdf_edit.text().strip()
        outdir = self.outdir_edit.text().strip()
        if not pdf or not outdir:
            return False
        p = Path(pdf).expanduser().resolve()
        if not p.exists() or not p.is_file():
            return False
        try:
            require_writable_output_dir_text(outdir)
        except ValueError:
            return False
        return True

    def _rebuild_pages_dir(self) -> Path | None:
        pdf_text = self.pdf_edit.text().strip()
        outdir_text = self.outdir_edit.text().strip()
        if not pdf_text or not outdir_text:
            return None

        outdir = Path(outdir_text).expanduser().resolve()
        if not outdir.exists() or not outdir.is_dir():
            return None
        pdf = Path(pdf_text).expanduser().resolve()
        try:
            lang = TargetLang(self.lang_combo.currentText().strip())
        except ValueError:
            return None

        paths = build_output_paths(outdir, pdf, lang)
        state = load_run_state(paths.run_state_path)
        if state is not None and state.run_dir_abs:
            run_dir = Path(state.run_dir_abs).expanduser().resolve()
            return run_dir / "pages"
        return paths.pages_dir

    def _has_rebuildable_pages(self) -> bool:
        pages_dir = self._rebuild_pages_dir()
        if pages_dir is None or not pages_dir.exists():
            return False
        return any(pages_dir.glob("page_*.txt"))

    def _update_controls(self) -> None:
        can_start = self._can_start()
        self.translate_btn.setEnabled(can_start)
        self.analyze_btn.setEnabled(can_start and not self._busy)
        self.cancel_btn.setEnabled(self._running)
        self.new_btn.setEnabled(not self._busy)
        self.partial_btn.setEnabled((not self._busy) and self._can_export_partial and self._last_workflow is not None)
        self.rebuild_btn.setEnabled((not self._busy) and self._has_rebuildable_pages())
        can_open = (
            (not self._busy)
            and self._last_output_docx is not None
            and self._last_output_docx.exists()
            and self._last_output_docx.stat().st_size > 0
        )
        self.open_btn.setEnabled(can_open)
        can_report = False
        if self._running:
            can_report = self._resolve_report_run_dir() is not None
        elif not self._busy:
            can_report = self._resolve_report_run_dir() is not None
        self.report_btn.setEnabled(can_report)
        self.save_joblog_btn.setEnabled((not self._busy) and (self._last_joblog_seed is not None))
        self.open_joblog_btn.setEnabled(not self._busy)

        self._set_menu_enabled("open_output_folder", can_open)
        self._set_menu_enabled("export_partial", (not self._busy) and self._can_export_partial)
        self._set_menu_enabled("glossary_builder", not self._busy)
        self._set_menu_enabled("calibration_audit", not self._busy)

    def _set_busy(self, busy: bool, *, translation: bool) -> None:
        self._busy = busy
        self._running = busy and translation
        for w in (
            self.pdf_edit, self.pdf_btn, self.lang_combo, self.outdir_edit, self.outdir_btn, self.show_adv, self.settings_btn,
            self.glossary_builder_btn, self.calibration_audit_btn,
            self.effort_policy_combo, self.effort_combo, self.images_combo, self.ocr_mode_combo, self.ocr_engine_combo,
            self.start_edit, self.end_edit, self.max_edit, self.workers_spin,
            self.resume_check, self.breaks_check, self.keep_check,
            self.context_file_edit, self.context_btn, self.context_text,
        ):
            w.setEnabled(not busy)
        self._update_controls()

    def _start(self) -> None:
        if self._busy:
            return
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        if (
            config.target_lang in (TargetLang.EN, TargetLang.FR)
            and config.effort_policy == EffortPolicy.FIXED_XHIGH
        ):
            decision = self._warn_fixed_xhigh_for_enfr()
            if decision == "switch":
                self.effort_policy_combo.setCurrentText("adaptive")
                try:
                    config = self._build_config()
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.critical(self, "Invalid configuration", str(exc))
                    return
            elif decision != "proceed":
                return

        self._save_settings()
        self._last_summary = None
        self._last_run_report_path = None
        self._last_run_dir = build_output_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir
        self._last_output_docx = None
        self._last_run_config = config
        self._last_joblog_seed = None
        self._last_workflow = None
        self._can_export_partial = False
        self.final_docx_edit.clear()
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self.status_label.setText("Starting...")
        self.header_status_label.setText("Starting...")
        self._reset_live_counters()

        max_retries = int(self._defaults.get("perf_max_transport_retries", 4) or 4)
        backoff_cap = float(self._defaults.get("perf_backoff_cap_seconds", 12.0) or 12.0)

        thread = QThread(self)
        worker = TranslationRunWorker(
            config=config,
            max_transport_retries=max_retries,
            backoff_cap_seconds=backoff_cap,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)
        self.request_cancel.connect(worker.cancel, Qt.ConnectionType.QueuedConnection)

        self._worker_thread = thread
        self._worker = worker
        self._set_busy(True, translation=True)
        thread.start()

    def _start_analyze(self) -> None:
        if self._busy:
            return
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        self._save_settings()
        self._last_summary = None
        self._last_run_report_path = None
        self._last_output_docx = None
        self._last_joblog_seed = None
        self.status_label.setText("Analyzing...")
        self.header_status_label.setText("Analyzing...")
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self._reset_live_counters()

        thread = QThread(self)
        worker = AnalyzeWorker(config=config)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_analyze_finished)
        worker.error.connect(self._on_analyze_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)

        self._worker_thread = thread
        self._worker = worker
        self._set_busy(True, translation=False)
        thread.start()

    def _on_progress(self, selected_index: int, selected_total: int, real_page: int, status: str, image_used: bool, retry_used: bool) -> None:
        if selected_total > 0:
            self.progress.setValue(max(0, min(100, int((float(selected_index) / float(selected_total)) * 100.0))))
        self._progress_done_pages = max(0, int(selected_index))
        self._progress_total_pages = max(0, int(selected_total))
        if real_page > 0:
            extra = []
            if image_used:
                extra.append("image")
                self._image_pages_seen.add(real_page)
            if retry_used:
                extra.append("retry")
                self._retry_pages_seen.add(real_page)
            suffix = f" [{', '.join(extra)}]" if extra else ""
            self.page_label.setText(f"Page {real_page} ({selected_index}/{selected_total}){suffix}")
        else:
            self.page_label.setText(f"Progress: {selected_index}/{selected_total}")
        self._update_live_counters()
        self.status_label.setText(status)
        self.header_status_label.setText(status)

    def _on_finished(self, summary_obj: object) -> None:
        summary = summary_obj if isinstance(summary_obj, RunSummary) else None
        if self._worker is not None and hasattr(self._worker, "workflow"):
            self._last_workflow = getattr(self._worker, "workflow")
        self._set_busy(False, translation=False)
        if summary is None:
            self.status_label.setText("Run finished with invalid summary")
            self.header_status_label.setText("Error")
            self._last_joblog_seed = None
            return
        self._last_summary = summary
        self._last_run_dir = summary.run_dir
        self._last_run_report_path = summary.run_summary_path
        if summary.success and summary.output_docx is not None:
            output = summary.output_docx.expanduser().resolve()
            self._last_output_docx = output
            self.final_docx_edit.setText(str(output))
            self.status_label.setText("Completed")
            self.header_status_label.setText("Completed")
            self._append_log(f"Saved DOCX: {output}")
            if summary.run_summary_path is not None:
                self._append_log(f"Run report: {summary.run_summary_path}")
            self._prepare_joblog_seed(summary)
            self._show_saved_docx_dialog("Translation complete")
            self._open_save_to_joblog_dialog()
        else:
            self._last_output_docx = None
            self._last_joblog_seed = None
            self._append_log(f"Run failed: {summary.error}; failed_page={summary.failed_page}")
            if summary.run_summary_path is not None:
                self._append_log(f"Run report: {summary.run_summary_path}")
            self.status_label.setText(f"Failed ({summary.error})")
            self.header_status_label.setText("Failed")
            if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
                self._append_log(f"DOCX save failed at: {summary.attempted_output_docx}")
            details = f"Run stopped at page {summary.failed_page}. Partial pages: {summary.completed_pages}"
            if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
                details = (
                    f"DOCX save failed at:\n{summary.attempted_output_docx}\n\n"
                    f"Partial pages: {summary.completed_pages}"
                )
            QMessageBox.warning(self, "Translation stopped", details)
        self._progress_done_pages = max(self._progress_done_pages, int(summary.completed_pages))
        self._progress_total_pages = max(self._progress_total_pages, self._progress_done_pages)
        self._update_live_counters()
        self._can_export_partial = summary.completed_pages > 0
        self._update_controls()
    def _on_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self._last_joblog_seed = None
        self.status_label.setText("Error")
        self.header_status_label.setText("Error")
        self._append_log(f"Runtime error: {message}")
        QMessageBox.critical(self, "Runtime error", message)

    def _on_analyze_finished(self, summary_obj: object) -> None:
        self._set_busy(False, translation=False)
        if not isinstance(summary_obj, AnalyzeSummary):
            self.status_label.setText("Analyze failed")
            self.header_status_label.setText("Analyze failed")
            QMessageBox.critical(self, "Analyze failed", "Invalid analyze response.")
            self._update_controls()
            return
        summary = summary_obj
        self.status_label.setText("Analyze complete")
        self.header_status_label.setText("Analyze complete")
        self._append_log(
            "Analyze complete: "
            f"selected_pages={summary.selected_pages_count}, "
            f"would_attach_images={summary.pages_would_attach_images}"
        )
        self._append_log(f"Analyze report: {summary.analyze_report_path}")
        self._progress_done_pages = 0
        self._progress_total_pages = int(summary.selected_pages_count)
        self._update_live_counters()
        QMessageBox.information(
            self,
            "Analyze complete",
            "Analyze-only finished.\n\n"
            f"Selected pages: {summary.selected_pages_count}\n"
            f"Would attach images: {summary.pages_would_attach_images}\n"
            f"Report: {summary.analyze_report_path}",
        )
        self._update_controls()

    def _on_analyze_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self.status_label.setText("Analyze failed")
        self.header_status_label.setText("Analyze failed")
        self._append_log(f"Analyze failed: {message}")
        QMessageBox.critical(self, "Analyze failed", message)

    def _dispatch_cancel(self) -> None:
        if self._worker is None:
            return
        cancel_cb = getattr(self._worker, "cancel", None)
        if callable(cancel_cb):
            cancel_cb()

    def _cancel(self) -> None:
        if self._running:
            self.request_cancel.emit()

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            cancel_cb = getattr(self._worker, "cancel", None)
            if callable(cancel_cb):
                try:
                    self.request_cancel.disconnect(cancel_cb)
                except Exception:
                    pass
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def _new_run(self) -> None:
        if self._busy:
            return
        self._last_summary = None
        self._last_run_report_path = None
        self._last_run_dir = None
        self._last_output_docx = None
        self._last_run_config = None
        self._last_joblog_seed = None
        self._last_workflow = None
        self._worker = None
        self._worker_thread = None
        self._can_export_partial = False
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self.status_label.setText("Idle")
        self.header_status_label.setText("Idle")
        self._reset_live_counters()
        self.final_docx_edit.clear()
        self.log_text.clear()
        self.details_btn.setChecked(False)
        self._set_details_visible(False)
        self._save_settings()
        self._update_controls()

    def _export_partial(self) -> None:
        wf = self._last_workflow
        if wf is None:
            QMessageBox.information(self, "Partial export", "No run context available.")
            return
        try:
            partial = wf.export_partial_docx()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Partial export failed", str(exc))
            return
        if partial is None:
            QMessageBox.information(self, "Partial export", "No completed pages available.")
            return
        self._append_log(f"Partial DOCX exported: {partial}")
        QMessageBox.information(self, "Partial export", f"Exported:\n{partial}")

    def _start_rebuild_docx(self) -> None:
        if self._busy:
            return
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        self._save_settings()
        self._last_summary = None
        self._last_run_config = config
        self._last_joblog_seed = None
        self._set_busy(True, translation=False)
        self.status_label.setText("Rebuilding DOCX...")
        self.header_status_label.setText("Rebuilding DOCX...")

        thread = QThread(self)
        worker = RebuildDocxWorker(config=config)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_rebuild_finished)
        worker.error.connect(self._on_rebuild_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)

        self._worker_thread = thread
        self._worker = worker
        thread.start()

    def _on_rebuild_finished(self, output_obj: object) -> None:
        self._set_busy(False, translation=False)
        if not isinstance(output_obj, Path):
            self.status_label.setText("Rebuild failed")
            self.header_status_label.setText("Rebuild failed")
            QMessageBox.critical(self, "Rebuild failed", "Rebuild returned an invalid output path.")
            return
        output = output_obj.expanduser().resolve()
        self._last_output_docx = output
        self._last_joblog_seed = None
        self.final_docx_edit.setText(str(output))
        self.status_label.setText("Completed")
        self.header_status_label.setText("Completed")
        self._append_log(f"Saved DOCX: {output}")
        self._show_saved_docx_dialog("Rebuild complete")
        self._update_controls()

    def _on_rebuild_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self.status_label.setText("Rebuild failed")
        self.header_status_label.setText("Rebuild failed")
        self._append_log(f"Rebuild failed: {message}")
        QMessageBox.critical(self, "Rebuild failed", message)

    def _open_output_file(self) -> None:
        if self._last_output_docx is None:
            return
        output_path = self._last_output_docx.expanduser().resolve()
        if not output_path.exists():
            QMessageBox.critical(self, "Open file failed", f"Output file not found:\n{output_path}")
            return
        try:
            if os.name == "nt":
                os.startfile(str(output_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_path)])
            else:
                subprocess.Popen(["xdg-open", str(output_path)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open file failed", str(exc))

    def _show_saved_docx_dialog(self, title: str) -> None:
        if self._last_output_docx is None:
            return
        message = f"Saved DOCX:\n{self._last_output_docx}\n\nOpen file now?"
        open_now = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if open_now == QMessageBox.StandardButton.Yes:
            self._open_output_file()

    def _prepare_joblog_seed(self, summary: RunSummary) -> None:
        if self._last_run_config is None:
            self._last_joblog_seed = None
            return

        settings = load_joblog_settings()
        default_rate = settings["default_rate_per_word"].get(self._last_run_config.target_lang.value, 0.0)
        try:
            seed = build_seed_from_run(
                pdf_path=self._last_run_config.pdf_path,
                lang=self._last_run_config.target_lang.value,
                pages_dir=summary.run_dir / "pages",
                completed_pages=summary.completed_pages,
                completed_at=datetime.now().isoformat(timespec="seconds"),
                default_rate_per_word=float(default_rate),
                api_cost=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Job log seed preparation failed: {exc}")
            self._last_joblog_seed = None
            return

        suggestion = extract_pdf_header_metadata(
            seed.pdf_path,
            vocab_cities=list(settings["vocab_cities"]),
            config=metadata_config_from_settings(settings),
            page_number=1,
        )
        if suggestion.case_entity:
            seed.case_entity = suggestion.case_entity
            seed.service_entity = suggestion.case_entity
        if suggestion.case_city:
            seed.case_city = suggestion.case_city
            seed.service_city = suggestion.case_city
        if suggestion.case_number:
            seed.case_number = suggestion.case_number

        self._last_joblog_seed = seed

    def _open_save_to_joblog_dialog(self) -> None:
        if self._last_joblog_seed is None:
            QMessageBox.information(self, "Job Log", "No completed run available to save.")
            return

        def _refresh_after_save() -> None:
            if self._joblog_window is not None and self._joblog_window.isVisible():
                self._joblog_window.refresh_rows()

        dialog = QtSaveToJobLogDialog(
            parent=self,
            db_path=self._joblog_db_path,
            seed=self._last_joblog_seed,
            on_saved=_refresh_after_save,
        )
        dialog.exec()

    def _open_joblog_window(self) -> None:
        if self._joblog_window is not None and self._joblog_window.isVisible():
            self._joblog_window.raise_()
            self._joblog_window.activateWindow()
            return
        window = QtJobLogWindow(parent=self, db_path=self._joblog_db_path)
        window.setModal(False)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda _obj=None: setattr(self, "_joblog_window", None))
        self._joblog_window = window
        window.show()

    def _open_output_folder(self) -> None:
        target: Path | None = None
        if self._last_output_docx is not None:
            out = self._last_output_docx.expanduser().resolve()
            if out.exists():
                target = out
        if target is None:
            outdir_text = self.outdir_edit.text().strip()
            if outdir_text:
                outdir = Path(outdir_text).expanduser().resolve()
                if outdir.exists():
                    target = outdir
        if target is None:
            QMessageBox.information(self, "Open output folder", "No output folder available.")
            return
        try:
            if os.name == "nt":
                if target.is_file():
                    subprocess.Popen(["explorer", f"/select,{target}"])
                else:
                    os.startfile(str(target))  # type: ignore[attr-defined]
            elif target.is_file():
                subprocess.Popen(["xdg-open", str(target.parent)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open output folder", str(exc))

    def _resolve_report_run_dir(self) -> Path | None:
        if self._last_run_dir is not None:
            return self._last_run_dir.expanduser().resolve()
        if self._last_summary is not None:
            return self._last_summary.run_dir.expanduser().resolve()
        if self._last_run_report_path is not None:
            return self._last_run_report_path.expanduser().resolve().parent
        if self._worker is not None and hasattr(self._worker, "workflow"):
            workflow = getattr(self._worker, "workflow", None)
            if workflow is not None and hasattr(workflow, "_last_paths"):
                paths = getattr(workflow, "_last_paths", None)
                run_dir = getattr(paths, "run_dir", None)
                if isinstance(run_dir, Path):
                    return run_dir.expanduser().resolve()
        return None

    def _open_run_report(self) -> None:
        run_dir = self._resolve_report_run_dir()
        if run_dir is None:
            QMessageBox.information(self, "Run report", "No run report available.")
            return
        if not run_dir.exists():
            QMessageBox.information(self, "Run report", f"Run folder is not ready yet:\n{run_dir}")
            return

        admin_mode = bool(self._defaults.get("diagnostics_admin_mode", True))
        include_snippets = (
            admin_mode and bool(self._defaults.get("diagnostics_include_sanitized_snippets", False))
        )
        try:
            report_text = build_run_report_markdown(
                run_dir=run_dir,
                admin_mode=admin_mode,
                include_sanitized_snippets=include_snippets,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Run report", str(exc))
            return

        chooser = QMessageBox(self)
        chooser.setIcon(QMessageBox.Icon.Question)
        chooser.setWindowTitle("Export Run Report")
        chooser.setText("Choose how to export the run report.")
        save_btn = chooser.addButton("Save .md", QMessageBox.ButtonRole.ActionRole)
        copy_btn = chooser.addButton("Copy to clipboard", QMessageBox.ButtonRole.ActionRole)
        chooser.addButton(QMessageBox.StandardButton.Cancel)
        chooser.exec()
        clicked = chooser.clickedButton()

        if clicked is copy_btn:
            QApplication.clipboard().setText(report_text)
            self._append_log("Run report copied to clipboard.")
            QMessageBox.information(self, "Run report", "Run report copied to clipboard.")
            return

        if clicked is not save_btn:
            return

        default_path = run_dir / "run_report.md"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Run Report",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not save_path:
            return
        output_path = Path(save_path).expanduser().resolve()
        try:
            output_path.write_text(report_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Run report", f"Failed to save run report: {exc}")
            return
        self._append_log(f"Run report exported: {output_path}")
        open_choice = QMessageBox.question(
            self,
            "Run report",
            "Open report folder now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if open_choice != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", f"/select,{output_path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_path.parent)])
            else:
                subprocess.Popen(["xdg-open", str(output_path.parent)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Run report", str(exc))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._click_debug_enabled:
            global_point = event.globalPosition().toPoint()
            target = QApplication.widgetAt(global_point)
            if target is None:
                self._append_log("[click-debug] widgetAt=None")
            else:
                object_name = target.objectName().strip() or "-"
                self._append_log(f"[click-debug] widgetAt={target.__class__.__name__} objectName={object_name}")
        super().mousePressEvent(event)

    def _update_card_max_width(self) -> None:
        vp = self._scroll_area.viewport()
        if vp is not None:
            scroll_layout = self._scroll_area.widget().layout()
            lr = scroll_layout.contentsMargins()
            available = vp.width() - lr.left() - lr.right()
            self.content_card.setMaximumWidth(max(600, min(1180, available)))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_card_max_width()
        central = self.centralWidget()
        if central is not None:
            central.update()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._initial_resize_done:
            return
        self._initial_resize_done = True
        screen = self.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = int(avail.width() * 0.92)
            h = int(avail.height() * 0.92)
            self.resize(w, h)
            self.move(
                avail.x() + (avail.width() - w) // 2,
                avail.y() + (avail.height() - h) // 2,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            QMessageBox.warning(self, "Run in progress", "Cancel the active run before closing the app.")
            event.ignore()
            return
        if self._settings_save_timer.isActive():
            self._settings_save_timer.stop()
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.close()
        self._save_settings()
        super().closeEvent(event)
