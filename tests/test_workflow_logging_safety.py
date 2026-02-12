from __future__ import annotations

from pathlib import Path

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.types import ImageMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


def test_runtime_failure_logs_are_metadata_only(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)

    def _explode(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        raise RuntimeError("SENSITIVE_PAGE_TEXT_SHOULD_NOT_APPEAR")

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _explode)

    logs: list[str] = []
    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
    )
    summary = TranslationWorkflow(client=object(), log_callback=logs.append).run(config)

    assert summary.success is False
    assert any("exception_class=RuntimeError" in line for line in logs)
    assert all("SENSITIVE_PAGE_TEXT_SHOULD_NOT_APPEAR" not in line for line in logs)
