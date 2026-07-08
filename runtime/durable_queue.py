"""File-backed durable pipeline job queue."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

from .execution_journal import append_journal_event
from .models import Pipeline, PipelineNode


TERMINAL_STATUSES = {"succeeded", "failed", "stopped", "cancelled"}


class DurableQueue:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.queue_dir = root / "artifacts" / "queue"
        self.jobs_dir = self.queue_dir / "jobs"
        self.lock_path = self.queue_dir / "queue.lock"

    def enqueue(
        self,
        pipeline: Pipeline,
        root_input: dict[str, Any],
        *,
        reset_registry: bool = False,
        priority: int = 100,
        max_attempts: int = 3,
    ) -> str:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        job_id = _new_job_id(pipeline.id, root_input)
        payload = {
            "job_id": job_id,
            "status": "queued",
            "pipeline": _pipeline_to_dict(pipeline),
            "root_input": root_input,
            "reset_registry": reset_registry,
            "created_at": _now(),
            "updated_at": _now(),
            "attempts": 0,
            "max_attempts": max(1, int(max_attempts)),
            "priority": int(priority),
            "worker_id": None,
            "lease_expires_at": None,
            "heartbeat_at": None,
            "result": None,
            "error": None,
        }
        with self._lock():
            path = self._job_path(job_id)
            if path.exists():
                raise RuntimeError(f"job already exists: {job_id}")
            _write_json_atomic(path, payload)
        append_journal_event(self.root, {"event": "queue_enqueued", "job_id": job_id, "pipeline_id": pipeline.id})
        return job_id

    def claim_next(self, worker_id: str, *, lease_seconds: float = 30.0) -> dict[str, Any] | None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        with self._lock():
            for path, job in self._queued_jobs_by_priority():
                job = _read_json(path)
                if job.get("status") != "queued":
                    continue
                job["status"] = "running"
                job["worker_id"] = worker_id
                job["attempts"] = int(job.get("attempts", 0)) + 1
                job["started_at"] = _now()
                job["heartbeat_at"] = _now()
                job["lease_expires_at"] = _from_timestamp(time.time() + lease_seconds)
                job["updated_at"] = _now()
                _write_json_atomic(path, job)
                append_journal_event(
                    self.root,
                    {
                        "event": "queue_claimed",
                        "job_id": job["job_id"],
                        "pipeline_id": job["pipeline"]["id"],
                        "worker_id": worker_id,
                    },
                )
                return job
        return None

    def heartbeat(self, job_id: str, worker_id: str, *, lease_seconds: float = 30.0) -> bool:
        with self._lock():
            path = self._job_path(job_id)
            if not path.exists():
                return False
            job = _read_json(path)
            if job.get("status") != "running" or job.get("worker_id") != worker_id:
                return False
            job["heartbeat_at"] = _now()
            job["lease_expires_at"] = _from_timestamp(time.time() + lease_seconds)
            job["updated_at"] = _now()
            _write_json_atomic(path, job)
        append_journal_event(self.root, {"event": "queue_heartbeat", "job_id": job_id, "worker_id": worker_id})
        return True

    def complete(self, job_id: str, *, result: dict[str, Any]) -> None:
        status = "succeeded" if result.get("status") == "ok" else "stopped"
        self._finish(job_id, status=status, result=result, error=None)

    def fail(self, job_id: str, *, error: str) -> None:
        with self._lock():
            path = self._job_path(job_id)
            if not path.exists():
                append_registry_event = None
                missing = True
                job = {}
            else:
                missing = False
                job = _read_json(path)
            if missing:
                pass
            elif job.get("status") in TERMINAL_STATUSES:
                return
            elif int(job.get("attempts", 0)) < int(job.get("max_attempts", 1)):
                job["status"] = "queued"
                job["worker_id"] = None
                job["lease_expires_at"] = None
                job["heartbeat_at"] = None
                job["error"] = error
                job["updated_at"] = _now()
                _write_json_atomic(path, job)
                append_registry_event = {
                    "event": "queue_retry_scheduled",
                    "job_id": job_id,
                    "attempts": int(job.get("attempts", 0)),
                    "max_attempts": int(job.get("max_attempts", 1)),
                }
            else:
                append_registry_event = None
        if missing:
            append_journal_event(self.root, {"event": "queue_fail_missing_job", "job_id": job_id, "error": error})
            return
        if append_registry_event is not None:
            append_journal_event(self.root, append_registry_event)
            return
        self._finish(job_id, status="failed", result=None, error=error)

    def cancel(self, job_id: str, *, reason: str = "cancelled") -> None:
        self._finish(job_id, status="cancelled", result=None, error=reason)

    def requeue(self, job_id: str, *, reason: str = "manual_requeue") -> bool:
        with self._lock():
            path = self._job_path(job_id)
            job = _read_json(path)
            if job.get("status") in TERMINAL_STATUSES:
                return False
            job["status"] = "queued"
            job["worker_id"] = None
            job["lease_expires_at"] = None
            job["heartbeat_at"] = None
            job["error"] = reason
            job["updated_at"] = _now()
            _write_json_atomic(path, job)
        append_journal_event(self.root, {"event": "queue_requeued", "job_id": job_id, "reason": reason})
        return True

    def archive_terminal(self) -> list[str]:
        archive_dir = self.queue_dir / "archive"
        archived: list[str] = []
        with self._lock():
            archive_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(self.jobs_dir.glob("*.json")):
                job = _read_json(path)
                if job.get("status") not in TERMINAL_STATUSES:
                    continue
                target = archive_dir / path.name
                shutil.move(str(path), str(target))
                archived.append(str(job["job_id"]))
        for job_id in archived:
            append_journal_event(self.root, {"event": "queue_archived", "job_id": job_id})
        return archived

    def cleanup_archived(self) -> int:
        archive_dir = self.queue_dir / "archive"
        if not archive_dir.exists():
            return 0
        removed = 0
        with self._lock():
            for path in sorted(archive_dir.glob("*.json")):
                path.unlink()
                removed += 1
        append_journal_event(self.root, {"event": "queue_archive_cleaned", "removed": removed})
        return removed

    def load(self, job_id: str) -> dict[str, Any]:
        return _read_json(self._job_path(job_id))

    def list_jobs(self, *, status: str | None = None) -> list[dict[str, Any]]:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        jobs = [_read_json(path) for path in sorted(self.jobs_dir.glob("*.json"))]
        if status is not None:
            jobs = [job for job in jobs if job.get("status") == status]
        return jobs

    def requeue_stale_running(self, *, older_than_seconds: float | None = None) -> list[str]:
        cutoff = time.time() - older_than_seconds if older_than_seconds is not None else None
        now = time.time()
        requeued: list[str] = []
        with self._lock():
            for path in sorted(self.jobs_dir.glob("*.json")):
                job = _read_json(path)
                if job.get("status") != "running":
                    continue
                stale = False
                if cutoff is not None:
                    started_at = _parse_time(str(job.get("started_at") or job.get("updated_at")))
                    stale = started_at < cutoff
                lease_expires_at = str(job.get("lease_expires_at") or "")
                if lease_expires_at:
                    stale = stale or _parse_time(lease_expires_at) <= now
                if not stale:
                    continue
                attempts = int(job.get("attempts", 0))
                max_attempts = int(job.get("max_attempts", 1))
                job["status"] = "queued" if attempts < max_attempts else "failed"
                job["worker_id"] = None
                job["lease_expires_at"] = None
                job["heartbeat_at"] = None
                if job["status"] == "failed":
                    job["error"] = "lease expired and max attempts reached"
                    job["finished_at"] = _now()
                job["updated_at"] = _now()
                _write_json_atomic(path, job)
                requeued.append(str(job["job_id"]))
        for job_id in requeued:
            append_journal_event(self.root, {"event": "queue_requeued", "job_id": job_id})
        return requeued

    def _queued_jobs_by_priority(self) -> list[tuple[Path, dict[str, Any]]]:
        jobs = [(path, _read_json(path)) for path in self.jobs_dir.glob("*.json")]
        queued = [(path, job) for path, job in jobs if job.get("status") == "queued"]
        return sorted(
            queued,
            key=lambda item: (int(item[1].get("priority", 100)), str(item[1].get("created_at", "")), str(item[1].get("job_id", ""))),
        )

    def _finish(self, job_id: str, *, status: str, result: dict[str, Any] | None, error: str | None) -> None:
        with self._lock():
            path = self._job_path(job_id)
            if not path.exists():
                append_event = None
                missing = True
                job = {}
            else:
                missing = False
                job = _read_json(path)
            if missing:
                pass
            elif job.get("status") in TERMINAL_STATUSES:
                return
            else:
                job["status"] = status
                job["worker_id"] = None
                job["lease_expires_at"] = None
                job["heartbeat_at"] = None
                job["result"] = result
                job["error"] = error
                job["finished_at"] = _now()
                job["updated_at"] = _now()
                _write_json_atomic(path, job)
                append_event = {
                    "event": "queue_finished",
                    "job_id": job_id,
                    "status": status,
                    "pipeline_id": job["pipeline"]["id"],
                }
        if missing:
            append_journal_event(self.root, {"event": "queue_finish_missing_job", "job_id": job_id, "status": status})
            return
        if append_event is not None:
            append_journal_event(self.root, append_event)

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    @contextmanager
    def _lock(self):
        lock = _QueueLock(self.lock_path)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()


def job_pipeline(job: dict[str, Any]) -> Pipeline:
    return _pipeline_from_dict(dict(job["pipeline"]))


class _QueueLock:
    def __init__(self, path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.fd: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"queue lock timeout: {self.path}")
                time.sleep(self.poll_seconds)

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "_QueueLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def _pipeline_to_dict(pipeline: Pipeline) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "version": pipeline.version,
        "nodes": [asdict(node) for node in pipeline.nodes],
        "edges": pipeline.edges,
        "retry_policy": pipeline.retry_policy,
    }


def _pipeline_from_dict(payload: dict[str, Any]) -> Pipeline:
    return Pipeline(
        id=str(payload["id"]),
        version=str(payload["version"]),
        nodes=[
            PipelineNode(id=str(node["id"]), capability=str(node["capability"]), input=dict(node["input"]))
            for node in payload["nodes"]
        ],
        edges=[list(edge) for edge in payload.get("edges", [])],
        retry_policy=dict(payload.get("retry_policy", {})),
    )


def _new_job_id(pipeline_id: str, root_input: dict[str, Any]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256(
        json.dumps({"pipeline_id": pipeline_id, "root_input": root_input, "stamp": stamp}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"job_{stamp}_{digest}"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _parse_time(value: str) -> float:
    if not value:
        return 0.0
    return datetime.fromisoformat(value).timestamp()
