"""Review queue export helpers for CLI workflows."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return default
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return default
    return default


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _to_text(value: object) -> str:
    return str(value or "").strip()


def _load_summary(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists() or not summary_path.is_file():
        raise FileNotFoundError(f"run summary not found: {summary_path}")
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid run summary JSON: {summary_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid run summary payload type: {summary_path}")
    return payload


def _coerce_reasons(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        cleaned = _to_text(item)
        if cleaned:
            output.append(cleaned)
    return output


def build_review_export_rows(run_summary: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_id = _to_text(run_summary.get("run_id", ""))
    lang = _to_text(run_summary.get("lang", ""))
    quality_risk_score = round(_to_float(run_summary.get("quality_risk_score", 0.0)), 4)

    queue_payload = run_summary.get("review_queue")
    queue_items = queue_payload if isinstance(queue_payload, list) else []
    rows: list[dict[str, Any]] = []
    for item in queue_items:
        if not isinstance(item, Mapping):
            continue
        reasons = _coerce_reasons(item.get("reasons", []))
        row = {
            "run_id": run_id,
            "target_lang": lang,
            "quality_risk_score": quality_risk_score,
            "page_number": _to_int(item.get("page_number", 0)),
            "page_score": round(_to_float(item.get("score", 0.0)), 4),
            "status": _to_text(item.get("status", "")),
            "recommended_action": _to_text(item.get("recommended_action", "")),
            "retry_reason": _to_text(item.get("retry_reason", "")),
            "transport_retries_count": _to_int(item.get("transport_retries_count", 0)),
            "rate_limit_hit": bool(item.get("rate_limit_hit", False)),
            "ocr_used": bool(item.get("ocr_used", False)),
            "image_used": bool(item.get("image_used", False)),
            "reasons": " | ".join(reasons),
        }
        rows.append(row)

    rows.sort(key=lambda row: (-_to_float(row.get("page_score", 0.0)), _to_int(row.get("page_number", 0))))
    meta = {
        "run_id": run_id,
        "target_lang": lang,
        "quality_risk_score": quality_risk_score,
        "review_queue_count": len(rows),
    }
    return meta, rows


def _resolve_export_paths(output_path: Path) -> tuple[Path, Path]:
    target = output_path.expanduser()
    if target.suffix == "":
        if target.exists() and target.is_dir():
            csv_path = target / "review_queue.csv"
            markdown_path = target / "review_queue.md"
            return csv_path.resolve(), markdown_path.resolve()
        return target.with_suffix(".csv").resolve(), target.with_suffix(".md").resolve()
    stem = target.with_suffix("")
    return stem.with_suffix(".csv").resolve(), stem.with_suffix(".md").resolve()


def export_review_queue(summary_path: Path, output_path: Path) -> tuple[Path, Path, int]:
    payload = _load_summary(summary_path.expanduser().resolve())
    meta, rows = build_review_export_rows(payload)
    csv_path, markdown_path = _resolve_export_paths(output_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_id",
        "target_lang",
        "quality_risk_score",
        "page_number",
        "page_score",
        "status",
        "recommended_action",
        "retry_reason",
        "transport_retries_count",
        "rate_limit_hit",
        "ocr_used",
        "image_used",
        "reasons",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    lines: list[str] = []
    lines.append("# Review Queue Export")
    lines.append("")
    lines.append(f"- Run ID: `{meta['run_id']}`")
    lines.append(f"- Target language: `{meta['target_lang']}`")
    lines.append(f"- Overall quality risk score: `{meta['quality_risk_score']}`")
    lines.append(f"- Flagged pages: `{meta['review_queue_count']}`")
    lines.append("")
    if rows:
        lines.append("| Page | Score | Status | Action | Retry Reason | Reasons |")
        lines.append("|------|-------|--------|--------|--------------|---------|")
        for row in rows:
            lines.append(
                f"| {row['page_number']} | {row['page_score']} | {row['status'] or '-'} "
                f"| {row['recommended_action'] or '-'} | {row['retry_reason'] or '-'} "
                f"| {row['reasons'] or '-'} |"
            )
    else:
        lines.append("No review queue entries were generated for this run.")
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")

    return csv_path, markdown_path, int(len(rows))
