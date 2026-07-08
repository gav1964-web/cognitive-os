from __future__ import annotations

from pathlib import Path

from runtime.extraction_proposal import build_extraction_proposal
from runtime.project_benchmark import analyze_project


ROOT = Path(__file__).resolve().parents[2]


def test_build_extraction_proposal_selects_safe_transform():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    outputs = analyze_project(project_dir)

    proposal = build_extraction_proposal(project_dir=project_dir, analyzer_outputs=outputs)

    assert proposal["status"] == "ok"
    assert proposal["selected"]["symbol"] == "normalize_text"
    assert proposal["safety"]["source_code_changes"] is False
    assert proposal["proposed_spec"]["id"] == "simple_cli_tool_normalize_text"
    assert proposal["proposed_spec"]["side_effects"]["filesystem"] == "none"


def test_build_extraction_proposal_can_write_foundry_spec(tmp_path):
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "data_pipeline_csv_json"
    outputs = analyze_project(project_dir)

    proposal = build_extraction_proposal(project_dir=project_dir, analyzer_outputs=outputs, write_spec=True, root=tmp_path)

    assert proposal["status"] == "ok"
    assert Path(proposal["spec_path"]).exists()
    assert proposal["proposed_spec"]["source_extraction"]["source"].endswith(":normalize_rows")
    assert proposal["proposed_spec"]["quality_gate"]["sample_input"] == {"rows": [{"value": " Sample "}]}


def test_build_extraction_proposal_uses_minimal_plan_order_for_ties():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "bot_with_handlers"
    outputs = analyze_project(project_dir)

    proposal = build_extraction_proposal(project_dir=project_dir, analyzer_outputs=outputs)

    assert proposal["status"] == "ok"
    assert proposal["selected"]["capability"] == "bot.py:parse_command"
