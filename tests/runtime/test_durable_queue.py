from __future__ import annotations

from pathlib import Path

from runtime.durable_queue import DurableQueue, job_pipeline
from runtime.models import Pipeline, PipelineNode


def test_durable_queue_persists_and_claims_jobs(tmp_path):
    queue = DurableQueue(tmp_path)
    pipeline = Pipeline(
        id="queued_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )

    job_id = queue.enqueue(pipeline, {"value": "queued"})
    reloaded = DurableQueue(tmp_path)
    claimed = reloaded.claim_next("worker-1")

    assert claimed is not None
    assert claimed["job_id"] == job_id
    assert claimed["status"] == "running"
    assert job_pipeline(claimed).id == "queued_hash"

    reloaded.complete(job_id, result={"status": "ok", "outputs": {}})
    assert reloaded.load(job_id)["status"] == "succeeded"


def test_durable_queue_requeues_stale_running_jobs(tmp_path):
    queue = DurableQueue(tmp_path)
    pipeline = Pipeline(
        id="queued_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )

    job_id = queue.enqueue(pipeline, {"value": "queued"})
    assert queue.claim_next("worker-1", lease_seconds=-1) is not None

    requeued = queue.requeue_stale_running(older_than_seconds=None)

    assert requeued == [job_id]
    assert queue.load(job_id)["status"] == "queued"


def test_durable_queue_claims_high_priority_first(tmp_path):
    queue = DurableQueue(tmp_path)
    pipeline = Pipeline(
        id="queued_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )
    low = queue.enqueue(pipeline, {"value": "low"}, priority=100)
    high = queue.enqueue(pipeline, {"value": "high"}, priority=1)

    claimed = queue.claim_next("worker-1")

    assert claimed is not None
    assert claimed["job_id"] == high
    assert low != high


def test_durable_queue_heartbeat_extends_lease(tmp_path):
    queue = DurableQueue(tmp_path)
    pipeline = Pipeline(
        id="queued_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )
    job_id = queue.enqueue(pipeline, {"value": "lease"})
    claimed = queue.claim_next("worker-1", lease_seconds=0.1)
    assert claimed is not None

    assert queue.heartbeat(job_id, "worker-1", lease_seconds=30)
    assert queue.requeue_stale_running(older_than_seconds=None) == []


def test_durable_queue_job_level_retry(tmp_path):
    queue = DurableQueue(tmp_path)
    pipeline = Pipeline(
        id="queued_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )
    job_id = queue.enqueue(pipeline, {"value": "retry"}, max_attempts=2)
    assert queue.claim_next("worker-1") is not None

    queue.fail(job_id, error="boom")

    job = queue.load(job_id)
    assert job["status"] == "queued"
    assert job["attempts"] == 1
