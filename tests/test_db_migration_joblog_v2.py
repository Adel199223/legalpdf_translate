from __future__ import annotations

import sqlite3
from pathlib import Path

from legalpdf_translate.joblog_db import delete_job_run, delete_job_runs, open_job_log, update_job_run


def _column_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(job_runs)").fetchall()
    return {str(row[1]) for row in rows}


def test_migration_adds_v2_columns_and_backfills(tmp_path: Path) -> None:
    db_path = tmp_path / "job_log.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            completed_at TEXT NOT NULL,
            case_number TEXT,
            entity TEXT,
            city TEXT,
            lang TEXT,
            pages INTEGER,
            word_count INTEGER,
            rate_per_word REAL,
            expected_total REAL,
            amount_paid REAL,
            api_cost REAL,
            profit REAL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO job_runs (
            completed_at, case_number, entity, city, lang, pages, word_count,
            rate_per_word, expected_total, amount_paid, api_cost, profit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-02-11T10:30:00",
            "140/22.5JAFAR",
            "Tribunal Judicial de Beja",
            "Beja",
            "EN",
            5,
            1200,
            0.08,
            96.0,
            0.0,
            2.0,
            94.0,
        ),
    )
    conn.commit()
    conn.close()

    migrated = open_job_log(db_path)
    columns = _column_names(migrated)
    assert "case_entity" in columns
    assert "case_city" in columns
    assert "service_entity" in columns
    assert "service_city" in columns
    assert "service_date" in columns
    assert "travel_km_outbound" in columns
    assert "travel_km_return" in columns
    assert "use_service_location_in_honorarios" in columns
    assert "translation_date" in columns
    assert "run_id" in columns
    assert "target_lang" in columns
    assert "total_tokens" in columns
    assert "court_email" in columns
    assert "estimated_api_cost" in columns
    assert "quality_risk_score" in columns
    assert "output_docx_path" in columns
    assert "partial_docx_path" in columns
    assert "header_text" not in columns
    assert "ocr_text" not in columns
    assert "extracted_text" not in columns

    row = migrated.execute(
        """
        SELECT case_entity, case_city, service_entity, service_city, service_date, translation_date,
               target_lang, court_email, estimated_api_cost, run_id, total_tokens, quality_risk_score,
               travel_km_outbound, travel_km_return, use_service_location_in_honorarios,
               output_docx_path, partial_docx_path
        FROM job_runs
        LIMIT 1
        """
    ).fetchone()
    migrated.close()

    assert row is not None
    assert row[0] == "Tribunal Judicial de Beja"
    assert row[1] == "Beja"
    assert row[2] == "Tribunal Judicial de Beja"
    assert row[3] == "Beja"
    assert row[4] == "2026-02-11"
    assert row[5] == "2026-02-11"
    assert row[6] == "EN"
    assert row[7] is None
    assert float(row[8]) == 2.0
    assert row[9] is None
    assert row[10] is None
    assert row[11] is None
    assert row[12] is None
    assert row[13] is None
    assert row[14] == 0
    assert row[15] is None
    assert row[16] is None


def test_update_job_run_updates_only_selected_fields_and_preserves_paths(tmp_path: Path) -> None:
    db_path = tmp_path / "job_log.sqlite3"
    with open_job_log(db_path) as conn:
        row_id = conn.execute(
            """
            INSERT INTO job_runs (
                completed_at,
                translation_date,
                job_type,
                case_number,
                case_entity,
                case_city,
                service_entity,
                service_city,
                service_date,
                lang,
                target_lang,
                run_id,
                pages,
                word_count,
                total_tokens,
                rate_per_word,
                expected_total,
                amount_paid,
                api_cost,
                estimated_api_cost,
                quality_risk_score,
                profit,
                output_docx_path,
                partial_docx_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-03-06T16:58:34",
                "2026-03-06",
                "Translation",
                "109/26.0PBBJA",
                "Juizo Local Criminal de Beja",
                "Beja",
                "Juizo Local Criminal de Beja",
                "Beja",
                "2026-03-06",
                "AR",
                "AR",
                "run-1",
                7,
                1666,
                57126,
                0.09,
                149.94,
                0.0,
                0.56,
                0.56,
                0.1754,
                149.38,
                "C:/tmp/out.docx",
                "C:/tmp/out_partial.docx",
            ),
        ).lastrowid
        update_job_run(
            conn,
            row_id=int(row_id),
            values={
                "job_type": "Interpretation",
                "pages": 9,
                "travel_km_outbound": 39.0,
                "travel_km_return": 39.0,
                "use_service_location_in_honorarios": 1,
                "profit": 100.0,
            },
        )
        row = conn.execute(
            """
            SELECT id, job_type, pages, travel_km_outbound, travel_km_return,
                   use_service_location_in_honorarios, profit, output_docx_path, partial_docx_path, case_number
            FROM job_runs
            WHERE id = ?
            """,
            (int(row_id),),
        ).fetchone()

    assert row is not None
    assert int(row[0]) == int(row_id)
    assert row[1] == "Interpretation"
    assert int(row[2]) == 9
    assert float(row[3]) == 39.0
    assert float(row[4]) == 39.0
    assert int(row[5]) == 1
    assert float(row[6]) == 100.0
    assert row[7] == "C:/tmp/out.docx"
    assert row[8] == "C:/tmp/out_partial.docx"
    assert row[9] == "109/26.0PBBJA"


def test_delete_job_run_removes_only_selected_row(tmp_path: Path) -> None:
    db_path = tmp_path / "job_log.sqlite3"
    with open_job_log(db_path) as conn:
        first_id = conn.execute(
            """
            INSERT INTO job_runs (
                completed_at,
                translation_date,
                case_number,
                case_entity,
                case_city,
                service_entity,
                service_city,
                service_date,
                lang,
                target_lang
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-03-05T10:00:00",
                "2026-03-05",
                "case-1",
                "Entity 1",
                "Beja",
                "Entity 1",
                "Beja",
                "2026-03-05",
                "AR",
                "AR",
            ),
        ).lastrowid
        second_id = conn.execute(
            """
            INSERT INTO job_runs (
                completed_at,
                translation_date,
                case_number,
                case_entity,
                case_city,
                service_entity,
                service_city,
                service_date,
                lang,
                target_lang
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-03-06T10:00:00",
                "2026-03-06",
                "case-2",
                "Entity 2",
                "Beja",
                "Entity 2",
                "Beja",
                "2026-03-06",
                "FR",
                "FR",
            ),
        ).lastrowid
        delete_job_run(conn, row_id=int(first_id))
        rows = conn.execute(
            "SELECT id, case_number, lang FROM job_runs ORDER BY id"
        ).fetchall()

    assert [tuple(row) for row in rows] == [(int(second_id), "case-2", "FR")]


def test_delete_job_runs_removes_only_selected_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "job_log.sqlite3"
    with open_job_log(db_path) as conn:
        row_ids: list[int] = []
        for case_number in ("case-1", "case-2", "case-3"):
            row_ids.append(
                int(
                    conn.execute(
                        """
                        INSERT INTO job_runs (
                            completed_at,
                            translation_date,
                            case_number,
                            case_entity,
                            case_city,
                            service_entity,
                            service_city,
                            service_date,
                            lang,
                            target_lang
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "2026-03-06T10:00:00",
                            "2026-03-06",
                            case_number,
                            "Entity",
                            "Beja",
                            "Entity",
                            "Beja",
                            "2026-03-06",
                            "EN",
                            "EN",
                        ),
                    ).lastrowid
                )
            )
        deleted_count = delete_job_runs(conn, row_ids=[row_ids[0], row_ids[2], row_ids[0]])
        rows = conn.execute("SELECT id, case_number FROM job_runs ORDER BY id").fetchall()

    assert deleted_count == 2
    assert [tuple(row) for row in rows] == [(int(row_ids[1]), "case-2")]
