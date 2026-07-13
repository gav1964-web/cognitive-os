"""Worker pool for durable queue jobs."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .durable_queue import DurableQueue, job_pipeline
from .execution_journal import append_journal_event
from .executor import execute_pipeline
from .goal_runtime import SpinalRecoveryController


class WorkerPool:
    def __init__(
        self,
        root: Path,
        *,
        max_workers: int = 2,
        worker_prefix: str = "worker",
        force_process_boundary: bool = True,
        lease_seconds: float = 30.0,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self.root = root
        self.max_workers = max_workers
        self.worker_prefix = worker_prefix
        self.force_process_boundary = force_process_boundary
        self.lease_seconds = lease_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.queue = DurableQueue(root)

    def run_until_idle(self, *, max_jobs: int | None = None) -> dict[str, Any]:
        processed = 0
        results: list[dict[str, Any]] = []
        while max_jobs is None or processed < max_jobs:
            batch_limit = self.max_workers if max_jobs is None else min(self.max_workers, max_jobs - processed)
            claims = []
            for index in range(batch_limit):
                worker_id = f"{self.worker_prefix}-{index + 1}"
                job = self.queue.claim_next(worker_id, lease_seconds=self.lease_seconds)
                if job is not None:
                    claims.append((worker_id, job))
            if not claims:
                break
            with ThreadPoolExecutor(max_workers=len(claims)) as executor:
                futures = {
                    executor.submit(
                        _run_job,
                        self.root,
                        self.queue,
                        worker_id,
                        job,
                        force_process_boundary=self.force_process_boundary,
                        lease_seconds=self.lease_seconds,
                        heartbeat_interval_seconds=self.heartbeat_interval_seconds,
                    ): job
                    for worker_id, job in claims
                }
                for future in as_completed(futures):
                    results.append(future.result())
                    processed += 1
        append_journal_event(
            self.root,
            {"event": "worker_pool_idle", "processed": processed, "max_workers": self.max_workers},
        )
        return {"status": "idle", "processed": processed, "results": results}

    def run_loop(
        self,
        *,
        max_cycles: int | None = None,
        idle_sleep_seconds: float = 1.0,
        max_jobs_per_cycle: int | None = None,
        stale_lease_seconds: float | None = None,
    ) -> dict[str, Any]:
        cycles = 0
        processed = 0
        while max_cycles is None or cycles < max_cycles:
            if stale_lease_seconds is not None:
                self.queue.requeue_stale_running(older_than_seconds=stale_lease_seconds)
            result = self.run_until_idle(max_jobs=max_jobs_per_cycle)
            processed += int(result["processed"])
            cycles += 1
            if result["processed"] == 0:
                time.sleep(idle_sleep_seconds)
        append_journal_event(
            self.root,
            {"event": "worker_pool_loop_stopped", "cycles": cycles, "processed": processed},
        )
        return {"status": "stopped", "cycles": cycles, "processed": processed}


def _run_job(
    root: Path,
    queue: DurableQueue,
    worker_id: str,
    job: dict[str, Any],
    *,
    force_process_boundary: bool,
    lease_seconds: float,
    heartbeat_interval_seconds: float,
) -> dict[str, Any]:
    job_id = str(job["job_id"])
    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(queue, job_id, worker_id, stop_heartbeat),
        kwargs={"lease_seconds": lease_seconds, "interval_seconds": heartbeat_interval_seconds},
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        append_journal_event(
            root,
            {
                "event": "worker_started",
                "job_id": job_id,
                "worker_id": worker_id,
                "pipeline_id": job["pipeline"]["id"],
            },
        )
        pipeline = job_pipeline(job)
        if force_process_boundary:
            pipeline.retry_policy["process_boundary"] = True
            pipeline.retry_policy.setdefault("node_timeout_seconds", 10)
        packets: list[dict[str, Any]] = []
        recovery = SpinalRecoveryController(max_adaptations=2, packet_sink=packets.append)
        result = execute_pipeline(
            root,
            pipeline,
            dict(job["root_input"]),
            reset_registry=bool(job.get("reset_registry", False)),
            correlation_id=job_id,
            packet_sink=packets.append,
            recovery_handler=recovery,
        )
        result["layer_packets"] = packets
        result["level35_adaptations"] = recovery.adaptations
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)
        queue.complete(job_id, result=result)
        append_journal_event(
            root,
            {
                "event": "worker_completed",
                "job_id": job_id,
                "worker_id": worker_id,
                "pipeline_id": job["pipeline"]["id"],
                "result_status": result.get("status"),
            },
        )
        return {
            "job_id": job_id,
            "status": "completed",
            "result_status": result.get("status"),
            "packet_count": len(packets),
            "adaptation_count": len(recovery.adaptations),
        }
    except Exception as exc:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)
        queue.fail(job_id, error=f"{type(exc).__name__}: {exc}")
        current = queue.load(job_id)
        status = "retry_scheduled" if current.get("status") == "queued" else "failed"
        append_journal_event(
            root,
            {
                "event": "worker_failed",
                "job_id": job_id,
                "worker_id": worker_id,
                "pipeline_id": job["pipeline"]["id"],
                "error": f"{type(exc).__name__}: {exc}",
                "job_status": current.get("status"),
            },
        )
        return {"job_id": job_id, "status": status, "error": f"{type(exc).__name__}: {exc}"}


def _heartbeat_loop(
    queue: DurableQueue,
    job_id: str,
    worker_id: str,
    stop_event: threading.Event,
    *,
    lease_seconds: float,
    interval_seconds: float,
) -> None:
    while not stop_event.wait(interval_seconds):
        if not queue.heartbeat(job_id, worker_id, lease_seconds=lease_seconds):
            return
