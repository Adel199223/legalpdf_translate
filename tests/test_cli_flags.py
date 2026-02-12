from __future__ import annotations

from pathlib import Path

from legalpdf_translate import cli
from legalpdf_translate.types import AnalyzeSummary, EffortPolicy, RunSummary


def test_cli_parser_accepts_analyze_only_flag() -> None:
    args = cli.build_arg_parser().parse_args(["--analyze-only"])
    assert args.analyze_only is True


def test_cli_effort_backward_compat_maps_fixed_policy(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    captured: dict[str, object] = {}

    class _FakeWorkflow:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            _ = kwargs

        def run(self, config):  # type: ignore[no-untyped-def]
            captured["config"] = config
            return RunSummary(
                success=True,
                exit_code=0,
                output_docx=outdir / "dummy.docx",
                partial_docx=None,
                run_dir=outdir,
                completed_pages=1,
                failed_page=None,
            )

    monkeypatch.setattr(cli, "TranslationWorkflow", _FakeWorkflow)
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--effort",
            "xhigh",
        ]
    )
    assert exit_code == 0
    assert captured["config"].effort_policy == EffortPolicy.FIXED_XHIGH


def test_cli_defaults_to_adaptive_policy_when_effort_not_explicit(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    captured: dict[str, object] = {}

    class _FakeWorkflow:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            _ = kwargs

        def run(self, config):  # type: ignore[no-untyped-def]
            captured["config"] = config
            return RunSummary(
                success=True,
                exit_code=0,
                output_docx=outdir / "dummy.docx",
                partial_docx=None,
                run_dir=outdir,
                completed_pages=1,
                failed_page=None,
            )

    monkeypatch.setattr(cli, "TranslationWorkflow", _FakeWorkflow)
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
        ]
    )

    assert exit_code == 0
    assert captured["config"].effort_policy == EffortPolicy.ADAPTIVE


def test_cli_effort_policy_overrides_effort(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    captured: dict[str, object] = {}

    class _FakeWorkflow:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            _ = kwargs

        def analyze(self, config):  # type: ignore[no-untyped-def]
            captured["config"] = config
            return AnalyzeSummary(
                run_dir=outdir,
                analyze_report_path=outdir / "analyze_report.json",
                selected_pages_count=1,
                pages_would_attach_images=0,
            )

    monkeypatch.setattr(cli, "TranslationWorkflow", _FakeWorkflow)
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--effort",
            "xhigh",
            "--effort-policy",
            "adaptive",
            "--analyze-only",
        ]
    )
    assert exit_code == 0
    assert captured["config"].effort_policy == EffortPolicy.ADAPTIVE


def test_cli_rejects_analyze_only_with_rebuild(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--analyze-only",
            "--rebuild-docx",
        ]
    )
    assert exit_code == 1
