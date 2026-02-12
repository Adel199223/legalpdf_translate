"""PySide6 main window for LegalPDF Translate."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
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
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..checkpoint import parse_effort, parse_image_mode, parse_ocr_engine_policy, parse_ocr_mode
from ..output_paths import require_writable_output_dir_text
from ..pdf_text_order import get_page_count
from ..resources_loader import get_resources_dir
from ..types import RunConfig, RunSummary, TargetLang
from ..user_settings import load_gui_settings, save_gui_settings
from ..workflow import TranslationWorkflow
from .styles import apply_primary_glow, apply_soft_shadow, make_blur_effect
from .worker import TranslationRunWorker


class _BackgroundWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ui_dir = get_resources_dir() / "ui"
        bg = ui_dir / "bg.png"
        if not bg.exists():
            bg = ui_dir / "ui_bg_tile.png"
        self._bg = QPixmap(str(bg))
        self._left = QPixmap(str(ui_dir / "ui_deco_left.png"))
        self._right = QPixmap(str(ui_dir / "ui_deco_right.png"))
        self._scaled_bg = QPixmap()

        self._glow_left = QLabel(self)
        self._glow_left.setStyleSheet("background-color: rgba(57, 216, 255, 95); border-radius: 160px;")
        self._glow_left.setGraphicsEffect(make_blur_effect(self._glow_left, radius=78))
        self._glow_left.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._glow_right = QLabel(self)
        self._glow_right.setStyleSheet("background-color: rgba(31, 186, 255, 72); border-radius: 180px;")
        self._glow_right.setGraphicsEffect(make_blur_effect(self._glow_right, radius=92))
        self._glow_right.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.width() > 0 and self.height() > 0:
            self._scaled_bg = self._bg.scaled(
                self.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._glow_left.setGeometry(-120, int(self.height() * 0.12), 340, 340)
        self._glow_right.setGeometry(self.width() - 240, int(self.height() * 0.44), 380, 380)

    def sample_background(self, rect: QRect) -> QPixmap:
        if rect.width() <= 0 or rect.height() <= 0 or self._scaled_bg.isNull():
            return QPixmap()
        source_rect = rect.intersected(self.rect())
        if source_rect.isNull():
            return QPixmap()
        sampled = self._scaled_bg.copy(source_rect)
        if source_rect == rect:
            return sampled
        target = QPixmap(rect.size())
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.drawPixmap(source_rect.topLeft() - rect.topLeft(), sampled)
        painter.end()
        return target

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._scaled_bg.isNull():
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
        else:
            painter.drawPixmap(0, 0, self._scaled_bg)
        h = max(180, self.height() - 160)
        w = max(68, min(112, int(self.width() * 0.09)))
        painter.setOpacity(0.45)
        if not self._left.isNull():
            painter.drawPixmap(8, 88, self._left.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if not self._right.isNull():
            painter.drawPixmap(max(8, self.width() - w - 8), 88, self._right.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        painter.setOpacity(1.0)
        painter.fillRect(self.rect(), QColor(3, 9, 24, 72))
        painter.end()
        super().paintEvent(event)


class QtMainWindow(QMainWindow):
    request_cancel = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LegalPDF Translate")
        self.resize(1240, 880)

        self._defaults = load_gui_settings()
        self._worker_thread: QThread | None = None
        self._worker: TranslationRunWorker | None = None
        self._last_workflow: TranslationWorkflow | None = None
        self._last_summary: RunSummary | None = None
        self._last_output_docx: Path | None = None
        self._busy = False
        self._running = False
        self._can_export_partial = False
        self._last_page_path: str | None = None

        self._build_ui()
        self._restore_settings()
        self._refresh_page_count()
        self._update_controls()
        QTimer.singleShot(0, self._sync_glass_background)

    def _build_ui(self) -> None:
        root = _BackgroundWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(0)
        outer.addStretch(1)

        self.glass_card = QFrame(objectName="GlassCard")
        self.glass_card.setMaximumWidth(1120)
        self.glass_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        outer.addWidget(self.glass_card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

        self._glass_blur = QLabel(self.glass_card)
        self._glass_blur.setScaledContents(True)
        self._glass_blur.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._glass_blur.setGraphicsEffect(make_blur_effect(self._glass_blur, radius=28))

        self._glass_tint = QFrame(self.glass_card, objectName="CardTint")
        self._glass_tint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.card_content = QWidget(self.glass_card)
        card_shell = QVBoxLayout(self.card_content)
        card_shell.setContentsMargins(18, 18, 18, 16)
        card_shell.setSpacing(10)

        self.header_card = QFrame(objectName="SurfacePanel")
        header_layout = QVBoxLayout(self.header_card)
        header_layout.setContentsMargins(14, 12, 14, 12)
        self.banner_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.banner_label.setMinimumHeight(58)
        self.banner_label.setMaximumHeight(78)
        self._banner_src = QPixmap(str(get_resources_dir() / "ui" / "ui_banner.png"))
        header_layout.addWidget(self.banner_label)
        title_row = QHBoxLayout()
        self.title_label = QLabel("LegalPDF Translate", objectName="TitleLabel")
        self.header_status_label = QLabel("Idle", objectName="StatusHeaderLabel")
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.header_status_label)
        header_layout.addLayout(title_row)
        card_shell.addWidget(self.header_card)

        self.main_card = QFrame(objectName="SurfacePanel")
        main_layout = QVBoxLayout(self.main_card)
        main_layout.setContentsMargins(16, 14, 16, 14)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)

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
        grid.addWidget(self.show_adv, 3, 0, 1, 2)
        main_layout.addLayout(grid)

        self.adv_frame = QFrame(objectName="SurfacePanel")
        adv = QFormLayout(self.adv_frame)
        adv.setContentsMargins(10, 10, 10, 10)
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
        toggles = QWidget(); tl = QHBoxLayout(toggles); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(12); tl.addWidget(self.resume_check); tl.addWidget(self.breaks_check); tl.addWidget(self.keep_check); tl.addStretch(1)
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
        footer = QVBoxLayout(self.footer_card)
        footer.setContentsMargins(14, 10, 14, 10)
        fp = QHBoxLayout(); fp.addWidget(QLabel("Final DOCX")); self.final_docx_edit = QLineEdit(readOnly=True); fp.addWidget(self.final_docx_edit, 1); footer.addLayout(fp)
        pr = QHBoxLayout(); self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0); self.page_label = QLabel("Page: -/-", objectName="MutedLabel"); pr.addWidget(self.progress, 1); pr.addWidget(self.page_label); footer.addLayout(pr)
        self.status_label = QLabel("Idle", objectName="PathLabel")
        footer.addWidget(self.status_label)

        buttons = QHBoxLayout(); buttons.setSpacing(8)
        self.translate_btn = QPushButton("Translate", objectName="PrimaryButton")
        self.cancel_btn = QPushButton("Cancel", objectName="DangerButton")
        self.new_btn = QPushButton("New Run")
        self.partial_btn = QPushButton("Export partial DOCX")
        self.rebuild_btn = QPushButton("Rebuild DOCX")
        self.open_btn = QPushButton("Open output folder")
        for btn in (self.translate_btn, self.cancel_btn, self.new_btn, self.partial_btn, self.rebuild_btn, self.open_btn):
            buttons.addWidget(btn)
        buttons.addStretch(1)
        footer.addLayout(buttons)
        card_shell.addWidget(self.footer_card)

        apply_soft_shadow(self.glass_card, blur_radius=60, offset_y=14)
        apply_primary_glow(self.translate_btn, blur_radius=28)

        self.pdf_btn.clicked.connect(self._pick_pdf)
        self.outdir_btn.clicked.connect(self._pick_outdir)
        self.context_btn.clicked.connect(self._pick_context)
        self.show_adv.toggled.connect(self._set_adv_visible)
        self.details_btn.toggled.connect(self._set_details_visible)
        self.translate_btn.clicked.connect(self._start)
        self.cancel_btn.clicked.connect(self._cancel)
        self.new_btn.clicked.connect(self._new_run)
        self.partial_btn.clicked.connect(self._export_partial)
        self.rebuild_btn.clicked.connect(self._rebuild_docx)
        self.open_btn.clicked.connect(self._open_output_folder)

        self.request_cancel.connect(self._dispatch_cancel)
        self.pdf_edit.textChanged.connect(self._on_form_changed)
        self.outdir_edit.textChanged.connect(self._on_form_changed)
        self.start_edit.textChanged.connect(self._on_form_changed)
        self.end_edit.textChanged.connect(self._on_form_changed)
        self.max_edit.textChanged.connect(self._on_form_changed)
        self.workers_spin.valueChanged.connect(self._on_form_changed)

        self._set_adv_visible(False)
        self._set_details_visible(False)
        self._refresh_banner()
        self._layout_glass_layers()

    def _restore_settings(self) -> None:
        defaults = self._defaults
        outdir = str(defaults.get("last_outdir", defaults.get("default_outdir", "")) or "").strip()
        self.outdir_edit.setText(outdir)

        lang = str(defaults.get("last_lang", defaults.get("default_lang", "EN")) or "EN").strip().upper()
        if lang not in {"EN", "FR", "AR"}:
            lang = "EN"
        self.lang_combo.setCurrentText(lang)
        self.effort_combo.setCurrentText(str(defaults.get("effort", defaults.get("default_effort", "high")) or "high"))
        self.images_combo.setCurrentText(str(defaults.get("image_mode", defaults.get("default_images_mode", "auto")) or "auto"))
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

    def _set_details_visible(self, visible: bool) -> None:
        self.log_text.setVisible(visible)
        self.details_btn.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.details_btn.setText("Hide details" if visible else "Show details")
        QTimer.singleShot(0, self._sync_glass_background)

    def _set_adv_visible(self, visible: bool) -> None:
        self.adv_frame.setVisible(visible)
        QTimer.singleShot(0, self._sync_glass_background)

    def _on_form_changed(self) -> None:
        self._refresh_page_count()
        self._update_controls()

    def _refresh_banner(self) -> None:
        if self._banner_src.isNull():
            return
        size = self.banner_label.size()
        if size.width() <= 1 or size.height() <= 1:
            return
        self.banner_label.setPixmap(
            self._banner_src.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _layout_glass_layers(self) -> None:
        if not hasattr(self, "glass_card"):
            return
        rect = self.glass_card.rect()
        self._glass_blur.setGeometry(rect)
        self._glass_tint.setGeometry(rect)
        self.card_content.setGeometry(rect)

    def _sync_glass_background(self) -> None:
        if not hasattr(self, "glass_card") or not hasattr(self, "_background_widget"):
            return
        self._layout_glass_layers()
        if self.glass_card.width() <= 0 or self.glass_card.height() <= 0:
            return
        sampled = self._background_widget.sample_background(self.glass_card.geometry())
        if not sampled.isNull():
            self._glass_blur.setPixmap(sampled)

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

        return RunConfig(
            pdf_path=pdf,
            output_dir=outdir,
            target_lang=TargetLang(self.lang_combo.currentText().strip().upper()),
            effort=parse_effort(self.effort_combo.currentText()),
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

    def _update_controls(self) -> None:
        can_start = self._can_start()
        self.translate_btn.setEnabled(can_start)
        self.cancel_btn.setEnabled(self._running)
        self.new_btn.setEnabled(not self._busy)
        self.partial_btn.setEnabled((not self._busy) and self._can_export_partial and self._last_workflow is not None)
        self.rebuild_btn.setEnabled(not self._busy)
        can_open = (not self._busy) and self._last_output_docx is not None and self._last_output_docx.exists()
        self.open_btn.setEnabled(can_open)

    def _set_busy(self, busy: bool, *, translation: bool) -> None:
        self._busy = busy
        self._running = busy and translation
        for w in (
            self.pdf_edit, self.pdf_btn, self.lang_combo, self.outdir_edit, self.outdir_btn, self.show_adv,
            self.effort_combo, self.images_combo, self.ocr_mode_combo, self.ocr_engine_combo,
            self.start_edit, self.end_edit, self.max_edit, self.workers_spin,
            self.resume_check, self.breaks_check, self.keep_check,
            self.context_file_edit, self.context_btn, self.context_text,
        ):
            w.setEnabled(not busy)
        self._update_controls()

    def _start(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        self._save_settings()
        self._last_summary = None
        self._last_output_docx = None
        self._last_workflow = None
        self._can_export_partial = False
        self.final_docx_edit.clear()
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self.status_label.setText("Starting...")
        self.header_status_label.setText("Starting...")

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

    def _on_progress(self, selected_index: int, selected_total: int, real_page: int, status: str, image_used: bool, retry_used: bool) -> None:
        if selected_total > 0:
            self.progress.setValue(max(0, min(100, int((float(selected_index) / float(selected_total)) * 100.0))))
        if real_page > 0:
            extra = []
            if image_used:
                extra.append("image")
            if retry_used:
                extra.append("retry")
            suffix = f" [{', '.join(extra)}]" if extra else ""
            self.page_label.setText(f"Page {real_page} ({selected_index}/{selected_total}){suffix}")
        else:
            self.page_label.setText(f"Progress: {selected_index}/{selected_total}")
        self.status_label.setText(status)
        self.header_status_label.setText(status)

    def _on_finished(self, summary_obj: object) -> None:
        summary = summary_obj if isinstance(summary_obj, RunSummary) else None
        if self._worker is not None:
            self._last_workflow = self._worker.workflow
        self._set_busy(False, translation=False)
        if summary is None:
            self.status_label.setText("Run finished with invalid summary")
            self.header_status_label.setText("Error")
            return
        self._last_summary = summary
        if summary.success and summary.output_docx is not None:
            output = summary.output_docx.expanduser().resolve()
            self._last_output_docx = output
            self.final_docx_edit.setText(str(output))
            self.status_label.setText("Completed")
            self.header_status_label.setText("Completed")
            self._append_log(f"Saved DOCX: {output}")
            QMessageBox.information(self, "Translation complete", f"Saved DOCX:\n{output}")
        else:
            self._append_log(f"Run failed: {summary.error}; failed_page={summary.failed_page}")
            self.status_label.setText(f"Failed ({summary.error})")
            self.header_status_label.setText("Failed")
            QMessageBox.warning(self, "Translation stopped", f"Run stopped at page {summary.failed_page}.\nPartial pages: {summary.completed_pages}")
        self._can_export_partial = summary.completed_pages > 0
        self._update_controls()
    def _on_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self.status_label.setText("Error")
        self.header_status_label.setText("Error")
        self._append_log(f"Runtime error: {message}")
        QMessageBox.critical(self, "Runtime error", message)

    def _dispatch_cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _cancel(self) -> None:
        if self._running:
            self.request_cancel.emit()

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            try:
                self.request_cancel.disconnect(self._worker.cancel)
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
        self._last_output_docx = None
        self._last_workflow = None
        self._can_export_partial = False
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self.status_label.setText("Idle")
        self.header_status_label.setText("Idle")
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

    def _rebuild_docx(self) -> None:
        if self._busy:
            return
        try:
            config = self._build_config()
            rebuilt = TranslationWorkflow(log_callback=self._append_log).rebuild_docx(config)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rebuild failed", str(exc))
            return
        output = rebuilt.expanduser().resolve()
        self._last_output_docx = output
        self.final_docx_edit.setText(str(output))
        self.status_label.setText("Completed")
        self.header_status_label.setText("Completed")
        self._append_log(f"Saved DOCX: {output}")
        QMessageBox.information(self, "Rebuild complete", f"Saved DOCX:\n{output}")
        self._update_controls()

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

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_banner()
        self._layout_glass_layers()
        QTimer.singleShot(0, self._sync_glass_background)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            QMessageBox.warning(self, "Run in progress", "Cancel the active run before closing the app.")
            event.ignore()
            return
        self._save_settings()
        super().closeEvent(event)
