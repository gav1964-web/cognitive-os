"""Read-only runtime control-plane helpers."""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .durable_queue import DurableQueue
from .quality import load_quality_metrics


def queue_summary(root: Path) -> dict[str, Any]:
    queue = DurableQueue(root)
    jobs = queue.list_jobs()
    counts = Counter(str(job.get("status", "unknown")) for job in jobs)
    running = [job for job in jobs if job.get("status") == "running"]
    stale = [job for job in running if _is_stale(job)]
    return {
        "total": len(jobs),
        "counts": dict(sorted(counts.items())),
        "stale_running": len(stale),
        "jobs": [_job_brief(job) for job in jobs],
    }


def inspect_job(root: Path, job_id: str, *, journal_tail: int = 20) -> dict[str, Any]:
    queue = DurableQueue(root)
    job = queue.load(job_id)
    return {
        "job": job,
        "journal": _journal_for_job(root, job_id, limit=journal_tail),
    }


def runtime_report(root: Path, *, journal_tail: int = 20) -> dict[str, Any]:
    return {
        "queue": queue_summary(root),
        "registry": _registry_summary(root),
        "quality": load_quality_metrics(root),
        "failures": _jsonl_tail(root / "artifacts" / "failures" / "events.jsonl", limit=journal_tail),
        "journal_tail": _jsonl_tail(root / "artifacts" / "execution" / "journal.jsonl", limit=journal_tail),
    }


def _registry_summary(root: Path) -> dict[str, Any]:
    path = root / "registry" / "capabilities.json"
    if not path.exists():
        return {"status": "missing", "counts": {}, "capabilities": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    capabilities = payload.get("capabilities", [])
    counts = Counter(str(item.get("lifecycle_status", "unknown")) for item in capabilities)
    return {
        "status": "ok",
        "counts": dict(sorted(counts.items())),
        "capabilities": [
            {
                "id": item.get("id"),
                "status": item.get("lifecycle_status"),
                "determinism_grade": item.get("determinism_grade"),
            }
            for item in capabilities
        ],
    }


def _job_brief(job: dict[str, Any]) -> dict[str, Any]:
    pipeline = dict(job.get("pipeline", {}))
    result = dict(job.get("result") or {})
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "pipeline_id": pipeline.get("id"),
        "priority": job.get("priority"),
        "attempts": job.get("attempts"),
        "max_attempts": job.get("max_attempts"),
        "worker_id": job.get("worker_id"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "lease_expires_at": job.get("lease_expires_at"),
        "stale": _is_stale(job) if job.get("status") == "running" else False,
        "packet_count": len(result.get("layer_packets", [])),
        "error": job.get("error"),
    }


def _is_stale(job: dict[str, Any]) -> bool:
    lease = str(job.get("lease_expires_at") or "")
    if not lease:
        return False
    return _parse_time(lease) <= time.time()


def _journal_for_job(root: Path, job_id: str, *, limit: int) -> list[dict[str, Any]]:
    events = _jsonl_tail(root / "artifacts" / "execution" / "journal.jsonl", limit=500)
    return [event for event in events if event.get("job_id") == job_id][-limit:]


def _jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"raw": line, "parse_error": True})
    return events


def _parse_time(value: str) -> float:
    if not value:
        return 0.0
    return datetime.fromisoformat(value).timestamp()
