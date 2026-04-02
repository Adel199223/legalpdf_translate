from __future__ import annotations

import json
from pathlib import Path
import sys

from docx import Document

TOOLING_ROOT = Path(__file__).resolve().parents[1] / "tooling"
if str(TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLING_ROOT))

import render_docx as render_tool


def _write_docx(path: Path, *paragraphs: str) -> Path:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    return path


def test_resolve_soffice_path_detects_localappdata_install(monkeypatch, tmp_path: Path) -> None:
    soffice_dir = tmp_path / "LocalAppData" / "Programs" / "LibreOffice" / "program"
    soffice = soffice_dir / "soffice.exe"
    soffice_cli = soffice_dir / "soffice.com"
    soffice.parent.mkdir(parents=True, exist_ok=True)
    soffice.write_bytes(b"")
    soffice_cli.write_bytes(b"")
    monkeypatch.setattr(render_tool.shutil, "which", lambda name: None)

    resolved = render_tool._resolve_soffice_path(
        environment={
            "LOCALAPPDATA": str(tmp_path / "LocalAppData"),
            "ProgramFiles": str(tmp_path / "ProgramFiles"),
            "ProgramFiles(x86)": str(tmp_path / "ProgramFilesX86"),
        }
    )

    assert resolved == soffice_cli.resolve()


def test_resolve_soffice_path_prefers_cli_adjacent_to_override(tmp_path: Path) -> None:
    soffice_dir = tmp_path / "LibreOffice" / "program"
    soffice_exe = soffice_dir / "soffice.exe"
    soffice_cli = soffice_dir / "soffice.com"
    soffice_dir.mkdir(parents=True, exist_ok=True)
    soffice_exe.write_bytes(b"")
    soffice_cli.write_bytes(b"")

    resolved = render_tool._resolve_soffice_path(
        environment={
            render_tool.SOFFICE_ENV: str(soffice_exe),
        }
    )

    assert resolved == soffice_cli.resolve()


def test_normalize_soffice_stderr_ignores_known_benign_warning() -> None:
    kept, ignored = render_tool._normalize_soffice_stderr(
        "Could not find platform independent libraries <prefix>\nReal warning\n"
    )

    assert kept == "Real warning"
    assert ignored == ["Could not find platform independent libraries <prefix>"]


def test_resolve_pdftoppm_path_accepts_env_bin_dir(tmp_path: Path) -> None:
    bin_dir = tmp_path / "poppler" / "Library" / "bin"
    pdftoppm = bin_dir / "pdftoppm.exe"
    pdftoppm.parent.mkdir(parents=True, exist_ok=True)
    pdftoppm.write_bytes(b"")

    resolved = render_tool._resolve_pdftoppm_path(
        environment={
            render_tool.POPPLER_ENV: str(bin_dir),
        }
    )

    assert resolved == pdftoppm.resolve()


def test_resolve_pdftoppm_path_detects_winget_nested_package_layout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pdftoppm = (
        tmp_path
        / "LocalAppData"
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "poppler-25.07.0"
        / "Library"
        / "bin"
        / "pdftoppm.exe"
    )
    pdftoppm.parent.mkdir(parents=True, exist_ok=True)
    pdftoppm.write_bytes(b"")
    monkeypatch.setattr(render_tool.shutil, "which", lambda name: None)

    resolved = render_tool._resolve_pdftoppm_path(
        environment={
            "LOCALAPPDATA": str(tmp_path / "LocalAppData"),
            "ProgramFiles": str(tmp_path / "ProgramFiles"),
        }
    )

    assert resolved == pdftoppm.resolve()


def test_render_docx_returns_structural_fallback_when_visual_tooling_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_docx = _write_docx(tmp_path / "input.docx", "Paragraph one", "Paragraph two")
    monkeypatch.setattr(render_tool, "_resolve_soffice_path", lambda **kwargs: None)
    monkeypatch.setattr(render_tool, "_resolve_pdftoppm_path", lambda **kwargs: None)
    monkeypatch.setattr(render_tool, "_load_pdf2image_convert", lambda: (None, "No module named 'pdf2image'"))

    result = render_tool.render_docx(
        input_path=input_docx,
        outdir=tmp_path / "rendered",
    )

    assert result["status"] == "fallback"
    assert result["fallback_mode"] == "structural_only_missing_soffice_pdftoppm_pdf2image"
    assert result["docx_summary"]["non_empty_paragraph_count"] == 2
    assert Path(result["summary_path"]).exists()


def test_render_docx_writes_pdf_pngs_and_summary(monkeypatch, tmp_path: Path) -> None:
    input_docx = _write_docx(tmp_path / "input.docx", "Paragraph one")
    outdir = tmp_path / "rendered"
    fake_soffice = tmp_path / "LibreOffice" / "program" / "soffice.exe"
    fake_pdftoppm = tmp_path / "Poppler" / "Library" / "bin" / "pdftoppm.exe"
    fake_soffice.parent.mkdir(parents=True, exist_ok=True)
    fake_pdftoppm.parent.mkdir(parents=True, exist_ok=True)
    fake_soffice.write_bytes(b"")
    fake_pdftoppm.write_bytes(b"")

    def _fake_convert_docx_to_pdf(*, input_path: Path, outdir: Path, soffice_path: Path):
        pdf_path = outdir / f"{input_path.stem}.pdf"
        outdir.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.7\n")
        return pdf_path, {"command": [str(soffice_path), "--headless"], "stdout": "OK", "stderr": ""}

    def _fake_rasterize(*, pdf_path: Path, outdir: Path, pdftoppm_path: Path, convert_from_path):
        first = outdir / f"{pdf_path.stem}-001.png"
        second = outdir / f"{pdf_path.stem}-002.png"
        first.write_bytes(b"png")
        second.write_bytes(b"png")
        return [first.resolve(), second.resolve()]

    monkeypatch.setattr(render_tool, "_resolve_soffice_path", lambda **kwargs: fake_soffice.resolve())
    monkeypatch.setattr(render_tool, "_resolve_pdftoppm_path", lambda **kwargs: fake_pdftoppm.resolve())
    monkeypatch.setattr(render_tool, "_load_pdf2image_convert", lambda: (lambda *args, **kwargs: [], ""))
    monkeypatch.setattr(render_tool, "_convert_docx_to_pdf", _fake_convert_docx_to_pdf)
    monkeypatch.setattr(render_tool, "_rasterize_pdf_to_pngs", _fake_rasterize)

    result = render_tool.render_docx(
        input_path=input_docx,
        outdir=outdir,
    )

    assert result["status"] == "ok"
    assert result["page_count"] == 2
    assert result["pdf_path"].endswith("input.pdf")
    assert len(result["page_image_paths"]) == 2
    summary_path = Path(result["summary_path"])
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["soffice_path"] == str(fake_soffice.resolve())
    assert summary["pdftoppm_path"] == str(fake_pdftoppm.resolve())


def test_build_arg_parser_defaults_to_tmp_docs_dir() -> None:
    parser = render_tool.build_arg_parser()
    args = parser.parse_args(["--input", "example.docx"])
    assert args.outdir == render_tool.DEFAULT_OUTDIR
