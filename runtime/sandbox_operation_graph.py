"""Build a small operation graph for sandbox programmer operations."""

from __future__ import annotations

from typing import Any

from .sandbox_programmer_profiles import graph_family, profile_entry


def build_sandbox_operation_graph(operation: dict[str, Any]) -> dict[str, Any]:
    profile = str(operation.get("profile") or "text_expression")
    family = graph_family(profile)
    if family == "numeric_args_stdout":
        return _numeric_args_graph(operation)
    if family == "numeric_args_file":
        return _numeric_args_file_graph(operation)
    if family == "stdin_stdout_text":
        return _stdin_stdout_graph(operation)
    if family == "stdin_file_text":
        return _stdin_file_graph(operation)
    if family == "file_stdout_text":
        return _file_stdout_graph(operation)
    parser = _parser_for_profile(profile)
    transform_nodes = _transform_nodes(operation=operation, parser_output=str(parser["output"]))
    return {
        "artifact_type": "SandboxOperationGraph",
        "status": "ready",
        "operation": operation.get("operation"),
        "profile": profile,
        "nodes": [
            {
                "id": "read_input",
                "kind": "read",
                "contract": {"input": "input_path", "output": "utf8_text"},
                "side_effects": ["read_file"],
            },
            {
                "id": "parse_input",
                "kind": "parse",
                "contract": {"input": "utf8_text", "output": parser["output"]},
                "parser": parser["parser"],
            },
            *transform_nodes,
            {
                "id": "serialize_output",
                "kind": "serialize",
                "contract": {"input": "transform_result", "output": "utf8_text"},
            },
            {
                "id": "write_output",
                "kind": "write",
                "contract": {"input": "utf8_text", "output": "output_path"},
                "side_effects": ["write_file"],
            },
            {
                "id": "verify",
                "kind": "verify",
                "contract": {"input": "project_dir", "output": "compile_pytest_result"},
            },
        ],
        "edges": _edges_for_transform_nodes([node["id"] for node in transform_nodes]),
        "invariants": {
            "sandbox_only": True,
            "raw_model_output_executed": False,
            "source_tree_changes": False,
            "registry_changes": False,
        },
    }


def _parser_for_profile(profile: str) -> dict[str, Any]:
    row = profile_entry(profile)
    return {
        "parser": str(row.get("parser") or "utf8_text"),
        "output": str(row.get("parser_output") or "text"),
        "stable_shape": bool(row.get("stable_shape", True)),
    }


def _numeric_args_graph(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "SandboxOperationGraph",
        "status": "ready",
        "operation": operation.get("operation"),
        "profile": str(operation.get("profile") or "numeric_args_expression"),
        "nodes": [
            {
                "id": "read_argv",
                "kind": "read",
                "contract": {"input": "argv", "output": "raw_cli_args"},
                "side_effects": [],
            },
            {
                "id": "parse_args",
                "kind": "parse",
                "contract": {"input": "raw_cli_args", "output": "numeric_args"},
                "parser": "argparse_numeric_args",
            },
            {
                "id": "transform",
                "kind": "transform",
                "contract": {"input": "two_numbers", "output": "number"},
                "operation": operation.get("operation"),
            },
            {
                "id": "serialize_stdout",
                "kind": "serialize",
                "contract": {"input": "number", "output": "stdout_text"},
            },
            {
                "id": "write_stdout",
                "kind": "write",
                "contract": {"input": "stdout_text", "output": "terminal_stdout"},
                "side_effects": ["write_stdout"],
            },
            {
                "id": "verify",
                "kind": "verify",
                "contract": {"input": "project_dir", "output": "compile_pytest_result"},
            },
        ],
        "edges": [
            ["read_argv", "parse_args"],
            ["parse_args", "transform"],
            ["transform", "serialize_stdout"],
            ["serialize_stdout", "write_stdout"],
            ["write_stdout", "verify"],
        ],
        "invariants": {
            "sandbox_only": True,
            "raw_model_output_executed": False,
            "source_tree_changes": False,
            "registry_changes": False,
        },
    }


def _numeric_args_file_graph(operation: dict[str, Any]) -> dict[str, Any]:
    graph = _numeric_args_graph(operation)
    graph["profile"] = "numeric_args_file_expression"
    nodes = graph["nodes"]
    nodes[3] = {
        "id": "serialize_output",
        "kind": "serialize",
        "contract": {"input": "number", "output": "utf8_text"},
    }
    nodes[4] = {
        "id": "write_output",
        "kind": "write",
        "contract": {"input": "utf8_text", "output": "output_path"},
        "side_effects": ["write_file"],
    }
    graph["edges"] = [
        ["read_argv", "parse_args"],
        ["parse_args", "transform"],
        ["transform", "serialize_output"],
        ["serialize_output", "write_output"],
        ["write_output", "verify"],
    ]
    return graph


def _stdin_stdout_graph(operation: dict[str, Any]) -> dict[str, Any]:
    return _stdout_text_graph(
        operation=operation,
        read_node={
            "id": "read_stdin",
            "kind": "read",
            "contract": {"input": "stdin", "output": "utf8_text"},
            "side_effects": ["read_stdin"],
        },
        read_edge_from="read_stdin",
    )


def _stdin_file_graph(operation: dict[str, Any]) -> dict[str, Any]:
    return _file_output_text_graph(
        operation=operation,
        read_node={
            "id": "read_stdin",
            "kind": "read",
            "contract": {"input": "stdin", "output": "utf8_text"},
            "side_effects": ["read_stdin"],
        },
        read_edge_from="read_stdin",
    )


def _file_stdout_graph(operation: dict[str, Any]) -> dict[str, Any]:
    return _stdout_text_graph(
        operation=operation,
        read_node={
            "id": "read_input",
            "kind": "read",
            "contract": {"input": "input_path", "output": "utf8_text"},
            "side_effects": ["read_file"],
        },
        read_edge_from="read_input",
    )


def _file_output_text_graph(*, operation: dict[str, Any], read_node: dict[str, Any], read_edge_from: str) -> dict[str, Any]:
    profile = str(operation.get("profile") or "")
    return {
        "artifact_type": "SandboxOperationGraph",
        "status": "ready",
        "operation": operation.get("operation"),
        "profile": profile,
        "nodes": [
            read_node,
            {
                "id": "parse_input",
                "kind": "parse",
                "contract": {"input": "utf8_text", "output": "text"},
                "parser": "utf8_text",
            },
            {
                "id": "transform",
                "kind": "transform",
                "contract": {"input": "text", "output": "text"},
                "operation": operation.get("operation"),
            },
            {
                "id": "serialize_output",
                "kind": "serialize",
                "contract": {"input": "transform_result", "output": "utf8_text"},
            },
            {
                "id": "write_output",
                "kind": "write",
                "contract": {"input": "utf8_text", "output": "output_path"},
                "side_effects": ["write_file"],
            },
            {
                "id": "verify",
                "kind": "verify",
                "contract": {"input": "project_dir", "output": "compile_pytest_result"},
            },
        ],
        "edges": [
            [read_edge_from, "parse_input"],
            ["parse_input", "transform"],
            ["transform", "serialize_output"],
            ["serialize_output", "write_output"],
            ["write_output", "verify"],
        ],
        "invariants": {
            "sandbox_only": True,
            "raw_model_output_executed": False,
            "source_tree_changes": False,
            "registry_changes": False,
        },
    }


def _stdout_text_graph(*, operation: dict[str, Any], read_node: dict[str, Any], read_edge_from: str) -> dict[str, Any]:
    profile = str(operation.get("profile") or "")
    return {
        "artifact_type": "SandboxOperationGraph",
        "status": "ready",
        "operation": operation.get("operation"),
        "profile": profile,
        "nodes": [
            read_node,
            {
                "id": "parse_input",
                "kind": "parse",
                "contract": {"input": "utf8_text", "output": "text"},
                "parser": "utf8_text",
            },
            {
                "id": "transform",
                "kind": "transform",
                "contract": {"input": "text", "output": "text"},
                "operation": operation.get("operation"),
            },
            {
                "id": "serialize_stdout",
                "kind": "serialize",
                "contract": {"input": "transform_result", "output": "stdout_text"},
            },
            {
                "id": "write_stdout",
                "kind": "write",
                "contract": {"input": "stdout_text", "output": "terminal_stdout"},
                "side_effects": ["write_stdout"],
            },
            {
                "id": "verify",
                "kind": "verify",
                "contract": {"input": "project_dir", "output": "compile_pytest_result"},
            },
        ],
        "edges": [
            [read_edge_from, "parse_input"],
            ["parse_input", "transform"],
            ["transform", "serialize_stdout"],
            ["serialize_stdout", "write_stdout"],
            ["write_stdout", "verify"],
        ],
        "invariants": {
            "sandbox_only": True,
            "raw_model_output_executed": False,
            "source_tree_changes": False,
            "registry_changes": False,
        },
    }


def _transform_nodes(*, operation: dict[str, Any], parser_output: str) -> list[dict[str, Any]]:
    steps = operation.get("steps")
    if not isinstance(steps, list) or not steps:
        profile = str(operation.get("profile") or "text_expression")
        return [
            {
                "id": "transform",
                "kind": "transform",
                "contract": {"input": parser_output, "output": str(profile_entry(profile).get("transform_output") or parser_output)},
                "operation": operation.get("operation"),
            }
        ]
    nodes = []
    previous = parser_output
    for index, step in enumerate(steps, start=1):
        step_operation = str(dict(step).get("operation") or f"step_{index}")
        output = "utf8_text" if index == len(steps) else "intermediate"
        nodes.append(
            {
                "id": f"transform_{index}",
                "kind": "transform",
                "contract": {"input": previous, "output": output},
                "operation": step_operation,
                "profile": str(dict(step).get("profile") or ""),
            }
        )
        previous = output
    return nodes


def _edges_for_transform_nodes(transform_ids: list[str]) -> list[list[str]]:
    edges = [["read_input", "parse_input"]]
    previous = "parse_input"
    for transform_id in transform_ids:
        edges.append([previous, transform_id])
        previous = transform_id
    edges.extend([[previous, "serialize_output"], ["serialize_output", "write_output"], ["write_output", "verify"]])
    return edges
