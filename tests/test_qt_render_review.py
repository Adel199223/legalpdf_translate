from __future__ import annotations

import os
import json
import subprocess
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
    assert result["dashboard_frame_width"] == 1200
    assert result["dashboard_frame_x"] == (result["content_card_width"] - result["dashboard_frame_width"]) // 2
    assert result["dashboard_frame_y"] > 0
    assert result["setup_panel_width"] > result["progress_panel_width"]
    assert result["footer_card_width"] < result["dashboard_frame_width"]


def test_render_profiles_ignore_live_screen_geometry(tmp_path: Path) -> None:
    script = f"""
import json
import sys
from pathlib import Path
from PySide6.QtCore import QRect

repo_root = Path({str(Path(__file__).resolve().parents[1])!r})
tooling_root = repo_root / "tooling"
src_root = repo_root / "src"
if str(tooling_root) not in sys.path:
    sys.path.insert(0, str(tooling_root))
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

import qt_render_review as render_tool
from legalpdf_translate.qt_gui import window_adaptive as window_adaptive_module

window_adaptive_module.available_screen_geometry = lambda _widget: QRect(0, 0, 980, 760)
result = render_tool.render_profiles(
    outdir=Path({str(tmp_path)!r}),
    profiles=["wide"],
    preview="reference_sample",
)[0]
print(json.dumps(result))
"""
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    metadata = json.loads(result.stdout.strip())

    assert metadata["profile"] == "wide"
    assert metadata["layout_mode"] == "desktop_exact"
    assert metadata["dashboard_frame_width"] == 1200
    assert metadata["dashboard_frame_x"] == (metadata["content_card_width"] - metadata["dashboard_frame_width"]) // 2


def test_build_arg_parser_defaults_to_ignored_tmp_dir() -> None:
    parser = render_tool.build_arg_parser()
    args = parser.parse_args([])
    assert args.outdir == render_tool.REPO_ROOT / "tmp" / "qt_ui_review"


def test_render_gmail_review_dialog_sample_writes_png_and_metadata(tmp_path: Path) -> None:
    result = render_tool.render_gmail_review_dialog_sample(outdir=tmp_path)
    png_path = tmp_path / "gmail_review.png"
    meta_path = tmp_path / "gmail_review.json"
    assert png_path.exists()
    assert png_path.stat().st_size > 0
    assert meta_path.exists()
    assert result["sample"] == "gmail_review"
    assert result["row_count"] == 2


def test_render_gmail_preview_dialog_sample_writes_png_and_metadata(tmp_path: Path) -> None:
    result = render_tool.render_gmail_preview_dialog_sample(outdir=tmp_path)
    png_path = tmp_path / "gmail_preview.png"
    meta_path = tmp_path / "gmail_preview.json"
    assert png_path.exists()
    assert png_path.stat().st_size > 0
    assert meta_path.exists()
    assert result["sample"] == "gmail_preview"
    assert result["page_count"] == 6
