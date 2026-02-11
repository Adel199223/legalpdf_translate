from pathlib import Path

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
from legalpdf_translate.types import ImageMode, ReasoningEffort, RunConfig, TargetLang


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
