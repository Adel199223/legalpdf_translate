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

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.styles import build_stylesheet
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    results = render_profiles(outdir=args.outdir, profiles=args.profiles, preview=args.preview)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
