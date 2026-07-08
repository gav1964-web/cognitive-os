from __future__ import annotations

from pathlib import Path

from runtime.project_benchmark import run_benchmark_case, run_benchmark_suite


ROOT = Path(__file__).resolve().parents[2]


def test_project_analyzer_benchmark_case_scores_expected_analysis():
    case_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    result = run_benchmark_case(case_dir)

    assert result["status"] == "ok"
    assert result["score"]["expected"] > 0
    assert result["score"]["recall"] > 0
    readiness = result["project_map_report"]["answers"]["6_runtime_extraction_readiness"]
    assert readiness["minimal_extraction_plan"]["capabilities_to_extract"]
    assert "level35_project_signals" in result
    assert "analysis_tasks" in result


def test_project_analyzer_benchmark_suite_has_category_summary():
    report = run_benchmark_suite(ROOT, benchmarks_dir=ROOT / "benchmarks" / "project_analyzer")

    assert report["status"] == "ok"
    assert report["project_count"] >= 8
    assert "capability_candidates" in report["category_summary"]
