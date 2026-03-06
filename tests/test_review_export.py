from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate.review_export import export_review_queue


def _write_run_summary(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_review_export_writes_csv_and_markdown(tmp_path: Path) -> None:
    run_summary_path = tmp_path / "run_summary.json"
    _write_run_summary(
        run_summary_path,
        {
            "run_id": "run-20260305-1500",
            "lang": "FR",
            "quality_risk_score": 0.6231,
            "review_queue_count": 2,
            "review_queue": [
                {
                    "page_number": 4,
                    "score": 0.7,
                    "status": "done",
                    "reasons": ["validator_failed", "retry_reason:outside_text"],
                    "recommended_action": "manual_review",
                    "retry_reason": "outside_text",
                    "transport_retries_count": 2,
                    "rate_limit_hit": False,
                    "ocr_used": False,
                    "image_used": True,
                },
                {
                    "page_number": 2,
                    "score": 0.9,
                    "status": "failed",
                    "reasons": ["page_failed"],
                    "recommended_action": "rerun_page",
                    "retry_reason": "other",
                    "transport_retries_count": 0,
                    "rate_limit_hit": False,
                    "ocr_used": False,
                    "image_used": False,
                },
            ],
        },
    )

    export_prefix = tmp_path / "exports" / "review_bundle"
    csv_path, markdown_path, review_count = export_review_queue(run_summary_path, export_prefix)

    assert review_count == 2
    assert csv_path.exists()
    assert markdown_path.exists()

    csv_text = csv_path.read_text(encoding="utf-8")
    md_text = markdown_path.read_text(encoding="utf-8")
    assert "run_id,target_lang,quality_risk_score,page_number,page_score" in csv_text
    assert "run-20260305-1500,FR,0.6231,2,0.9,failed,rerun_page" in csv_text
    assert "# Review Queue Export" in md_text
    assert "Overall quality risk score: `0.6231`" in md_text
    assert "| 2 | 0.9 | failed | rerun_page | other | page_failed |" in md_text


def test_review_export_empty_queue_is_explicit(tmp_path: Path) -> None:
    run_summary_path = tmp_path / "run_summary.json"
    _write_run_summary(
        run_summary_path,
        {
            "run_id": "run-20260305-1700",
            "lang": "EN",
            "quality_risk_score": 0.0,
            "review_queue": [],
        },
    )

    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    csv_path, markdown_path, review_count = export_review_queue(run_summary_path, export_dir)

    assert review_count == 0
    assert csv_path.name == "review_queue.csv"
    assert markdown_path.name == "review_queue.md"
    assert csv_path.exists()
    assert markdown_path.exists()
    assert "No review queue entries were generated for this run." in markdown_path.read_text(encoding="utf-8")
