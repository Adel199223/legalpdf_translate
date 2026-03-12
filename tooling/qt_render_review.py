"""Deterministic Qt dashboard renders for reference-locked UI review."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QRect
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from legalpdf_translate.gmail_batch import FetchedGmailMessage, GmailAttachmentCandidate
import legalpdf_translate.qt_gui.app_window as app_window_module
import legalpdf_translate.qt_gui.dialogs as dialogs_module
from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.dialogs import (
    QtGmailAttachmentPreviewDialog,
    QtGmailBatchReviewDialog,
    QtHonorariosExportDialog,
)
from legalpdf_translate.qt_gui.styles import build_stylesheet
from legalpdf_translate.qt_gui import window_adaptive as window_adaptive_module
from legalpdf_translate.qt_gui.worker import (
    GmailAttachmentPreviewBootstrapResult,
    GmailAttachmentPreviewPageResult,
)
from legalpdf_translate.resources_loader import resource_path
from legalpdf_translate.honorarios_docx import (
    build_interpretation_honorarios_draft,
    default_interpretation_recipient_block,
)
from legalpdf_translate.user_profile import default_primary_profile
from legalpdf_translate.user_settings import DEFAULT_GUI_SETTINGS


PROFILE_SIZES: dict[str, tuple[int, int]] = {
    "wide": (1800, 1000),
    "medium": (1360, 880),
    "narrow": (980, 760),
}
THEME_NAMES = ("dark_futuristic", "dark_simple")
RENDER_SCREEN_GEOMETRY = QRect(0, 0, 2560, 1600)

PREVIEW_TEXT = {
    "pdf_name": "test_document.pdf",
    "pages": "Pages: 25",
    "outdir": "C:/Users/FA507/Downloads",
    "status": "Translating text blocks and rebuilding pages...",
    "idle": "Idle",
    "eta": "~2m",
}


def _ensure_app(theme: str = "dark_futuristic") -> tuple[QApplication, bool]:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])
    app.setApplicationName("LegalPDF Translate")
    app.setOrganizationName("LegalPDFTranslate")
    app.setFont(QFont("Segoe UI", 12))
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet(theme))
    icon_path = resource_path("resources/icons/LegalPDFTranslate.png")
    app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)
    return app, owns_app


@contextmanager
def _deterministic_render_screen():
    original = window_adaptive_module.available_screen_geometry

    def _fixed_geometry(_widget) -> QRect:
        return QRect(RENDER_SCREEN_GEOMETRY)

    window_adaptive_module.available_screen_geometry = _fixed_geometry
    try:
        yield
    finally:
        window_adaptive_module.available_screen_geometry = original


def resolve_profiles(values: Iterable[str]) -> list[str]:
    resolved: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key == "":
            continue
        if key not in PROFILE_SIZES:
            raise ValueError(f"Unknown render profile: {value}")
        if key not in resolved:
            resolved.append(key)
    return resolved or ["wide", "medium", "narrow"]


def resolve_themes(values: Iterable[str]) -> list[str]:
    resolved: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key == "":
            continue
        if key not in THEME_NAMES:
            raise ValueError(f"Unknown theme: {value}")
        if key not in resolved:
            resolved.append(key)
    return resolved or ["dark_futuristic", "dark_simple"]


@contextmanager
def _deterministic_ui_defaults(theme: str):
    profile = default_primary_profile(email="adel@example.com")
    profile.travel_origin_label = "Marmelar"
    profile.travel_distances_by_city = {
        "Ferreira do Alentejo": 42.0,
        "Beja": 39.0,
    }
    settings = dict(DEFAULT_GUI_SETTINGS)
    settings["ui_theme"] = theme
    settings["default_outdir"] = PREVIEW_TEXT["outdir"]
    original_load_gui = app_window_module.load_gui_settings
    original_load_profiles = dialogs_module.load_profile_settings
    app_window_module.load_gui_settings = lambda: dict(settings)
    dialogs_module.load_profile_settings = lambda: ([profile], profile.id)
    try:
        yield profile
    finally:
        app_window_module.load_gui_settings = original_load_gui
        dialogs_module.load_profile_settings = original_load_profiles


def apply_reference_sample(window: QtMainWindow) -> None:
    pdf_blocked = window.pdf_edit.blockSignals(True)
    outdir_blocked = window.outdir_edit.blockSignals(True)
    lang_blocked = window.lang_combo.blockSignals(True)
    try:
        window.pdf_edit.setText(PREVIEW_TEXT["pdf_name"])
        window.outdir_edit.setText(PREVIEW_TEXT["outdir"])
        window.lang_combo.setCurrentText("EN")
    finally:
        window.pdf_edit.blockSignals(pdf_blocked)
        window.outdir_edit.blockSignals(outdir_blocked)
        window.lang_combo.blockSignals(lang_blocked)

    window.pages_label.setText(PREVIEW_TEXT["pages"])
    window._refresh_lang_badge()
    window.progress.setValue(50)
    window._dashboard_eta_text = PREVIEW_TEXT["eta"]
    window._dashboard_snapshot.progress_percent = 50
    window._dashboard_snapshot.eta_text = PREVIEW_TEXT["eta"]
    window._dashboard_snapshot.current_task = PREVIEW_TEXT["status"]
    window._dashboard_snapshot.pages_done = 12
    window._dashboard_snapshot.pages_total = 25
    window._dashboard_snapshot.page_retries = 0
    window._dashboard_snapshot.images_done = 3
    window._dashboard_snapshot.images_total = 3
    window._dashboard_snapshot.image_retries = 0
    window._dashboard_snapshot.errors_count = 0
    window._dashboard_snapshot.error_retries = 0
    window._dashboard_snapshot.pages_title = "Pages"
    window._dashboard_snapshot.images_title = "Images"
    window._dashboard_snapshot.errors_title = "Errors"
    window._apply_dashboard_snapshot()
    window.header_status_label.setText(PREVIEW_TEXT["idle"])
    window.queue_status_label.setText("Queue: idle")
    window.translate_btn.setEnabled(True)
    window.cancel_btn.setEnabled(True)
    window.more_btn.setEnabled(True)


def _rgb_triplet(color: QColor) -> list[int]:
    return [int(color.red()), int(color.green()), int(color.blue())]


def _sample_rgb(image: QImage, x: int, y: int) -> list[int]:
    clamped_x = max(0, min(image.width() - 1, int(x)))
    clamped_y = max(0, min(image.height() - 1, int(y)))
    return _rgb_triplet(image.pixelColor(clamped_x, clamped_y))


def _widget_rect_in_window(window: QtMainWindow, widget) -> QRect:
    top_left = widget.mapTo(window, QPoint(0, 0))
    return QRect(top_left, widget.size())


def _sample_dominant_rgb(image: QImage, rect: QRect, *, mode: str) -> list[int]:
    left = max(0, rect.left())
    top = max(0, rect.top())
    right = min(image.width() - 1, rect.right())
    bottom = min(image.height() - 1, rect.bottom())
    if right < left or bottom < top:
        return _sample_rgb(image, rect.center().x(), rect.center().y())

    best_score: tuple[int, int] | None = None
    best_color = image.pixelColor(left, top)
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            color = image.pixelColor(x, y)
            red = int(color.red())
            green = int(color.green())
            blue = int(color.blue())
            if mode == "warm":
                score = (red - max(green, blue), red + green + blue)
            elif mode == "teal":
                score = (min(green, blue) - red, green + blue)
            else:
                score = (red + green + blue, min(green, blue) - red)
            if best_score is None or score > best_score:
                best_score = score
                best_color = color
    return _rgb_triplet(best_color)


def render_gmail_review_dialog_sample(*, outdir: Path, theme: str = "dark_futuristic") -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app(theme)
    with _deterministic_render_screen(), _deterministic_ui_defaults(theme):
        dialog = QtGmailBatchReviewDialog(
            parent=None,
            message=FetchedGmailMessage(
                message_id="msg-100",
                thread_id="thread-200",
                subject="Remessa de peça processual",
                from_header='Palmira M Romaneiro <palmira.m.romaneiro@tribunais.org.pt>',
                account_email="adel.belghali@gmail.com",
                attachments=(
                    GmailAttachmentCandidate(
                        attachment_id="att-1",
                        filename="cef31abb-bd4f-4582-b15e-09bbb40d1834_temp.pdf",
                        mime_type="application/pdf",
                        size_bytes=182_784,
                        source_message_id="msg-100",
                    ),
                    GmailAttachmentCandidate(
                        attachment_id="att-2",
                        filename="scene.jpg",
                        mime_type="image/jpeg",
                        size_bytes=98_304,
                        source_message_id="msg-100",
                    ),
                ),
            ),
            gog_path=Path("C:/gog.exe"),
            account_email="adel.belghali@gmail.com",
            target_lang="FR",
            default_start_page=2,
            output_dir_text="C:/Users/FA507/Downloads",
        )
        try:
            dialog.table.selectRow(0)
            dialog._set_row_page_count(0, 6)
            dialog._set_row_start_page(0, 2)
            dialog._refresh_detail_panel()
            dialog.show()
            app.processEvents()
            image_path = outdir / "gmail_review.png"
            meta_path = outdir / "gmail_review.json"
            dialog.grab().save(str(image_path))
            metadata = {
                "sample": "gmail_review",
                "theme": theme,
                "width": int(dialog.width()),
                "height": int(dialog.height()),
                "row_count": int(dialog.table.rowCount()),
                "current_row": int(dialog.table.currentRow()),
                "target_lang": dialog.target_lang_combo.currentText(),
                "image_path": str(image_path),
            }
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return metadata
        finally:
            dialog.close()
            dialog.deleteLater()
            if owns_app:
                app.quit()


def _sample_preview_image_bytes(page_number: int) -> tuple[bytes, int, int]:
    width = 900
    height = 1260
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#f7f4ee") if page_number % 2 else QColor("#eef4ff"))

    painter = QPainter(image)
    painter.setPen(QPen(QColor("#1c2430"), 4))
    painter.drawRect(30, 30, width - 60, height - 60)
    painter.setPen(QColor("#2f3c4d"))
    painter.setFont(QFont("Segoe UI", 28))
    painter.drawText(80, 120, f"Preview page {page_number}")
    painter.setFont(QFont("Segoe UI", 16))
    painter.drawText(80, 190, "Deterministic Qt render sample")
    painter.drawText(80, 250, "Gmail attachment preview")
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data()), width, height


def render_gmail_preview_dialog_sample(*, outdir: Path, theme: str = "dark_futuristic") -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app(theme)

    class _SamplePreviewDialog(QtGmailAttachmentPreviewDialog):
        def _start_bootstrap(self) -> None:
            return None

        def _start_page_worker(self, page_number: int) -> None:
            self._inflight_pages.add(page_number)
            image_bytes, width, height = _sample_preview_image_bytes(page_number)
            self._on_page_loaded(
                GmailAttachmentPreviewPageResult(
                    attachment=self._attachment,
                    local_path=Path("C:/preview/sample.pdf"),
                    page_count=max(1, int(self._page_count or 1)),
                    page_number=page_number,
                    image_bytes=image_bytes,
                    image_format="png",
                    width_px=width,
                    height_px=height,
                )
            )

    with _deterministic_render_screen(), _deterministic_ui_defaults(theme):
        dialog = _SamplePreviewDialog(
            parent=None,
            attachment=GmailAttachmentCandidate(
                attachment_id="att-1",
                filename="21-25.pdf",
                mime_type="application/pdf",
                size_bytes=182_784,
                source_message_id="msg-100",
            ),
            gog_path=Path("C:/gog.exe"),
            account_email="adel.belghali@gmail.com",
            preview_dir=outdir,
            initial_start_page=2,
            cached_path=outdir / "sample_preview.pdf",
            known_page_count=6,
        )
        try:
            dialog._on_bootstrap_loaded(
                GmailAttachmentPreviewBootstrapResult(
                    attachment=dialog._attachment,
                    local_path=outdir / "sample_preview.pdf",
                    page_count=6,
                    page_sizes=((900.0, 1260.0),) * 6,
                )
            )
            dialog.show()
            app.processEvents()
            dialog._scroll_to_page(2)
            QTest.qWait(dialog._PAGE_REFRESH_DEBOUNCE_MS + 40)
            app.processEvents()
            image_path = outdir / "gmail_preview.png"
            meta_path = outdir / "gmail_preview.json"
            dialog.grab().save(str(image_path))
            metadata = {
                "sample": "gmail_preview",
                "theme": theme,
                "width": int(dialog.width()),
                "height": int(dialog.height()),
                "page_count": int(dialog.resolved_page_count or 0),
                "cached_pages": len(dialog._page_cache),
                "image_path": str(image_path),
            }
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return metadata
        finally:
            dialog.close()
            dialog.deleteLater()
            if owns_app:
                app.quit()


def _modal_button(window: QMessageBox):
    buttons = window.buttons()
    return buttons[-1] if buttons else None


def _modal_metadata(*, sample: str, theme: str, window: QMessageBox, image_path: Path) -> dict[str, object]:
    grabbed = window.grab()
    grabbed.save(str(image_path))
    image = grabbed.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    button = _modal_button(window)
    button_rect = _widget_rect_in_window(window, button) if button is not None else QRect(0, 0, 1, 1)
    return {
        "sample": sample,
        "theme": theme,
        "width": int(window.width()),
        "height": int(window.height()),
        "dialog_fill_rgb": _sample_rgb(image, window.width() // 2, window.height() // 2),
        "dialog_border_rgb": _sample_dominant_rgb(
            image,
            QRect(24, 8, max(1, window.width() - 48), 18),
            mode="teal",
        ),
        "button_rgb": _sample_dominant_rgb(image, button_rect.adjusted(-4, -4, 4, 4), mode="teal"),
        "image_path": str(image_path),
    }


def render_honorarios_export_dialog_sample(*, outdir: Path, theme: str = "dark_futuristic") -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app(theme)
    with _deterministic_render_screen(), _deterministic_ui_defaults(theme):
        profile = default_primary_profile(email="adel@example.com")
        profile.travel_origin_label = "Marmelar"
        profile.travel_distances_by_city = {"Ferreira do Alentejo": 42.0}
        dialog = QtHonorariosExportDialog(
            parent=None,
            draft=build_interpretation_honorarios_draft(
                case_number="66/26.3GAFAL",
                case_entity="Tribunal Judicial",
                case_city="Ferreira do Alentejo",
                service_date="2026-03-11",
                service_entity="Tribunal Judicial",
                service_city="Ferreira do Alentejo",
                use_service_location_in_honorarios=False,
                travel_km_outbound=42.0,
                travel_km_return=42.0,
                recipient_block=default_interpretation_recipient_block(
                    "Tribunal Judicial",
                    "Ferreira do Alentejo",
                ),
                profile=profile,
            ),
            default_directory=outdir,
        )
        try:
            dialog.resize(1040, 760)
            dialog.show()
            app.processEvents()
            image_path = outdir / "honorarios_export_dialog.png"
            meta_path = outdir / "honorarios_export_dialog.json"
            grabbed = dialog.grab()
            grabbed.save(str(image_path))
            image = grabbed.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            generate_rect = _widget_rect_in_window(dialog, dialog.generate_btn)
            status_rect = _widget_rect_in_window(dialog, dialog.export_status_label)
            metadata = {
                "sample": "honorarios_export_dialog",
                "theme": theme,
                "width": int(dialog.width()),
                "height": int(dialog.height()),
                "generate_button_rgb": _sample_dominant_rgb(
                    image,
                    generate_rect.adjusted(-8, -8, 8, 8),
                    mode="teal",
                ),
                "dialog_fill_rgb": _sample_rgb(image, dialog.width() // 2, dialog.height() // 2),
                "dialog_border_rgb": _sample_dominant_rgb(
                    image,
                    QRect(28, 8, max(1, dialog.width() - 56), 18),
                    mode="teal",
                ),
                "status_label_rgb": _sample_rgb(
                    image,
                    max(0, status_rect.center().x()),
                    max(0, status_rect.center().y()),
                ),
                "image_path": str(image_path),
            }
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return metadata
        finally:
            dialog.close()
            dialog.deleteLater()
            if owns_app:
                app.quit()


def render_honorarios_pdf_failure_sample(*, outdir: Path, theme: str = "dark_futuristic") -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app(theme)
    with _deterministic_render_screen(), _deterministic_ui_defaults(theme):
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Requerimento de Honorários")
        box.setText("The honorários DOCX is ready, but the PDF is unavailable.")
        box.setInformativeText(
            "Microsoft Word could not export the PDF.\n\n"
            "Email drafting requires the PDF, so draft creation will stay blocked until a valid PDF is available."
        )
        box.addButton("Open DOCX", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Retry PDF", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Select existing PDF...", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Continue local-only", QMessageBox.ButtonRole.AcceptRole)
        try:
            box.show()
            app.processEvents()
            image_path = outdir / "honorarios_pdf_failure.png"
            meta_path = outdir / "honorarios_pdf_failure.json"
            metadata = _modal_metadata(
                sample="honorarios_pdf_failure",
                theme=theme,
                window=box,
                image_path=image_path,
            )
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return metadata
        finally:
            box.close()
            box.deleteLater()
            if owns_app:
                app.quit()


def render_gmail_pdf_unavailable_sample(*, outdir: Path, theme: str = "dark_futuristic") -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app(theme)
    with _deterministic_render_screen(), _deterministic_ui_defaults(theme):
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Gmail draft")
        box.setText("The honorários PDF is unavailable for this export. Gmail draft creation requires the PDF.")
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        try:
            box.show()
            app.processEvents()
            image_path = outdir / "gmail_pdf_unavailable.png"
            meta_path = outdir / "gmail_pdf_unavailable.json"
            metadata = _modal_metadata(
                sample="gmail_pdf_unavailable",
                theme=theme,
                window=box,
                image_path=image_path,
            )
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return metadata
        finally:
            box.close()
            box.deleteLater()
            if owns_app:
                app.quit()


def render_profiles(
    *,
    outdir: Path,
    profiles: Iterable[str],
    preview: str = "reference_sample",
    theme: str = "dark_futuristic",
) -> list[dict[str, object]]:
    profile_names = resolve_profiles(profiles)
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app(theme)
    results: list[dict[str, object]] = []

    try:
        with _deterministic_render_screen(), _deterministic_ui_defaults(theme):
            for profile_name in profile_names:
                width, height = PROFILE_SIZES[profile_name]
                window = QtMainWindow()
                try:
                    window.reload_shared_settings({"ui_theme": theme})
                    window._initial_resize_done = True
                    window.resize(width, height)
                    if preview == "reference_sample":
                        apply_reference_sample(window)
                    window.show()
                    app.processEvents()
                    window.resize(width, height)
                    app.processEvents()
                    window._update_card_max_width(viewport_width=width)
                    app.processEvents()

                    image_path = outdir / f"{profile_name}.png"
                    meta_path = outdir / f"{profile_name}.json"
                    grabbed = window.grab()
                    grabbed.save(str(image_path))
                    image = grabbed.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                    dashboard_rect = _widget_rect_in_window(window, window.dashboard_frame)
                    footer_rect = _widget_rect_in_window(window, window.footer_card)
                    translate_rect = _widget_rect_in_window(window, window.translate_btn)
                    cancel_rect = _widget_rect_in_window(window, window.cancel_btn)
                    dashboard_nav_rect = _widget_rect_in_window(window, window.dashboard_nav_btn)
                    settings_nav_rect = _widget_rect_in_window(window, window.settings_nav_btn)
                    metadata = {
                        "profile": profile_name,
                        "theme": theme,
                        "width": width,
                        "height": height,
                        "layout_mode": getattr(window, "_layout_mode", ""),
                        "sidebar_width": int(window.sidebar_frame.width()),
                        "content_card_width": int(window.content_card.width()),
                        "dashboard_frame_width": int(window.dashboard_frame.width()),
                        "dashboard_frame_x": int(window.dashboard_frame.geometry().x()),
                        "dashboard_frame_y": int(window.dashboard_frame.geometry().y()),
                        "setup_panel_width": int(window.setup_panel.width()),
                        "progress_panel_width": int(window.progress_panel.width()),
                        "footer_card_width": int(window.footer_card.width()),
                        "menu_bar_mid_rgb": _sample_rgb(image, width // 2, 24),
                        "left_glow_rgb": _sample_rgb(image, int(width * 0.18), int(height * 0.30)),
                        "left_glow_control_rgb": _sample_rgb(image, int(width * 0.18), int(height * 0.72)),
                        "dashboard_border_rgb": _sample_dominant_rgb(
                            image,
                            QRect(
                                dashboard_rect.x() + 36,
                                dashboard_rect.y() - 4,
                                max(1, dashboard_rect.width() - 72),
                                18,
                            ),
                            mode="teal",
                        ),
                        "dashboard_fill_rgb": _sample_rgb(
                            image,
                            dashboard_rect.x() + (dashboard_rect.width() // 2),
                            dashboard_rect.y() + 44,
                        ),
                        "footer_halo_rgb": _sample_dominant_rgb(
                            image,
                            QRect(
                                footer_rect.x() + (footer_rect.width() // 5),
                                footer_rect.y() - 26,
                                max(1, (footer_rect.width() * 3) // 5),
                                24,
                            ),
                            mode="teal",
                        ),
                        "footer_fill_rgb": _sample_rgb(
                            image,
                            footer_rect.x() + (footer_rect.width() // 2),
                            footer_rect.y() + footer_rect.height() - 14,
                        ),
                        "primary_button_rgb": _sample_dominant_rgb(
                            image,
                            QRect(
                                translate_rect.x() - 8,
                                translate_rect.y() - 24,
                                max(1, translate_rect.width() // 2),
                                28,
                            ),
                            mode="teal",
                        ),
                        "danger_button_rgb": _sample_dominant_rgb(
                            image,
                            QRect(
                                cancel_rect.x() - 8,
                                cancel_rect.y() - 8,
                                cancel_rect.width() + 24,
                                28,
                            ),
                            mode="warm",
                        ),
                        "sidebar_active_rgb": _sample_rgb(
                            image,
                            dashboard_nav_rect.x() + 18,
                            dashboard_nav_rect.y() + (dashboard_nav_rect.height() // 2),
                        ),
                        "sidebar_inactive_rgb": _sample_rgb(
                            image,
                            settings_nav_rect.x() + 18,
                            settings_nav_rect.y() + (settings_nav_rect.height() // 2),
                        ),
                        "image_path": str(image_path),
                    }
                    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
                    results.append(metadata)
                finally:
                    window.close()
                    window.deleteLater()
    finally:
        if owns_app:
            app.quit()

    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render deterministic Qt dashboard screenshots.")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=REPO_ROOT / "tmp" / "qt_ui_review",
        help="Directory where profile screenshots and metadata JSON should be written.",
    )
    parser.add_argument(
        "--profiles",
        nargs="*",
        default=["wide", "medium", "narrow"],
        help="Render profiles to generate: wide medium narrow.",
    )
    parser.add_argument(
        "--themes",
        nargs="*",
        default=["dark_futuristic", "dark_simple"],
        help="Themes to render: dark_futuristic dark_simple.",
    )
    parser.add_argument(
        "--preview",
        default="reference_sample",
        choices=["reference_sample"],
        help="Preview state to apply before capture.",
    )
    parser.add_argument(
        "--include-gmail-review",
        action="store_true",
        help="Also render the Gmail Attachment Review sample dialog into the output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    results: dict[str, object] = {"themes": []}
    for theme in resolve_themes(args.themes):
        theme_outdir = args.outdir / theme
        theme_result: dict[str, object] = {
            "theme": theme,
            "profiles": render_profiles(
                outdir=theme_outdir / "dashboard",
                profiles=args.profiles,
                preview=args.preview,
                theme=theme,
            ),
            "honorarios_export_dialog": render_honorarios_export_dialog_sample(
                outdir=theme_outdir,
                theme=theme,
            ),
            "honorarios_pdf_failure": render_honorarios_pdf_failure_sample(
                outdir=theme_outdir,
                theme=theme,
            ),
            "gmail_pdf_unavailable": render_gmail_pdf_unavailable_sample(
                outdir=theme_outdir,
                theme=theme,
            ),
        }
        if args.include_gmail_review:
            theme_result["gmail_review"] = render_gmail_review_dialog_sample(outdir=theme_outdir, theme=theme)
            theme_result["gmail_preview"] = render_gmail_preview_dialog_sample(outdir=theme_outdir, theme=theme)
        results["themes"].append(theme_result)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
