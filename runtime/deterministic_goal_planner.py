"""Deterministic plans for Level 4 routes with known capability chains."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .graph_planner import plan_from_spec
from .models import Pipeline
from .pipeline import validate_pipeline
from .registry import CapabilityRegistry


def plan_from_required_capabilities(
    goal: str,
    required_capabilities: list[str],
    registry: CapabilityRegistry,
) -> dict[str, Any] | None:
    proposal = _proposal_for(goal, required_capabilities)
    if proposal is None:
        return None
    planned = plan_from_spec(proposal, registry)
    pipeline = planned["pipeline"]
    validate_pipeline(pipeline, registry)
    return {
        "status": "planned",
        "goal": goal,
        "proposal": proposal,
        "pipeline": _pipeline_to_dict(pipeline),
        "selection": planned["selection"],
        "planner": "deterministic_required_capabilities",
    }


def _proposal_for(goal: str, required_capabilities: list[str]) -> dict[str, Any] | None:
    capabilities = tuple(required_capabilities)
    if capabilities == ("normalize_text", "hash_payload"):
        return {
            "id": "deterministic_normalize_hash",
            "version": "0.1.0",
            "steps": [
                {"id": "normalize_text", "capability": "normalize_text", "input": {"text": "$input.text"}},
                {
                    "id": "hash_payload",
                    "capability": "hash_payload",
                    "input": {"value": "$nodes.normalize_text.output.text"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("list_files",):
        return {
            "id": "deterministic_list_files",
            "version": "0.1.0",
            "steps": [
                {"id": "list_files", "capability": "list_files", "input": {"path": "$input.path"}},
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("scan_project_tree",):
        return {
            "id": "deterministic_scan_project_tree",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "scan_project_tree",
                    "capability": "scan_project_tree",
                    "input": {
                        "path": "$input.path",
                        "max_files": 5000,
                        "max_depth": 8,
                    },
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("scan_project_tree", "detect_project_stack"):
        return {
            "id": "deterministic_project_intake",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "scan_project_tree",
                    "capability": "scan_project_tree",
                    "input": {
                        "path": "$input.path",
                        "max_files": 5000,
                        "max_depth": 8,
                    },
                },
                {
                    "id": "detect_project_stack",
                    "capability": "detect_project_stack",
                    "input": {"path": "$input.path"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("scan_project_tree", "detect_project_stack", "read_many_files", "extract_python_structure"):
        return {
            "id": "deterministic_project_analysis_intake",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "scan_project_tree",
                    "capability": "scan_project_tree",
                    "input": {
                        "path": "$input.path",
                        "max_files": 5000,
                        "max_depth": 8,
                    },
                },
                {
                    "id": "detect_project_stack",
                    "capability": "detect_project_stack",
                    "input": {"path": "$input.path"},
                },
                {
                    "id": "read_many_files",
                    "capability": "read_many_files",
                    "input": {
                        "root": "$input.path",
                        "paths": [],
                        "auto_discover": True,
                        "max_bytes_per_file": 50000,
                        "max_files": 12,
                    },
                },
                {
                    "id": "extract_python_structure",
                    "capability": "extract_python_structure",
                    "input": {
                        "root": "$input.path",
                        "max_files": 50,
                        "max_bytes_per_file": 200000,
                    },
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == (
        "scan_project_tree",
        "detect_project_stack",
        "read_many_files",
        "extract_python_structure",
        "extract_runtime_commands",
        "project_map_report",
    ):
        return {
            "id": "deterministic_project_map_report",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "scan_project_tree",
                    "capability": "scan_project_tree",
                    "input": {"path": "$input.path", "max_files": 5000, "max_depth": 8},
                },
                {"id": "detect_project_stack", "capability": "detect_project_stack", "input": {"path": "$input.path"}},
                {
                    "id": "read_many_files",
                    "capability": "read_many_files",
                    "input": {
                        "root": "$input.path",
                        "paths": [],
                        "auto_discover": True,
                        "max_bytes_per_file": 50000,
                        "max_files": 12,
                    },
                },
                {
                    "id": "extract_python_structure",
                    "capability": "extract_python_structure",
                    "input": {"root": "$input.path", "max_files": 50, "max_bytes_per_file": 200000},
                },
                {
                    "id": "extract_runtime_commands",
                    "capability": "extract_runtime_commands",
                    "input": {"root": "$input.path"},
                },
                {
                    "id": "project_map_report",
                    "capability": "project_map_report",
                    "input": {
                        "tree": "$nodes.scan_project_tree.output",
                        "stack": "$nodes.detect_project_stack.output",
                        "files": "$nodes.read_many_files.output",
                        "python_structure": "$nodes.extract_python_structure.output",
                        "runtime_commands": "$nodes.extract_runtime_commands.output",
                    },
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == (
        "scan_project_tree",
        "detect_project_stack",
        "read_many_files",
        "extract_python_structure",
        "extract_runtime_commands",
        "project_map_report",
        "project_fact_questions",
    ):
        return {
            "id": "deterministic_project_fact_questions",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "scan_project_tree",
                    "capability": "scan_project_tree",
                    "input": {"path": "$input.path", "max_files": 5000, "max_depth": 8},
                },
                {"id": "detect_project_stack", "capability": "detect_project_stack", "input": {"path": "$input.path"}},
                {
                    "id": "read_many_files",
                    "capability": "read_many_files",
                    "input": {
                        "root": "$input.path",
                        "paths": [],
                        "auto_discover": True,
                        "max_bytes_per_file": 50000,
                        "max_files": 12,
                    },
                },
                {
                    "id": "extract_python_structure",
                    "capability": "extract_python_structure",
                    "input": {"root": "$input.path", "max_files": 5000, "max_bytes_per_file": 2000000},
                },
                {
                    "id": "extract_runtime_commands",
                    "capability": "extract_runtime_commands",
                    "input": {"root": "$input.path"},
                },
                {
                    "id": "project_map_report",
                    "capability": "project_map_report",
                    "input": {
                        "tree": "$nodes.scan_project_tree.output",
                        "stack": "$nodes.detect_project_stack.output",
                        "files": "$nodes.read_many_files.output",
                        "python_structure": "$nodes.extract_python_structure.output",
                        "runtime_commands": "$nodes.extract_runtime_commands.output",
                    },
                },
                {
                    "id": "project_fact_questions",
                    "capability": "project_fact_questions",
                    "input": {
                        "tree": "$nodes.scan_project_tree.output",
                        "python_structure": "$nodes.extract_python_structure.output",
                        "project_map_report": "$nodes.project_map_report.output",
                        "scope": "active_core",
                        "questions": [],
                    },
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("read_text_file", "markdown_to_text", "write_text_file"):
        return {
            "id": "deterministic_markdown_file_to_text_file",
            "version": "0.1.0",
            "steps": [
                {"id": "read_text_file", "capability": "read_text_file", "input": {"path": "$input.input_path"}},
                {
                    "id": "markdown_to_text",
                    "capability": "markdown_to_text",
                    "input": {"markdown": "$nodes.read_text_file.output.text"},
                },
                {
                    "id": "write_text_file",
                    "capability": "write_text_file",
                    "input": {"path": "$input.output_path", "text": "$nodes.markdown_to_text.output.text"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("read_text_file", "markdown_to_rtf", "write_text_file"):
        return {
            "id": "deterministic_markdown_file_to_rtf_file",
            "version": "0.1.0",
            "steps": [
                {"id": "read_text_file", "capability": "read_text_file", "input": {"path": "$input.input_path"}},
                {
                    "id": "markdown_to_rtf",
                    "capability": "markdown_to_rtf",
                    "input": {"markdown": "$nodes.read_text_file.output.text"},
                },
                {
                    "id": "write_text_file",
                    "capability": "write_text_file",
                    "input": {"path": "$input.output_path", "text": "$nodes.markdown_to_rtf.output.rtf"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("fetch_html", "extract_links"):
        return {
            "id": "deterministic_fetch_links",
            "version": "0.1.0",
            "steps": [
                {"id": "fetch_html", "capability": "fetch_html", "input": {"url": "$input.url"}},
                {
                    "id": "extract_links",
                    "capability": "extract_links",
                    "input": {"html": "$nodes.fetch_html.output.html"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("fetch_html", "parse_title", "save_json"):
        return {
            "id": "deterministic_fetch_parse_save",
            "version": "0.1.0",
            "steps": [
                {"id": "fetch", "capability": "fetch_html", "input": {"url": "$input.url"}},
                {
                    "id": "parse",
                    "capability": "parse_title",
                    "input": {"html": "$nodes.fetch.output.html"},
                },
                {
                    "id": "save",
                    "capability": "save_json",
                    "input": {"path": "$input.output_path", "data": "$nodes.parse.output"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("translate_text",):
        return {
            "id": "deterministic_translate_text",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "translate_text",
                    "capability": "translate_text",
                    "input": {"text": "$input.text", "target_language": _target_language_for_goal(goal)},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("parse_pdf",):
        return {
            "id": "deterministic_parse_pdf",
            "version": "0.1.0",
            "steps": [
                {"id": "parse_pdf", "capability": "parse_pdf", "input": {"path": "$input.path"}},
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("spreadsheet_to_csv",):
        return {
            "id": "deterministic_spreadsheet_to_csv",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "spreadsheet_to_csv",
                    "capability": "spreadsheet_to_csv",
                    "input": {"input_path": "$input.input_path", "output_path": "$input.output_path"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    if capabilities == ("csv_to_spreadsheet",):
        return {
            "id": "deterministic_csv_to_spreadsheet",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "csv_to_spreadsheet",
                    "capability": "csv_to_spreadsheet",
                    "input": {"input_path": "$input.input_path", "output_path": "$input.output_path"},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    return None


def _target_language_for_goal(goal: str) -> str:
    normalized = goal.lower()
    if "german" in normalized or "deutsch" in normalized or "немец" in normalized:
        return "German"
    return "$input.target_language"


def _pipeline_to_dict(pipeline: Pipeline) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "version": pipeline.version,
        "nodes": [asdict(node) for node in pipeline.nodes],
        "edges": pipeline.edges,
        "retry_policy": pipeline.retry_policy,
    }
