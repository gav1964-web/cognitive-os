from __future__ import annotations

from pathlib import Path
import shutil

from runtime.durable_queue import DurableQueue
from runtime.models import Pipeline, PipelineNode
from runtime.registry import CapabilityRegistry
from runtime.worker_pool import WorkerPool


def test_worker_pool_drains_durable_queue():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    shutil.rmtree(root / "artifacts" / "queue", ignore_errors=True)
    queue = DurableQueue(root)
    pipeline = Pipeline(
        id="worker_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={"node_timeout_seconds": 5},
    )
    first = queue.enqueue(pipeline, {"value": "first"})
    second = queue.enqueue(pipeline, {"value": "second"})

    result = WorkerPool(root, max_workers=2).run_until_idle(max_jobs=2)

    assert result["status"] == "idle"
    assert result["processed"] == 2
    assert queue.load(first)["status"] == "succeeded"
    assert queue.load(second)["status"] == "succeeded"
    assert queue.load(first)["result"]["outputs"]["hash"]["hash"].startswith("sha256:")


def test_worker_pool_retries_failed_job_until_max_attempts():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    shutil.rmtree(root / "artifacts" / "queue", ignore_errors=True)
    queue = DurableQueue(root)
    pipeline = Pipeline(
        id="worker_bad",
        version="0.1.0",
        nodes=[PipelineNode(id="missing", capability="missing_capability", input={})],
        edges=[],
        retry_policy={},
    )
    job_id = queue.enqueue(pipeline, {}, max_attempts=2)
    pool = WorkerPool(root, max_workers=1, force_process_boundary=False)

    first = pool.run_until_idle(max_jobs=1)
    second = pool.run_until_idle(max_jobs=1)

    assert first["results"][0]["status"] == "retry_scheduled"
    assert second["results"][0]["status"] == "failed"
    job = queue.load(job_id)
    assert job["status"] == "failed"
    assert job["attempts"] == 2


def test_worker_pool_bounded_loop_runs_to_idle():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    shutil.rmtree(root / "artifacts" / "queue", ignore_errors=True)
    queue = DurableQueue(root)
    pipeline = Pipeline(
        id="worker_loop",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={"node_timeout_seconds": 5},
    )
    queue.enqueue(pipeline, {"value": "loop"})

    result = WorkerPool(root, max_workers=1).run_loop(max_cycles=2, idle_sleep_seconds=0, max_jobs_per_cycle=1)

    assert result["status"] == "stopped"
    assert result["cycles"] == 2
    assert result["processed"] == 1
