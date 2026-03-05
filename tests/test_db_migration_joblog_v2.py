from __future__ import annotations

import sqlite3
from pathlib import Path

from legalpdf_translate.joblog_db import open_job_log


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
    assert "translation_date" in columns
    assert "run_id" in columns
    assert "target_lang" in columns
    assert "total_tokens" in columns
    assert "estimated_api_cost" in columns
    assert "quality_risk_score" in columns
    assert "header_text" not in columns
    assert "ocr_text" not in columns
    assert "extracted_text" not in columns

    row = migrated.execute(
        """
        SELECT case_entity, case_city, service_entity, service_city, service_date, translation_date,
               target_lang, estimated_api_cost, run_id, total_tokens, quality_risk_score
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
    assert float(row[7]) == 2.0
    assert row[8] is None
    assert row[9] is None
    assert row[10] is None
