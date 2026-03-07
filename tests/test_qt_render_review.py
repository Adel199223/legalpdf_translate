from __future__ import annotations

import os
import sys
from pathlib import Path

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TOOLING_ROOT = Path(__file__).resolve().parents[1] / "tooling"
if str(TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLING_ROOT))

from PySide6.QtWidgets import QApplication

import qt_render_review as render_tool


def test_resolve_profiles_rejects_unknown_name() -> None:
    try:
        render_tool.resolve_profiles(["wide", "unknown"])
    except ValueError as exc:
        assert "unknown" in str(exc).lower()
    else:
        raise AssertionError("Expected unknown profile rejection.")


def test_apply_reference_sample_sets_preview_values() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = render_tool.QtMainWindow()
    try:
        render_tool.apply_reference_sample(window)
        assert window.title_label.text() == "LegalPDF Translate"
        assert window.pdf_edit.text() == "test_document.pdf"
        assert window.pages_label.text() == "Pages: 25"
        assert window.outdir_edit.text() == "C:/Users/FA507/Downloads"
        assert window.progress.value() == 50
        assert window.progress_eta_label.text() == "Est. remaining: ~2m"
        assert "Translating text blocks" in window.status_label.text()
        assert window.metric_pages_value_label.text() == "12 / 25"
        assert window.metric_images_value_label.text() == "3 / 3"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_render_profiles_writes_png_and_metadata(tmp_path: Path) -> None:
    results = render_tool.render_profiles(outdir=tmp_path, profiles=["wide"], preview="reference_sample")
    assert len(results) == 1
    result = results[0]
    png_path = tmp_path / "wide.png"
    meta_path = tmp_path / "wide.json"
    assert png_path.exists()
    assert png_path.stat().st_size > 0
    assert meta_path.exists()
    assert result["profile"] == "wide"
    assert result["layout_mode"] == "desktop_exact"
