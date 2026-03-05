"""Sequential queue runner with manifest parsing and crash-safe checkpointing."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .types import RunSummary

_ALLOWED_QUEUE_STATUSES = {"pending", "running", "done", "failed", "skipped"}


@dataclass(slots=True)
class QueueJobRunResult:
    success: bool
    exit_code: int
    error: str | None = None
    run_dir: Path | None = None
    run_summary_path: Path | None = None
    output_docx: Path | None = None


@dataclass(slots=True)
class QueueRunSummary:
    success: bool
    total_jobs: int
    done_jobs: int
    failed_jobs: int
    skipped_jobs: int
    checkpoint_path: Path
    queue_summary_path: Path
    jobs: list[dict[str, Any]]


def queue_result_from_run_summary(summary: RunSummary) -> QueueJobRunResult:
    return QueueJobRunResult(
        success=bool(summary.success),
        exit_code=int(summary.exit_code),
        error=(str(summary.error) if summary.error is not None else None),
        run_dir=summary.run_dir.expanduser().resolve(),
        run_summary_path=(
            summary.run_summary_path.expanduser().resolve()
            if summary.run_summary_path is not None
            else None
        ),
        output_docx=(
            summary.output_docx.expanduser().resolve()
            if summary.output_docx is not None
            else None
        ),
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def queue_artifact_paths(manifest_path: Path) -> tuple[Path, Path]:
    manifest_abs = manifest_path.expanduser().resolve()
    base = manifest_abs.parent / manifest_abs.stem
    checkpoint_path = base.with_suffix(".queue_checkpoint.json")
    summary_path = base.with_suffix(".queue_summary.json")
    return checkpoint_path, summary_path


def _coerce_job_id(value: object, *, index: int) -> str:
    text = str(value or "").strip()
    if text == "":
        text = f"job_{index:04d}"
    return text


def _normalize_manifest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Queue manifest row {index} must be an object.")
        payload = dict(item)
        job_id = _coerce_job_id(payload.get("job_id"), index=index)
        if job_id in seen_ids:
            raise ValueError(f"Queue manifest has duplicate job_id: {job_id}")
        seen_ids.add(job_id)
        normalized.append(
            {
                "job_id": job_id,
                "index": index,
                "payload": payload,
                "status": "pending",
                "attempt_count": 0,
                "skip_reason": "",
                "error": "",
                "exit_code": 0,
                "run_dir": "",
                "run_summary_path": "",
                "output_docx": "",
                "started_at": "",
                "finished_at": "",
                "duration_seconds": 0.0,
            }
        )
    return normalized


def parse_queue_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    manifest_abs = manifest_path.expanduser().resolve()
    if not manifest_abs.exists() or not manifest_abs.is_file():
        raise FileNotFoundError(f"Queue manifest not found: {manifest_abs}")
    raw_text = manifest_abs.read_text(encoding="utf-8")
    suffix = manifest_abs.suffix.lower()
    rows: list[dict[str, Any]] = []
    if suffix == ".jsonl":
        for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
            line = raw_line.strip()
            if line == "":
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Queue JSONL line {line_number} must be an object.")
            rows.append(dict(item))
    else:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid queue manifest JSON: {exc}") from exc
        if isinstance(payload, list):
            rows = [dict(item) for item in payload if isinstance(item, dict)]
            if len(rows) != len(payload):
                raise ValueError("Queue manifest JSON array must contain only objects.")
        elif isinstance(payload, dict):
            jobs_payload = payload.get("jobs")
            if not isinstance(jobs_payload, list):
                raise ValueError("Queue manifest object must contain a 'jobs' array.")
            rows = [dict(item) for item in jobs_payload if isinstance(item, dict)]
            if len(rows) != len(jobs_payload):
                raise ValueError("Queue manifest 'jobs' must contain only objects.")
        else:
            raise ValueError("Queue manifest must be a JSON array, JSONL, or object with 'jobs'.")
    if not rows:
        raise ValueError("Queue manifest has no jobs.")
    return _normalize_manifest_rows(rows)


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _job_counts(jobs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pending": 0, "running": 0, "done": 0, "failed": 0, "skipped": 0}
    for job in jobs:
        status = str(job.get("status", "") or "").strip().lower()
        if status not in counts:
            continue
        counts[status] += 1
    return counts


def _checkpoint_payload(
    *,
    manifest_path: Path,
    manifest_sha256: str,
    rerun_failed_only: bool,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "queue_checkpoint_v1",
        "updated_at": _utc_now(),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "rerun_failed_only": bool(rerun_failed_only),
        "jobs": jobs,
    }


def _summary_payload(
    *,
    manifest_path: Path,
    manifest_sha256: str,
    rerun_failed_only: bool,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = _job_counts(jobs)
    total_jobs = len(jobs)
    failed_jobs = int(counts.get("failed", 0))
    pending_or_running = int(counts.get("pending", 0) + counts.get("running", 0))
    success = failed_jobs == 0 and pending_or_running == 0
    return {
        "schema_version": "queue_summary_v1",
        "generated_at": _utc_now(),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "rerun_failed_only": bool(rerun_failed_only),
        "success": bool(success),
        "counts": {
            "total_jobs": int(total_jobs),
            "pending_jobs": int(counts.get("pending", 0)),
            "running_jobs": int(counts.get("running", 0)),
            "done_jobs": int(counts.get("done", 0)),
            "failed_jobs": int(failed_jobs),
            "skipped_jobs": int(counts.get("skipped", 0)),
        },
        "jobs": jobs,
    }


def run_queue_manifest(
    *,
    manifest_path: Path,
    run_job: Callable[[dict[str, Any]], QueueJobRunResult],
    rerun_failed_only: bool,
    log_callback: Callable[[str], None] | None = None,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
) -> QueueRunSummary:
    manifest_abs = manifest_path.expanduser().resolve()
    jobs = parse_queue_manifest(manifest_abs)
    checkpoint_path, summary_path = queue_artifact_paths(manifest_abs)
    manifest_sha256 = _sha256_file(manifest_abs)

    checkpoint_payload = _load_checkpoint(checkpoint_path)
    if isinstance(checkpoint_payload, dict):
        checkpoint_manifest_hash = str(checkpoint_payload.get("manifest_sha256", "") or "")
        checkpoint_jobs_obj = checkpoint_payload.get("jobs")
        if checkpoint_manifest_hash == manifest_sha256 and isinstance(checkpoint_jobs_obj, list):
            existing_by_id: dict[str, dict[str, Any]] = {}
            for raw in checkpoint_jobs_obj:
                if not isinstance(raw, dict):
                    continue
                job_id = str(raw.get("job_id", "") or "").strip()
                if job_id == "":
                    continue
                existing_by_id[job_id] = raw
            for job in jobs:
                existing = existing_by_id.get(str(job.get("job_id", "")))
                if not isinstance(existing, dict):
                    continue
                status = str(existing.get("status", "") or "").strip().lower()
                if status not in _ALLOWED_QUEUE_STATUSES:
                    continue
                job["status"] = "pending" if status == "running" else status
                job["attempt_count"] = int(existing.get("attempt_count", job.get("attempt_count", 0)) or 0)
                job["skip_reason"] = str(existing.get("skip_reason", "") or "")
                job["error"] = str(existing.get("error", "") or "")
                job["exit_code"] = int(existing.get("exit_code", 0) or 0)
                job["run_dir"] = str(existing.get("run_dir", "") or "")
                job["run_summary_path"] = str(existing.get("run_summary_path", "") or "")
                job["output_docx"] = str(existing.get("output_docx", "") or "")
                job["started_at"] = str(existing.get("started_at", "") or "")
                job["finished_at"] = str(existing.get("finished_at", "") or "")
                job["duration_seconds"] = float(existing.get("duration_seconds", 0.0) or 0.0)

    if rerun_failed_only:
        any_failed = False
        for job in jobs:
            status = str(job.get("status", "") or "").strip().lower()
            if status == "failed":
                any_failed = True
                job["status"] = "pending"
                job["skip_reason"] = ""
                continue
            job["status"] = "skipped"
            if status == "done":
                job["skip_reason"] = "rerun_failed_only_not_failed"
            else:
                job["skip_reason"] = "rerun_failed_only_without_prior_failure"
        if log_callback is not None and not any_failed:
            log_callback("Queue rerun-failed-only: no failed jobs found in checkpoint state.")
    else:
        for job in jobs:
            status = str(job.get("status", "") or "").strip().lower()
            if status == "done":
                continue
            job["status"] = "pending"
            job["skip_reason"] = ""

    def _persist() -> None:
        checkpoint_obj = _checkpoint_payload(
            manifest_path=manifest_abs,
            manifest_sha256=manifest_sha256,
            rerun_failed_only=rerun_failed_only,
            jobs=jobs,
        )
        summary_obj = _summary_payload(
            manifest_path=manifest_abs,
            manifest_sha256=manifest_sha256,
            rerun_failed_only=rerun_failed_only,
            jobs=jobs,
        )
        _write_json_atomic(checkpoint_path, checkpoint_obj)
        _write_json_atomic(summary_path, summary_obj)

    _persist()

    for job in jobs:
        status = str(job.get("status", "") or "").strip().lower()
        if status in {"done", "skipped"}:
            if status_callback is not None:
                status_callback(dict(job))
            continue
        payload = job.get("payload")
        if not isinstance(payload, dict):
            job["status"] = "failed"
            job["error"] = "invalid_manifest_row_payload"
            _persist()
            if status_callback is not None:
                status_callback(dict(job))
            continue

        job["status"] = "running"
        job["error"] = ""
        job["skip_reason"] = ""
        job["started_at"] = _utc_now()
        job["finished_at"] = ""
        job["duration_seconds"] = 0.0
        job["attempt_count"] = int(job.get("attempt_count", 0) or 0) + 1
        _persist()
        if status_callback is not None:
            status_callback(dict(job))

        started = time.perf_counter()
        try:
            run_result = run_job(payload)
        except Exception as exc:  # noqa: BLE001
            run_result = QueueJobRunResult(success=False, exit_code=2, error=f"{type(exc).__name__}: {exc}")

        duration_seconds = time.perf_counter() - started
        job["duration_seconds"] = round(float(duration_seconds), 3)
        job["finished_at"] = _utc_now()
        job["exit_code"] = int(run_result.exit_code)
        job["run_dir"] = str(run_result.run_dir) if run_result.run_dir is not None else ""
        job["run_summary_path"] = (
            str(run_result.run_summary_path) if run_result.run_summary_path is not None else ""
        )
        job["output_docx"] = str(run_result.output_docx) if run_result.output_docx is not None else ""
        if run_result.success:
            job["status"] = "done"
            job["error"] = ""
            if log_callback is not None:
                log_callback(f"Queue job {job.get('job_id')} done.")
        else:
            job["status"] = "failed"
            job["error"] = str(run_result.error or "queue_job_failed")
            if log_callback is not None:
                log_callback(
                    f"Queue job {job.get('job_id')} failed: {job.get('error')} (exit_code={run_result.exit_code})."
                )
        _persist()
        if status_callback is not None:
            status_callback(dict(job))

    final_summary = _summary_payload(
        manifest_path=manifest_abs,
        manifest_sha256=manifest_sha256,
        rerun_failed_only=rerun_failed_only,
        jobs=jobs,
    )
    done_jobs = int(final_summary["counts"]["done_jobs"])
    failed_jobs = int(final_summary["counts"]["failed_jobs"])
    skipped_jobs = int(final_summary["counts"]["skipped_jobs"])
    total_jobs = int(final_summary["counts"]["total_jobs"])
    return QueueRunSummary(
        success=bool(final_summary["success"]),
        total_jobs=total_jobs,
        done_jobs=done_jobs,
        failed_jobs=failed_jobs,
        skipped_jobs=skipped_jobs,
        checkpoint_path=checkpoint_path,
        queue_summary_path=summary_path,
        jobs=[dict(job) for job in jobs],
    )
