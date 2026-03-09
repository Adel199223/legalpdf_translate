from pathlib import Path

import pytest
from docx import Document

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.checkpoint import (
    build_run_paths,
    ensure_run_dirs,
    is_resume_compatible,
    list_completed_pages,
    load_run_state,
    mark_page_done,
    new_run_state,
    save_run_state_atomic,
    sha256_of_file,
    sha256_of_text,
)
from legalpdf_translate.types import ImageMode, PageStatus, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow, _PageOutcome


def _config(tmp_path: Path, pdf_path: Path) -> RunConfig:
    return RunConfig(
        pdf_path=pdf_path,
        output_dir=tmp_path / "out",
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        max_pages=3,
        resume=True,
        page_breaks=True,
        keep_intermediates=True,
    )


def test_run_state_atomic_save_and_load(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"fake")
    config = _config(tmp_path, pdf)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang, run_started_at="20260211_010101")
    ensure_run_dirs(paths)

    state = new_run_state(
        config=config,
        paths=paths,
        pdf_fingerprint=sha256_of_file(pdf),
        context_hash=sha256_of_text(None),
        total_pages=8,
        selected_pages=[1, 2, 3],
    )
    save_run_state_atomic(paths.run_state_path, state)
    assert paths.run_state_path.exists()
    assert not paths.run_state_path.with_suffix(".tmp").exists()

    loaded = load_run_state(paths.run_state_path)
    assert loaded is not None
    assert loaded.total_pages == 8
    assert loaded.max_pages_effective == 3
    assert loaded.selection_start_page == 1
    assert loaded.selection_end_page == 3
    assert loaded.selection_page_count == 3
    assert loaded.frozen_outdir_abs == str(paths.frozen_outdir)
    assert loaded.run_dir_abs == str(paths.run_dir)
    assert loaded.run_started_at == "20260211_010101"


def test_resume_compatibility_and_done_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"fake")
    config = _config(tmp_path, pdf)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang, run_started_at="20260211_020202")
    state = new_run_state(
        config=config,
        paths=paths,
        pdf_fingerprint=sha256_of_file(pdf),
        context_hash=sha256_of_text("ctx"),
        total_pages=5,
        selected_pages=[1, 2, 3],
    )
    mark_page_done(state, 1, image_used=False, retry_used=False, usage={})
    assert list_completed_pages(state) == [1]

    assert is_resume_compatible(
        state,
        config=config,
        paths=paths,
        pdf_fingerprint=sha256_of_file(pdf),
        context_hash=sha256_of_text("ctx"),
        selection_start_page=1,
        selection_end_page=3,
        selection_page_count=3,
        max_pages_effective=3,
    )
    assert not is_resume_compatible(
        state,
        config=config,
        paths=paths,
        pdf_fingerprint=sha256_of_file(pdf),
        context_hash=sha256_of_text("different"),
        selection_start_page=1,
        selection_end_page=3,
        selection_page_count=3,
        max_pages_effective=3,
    )


def test_resume_compatibility_tolerates_missing_glossary_fingerprint_key(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"fake")
    config = _config(tmp_path, pdf)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang, run_started_at="20260213_010101")
    state = new_run_state(
        config=config,
        paths=paths,
        pdf_fingerprint=sha256_of_file(pdf),
        context_hash=sha256_of_text("ctx"),
        total_pages=5,
        selected_pages=[1, 2, 3],
    )
    state.settings.pop("glossary_file_path", None)

    assert is_resume_compatible(
        state,
        config=config,
        paths=paths,
        pdf_fingerprint=sha256_of_file(pdf),
        context_hash=sha256_of_text("ctx"),
        selection_start_page=1,
        selection_end_page=3,
        selection_page_count=3,
        max_pages_effective=3,
    )


def test_resume_mismatch_is_explicit_and_does_not_start_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    outdir = tmp_path / "out"
    outdir.mkdir()

    base_config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        start_page=1,
        end_page=2,
        max_pages=2,
        resume=True,
        page_breaks=True,
        keep_intermediates=True,
    )
    paths = build_run_paths(base_config.output_dir, base_config.pdf_path, base_config.target_lang)
    ensure_run_dirs(paths)
    state = new_run_state(
        config=base_config,
        paths=paths,
        pdf_fingerprint=sha256_of_text("pdf-fingerprint"),
        context_hash=sha256_of_text(None),
        total_pages=6,
        selected_pages=[1, 2],
    )
    save_run_state_atomic(paths.run_state_path, state)

    mismatch_config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        start_page=2,
        end_page=3,
        max_pages=2,
        resume=True,
        page_breaks=True,
        keep_intermediates=True,
    )

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 6)
    monkeypatch.setattr(workflow_module, "sha256_of_file", lambda _pdf: sha256_of_text("pdf-fingerprint"))

    started_processing = False

    def _forbid_process_page(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal started_processing
        started_processing = True
        raise AssertionError("_process_page must not run on incompatible resume")

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _forbid_process_page)

    workflow = TranslationWorkflow(client=object())
    with pytest.raises(ValueError, match="Checkpoint is incompatible with current run settings"):
        workflow.run(mismatch_config)
    assert started_processing is False


def test_load_run_state_returns_none_for_corrupt_json(tmp_path: Path) -> None:
    run_state_path = tmp_path / "run_state.json"
    run_state_path.write_text("{not-valid-json", encoding="utf-8")

    assert load_run_state(run_state_path) is None


def test_workflow_logs_unreadable_checkpoint_and_starts_new_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=True,
        page_breaks=True,
        keep_intermediates=True,
    )
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
    ensure_run_dirs(paths)
    paths.run_state_path.write_text("{invalid-json", encoding="utf-8")

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)

    def _fake_process_page(
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):  # type: ignore[no-untyped-def]
        page_path = paths.pages_dir / f"page_{page_number:04d}.txt"
        page_path.write_text("OK", encoding="utf-8")
        return _PageOutcome(
            status=PageStatus.DONE,
            image_used=False,
            retry_used=False,
            usage={},
            error=None,
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fake_process_page)
    logs: list[str] = []
    workflow = TranslationWorkflow(client=object(), log_callback=logs.append)
    summary = workflow.run(config)

    assert summary.success is True
    assert any("run_state.json is unreadable" in line for line in logs)


def test_completed_checkpoint_with_missing_page_outputs_starts_fresh_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=True,
        page_breaks=True,
        keep_intermediates=False,
    )
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
    ensure_run_dirs(paths)
    stale_run_id = "20260307_232630"
    state = new_run_state(
        config=config,
        paths=build_run_paths(
            config.output_dir,
            config.pdf_path,
            config.target_lang,
            run_started_at=stale_run_id,
        ),
        pdf_fingerprint=sha256_of_text("pdf-fingerprint"),
        context_hash=sha256_of_text(None),
        total_pages=1,
        selected_pages=[1],
    )
    mark_page_done(state, 1, image_used=False, retry_used=False, usage={})
    state.run_status = "completed"
    state.finished_at = "2026-03-07T23:27:00+00:00"
    state.done_count = 1
    state.pending_count = 0
    state.run_dir_abs = str(paths.run_dir)
    state.frozen_outdir_abs = str(paths.frozen_outdir)
    state.run_started_at = stale_run_id
    save_run_state_atomic(paths.run_state_path, state)

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "sha256_of_file", lambda _pdf: sha256_of_text("pdf-fingerprint"))

    called_pages: list[int] = []

    def _fake_process_page(
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):  # type: ignore[no-untyped-def]
        called_pages.append(page_number)
        page_path = paths.pages_dir / f"page_{page_number:04d}.txt"
        page_path.write_text("OK", encoding="utf-8")
        return _PageOutcome(
            status=PageStatus.DONE,
            image_used=False,
            retry_used=False,
            usage={},
            error=None,
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fake_process_page)
    logs: list[str] = []
    workflow = TranslationWorkflow(client=object(), log_callback=logs.append)
    summary = workflow.run(config)

    assert summary.success is True
    assert called_pages == [1]
    assert summary.output_docx is not None
    assert stale_run_id not in summary.output_docx.name
    assert Document(summary.output_docx).paragraphs[0].text == "OK"

    refreshed = load_run_state(paths.run_state_path)
    assert refreshed is not None
    assert refreshed.run_started_at != stale_run_id
    assert any("saved page files are missing" in line for line in logs)
