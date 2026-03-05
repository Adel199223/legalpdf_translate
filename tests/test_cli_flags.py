from __future__ import annotations

from pathlib import Path

from legalpdf_translate import cli
from legalpdf_translate.queue_runner import QueueRunSummary
from legalpdf_translate.types import AnalyzeSummary, BudgetExceedPolicy, EffortPolicy, RunSummary


def test_cli_parser_accepts_analyze_only_flag() -> None:
    args = cli.build_arg_parser().parse_args(["--analyze-only"])
    assert args.analyze_only is True


def _stub_cli_settings(monkeypatch, *, glossary_file_path: str = "") -> None:
    monkeypatch.setattr(cli, "load_gui_settings", lambda: {"glossary_file_path": glossary_file_path})


def test_cli_defaults_to_stripping_bidi_controls(tmp_path: Path, monkeypatch) -> None:
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
    _stub_cli_settings(monkeypatch)

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
    assert captured["config"].strip_bidi_controls is True


def test_cli_can_preserve_bidi_controls(tmp_path: Path, monkeypatch) -> None:
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
    _stub_cli_settings(monkeypatch)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--preserve-bidi-controls",
        ]
    )

    assert exit_code == 0
    assert captured["config"].strip_bidi_controls is False


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
    _stub_cli_settings(monkeypatch)

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
    _stub_cli_settings(monkeypatch)

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
    _stub_cli_settings(monkeypatch)

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
    _stub_cli_settings(monkeypatch)

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


def test_cli_glossary_file_flag_overrides_settings(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()
    cli_glossary = tmp_path / "cli_glossary.json"
    cli_glossary.write_text('{"version":1,"rules":[]}', encoding="utf-8")
    settings_glossary = tmp_path / "settings_glossary.json"
    settings_glossary.write_text('{"version":1,"rules":[]}', encoding="utf-8")

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
    _stub_cli_settings(monkeypatch, glossary_file_path=str(settings_glossary))

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--glossary-file",
            str(cli_glossary),
        ]
    )

    assert exit_code == 0
    assert captured["config"].glossary_file == cli_glossary.resolve()


def test_cli_uses_settings_glossary_when_flag_missing(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()
    settings_glossary = tmp_path / "settings_glossary.json"
    settings_glossary.write_text('{"version":1,"rules":[]}', encoding="utf-8")

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
    _stub_cli_settings(monkeypatch, glossary_file_path=str(settings_glossary))

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
    assert captured["config"].glossary_file == settings_glossary.resolve()


def test_cli_budget_flags_are_parsed_and_wired(tmp_path: Path, monkeypatch) -> None:
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
    _stub_cli_settings(monkeypatch)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--budget-cap-usd",
            "2.5",
            "--cost-profile-id",
            "  legal_ops_profile  ",
            "--budget-on-exceed",
            "block",
        ]
    )

    assert exit_code == 0
    assert captured["config"].budget_cap_usd == 2.5
    assert captured["config"].cost_profile_id == "legal_ops_profile"
    assert captured["config"].budget_on_exceed == BudgetExceedPolicy.BLOCK


def test_cli_budget_policy_defaults_to_warn(tmp_path: Path, monkeypatch) -> None:
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
    _stub_cli_settings(monkeypatch)

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
    assert captured["config"].budget_on_exceed == BudgetExceedPolicy.WARN


def test_cli_rejects_negative_budget_cap(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)
    _stub_cli_settings(monkeypatch)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--budget-cap-usd",
            "-0.01",
        ]
    )

    assert exit_code == 1


def test_cli_review_export_flag_triggers_export(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()
    summary_path = outdir / "run_summary.json"
    summary_path.write_text("{}", encoding="utf-8")
    export_target = tmp_path / "exports" / "review_bundle"

    captured: dict[str, object] = {}

    class _FakeWorkflow:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            _ = kwargs

        def run(self, config):  # type: ignore[no-untyped-def]
            _ = config
            return RunSummary(
                success=True,
                exit_code=0,
                output_docx=outdir / "dummy.docx",
                partial_docx=None,
                run_dir=outdir,
                completed_pages=1,
                failed_page=None,
                run_summary_path=summary_path,
            )

    def _fake_export(*, summary_path: Path, output_path: Path):  # type: ignore[no-untyped-def]
        captured["summary_path"] = summary_path
        captured["output_path"] = output_path
        return (output_path.with_suffix(".csv"), output_path.with_suffix(".md"), 2)

    monkeypatch.setattr(cli, "TranslationWorkflow", _FakeWorkflow)
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)
    monkeypatch.setattr(cli, "export_review_queue", _fake_export)
    _stub_cli_settings(monkeypatch)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--review-export",
            str(export_target),
        ]
    )

    assert exit_code == 0
    assert captured["summary_path"] == summary_path
    assert captured["output_path"] == export_target


def test_cli_review_export_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()
    summary_path = outdir / "run_summary.json"
    summary_path.write_text("{}", encoding="utf-8")

    class _FakeWorkflow:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            _ = kwargs

        def run(self, config):  # type: ignore[no-untyped-def]
            _ = config
            return RunSummary(
                success=True,
                exit_code=0,
                output_docx=outdir / "dummy.docx",
                partial_docx=None,
                run_dir=outdir,
                completed_pages=1,
                failed_page=None,
                run_summary_path=summary_path,
            )

    def _explode_export(*, summary_path: Path, output_path: Path):  # type: ignore[no-untyped-def]
        _ = summary_path, output_path
        raise RuntimeError("export failed")

    monkeypatch.setattr(cli, "TranslationWorkflow", _FakeWorkflow)
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)
    monkeypatch.setattr(cli, "export_review_queue", _explode_export)
    _stub_cli_settings(monkeypatch)

    exit_code = cli.main(
        [
            "--pdf",
            str(pdf),
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
            "--review-export",
            str(tmp_path / "exports" / "bundle"),
        ]
    )

    assert exit_code == 0


def test_cli_parser_accepts_queue_flags() -> None:
    args = cli.build_arg_parser().parse_args(["--queue-manifest", "queue.jsonl", "--rerun-failed-only", "true"])
    assert args.queue_manifest == "queue.jsonl"
    assert args.rerun_failed_only == "true"


def test_cli_queue_mode_runs_manifest_jobs(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "queue.json"
    manifest_path.write_text("[]", encoding="utf-8")
    pdf_path = tmp_path / "queued.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
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

    def _fake_run_queue_manifest(  # type: ignore[no-untyped-def]
        *,
        manifest_path: Path,
        run_job,
        rerun_failed_only: bool,
        log_callback=None,
    ):
        _ = log_callback
        captured["manifest_path"] = manifest_path
        captured["rerun_failed_only"] = rerun_failed_only
        captured["run_job_result"] = run_job(
            {"pdf": str(pdf_path), "lang": "FR", "outdir": str(outdir), "workers": 2}
        )
        checkpoint_path = tmp_path / "queue.queue_checkpoint.json"
        summary_path = tmp_path / "queue.queue_summary.json"
        checkpoint_path.write_text("{}", encoding="utf-8")
        summary_path.write_text("{}", encoding="utf-8")
        return QueueRunSummary(
            success=True,
            total_jobs=1,
            done_jobs=1,
            failed_jobs=0,
            skipped_jobs=0,
            checkpoint_path=checkpoint_path,
            queue_summary_path=summary_path,
            jobs=[{"job_id": "job_0001", "status": "done"}],
        )

    monkeypatch.setattr(cli, "TranslationWorkflow", _FakeWorkflow)
    monkeypatch.setattr(cli, "run_queue_manifest", _fake_run_queue_manifest)
    monkeypatch.setattr(cli, "require_writable_output_dir_text", lambda _: outdir)
    _stub_cli_settings(monkeypatch)

    exit_code = cli.main(
        [
            "--queue-manifest",
            str(manifest_path),
            "--rerun-failed-only",
            "true",
            "--lang",
            "EN",
            "--outdir",
            str(outdir),
        ]
    )

    assert exit_code == 0
    assert captured["manifest_path"] == manifest_path.resolve()
    assert captured["rerun_failed_only"] is True
    assert getattr(captured["run_job_result"], "success", False) is True
    assert captured["config"].target_lang.value == "FR"


def test_cli_queue_mode_rejects_invalid_rerun_flag(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "queue.json"
    manifest_path.write_text("[]", encoding="utf-8")
    _stub_cli_settings(monkeypatch)
    exit_code = cli.main(
        [
            "--queue-manifest",
            str(manifest_path),
            "--rerun-failed-only",
            "maybe",
        ]
    )
    assert exit_code == 1
