"""Infer conceptual main/run contracts from executable module ASTs."""

from __future__ import annotations

import ast
from typing import Any

from runtime.source_target_policy import load_role_source_policy


def module_script_contract(tree: ast.Module, imports: set[str]) -> dict[str, Any]:
    policy = _policy()
    args = _cli_arguments(tree, policy)
    args.extend(_environment_arguments(tree, policy, known={row["name"] for row in args}))
    effects = _side_effects(tree, imports, policy)
    output_type, output_basis = _output_shape(tree, effects, policy)
    structural = {
        "source_body_available": True,
        "source_body_complete": True,
        "docstring_available": bool(ast.get_docstring(tree)),
        "argument_count": len(args),
        "typed_argument_count": len(args),
        "argument_constraint_types": {row["name"]: row["annotation"] for row in args},
        "argument_usage_types": {row["name"]: row["annotation"] for row in args},
        "explicit_return_annotation": "",
        "inferred_output_type": output_type,
        "output_inference_basis": output_basis,
        "return_paths": 0,
        "yield_paths": 0,
        "raises": ["SystemExit"] if _has_exit(tree) else [],
        "state_mutation": bool(effects),
        "dynamic_dispatch": False,
        "file_extension_policy": False,
        "observed_side_effects": effects,
    }
    return {
        "signature": {"args": args, "returns": ""},
        "side_effects": effects,
        "contract_side_effects": effects,
        "structural_contract": structural,
    }


def _policy() -> dict[str, Any]:
    source = load_role_source_policy().get("implementation_target_policy") or {}
    return dict(dict(source).get("module_script_boundary") or {})


def _cli_arguments(tree: ast.Module, policy: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[tuple[int, dict[str, str]]] = []
    path_markers = [str(item).lower() for item in list(policy.get("path_argument_markers") or [])]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        index = _argv_index(value)
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if index is None or index < 1 or not names:
            continue
        for name in names:
            annotation = "PathLike" if any(marker in name.lower() for marker in path_markers) else "str"
            rows.append((index, {"name": name, "annotation": annotation}))
    return _dedupe_args([row for _, row in sorted(rows, key=lambda item: item[0])])


def _environment_arguments(
    tree: ast.Module, policy: dict[str, Any], *, known: set[str]
) -> list[dict[str, str]]:
    markers = [str(item).lower() for item in list(policy.get("secret_env_markers") or [])]
    rows = []
    for node in ast.walk(tree):
        key = _environment_key(node)
        if not key:
            continue
        name = key.lower()
        if name in known:
            continue
        annotation = "SecretStr" if any(marker in name for marker in markers) else "str"
        rows.append({"name": name, "annotation": annotation})
    return _dedupe_args(rows)


def _argv_index(node: ast.AST | None) -> int | None:
    for child in ast.walk(node) if node is not None else []:
        if not isinstance(child, ast.Subscript) or _name(child.value) != "sys.argv":
            continue
        value = child.slice.value if isinstance(child.slice, ast.Index) else child.slice
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            return value.value
    return None


def _environment_key(node: ast.AST) -> str:
    if isinstance(node, ast.Subscript) and _name(node.value) in {"os.environ", "environ"}:
        value = node.slice.value if isinstance(node.slice, ast.Index) else node.slice
        return str(value.value) if isinstance(value, ast.Constant) and isinstance(value.value, str) else ""
    if isinstance(node, ast.Call) and _name(node.func) in {"os.getenv", "os.environ.get", "getenv"} and node.args:
        value = node.args[0]
        return str(value.value) if isinstance(value, ast.Constant) and isinstance(value.value, str) else ""
    return ""


def _side_effects(tree: ast.Module, imports: set[str], policy: dict[str, Any]) -> list[str]:
    effects = set()
    network_imports = {str(item) for item in list(policy.get("network_imports") or [])}
    if imports & network_imports:
        effects.add("network")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = _name(node.func).lower()
        if call == "open" or call.endswith(".open"):
            effects.add("filesystem_write" if _open_writes(node) else "filesystem")
        if "imread" in call:
            effects.add("filesystem")
        if "imwrite" in call or call.endswith((".write", ".write_text", ".write_bytes")):
            effects.add("filesystem_write")
        if call in {"print", "logging.info", "logging.warning", "logging.error"}:
            effects.add("stdout")
    if any(_environment_key(node) for node in ast.walk(tree)):
        effects.add("environment")
    return sorted(effects)


def _open_writes(node: ast.Call) -> bool:
    mode = node.args[1] if len(node.args) > 1 else next(
        (item.value for item in node.keywords if item.arg == "mode"), None
    )
    return isinstance(mode, ast.Constant) and any(marker in str(mode.value) for marker in "wax+")


def _output_shape(tree: ast.Module, effects: list[str], policy: dict[str, Any]) -> tuple[str, str]:
    calls = {_name(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    json_calls = {str(item) for item in list(policy.get("json_output_calls") or [])}
    if "filesystem_write" in effects and calls & json_calls:
        return "JsonFileArtifact", "module_json_serialization_and_file_write"
    if "filesystem_write" in effects:
        return "FileArtifact", "module_file_write"
    return "VoidSideEffect", "module_side_effect_execution"


def _has_exit(tree: ast.Module) -> bool:
    return any(isinstance(node, ast.Call) and _name(node.func) in {"exit", "quit", "sys.exit"} for node in ast.walk(tree))


def _name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _dedupe_args(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return list({row["name"]: row for row in rows}.values())
