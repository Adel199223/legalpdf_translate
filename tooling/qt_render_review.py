"""Deterministic Qt dashboard renders for reference-locked UI review."""

from __future__ import annotations

import argparse
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

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from legalpdf_translate.gmail_batch import FetchedGmailMessage, GmailAttachmentCandidate
from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.dialogs import QtGmailAttachmentPreviewDialog, QtGmailBatchReviewDialog
from legalpdf_translate.qt_gui.styles import build_stylesheet
from legalpdf_translate.qt_gui.worker import (
    GmailAttachmentPreviewBootstrapResult,
    GmailAttachmentPreviewPageResult,
)
from legalpdf_translate.resources_loader import resource_path


PROFILE_SIZES: dict[str, tuple[int, int]] = {
    "wide": (1800, 1000),
    "medium": (1360, 880),
    "narrow": (980, 760),
}

PREVIEW_TEXT = {
    "pdf_name": "test_document.pdf",
    "pages": "Pages: 25",
    "outdir": "C:/Users/FA507/Downloads",
    "status": "Translating text blocks and rebuilding pages...",
    "idle": "Idle",
    "eta": "~2m",
}


def _ensure_app() -> tuple[QApplication, bool]:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])
        app.setApplicationName("LegalPDF Translate")
        app.setOrganizationName("LegalPDFTranslate")
        app.setFont(QFont("Segoe UI", 12))
        app.setStyle("Fusion")
        app.setStyleSheet(build_stylesheet())
        icon_path = resource_path("resources/icons/LegalPDFTranslate.png")
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)
    return app, owns_app


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


def render_gmail_review_dialog_sample(*, outdir: Path) -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app()
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


def render_gmail_preview_dialog_sample(*, outdir: Path) -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app()

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


def render_profiles(
    *,
    outdir: Path,
    profiles: Iterable[str],
    preview: str = "reference_sample",
) -> list[dict[str, object]]:
    profile_names = resolve_profiles(profiles)
    outdir.mkdir(parents=True, exist_ok=True)
    app, owns_app = _ensure_app()
    results: list[dict[str, object]] = []

    try:
        for profile_name in profile_names:
            width, height = PROFILE_SIZES[profile_name]
            window = QtMainWindow()
            try:
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
                window.grab().save(str(image_path))
                metadata = {
                    "profile": profile_name,
                    "width": width,
                    "height": height,
                    "layout_mode": getattr(window, "_layout_mode", ""),
                    "sidebar_width": int(window.sidebar_frame.width()),
                    "content_card_width": int(window.content_card.width()),
                    "setup_panel_width": int(window.setup_panel.width()),
                    "progress_panel_width": int(window.progress_panel.width()),
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
        default=REPO_ROOT / "tmp_ui_review",
        help="Directory where profile screenshots and metadata JSON should be written.",
    )
    parser.add_argument(
        "--profiles",
        nargs="*",
        default=["wide", "medium", "narrow"],
        help="Render profiles to generate: wide medium narrow.",
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
    results: dict[str, object] = {
        "profiles": render_profiles(outdir=args.outdir, profiles=args.profiles, preview=args.preview),
    }
    if args.include_gmail_review:
        results["gmail_review"] = render_gmail_review_dialog_sample(outdir=args.outdir)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
