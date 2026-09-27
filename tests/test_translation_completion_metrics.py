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
    assert (fresh["word_count"], fresh["expected_total"], fresh["profit"]) == (9, .81, None)
    assert original == before


@pytest.mark.parametrize("edits, expected", [
    ({}, (.81, None)),
    ({"expected_total": 12, "profit": 7}, (12, None)),
    ({"expected_total": 12, "profit": 11.9}, (12, None)),
    ({"rate_per_word": .10}, (.90, None)),
    ({"amount_paid": 5}, (.81, None)),
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


@pytest.mark.parametrize("lang", ["AR", "EN", "FR"])
@pytest.mark.parametrize("mode,total", [("auto", 30.73), ("manual", 91.04)])
def test_rate_and_current_word_count_save_reconciles_explicit_mode(tmp_path, lang, mode, total):
    docx = tmp_path / "reviewed.docx"
    write_docx(docx, 1138)
    seed = {**completion_seed(docx), "lang": lang, "target_lang": lang,
            "word_count": 1132, "expected_total": 90.56, "rate_per_word": .08}
    response = service.save_translation_row(
        settings_path=tmp_path / "settings.json", job_log_db_path=tmp_path / "jobs.sqlite",
        seed_payload=seed, word_count_docx=docx,
        form_values={**seed, "word_count": 1138, "rate_per_word": "0,027",
                     "expected_total": 91.04, "expected_total_mode": mode},
    )
    row = response["normalized_payload"]
    assert (row["word_count"], row["rate_per_word"], row["expected_total"], row["profit"]) == (1138, .027, total, None)


def test_historical_finance_and_null_profit_round_trip_without_default_promotion(tmp_path):
    import json
    import sqlite3

    settings, db = tmp_path / "settings.json", tmp_path / "jobs.sqlite"
    settings.write_text(json.dumps({"default_rate_per_word": {"EN": .027, "FR": .027, "AR": .027}}))
    seed = completion_seed(tmp_path / "missing.docx")
    first = service.save_translation_row(settings_path=settings, job_log_db_path=db,
        seed_payload=seed, form_values=seed)
    row_id = first["saved_result"]["row_id"]
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE job_runs SET profit=12.34567, api_cost=0.1648255 WHERE id=?", (row_id,))
    history = service.list_translation_history(db_path=db)[0]
    saved = service.save_translation_row(settings_path=settings, job_log_db_path=db, row_id=row_id,
        seed_payload=history["seed"], form_values={**history["seed"], "case_number": "CHANGED",
            "expected_total_mode": "manual", "profit": 999})["normalized_payload"]
    assert saved["rate_per_word"] == .09
    assert saved["expected_total"] == .90
    assert saved["profit"] == 12.34567
    assert saved["api_cost"] == .1648255
    assert service.list_translation_history(db_path=db)[0]["row"]["case_number"] == "CHANGED"
    assert json.loads(settings.read_text())["default_rate_per_word"] == dict.fromkeys(["EN", "FR", "AR"], .027)


def test_explicit_zero_manual_fee_is_not_replaced_by_seed(tmp_path):
    seed = completion_seed(tmp_path / "unused.docx")
    saved = service.save_translation_row(settings_path=tmp_path / "settings.json", job_log_db_path=tmp_path / "jobs.sqlite",
        seed_payload=seed, form_values={**seed, "rate_per_word": 0, "expected_total": 0,
            "api_cost": 0, "expected_total_mode": "manual"})["normalized_payload"]
    assert (saved["rate_per_word"], saved["expected_total"], saved["api_cost"]) == (0, 0, 0)
