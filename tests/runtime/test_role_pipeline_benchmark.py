from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.local_inference import LocalInferenceConfig
from runtime.role_pipeline_benchmark import run_role_pipeline_benchmark


ROOT = Path(__file__).resolve().parents[2]


def test_role_pipeline_benchmark_scores_corpus():
    report = run_role_pipeline_benchmark(
        ROOT,
        benchmarks_dir=ROOT / "benchmarks" / "project_analyzer",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["project_count"] >= 8
    assert report["summary"]["artifact_score"] >= 0.95
    assert report["summary"]["implementation_score"] == 1.0
    assert report["summary"]["qa_score"] == 1.0
    assert report["summary"]["safety_score"] == 1.0
    assert report["summary"]["llm_invoked"] == 0
    assert report["summary"]["advisory_quality"]["accepted_risk_count"] == 0
    assert Path(report["report_path"]).exists()


def test_role_pipeline_benchmark_cli():
    tool = ROOT / "tools" / "role_pipeline_benchmark.py"
    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(ROOT), "--write"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["summary"]["safety_score"] == 1.0
    assert payload["summary"]["implementation_score"] == 1.0
    assert payload["summary"]["qa_score"] == 1.0
    assert "advisory_delta_score" in payload["summary"]
    assert "advisory_quality" in payload["summary"]


def test_role_pipeline_benchmark_architect_llm_fallback():
    config = LocalInferenceConfig(base_url="http://127.0.0.1:9/v1", model="missing", timeout_seconds=0.05)
    report = run_role_pipeline_benchmark(
        ROOT,
        benchmarks_dir=ROOT / "benchmarks" / "project_analyzer",
        architect_advisory_config=config,
    )

    assert report["status"] == "ok"
    assert report["summary"]["artifact_score"] == 1.0
    assert report["summary"]["implementation_score"] == 1.0
    assert report["summary"]["qa_score"] == 1.0
    assert report["summary"]["llm_invoked"] == 0
    assert report["summary"]["advisory_quality"]["rejected_reason_counts"] == {}
