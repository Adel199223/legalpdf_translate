from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.checkpoint import build_run_paths, load_run_state
from legalpdf_translate.types import ImageMode, PageStatus, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow, _PageOutcome


def _config(pdf: Path, outdir: Path, *, workers: int, max_pages: int) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        max_pages=max_pages,
        workers=workers,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
    )


def test_parallel_completion_does_not_break_ordering(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir_serial = tmp_path / "out_serial"
    outdir_parallel = tmp_path / "out_parallel"
    outdir_serial.mkdir()
    outdir_parallel.mkdir()

    total_pages = 6
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: total_pages)

    completion_order: list[int] = []
    completion_lock = threading.Lock()

    def _fake_process_page(
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):  # type: ignore[no-untyped-def]
        # Force out-of-order completion when workers > 1.
        if config.workers > 1:
            time.sleep((total_pages - page_number) * 0.2)
        page_path = paths.pages_dir / f"page_{page_number:04d}.txt"
        page_path.write_text(f"PAGE {page_number}", encoding="utf-8")
        if config.workers > 1:
            with completion_lock:
                completion_order.append(page_number)
        return _PageOutcome(
            status=PageStatus.DONE,
            image_used=False,
            retry_used=False,
            usage={},
            error=None,
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fake_process_page)

    serial_summary = TranslationWorkflow(client=object()).run(
        _config(pdf, outdir_serial, workers=1, max_pages=total_pages)
    )
    parallel_summary = TranslationWorkflow(client=object()).run(
        _config(pdf, outdir_parallel, workers=4, max_pages=total_pages)
    )

    assert serial_summary.success is True
    assert parallel_summary.success is True

    serial_paths = build_run_paths(outdir_serial, pdf, TargetLang.EN)
    parallel_paths = build_run_paths(outdir_parallel, pdf, TargetLang.EN)
    serial_page_texts = [path.read_text(encoding="utf-8") for path in sorted(serial_paths.pages_dir.glob("page_*.txt"))]
    parallel_page_texts = [
        path.read_text(encoding="utf-8") for path in sorted(parallel_paths.pages_dir.glob("page_*.txt"))
    ]
    expected = [f"PAGE {page}" for page in range(1, total_pages + 1)]
    assert serial_page_texts == expected
    assert parallel_page_texts == expected
    assert completion_order != sorted(completion_order)


def test_run_state_stays_consistent_under_parallel_completion(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    total_pages = 8
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: total_pages)

    def _fake_process_page(
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):  # type: ignore[no-untyped-def]
        time.sleep((total_pages - page_number) * 0.01)
        page_path = paths.pages_dir / f"page_{page_number:04d}.txt"
        page_path.write_text(f"PAGE {page_number}", encoding="utf-8")
        return _PageOutcome(
            status=PageStatus.DONE,
            image_used=False,
            retry_used=False,
            usage={"attempt_1": {"total_tokens": page_number}},
            error=None,
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fake_process_page)

    summary = TranslationWorkflow(client=object()).run(_config(pdf, outdir, workers=4, max_pages=total_pages))
    assert summary.success is True

    run_paths = build_run_paths(outdir, pdf, TargetLang.EN)
    raw_state = run_paths.run_state_path.read_text(encoding="utf-8")
    parsed = json.loads(raw_state)
    assert isinstance(parsed, dict)

    loaded = load_run_state(run_paths.run_state_path)
    assert loaded is not None
    assert loaded.run_status == "completed"
    assert loaded.done_count == total_pages
    assert loaded.failed_count == 0
    assert loaded.pending_count == 0
    for page_number in range(1, total_pages + 1):
        assert loaded.pages[str(page_number)]["status"] == PageStatus.DONE.value


def test_stop_submitting_after_first_hard_failure(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    total_pages = 8
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: total_pages)

    started_pages: list[int] = []
    started_lock = threading.Lock()

    def _fake_process_page(
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):  # type: ignore[no-untyped-def]
        with started_lock:
            started_pages.append(page_number)
        if page_number == 2:
            return _PageOutcome(
                status=PageStatus.FAILED,
                image_used=False,
                retry_used=True,
                usage={"attempt_1": {"total_tokens": 10}},
                error="runtime_failure",
            )
        if page_number in (1, 3):
            time.sleep(0.15)
        page_path = paths.pages_dir / f"page_{page_number:04d}.txt"
        page_path.write_text(f"PAGE {page_number}", encoding="utf-8")
        return _PageOutcome(
            status=PageStatus.DONE,
            image_used=False,
            retry_used=False,
            usage={"attempt_1": {"total_tokens": 10}},
            error=None,
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fake_process_page)

    summary = TranslationWorkflow(client=object()).run(_config(pdf, outdir, workers=3, max_pages=total_pages))
    assert summary.success is False
    assert summary.failed_page == 2
    assert summary.error == "runtime_failure"
    assert set(started_pages).issubset({1, 2, 3})

    run_paths = build_run_paths(outdir, pdf, TargetLang.EN)
    loaded = load_run_state(run_paths.run_state_path)
    assert loaded is not None
    assert loaded.run_status == "runtime_failure"
    assert loaded.halt_reason is not None
    assert "page 2" in loaded.halt_reason.lower()
    for page_number in range(4, total_pages + 1):
        assert loaded.pages[str(page_number)]["status"] == PageStatus.PENDING.value
