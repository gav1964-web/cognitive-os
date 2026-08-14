from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.durable_queue import DurableQueue
from runtime.models import Pipeline, PipelineNode
from runtime.registry import CapabilityRegistry


def test_queue_cleanup_and_registry_selection_report_cli(runtime_workspace):
    source = Path(__file__).resolve().parents[2]
    queue = DurableQueue(runtime_workspace)
    pipeline = Pipeline(
        id="cleanup_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )
    job_id = queue.enqueue(pipeline, {"value": "cleanup"})
    queue.complete(job_id, result={"status": "ok", "outputs": {}})

    cleanup = _run_tool(source, runtime_workspace, "queue_cleanup.py", "--archive-terminal")
    report = _run_tool(source, runtime_workspace, "registry_selection_report.py")

    assert cleanup["archived"] == [job_id]
    assert any(item["id"] == "hash_payload" for item in report["capabilities"])


def test_runtime_smoke_skip_pytest_cli(runtime_workspace):
    source = Path(__file__).resolve().parents[2]
    result = _run_tool(source, runtime_workspace, "runtime_smoke.py", "--skip-pytest")

    assert result["status"] == "ok"


def test_registry_selection_report_api(runtime_workspace):
    root = runtime_workspace
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    report = registry.selection_report()

    assert any(item["id"] == "normalize_text" for item in report["capabilities"])


def _run_tool(source: Path, root: Path, tool_name: str, *args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(source / "tools" / tool_name), "--root", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
