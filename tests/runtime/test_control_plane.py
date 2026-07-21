from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from runtime.control_plane import inspect_job, queue_summary, runtime_report
from runtime.durable_queue import DurableQueue
from runtime.models import Pipeline, PipelineNode


def test_control_plane_summarizes_and_inspects_jobs(tmp_path):
    queue = DurableQueue(tmp_path)
    pipeline = Pipeline(
        id="control_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )
    job_id = queue.enqueue(pipeline, {"value": "control"}, priority=7)
    claimed = queue.claim_next("control-test")
    assert claimed is not None
    queue.complete(job_id, result={"status": "ok", "layer_packets": [{"packet_type": "execution_event"}]})

    summary = queue_summary(tmp_path)
    inspected = inspect_job(tmp_path, job_id)
    report = runtime_report(tmp_path)

    assert summary["counts"]["succeeded"] == 1
    assert summary["jobs"][0]["priority"] == 7
    assert summary["jobs"][0]["packet_count"] == 1
    assert inspected["job"]["job_id"] == job_id
    assert report["queue"]["total"] == 1


def test_control_plane_cli_status_cancel_requeue_and_report():
    root = Path(__file__).resolve().parents[2]
    shutil.rmtree(root / "artifacts" / "queue", ignore_errors=True)
    queue = DurableQueue(root)
    pipeline = Pipeline(
        id="control_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )
    job_id = queue.enqueue(pipeline, {"value": "control"}, priority=3)

    status = _run_tool(root, "queue_status.py")
    inspected = _run_tool(root, "job_inspect.py", "--id", job_id)
    cancelled = _run_tool(root, "job_cancel.py", "--id", job_id, "--reason", "test_cancel")
    requeued = _run_tool(root, "job_requeue.py", "--id", job_id)
    report = _run_tool(root, "runtime_report.py", "--journal-tail", "5")

    assert status["total"] == 1
    assert inspected["job"]["job_id"] == job_id
    assert cancelled["status"] == "cancelled"
    assert requeued["requeued"] == []
    assert report["queue"]["total"] == 1


def _run_tool(root: Path, tool_name: str, *args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(root / "tools" / tool_name), "--root", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
