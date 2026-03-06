#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _collect_run_summaries(roots: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for summary_path in root.rglob("run_summary.json"):
            if not summary_path.parent.name.endswith("_run"):
                continue
            resolved = str(summary_path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)

            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            run_id = str(data.get("run_id", ""))
            is_translation_run = not run_id.startswith("glossary_builder_")
            totals = data.get("totals", {}) if isinstance(data.get("totals"), dict) else {}
            counts = data.get("counts", {}) if isinstance(data.get("counts"), dict) else {}
            diagnostics = (
                data.get("diagnostics", {}) if isinstance(data.get("diagnostics"), dict) else {}
            )
            pipeline = data.get("pipeline", {}) if isinstance(data.get("pipeline"), dict) else {}
            top_slowest = (
                data.get("top_slowest_pages", []) if isinstance(data.get("top_slowest_pages"), list) else []
            )

            wall_seconds = totals.get("total_wall_seconds")
            top3_wall = sum(
                item.get("wall_seconds", 0)
                for item in top_slowest[:3]
                if isinstance(item, dict) and isinstance(item.get("wall_seconds"), (int, float))
            )

            row = {
                "path": resolved,
                "run_dir": summary_path.parent.name,
                "run_id": run_id,
                "is_translation_run": is_translation_run,
                "lang": data.get("lang"),
                "selected_pages_count": data.get("selected_pages_count"),
                "effort_policy": data.get("effort_policy")
                or (data.get("settings", {}) if isinstance(data.get("settings"), dict) else {}).get("effort_policy"),
                "image_mode": data.get("image_mode")
                or (data.get("settings", {}) if isinstance(data.get("settings"), dict) else {}).get("image_mode"),
                "total_tokens": totals.get("total_tokens"),
                "total_input_tokens": totals.get("total_input_tokens"),
                "total_output_tokens": totals.get("total_output_tokens"),
                "total_reasoning_tokens": totals.get("total_reasoning_tokens"),
                "total_wall_seconds": wall_seconds,
                "api_calls_total": diagnostics.get("api_calls_total"),
                "ocr_seconds_total": diagnostics.get("ocr_seconds_total"),
                "ocr_requested": pipeline.get("ocr_requested"),
                "ocr_used_pages": pipeline.get("ocr_used_pages"),
                "retry_pages": counts.get("pages_with_retries"),
                "failed_pages": counts.get("pages_failed"),
                "image_pages": counts.get("pages_with_images"),
                "cost_estimate": totals.get("total_cost_estimate_if_available"),
                "slowest_top3_wall_sum": top3_wall,
                "slowest_top3_ratio": (
                    top3_wall / wall_seconds
                    if isinstance(wall_seconds, (int, float)) and wall_seconds > 0
                    else None
                ),
            }
            rows.append(row)
    return sorted(rows, key=lambda row: row["path"])


def _number_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]


def _build_settings_snapshot() -> tuple[str, dict[str, Any]]:
    appdata = os.environ.get("APPDATA", "").strip()
    settings_path = (
        Path(appdata) / "LegalPDFTranslate" / "settings.json"
        if appdata
        else Path.home() / ".legalpdf_translate" / "settings.json"
    )
    settings: dict[str, Any] = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

    keys = [
        "default_effort",
        "default_effort_policy",
        "default_images_mode",
        "default_workers",
        "default_resume",
        "ocr_mode_default",
        "ocr_engine_default",
        "workers",
        "effort_policy",
        "image_mode",
        "resume",
        "diagnostics_show_cost_summary",
        "study_glossary_corpus_source",
        "study_glossary_default_coverage_percent",
    ]
    return str(settings_path), {key: settings.get(key) for key in keys if key in settings}


def _build_joblog_snapshot() -> tuple[str, dict[str, Any]]:
    appdata = os.environ.get("APPDATA", "").strip()
    db_path = (
        Path(appdata) / "LegalPDFTranslate" / "job_log.sqlite3"
        if appdata
        else Path.home() / ".legalpdf_translate" / "job_log.sqlite3"
    )
    snapshot: dict[str, Any] = {"exists": db_path.exists()}
    if not db_path.exists():
        return str(db_path), snapshot

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        snapshot["job_runs_count"] = cur.execute("SELECT COUNT(*) c FROM job_runs").fetchone()["c"]
        snapshot["lang_counts"] = [
            dict(row)
            for row in cur.execute("SELECT lang, COUNT(*) c FROM job_runs GROUP BY lang ORDER BY c DESC")
        ]
        snapshot["api_cost_stats"] = dict(
            cur.execute(
                "SELECT MIN(api_cost) min_api_cost, MAX(api_cost) max_api_cost, "
                "AVG(api_cost) avg_api_cost, SUM(api_cost) total_api_cost FROM job_runs"
            ).fetchone()
        )
    finally:
        conn.close()
    return str(db_path), snapshot


def build_packet(scan_roots: list[Path]) -> dict[str, Any]:
    all_rows = _collect_run_summaries(scan_roots)
    translation_rows = [row for row in all_rows if row["is_translation_run"]]

    langs = Counter(row.get("lang") for row in translation_rows if row.get("lang"))
    pages = _number_values(translation_rows, "selected_pages_count")
    total_tokens = _number_values(translation_rows, "total_tokens")
    reasoning_tokens = _number_values(translation_rows, "total_reasoning_tokens")
    wall_seconds = _number_values(translation_rows, "total_wall_seconds")
    slow_ratios = _number_values(translation_rows, "slowest_top3_ratio")

    retry_total = sum(int(row.get("retry_pages") or 0) for row in translation_rows)
    failed_total = sum(int(row.get("failed_pages") or 0) for row in translation_rows)
    image_total = sum(int(row.get("image_pages") or 0) for row in translation_rows)
    ocr_used_total = sum(int(row.get("ocr_used_pages") or 0) for row in translation_rows)
    ocr_requested_runs = sum(1 for row in translation_rows if row.get("ocr_requested") is True)
    cost_known = sum(1 for row in translation_rows if isinstance(row.get("cost_estimate"), (int, float)))

    settings_path, settings_snapshot = _build_settings_snapshot()
    joblog_path, joblog_snapshot = _build_joblog_snapshot()

    return {
        "packet_id": "AUDIT_USAGE_PACKET_2026-03-05",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scan_roots": [str(path) for path in scan_roots],
        "settings_path": settings_path,
        "joblog_path": joblog_path,
        "run_summary_count_all": len(all_rows),
        "run_summary_count_translation_only": len(translation_rows),
        "language_mix_translation_only": dict(langs),
        "pages_per_run_translation_only": {
            "min": min(pages) if pages else None,
            "max": max(pages) if pages else None,
            "avg": round(sum(pages) / len(pages), 3) if pages else None,
            "median": statistics.median(pages) if pages else None,
        },
        "token_distribution_translation_only": {
            "total_tokens_sum": int(sum(total_tokens)) if total_tokens else None,
            "total_tokens_avg": round(sum(total_tokens) / len(total_tokens), 3) if total_tokens else None,
            "total_tokens_max": int(max(total_tokens)) if total_tokens else None,
            "reasoning_tokens_sum": int(sum(reasoning_tokens)) if reasoning_tokens else None,
            "reasoning_tokens_avg": (
                round(sum(reasoning_tokens) / len(reasoning_tokens), 3) if reasoning_tokens else None
            ),
        },
        "latency_distribution_translation_only": {
            "wall_seconds_sum": round(sum(wall_seconds), 3) if wall_seconds else None,
            "wall_seconds_avg": round(sum(wall_seconds) / len(wall_seconds), 3) if wall_seconds else None,
            "wall_seconds_max": max(wall_seconds) if wall_seconds else None,
        },
        "slowest_page_concentration_top3_ratio_translation_only": {
            "avg_ratio": round(sum(slow_ratios) / len(slow_ratios), 4) if slow_ratios else None,
            "max_ratio": round(max(slow_ratios), 4) if slow_ratios else None,
        },
        "retry_failure_frequency_translation_only": {
            "retry_pages_total": retry_total,
            "failed_pages_total": failed_total,
        },
        "ocr_usage_translation_only": {
            "ocr_requested_runs": ocr_requested_runs,
            "ocr_used_pages_total": ocr_used_total,
        },
        "image_usage_translation_only": {
            "image_pages_total": image_total,
        },
        "cost_field_coverage_translation_only": {
            "cost_estimate_present_runs": cost_known,
            "cost_estimate_missing_runs": len(translation_rows) - cost_known,
            "cost_estimate_coverage_ratio": (
                round(cost_known / len(translation_rows), 4) if translation_rows else None
            ),
        },
        "settings_snapshot": settings_snapshot,
        "joblog_snapshot": joblog_snapshot,
        "per_run_rows_all": all_rows,
        "per_run_rows_translation_only": translation_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build usage audit packet from local run artifacts.")
    parser.add_argument(
        "--scan-root",
        action="append",
        default=[],
        help="Root path to scan for *_run/run_summary.json (repeatable).",
    )
    parser.add_argument(
        "--output-json",
        default="docs/assistant/audits/AUDIT_USAGE_PACKET_2026-03-05.json",
        help="Output packet path.",
    )
    args = parser.parse_args()

    roots = [Path(path).expanduser() for path in args.scan_root]
    if not roots:
        roots = [
            Path(r"C:\Users\FA507\Downloads"),
            Path(r"C:\Users\FA507\.codex\legalpdf_translate"),
        ]

    packet = build_packet(roots)
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote usage audit packet: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
