from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules",
    "tests", "test", "docs", "examples", "build", "dist", "site-packages",
}


def module_findings(path: Path, corpus: Path, tree: ast.Module) -> list[dict[str, Any]]:
    aliases = import_aliases(tree)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    profiles = {
        name: {
            "effects": effects(node, aliases),
            "transforms": transforms(node, aliases),
        }
        for name, node in functions.items()
    }
    rows = []
    relative = path.relative_to(corpus)
    project = relative.parts[0] if len(relative.parts) > 1 else corpus.name
    for name, node in functions.items():
        profile = profiles[name]
        local_calls = sorted(called_names(node) & set(functions) - {name})
        pure_helpers = [
            called for called in local_calls
            if profiles[called]["transforms"] and not profiles[called]["effects"]
        ]
        effective_transforms = sorted(set(profile["transforms"]).union(
            signal for helper in pure_helpers for signal in profiles[helper]["transforms"]
        ))
        if not profile["effects"] or not effective_transforms:
            continue
        for cluster in pattern_clusters(node, profile["effects"], effective_transforms):
            rows.append({
                "cluster": cluster,
                "source": f"{path.relative_to(corpus).as_posix()}:{name}",
                "corpus": corpus.name,
                "project": project,
                "project_type": "plugin" if corpus.name == "plugins" else "benchmark_project",
                "structural_fingerprint": structural_fingerprint(node),
                "line": int(getattr(node, "lineno", 0) or 0),
                "loc": int(getattr(node, "end_lineno", node.lineno) - node.lineno + 1),
                "effects": profile["effects"],
                "transform_signals": effective_transforms,
                "local_calls": local_calls,
                "pure_helpers": pure_helpers,
                "resolved_by_pure_helper": bool(pure_helpers),
            })
    return rows


def effects(node: ast.AST, aliases: dict[str, str] | None = None) -> list[str]:
    result = set()
    for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
        name = call_name(call.func, aliases)
        if name.endswith(("read_text", "write_text", ".open")) or name == "open":
            result.add("filesystem")
        if name.startswith(("subprocess.", "os.system", "os.popen")):
            result.add("subprocess")
        if name.startswith(("requests.", "httpx.", "urllib.request.", "aiohttp.")):
            result.add("network")
        if any(part in name.lower() for part in (".execute", ".commit", ".cursor")):
            result.add("database")
    return sorted(result)


def transforms(node: ast.AST, aliases: dict[str, str] | None = None) -> list[str]:
    signals = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            name = call_name(item.func, aliases)
            if name.endswith(("split", "splitlines", "rsplit")):
                signals.add("parse_text")
            if name == "json.loads":
                signals.add("parse_json")
            if name.endswith(".json"):
                signals.add("parse_network_response")
            if name in {"csv.reader", "csv.DictReader"}:
                signals.add("parse_structured_stream")
            if name == "json.dumps":
                signals.add("serialize_json")
            if name.endswith(("strip", "lower", "upper", "replace")):
                signals.add("normalize_text")
            if isinstance(item.func, ast.Attribute) and item.func.attr == "append" and item.args and isinstance(item.args[0], ast.Dict):
                signals.add("append_mapping")
        elif isinstance(item, (ast.Dict, ast.DictComp)):
            signals.add("mapping_projection")
    if has_request_mapping(node, aliases):
        signals.add("request_mapping")
    if has_return_mapping(node):
        signals.add("response_mapping")
    return sorted(signals)


def pattern_clusters(node: ast.AST, effects: list[str], transforms: list[str]) -> list[str]:
    rows = []
    effect_set, transform_set = set(effects), set(transforms)
    if "append_mapping" in transform_set:
        rows.append("append_mapping_inside_effectful_loop")
    if "parse_text" in transform_set and effect_set & {"filesystem", "network"}:
        rows.append("parse_text_inside_io_boundary")
    if "parse_json" in transform_set and "filesystem" in effect_set:
        rows.append("parse_json_inside_filesystem_boundary")
    if "parse_json" in transform_set and "network" in effect_set:
        rows.append("parse_json_inside_network_boundary")
    if "parse_structured_stream" in transform_set and "filesystem" in effect_set:
        rows.append("parse_structured_stream_inside_io_boundary")
    if "serialize_json" in transform_set and "filesystem" in effect_set:
        rows.append("serialize_json_inside_filesystem_boundary")
    if "subprocess" in effect_set and has_dynamic_subprocess_arguments(node):
        rows.append("dynamic_command_inside_subprocess_boundary")
    if "network" in effect_set and "request_mapping" in transform_set:
        rows.append("request_mapping_inside_network_boundary")
    if "network" in effect_set and transform_set & {"parse_json", "parse_network_response"}:
        rows.append("network_response_parse_inside_effect_boundary")
    if "network" in effect_set and "response_mapping" in transform_set:
        rows.append("response_mapping_inside_network_boundary")
    return rows


def has_request_mapping(node: ast.AST, aliases: dict[str, str] | None = None) -> bool:
    mapping_names = {
        target.id
        for assignment in ast.walk(node)
        if isinstance(assignment, (ast.Assign, ast.AnnAssign))
        and isinstance(assignment.value, ast.Dict)
        for target in (
            assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        )
        if isinstance(target, ast.Name)
    }
    for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
        name = call_name(call.func, aliases)
        if not name.startswith(("requests.", "httpx.", "urllib.request.Request", "urllib.parse.urlencode")):
            continue
        values = [*call.args, *(keyword.value for keyword in call.keywords)]
        if any(isinstance(item, ast.Dict) for value in values for item in ast.walk(value)):
            return True
        if any(isinstance(item, ast.Name) and item.id in mapping_names for value in values for item in ast.walk(value)):
            return True
    return False


def has_return_mapping(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Return) and isinstance(item.value, ast.Dict)
        for item in ast.walk(node)
    )


def has_dynamic_subprocess_arguments(node: ast.AST) -> bool:
    for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
        if not call_name(call.func).startswith(("subprocess.", "os.system", "os.popen")) or not call.args:
            continue
        argument = call.args[0]
        if isinstance(argument, (ast.List, ast.Tuple)):
            return any(not isinstance(item, ast.Constant) for item in argument.elts)
        return not isinstance(argument, ast.Constant)
    return False


def called_names(node: ast.AST) -> set[str]:
    return {
        name
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        for name in [call_name(call.func).split(".")[-1]]
        if name
    }


def call_name(node: ast.AST, aliases: dict[str, str] | None = None) -> str:
    if isinstance(node, ast.Name):
        return dict(aliases or {}).get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = call_name(node.value, aliases)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def import_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                if item.name != "*":
                    aliases[item.asname or item.name] = f"{node.module}.{item.name}"
    return aliases


def structural_fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    body = ast.Module(body=node.body, type_ignores=[])
    payload = ast.dump(body, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def python_files(root: Path):
    for path in root.rglob("*.py"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in EXCLUDED_DIRS or part.startswith(".") for part in relative.parts[:-1]):
            continue
        yield path
