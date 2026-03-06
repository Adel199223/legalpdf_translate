from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate.queue_runner import QueueJobRunResult, run_queue_manifest


def _write_manifest(path: Path) -> None:
    payload = [
        {"job_id": "job_a", "pdf": "a.pdf", "lang": "EN", "outdir": "C:/tmp/out"},
        {"job_id": "job_b", "pdf": "b.pdf", "lang": "FR", "outdir": "C:/tmp/out"},
        {"job_id": "job_c", "pdf": "c.pdf", "lang": "AR", "outdir": "C:/tmp/out"},
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_queue_rerun_failed_only_retries_only_failed_jobs(tmp_path: Path) -> None:
    manifest_path = tmp_path / "queue.json"
    _write_manifest(manifest_path)

    def _first_run(payload: dict[str, object]) -> QueueJobRunResult:
        job_id = str(payload.get("job_id", "") or "")
        if job_id == "job_b":
            return QueueJobRunResult(success=False, exit_code=1, error="intentional_failure")
        return QueueJobRunResult(success=True, exit_code=0)

    first_summary = run_queue_manifest(
        manifest_path=manifest_path,
        run_job=_first_run,
        rerun_failed_only=False,
    )
    assert first_summary.done_jobs == 2
    assert first_summary.failed_jobs == 1

    rerun_calls: list[str] = []

    def _rerun(payload: dict[str, object]) -> QueueJobRunResult:
        job_id = str(payload.get("job_id", "") or "")
        rerun_calls.append(job_id)
        return QueueJobRunResult(success=True, exit_code=0)

    second_summary = run_queue_manifest(
        manifest_path=manifest_path,
        run_job=_rerun,
        rerun_failed_only=True,
    )

    assert rerun_calls == ["job_b"]
    assert second_summary.done_jobs == 1
    assert second_summary.failed_jobs == 0
    assert second_summary.skipped_jobs == 2
    assert second_summary.success is True
    by_job_id = {str(row.get("job_id")): row for row in second_summary.jobs}
    assert by_job_id["job_a"]["status"] == "skipped"
    assert by_job_id["job_a"]["skip_reason"] == "rerun_failed_only_not_failed"
    assert by_job_id["job_b"]["status"] == "done"
    assert by_job_id["job_c"]["status"] == "skipped"
    assert by_job_id["job_c"]["skip_reason"] == "rerun_failed_only_not_failed"


def test_queue_rerun_failed_only_with_no_prior_failures_skips_all(tmp_path: Path) -> None:
    manifest_path = tmp_path / "queue.json"
    _write_manifest(manifest_path)

    def _success_run(_: dict[str, object]) -> QueueJobRunResult:
        return QueueJobRunResult(success=True, exit_code=0)

    first_summary = run_queue_manifest(
        manifest_path=manifest_path,
        run_job=_success_run,
        rerun_failed_only=False,
    )
    assert first_summary.done_jobs == 3
    assert first_summary.failed_jobs == 0

    rerun_calls: list[str] = []

    def _rerun(payload: dict[str, object]) -> QueueJobRunResult:
        rerun_calls.append(str(payload.get("job_id", "") or ""))
        return QueueJobRunResult(success=True, exit_code=0)

    second_summary = run_queue_manifest(
        manifest_path=manifest_path,
        run_job=_rerun,
        rerun_failed_only=True,
    )
    assert rerun_calls == []
    assert second_summary.done_jobs == 0
    assert second_summary.failed_jobs == 0
    assert second_summary.skipped_jobs == 3
    assert second_summary.success is True
