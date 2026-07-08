from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from runtime.deterministic_goal_planner import plan_from_required_capabilities
from runtime.registry import CapabilityRegistry


def test_deterministic_goal_planner_builds_list_files_plan():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    planned = plan_from_required_capabilities("List files from $input.path", ["list_files"], registry)

    assert planned is not None
    assert planned["planner"] == "deterministic_required_capabilities"
    assert planned["pipeline"]["nodes"][0]["capability"] == "list_files"


def test_deterministic_goal_planner_builds_scan_project_tree_plan():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    planned = plan_from_required_capabilities(
        "Analyze project map",
        [
            "scan_project_tree",
            "detect_project_stack",
            "read_many_files",
            "extract_python_structure",
            "extract_runtime_commands",
            "project_map_report",
        ],
        registry,
    )

    assert planned is not None
    assert planned["planner"] == "deterministic_required_capabilities"
    assert [node["capability"] for node in planned["pipeline"]["nodes"]] == [
        "scan_project_tree",
        "detect_project_stack",
        "read_many_files",
        "extract_python_structure",
        "extract_runtime_commands",
        "project_map_report",
    ]
    assert planned["pipeline"]["nodes"][0]["input"]["max_depth"] == 8
    assert planned["pipeline"]["nodes"][2]["input"]["paths"] == []
    assert planned["pipeline"]["nodes"][2]["input"]["auto_discover"] is True
    assert planned["pipeline"]["nodes"][-1]["input"]["tree"] == "$nodes.scan_project_tree.output"


def test_goal_run_list_files_uses_deterministic_planner():
    root = Path(__file__).resolve().parents[2]
    # Use a clean runtime root so a matured memory template cannot supersede
    # the deterministic required-capabilities planner.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cos_det_goal_") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(root / "plugins", temp_root / "plugins")
        shutil.copytree(root / "registry", temp_root / "registry")
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "goal_run.py"),
                "--root",
                str(temp_root),
                "--goal",
                "List files from $input.path",
                "--execute",
                "--input-json",
                json.dumps({"path": "plugins"}),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    payload = json.loads(result.stdout)

    assert payload["level35_plan"]["planner"] == "deterministic_required_capabilities"
    assert payload["execution"]["status"] == "ok"
    assert payload["execution"]["outputs"]["list_files"]["files"]


def test_deterministic_goal_planner_builds_markdown_file_plan():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    planned = plan_from_required_capabilities(
        "Convert markdown file from $input.input_path to plain text file at $input.output_path",
        ["read_text_file", "markdown_to_text", "write_text_file"],
        registry,
    )

    assert planned is not None
    assert [node["capability"] for node in planned["pipeline"]["nodes"]] == [
        "read_text_file",
        "markdown_to_text",
        "write_text_file",
    ]


def test_deterministic_goal_planner_builds_markdown_to_rtf_file_plan():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    planned = plan_from_required_capabilities(
        "Convert markdown file from $input.input_path to RTF file at $input.output_path",
        ["read_text_file", "markdown_to_rtf", "write_text_file"],
        registry,
    )

    assert planned is not None
    assert [node["capability"] for node in planned["pipeline"]["nodes"]] == [
        "read_text_file",
        "markdown_to_rtf",
        "write_text_file",
    ]
    assert planned["pipeline"]["nodes"][-1]["input"]["text"] == "$nodes.markdown_to_rtf.output.rtf"


def test_deterministic_goal_planner_builds_translate_plan():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    planned = plan_from_required_capabilities("Translate $input.text to German", ["translate_text"], registry)

    assert planned is not None
    assert planned["planner"] == "deterministic_required_capabilities"
    assert planned["pipeline"]["nodes"][0]["capability"] == "translate_text"
    assert planned["pipeline"]["nodes"][0]["input"]["target_language"] == "German"


def test_goal_run_translate_uses_promoted_capability():
    root = Path(__file__).resolve().parents[2]
    # Use a clean runtime root so a matured memory template cannot supersede
    # the deterministic required-capabilities planner.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cos_translate_goal_") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(root / "plugins", temp_root / "plugins")
        shutil.copytree(root / "registry", temp_root / "registry")
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "goal_run.py"),
                "--root",
                str(temp_root),
                "--goal",
                "Translate input text from $input.text to German",
                "--execute",
                "--input-json",
                json.dumps({"text": "hello"}),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    payload = json.loads(result.stdout)

    assert payload["level4_decision"]["action"] == "PLAN_WITH_L35"
    assert payload["level35_plan"]["planner"] == "deterministic_required_capabilities"
    assert payload["execution"]["outputs"]["translate_text"] == {"text": "hallo", "language": "German"}


def test_deterministic_goal_planner_builds_parse_pdf_plan_when_available():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    if "parse_pdf" not in registry.capabilities:
        return

    planned = plan_from_required_capabilities("Parse a PDF file from $input.path", ["parse_pdf"], registry)

    assert planned is not None
    assert planned["pipeline"]["nodes"][0]["capability"] == "parse_pdf"
    assert planned["pipeline"]["nodes"][0]["input"]["path"] == "$input.path"


def test_deterministic_goal_planner_builds_spreadsheet_conversion_plans():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()

    to_csv = plan_from_required_capabilities("Convert XLSX file to CSV", ["spreadsheet_to_csv"], registry)
    to_xlsx = plan_from_required_capabilities("Convert CSV file to XLSX", ["csv_to_spreadsheet"], registry)

    assert to_csv is not None
    assert to_csv["pipeline"]["nodes"][0]["capability"] == "spreadsheet_to_csv"
    assert to_csv["pipeline"]["nodes"][0]["input"] == {
        "input_path": "$input.input_path",
        "output_path": "$input.output_path",
    }
    assert to_xlsx is not None
    assert to_xlsx["pipeline"]["nodes"][0]["capability"] == "csv_to_spreadsheet"
