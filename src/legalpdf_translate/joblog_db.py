"""SQLite Job Log storage and schema migration."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .user_settings import settings_path

JOB_LOG_DB_FILENAME = "job_log.sqlite3"

JOB_RUN_COLUMNS = [
    "completed_at",
    "translation_date",
    "job_type",
    "case_number",
    "court_email",
    "case_entity",
    "case_city",
    "service_entity",
    "service_city",
    "service_date",
    "lang",
    "target_lang",
    "run_id",
    "pages",
    "word_count",
    "total_tokens",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "estimated_api_cost",
    "quality_risk_score",
    "profit",
    "output_docx_path",
    "partial_docx_path",
]


def job_log_db_path() -> Path:
    return settings_path().with_name(JOB_LOG_DB_FILENAME)


def open_job_log(db_path: Path | None = None) -> sqlite3.Connection:
    path = (db_path or job_log_db_path()).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_joblog_schema(conn)
    return conn


def ensure_joblog_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            completed_at TEXT NOT NULL,
            translation_date TEXT,
            job_type TEXT DEFAULT 'Translation',
            case_number TEXT,
            court_email TEXT,
            case_entity TEXT,
            case_city TEXT,
            service_entity TEXT,
            service_city TEXT,
            service_date TEXT,
            lang TEXT,
            target_lang TEXT,
            run_id TEXT,
            pages INTEGER,
            word_count INTEGER,
            total_tokens INTEGER,
            rate_per_word REAL,
            expected_total REAL,
            amount_paid REAL,
            api_cost REAL,
            estimated_api_cost REAL,
            quality_risk_score REAL,
            profit REAL,
            output_docx_path TEXT,
            partial_docx_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    migrate_joblog_v2(conn)
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _add_column_if_missing(conn: sqlite3.Connection, existing_columns: set[str], name: str, ddl: str) -> None:
    if name in existing_columns:
        return
    conn.execute(f"ALTER TABLE job_runs ADD COLUMN {name} {ddl}")


def _backfill_service_date_from_completed_at(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, completed_at
        FROM job_runs
        WHERE service_date IS NULL OR trim(service_date) = ''
        """
    ).fetchall()
    for row in rows:
        completed_at = str(row["completed_at"] or "").strip()
        if completed_at == "":
            continue
        parsed_date = _date_only(completed_at)
        if parsed_date is None:
            continue
        conn.execute(
            "UPDATE job_runs SET service_date = ? WHERE id = ?",
            (parsed_date, int(row["id"])),
        )


def _backfill_translation_date_from_completed_at(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, completed_at
        FROM job_runs
        WHERE translation_date IS NULL OR trim(translation_date) = ''
        """
    ).fetchall()
    for row in rows:
        completed_at = str(row["completed_at"] or "").strip()
        if completed_at == "":
            continue
        parsed_date = _date_only(completed_at)
        if parsed_date is None:
            continue
        conn.execute(
            "UPDATE job_runs SET translation_date = ? WHERE id = ?",
            (parsed_date, int(row["id"])),
        )


def _date_only(timestamp_value: str) -> str | None:
    cleaned = timestamp_value.strip()
    if cleaned == "":
        return None
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            return cleaned[:10]
        except Exception:
            return None
    return dt.date().isoformat()


def migrate_joblog_v2(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "job_runs")
    _add_column_if_missing(conn, columns, "job_type", "TEXT DEFAULT 'Translation'")
    _add_column_if_missing(conn, columns, "translation_date", "TEXT")
    _add_column_if_missing(conn, columns, "court_email", "TEXT")
    _add_column_if_missing(conn, columns, "case_entity", "TEXT")
    _add_column_if_missing(conn, columns, "case_city", "TEXT")
    _add_column_if_missing(conn, columns, "service_entity", "TEXT")
    _add_column_if_missing(conn, columns, "service_city", "TEXT")
    _add_column_if_missing(conn, columns, "service_date", "TEXT")
    _add_column_if_missing(conn, columns, "target_lang", "TEXT")
    _add_column_if_missing(conn, columns, "run_id", "TEXT")
    _add_column_if_missing(conn, columns, "total_tokens", "INTEGER")
    _add_column_if_missing(conn, columns, "estimated_api_cost", "REAL")
    _add_column_if_missing(conn, columns, "quality_risk_score", "REAL")
    _add_column_if_missing(conn, columns, "output_docx_path", "TEXT")
    _add_column_if_missing(conn, columns, "partial_docx_path", "TEXT")

    columns = _table_columns(conn, "job_runs")
    has_entity = "entity" in columns
    has_city = "city" in columns

    if has_entity:
        conn.execute(
            """
            UPDATE job_runs
            SET case_entity = COALESCE(NULLIF(trim(case_entity), ''), NULLIF(trim(entity), ''))
            WHERE case_entity IS NULL OR trim(case_entity) = ''
            """
        )
    if has_city:
        conn.execute(
            """
            UPDATE job_runs
            SET case_city = COALESCE(NULLIF(trim(case_city), ''), NULLIF(trim(city), ''))
            WHERE case_city IS NULL OR trim(case_city) = ''
            """
        )

    conn.execute(
        """
        UPDATE job_runs
        SET service_entity = COALESCE(NULLIF(trim(service_entity), ''), NULLIF(trim(case_entity), ''))
        WHERE service_entity IS NULL OR trim(service_entity) = ''
        """
    )
    conn.execute(
        """
        UPDATE job_runs
        SET service_city = COALESCE(NULLIF(trim(service_city), ''), NULLIF(trim(case_city), ''))
        WHERE service_city IS NULL OR trim(service_city) = ''
        """
    )
    conn.execute(
        """
        UPDATE job_runs
        SET target_lang = COALESCE(NULLIF(trim(target_lang), ''), NULLIF(trim(lang), ''))
        WHERE target_lang IS NULL OR trim(target_lang) = ''
        """
    )
    conn.execute(
        """
        UPDATE job_runs
        SET estimated_api_cost = COALESCE(estimated_api_cost, api_cost)
        WHERE estimated_api_cost IS NULL
        """
    )
    _backfill_translation_date_from_completed_at(conn)
    _backfill_service_date_from_completed_at(conn)


def insert_job_run(conn: sqlite3.Connection, values: Mapping[str, Any]) -> int:
    payload = {column: values.get(column) for column in JOB_RUN_COLUMNS}
    placeholders = ", ".join("?" for _ in JOB_RUN_COLUMNS)
    columns_sql = ", ".join(JOB_RUN_COLUMNS)
    cursor = conn.execute(
        f"INSERT INTO job_runs ({columns_sql}) VALUES ({placeholders})",
        [payload[column] for column in JOB_RUN_COLUMNS],
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_job_runs(conn: sqlite3.Connection, *, limit: int = 500) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            id,
            completed_at,
            COALESCE(NULLIF(trim(translation_date), ''), date(completed_at)) AS translation_date,
            job_type,
            case_number,
            court_email,
            case_entity,
            case_city,
            service_entity,
            service_city,
            service_date,
            lang,
            COALESCE(NULLIF(trim(target_lang), ''), NULLIF(trim(lang), '')) AS target_lang,
            run_id,
            pages,
            word_count,
            total_tokens,
            rate_per_word,
            expected_total,
            amount_paid,
            api_cost,
            COALESCE(estimated_api_cost, api_cost) AS estimated_api_cost,
            quality_risk_score,
            profit,
            output_docx_path,
            partial_docx_path
        FROM job_runs
        ORDER BY completed_at DESC, id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    return list(cursor.fetchall())


def update_job_run_output_paths(
    conn: sqlite3.Connection,
    *,
    row_id: int,
    output_docx_path: str | None = None,
    partial_docx_path: str | None = None,
) -> None:
    assignments: list[str] = []
    params: list[Any] = []
    if output_docx_path is not None:
        assignments.append("output_docx_path = ?")
        params.append(output_docx_path)
    if partial_docx_path is not None:
        assignments.append("partial_docx_path = ?")
        params.append(partial_docx_path)
    if not assignments:
        return
    params.append(int(row_id))
    conn.execute(
        f"UPDATE job_runs SET {', '.join(assignments)} WHERE id = ?",
        params,
    )
    conn.commit()


def update_joblog_visible_columns(
    visible_columns: Iterable[str],
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    allowed = {
        "translation_date",
        "completed_at",
        "job_type",
        "case_number",
        "court_email",
        "case_entity",
        "case_city",
        "service_entity",
        "service_city",
        "service_date",
        "lang",
        "target_lang",
        "run_id",
        "pages",
        "word_count",
        "total_tokens",
        "rate_per_word",
        "expected_total",
        "amount_paid",
        "api_cost",
        "estimated_api_cost",
        "quality_risk_score",
        "profit",
    }
    for name in visible_columns:
        cleaned = str(name).strip()
        if cleaned == "" or cleaned not in allowed:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique
