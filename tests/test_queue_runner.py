from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate.queue_runner import QueueJobRunResult, parse_queue_manifest, run_queue_manifest


def _write_manifest(path: Path) -> None:
    payload = [
        {"job_id": "job_a", "pdf": "a.pdf", "lang": "EN", "outdir": "C:/tmp/out"},
        {"job_id": "job_b", "pdf": "b.pdf", "lang": "FR", "outdir": "C:/tmp/out"},
        {"job_id": "job_c", "pdf": "c.pdf", "lang": "AR", "outdir": "C:/tmp/out"},
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_parse_queue_manifest_accepts_json_and_jsonl(tmp_path: Path) -> None:
    json_path = tmp_path / "queue.json"
    _write_manifest(json_path)
    parsed_json = parse_queue_manifest(json_path)
    assert [item["job_id"] for item in parsed_json] == ["job_a", "job_b", "job_c"]

    jsonl_path = tmp_path / "queue.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps({"job_id": "line_1", "pdf": "a.pdf", "lang": "EN", "outdir": "C:/tmp/out"}),
                json.dumps({"job_id": "line_2", "pdf": "b.pdf", "lang": "FR", "outdir": "C:/tmp/out"}),
            ]
        ),
        encoding="utf-8",
    )
    parsed_jsonl = parse_queue_manifest(jsonl_path)
    assert [item["job_id"] for item in parsed_jsonl] == ["line_1", "line_2"]


def test_queue_runner_resume_skips_completed_jobs(tmp_path: Path) -> None:
    manifest_path = tmp_path / "queue.json"
    _write_manifest(manifest_path)

    first_calls: list[str] = []

    def _first_run(payload: dict[str, object]) -> QueueJobRunResult:
        job_id = str(payload.get("job_id", "") or "")
        first_calls.append(job_id)
        if job_id == "job_b":
            return QueueJobRunResult(success=False, exit_code=1, error="intentional_failure")
        return QueueJobRunResult(success=True, exit_code=0)

    first_summary = run_queue_manifest(
        manifest_path=manifest_path,
        run_job=_first_run,
        rerun_failed_only=False,
    )
    assert first_calls == ["job_a", "job_b", "job_c"]
    assert first_summary.done_jobs == 2
    assert first_summary.failed_jobs == 1
    assert first_summary.queue_summary_path.exists()
    assert first_summary.checkpoint_path.exists()

    second_calls: list[str] = []

    def _second_run(payload: dict[str, object]) -> QueueJobRunResult:
        job_id = str(payload.get("job_id", "") or "")
        second_calls.append(job_id)
        return QueueJobRunResult(success=True, exit_code=0)

    second_summary = run_queue_manifest(
        manifest_path=manifest_path,
        run_job=_second_run,
        rerun_failed_only=False,
    )
    assert second_calls == ["job_b"]
    assert second_summary.done_jobs == 3
    assert second_summary.failed_jobs == 0
    assert second_summary.success is True
