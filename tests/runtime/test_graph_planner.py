from __future__ import annotations

from pathlib import Path

from runtime.executor import execute_pipeline
from runtime.graph_planner import plan_from_spec, plan_pipeline
from runtime.registry import CapabilityRegistry


def test_rule_based_graph_planner_builds_executable_pipeline():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    pipeline = plan_pipeline("normalize_then_hash", registry)

    result = execute_pipeline(root, pipeline, {"text": " hello   world "})

    assert result["status"] == "ok"
    assert result["completed_nodes"] == ["normalize", "hash"]
    assert result["outputs"]["normalize"] == {"text": "hello world"}
    assert result["outputs"]["hash"]["hash"].startswith("sha256:")


def test_graph_planner_builds_markdown_file_pipeline(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    monkeypatch.chdir(tmp_path)
    Path("in.md").write_text("# Hello **planner**", encoding="utf-8")
    pipeline = plan_pipeline("markdown_file_to_text_file", registry)

    result = execute_pipeline(root, pipeline, {"input_path": "in.md", "output_path": "out.txt"})

    assert result["status"] == "ok"
    assert Path("out.txt").read_text(encoding="utf-8") == "Hello planner"


def test_graph_planner_builds_markdown_to_rtf_file_pipeline(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    monkeypatch.chdir(tmp_path)
    Path("in.md").write_text("# Hello **planner**", encoding="utf-8")
    pipeline = plan_pipeline("markdown_file_to_rtf_file", registry)

    result = execute_pipeline(root, pipeline, {"input_path": "in.md", "output_path": "out.rtf"})

    output = Path("out.rtf").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert output.startswith("{\\rtf1")
    assert "\\b planner\\b0" in output


def test_graph_planner_accepts_structured_goal_spec():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    planned = plan_from_spec(
        {
            "id": "spec_hash",
            "steps": [
                {"id": "normalize", "capability": "normalize_text", "input": {"text": "$input.text"}},
                {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.normalize.output.text"}},
            ],
        },
        registry,
    )

    result = execute_pipeline(root, planned["pipeline"], {"text": " hi  there "})

    assert result["status"] == "ok"
    assert planned["selection"][0]["capability_id"] == "normalize_text"


def test_graph_planner_builds_spreadsheet_file_pipelines(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    monkeypatch.chdir(tmp_path)
    Path("in.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    to_xlsx = plan_pipeline("csv_to_spreadsheet", registry)

    first = execute_pipeline(root, to_xlsx, {"input_path": "in.csv", "output_path": "book.xlsx"})
    to_csv = plan_pipeline("spreadsheet_to_csv", registry)
    second = execute_pipeline(root, to_csv, {"input_path": "book.xlsx", "output_path": "out.csv"})

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert Path("out.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"
