from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import pytest

from legalpdf_translate import translation_service as service


def write_docx(path: Path, words: int) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>' + " ".join(["fictional"] * words)
            + '</w:t></w:r></w:p></w:body></w:document>',
        )


def completion_seed(docx: Path) -> dict:
    return {
        "translation_date": "2026-09-26", "case_number": "FICTIONAL-1",
        "case_entity": "Court", "case_city": "City", "court_email": "court@example.test",
        "run_id": "fictional-run", "target_lang": "AR", "pages": 1,
        "word_count": 10, "rate_per_word": .09, "expected_total": .90,
        "amount_paid": 0, "api_cost": .10, "profit": .80, "output_docx": str(docx),
    }


def completion_job(docx: Path) -> dict:
    return {"job_id": "fictional-job", "job_kind": "translate", "status": "completed",
            "result": {"save_seed": completion_seed(docx)},
            "artifacts": {"output_docx": str(docx)}}


@pytest.fixture(autouse=True)
def local_capabilities(monkeypatch):
    monkeypatch.setattr(service, "build_translation_capability_flags", lambda **_: {})


def test_completed_snapshot_recounts_reviewed_docx_without_mutating_original(tmp_path):
    docx = tmp_path / "reviewed.docx"
    write_docx(docx, 9)
    original = completion_job(docx)
    before = deepcopy(original)
    fresh = service.refresh_completed_translation_metrics(original)["result"]["save_seed"]
    assert (fresh["word_count"], fresh["expected_total"], fresh["profit"]) == (9, .81, .71)
    assert original == before


@pytest.mark.parametrize("edits, expected", [
    ({}, (.81, .71)),
    ({"expected_total": 12, "profit": 7}, (12, 7)),
    ({"expected_total": 12, "profit": 11.9}, (12, 11.9)),
    ({"rate_per_word": .10}, (.90, .80)),
    ({"amount_paid": 5}, (.81, 4.90)),
])
def test_reviewed_save_updates_only_calculated_amounts(tmp_path, edits, expected):
    docx = tmp_path / "reviewed.docx"
    write_docx(docx, 9)
    seed = completion_seed(docx)
    form = {**seed, "case_number": "EDITED-CASE", **edits}
    response = service.save_translation_row(
        settings_path=tmp_path / "settings.json", job_log_db_path=tmp_path / "jobs.sqlite",
        form_values=form, seed_payload=seed, word_count_docx=docx,
    )
    row = response["normalized_payload"]
    assert row["word_count"] == 9
    assert (row["expected_total"], row["profit"]) == expected
    assert row["case_number"] == "EDITED-CASE"


@pytest.mark.parametrize("contents", [None, b"not a docx", b"bad xml"])
def test_unreadable_reviewed_docx_blocks_before_row_or_settings_write(tmp_path, contents):
    docx = tmp_path / "reviewed.docx"
    if contents == b"bad xml":
        with ZipFile(docx, "w") as archive:
            archive.writestr("word/document.xml", contents)
    elif contents is not None:
        docx.write_bytes(contents)
    with pytest.raises(ValueError, match="reviewed translation DOCX"):
        service.save_translation_row(
            settings_path=tmp_path / "settings.json", job_log_db_path=tmp_path / "jobs.sqlite",
            form_values=completion_seed(docx), seed_payload=completion_seed(docx), word_count_docx=docx,
        )
    assert not (tmp_path / "jobs.sqlite").exists()
    assert not (tmp_path / "settings.json").exists()


def test_historical_record_edit_does_not_require_or_recount_old_artifact(tmp_path):
    seed = completion_seed(tmp_path / "no-longer-present.docx")
    response = service.save_translation_row(
        settings_path=tmp_path / "settings.json", job_log_db_path=tmp_path / "jobs.sqlite",
        form_values={**seed, "word_count": 123, "expected_total": 12, "profit": 8}, seed_payload=seed,
    )
    assert response["normalized_payload"]["word_count"] == 123
    assert response["normalized_payload"]["expected_total"] == 12
