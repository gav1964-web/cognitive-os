"""Extract Python file structure using the stdlib AST parser."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .domain_anchors import domain_flow_anchors
from .insights import class_fields, function_error_profile, import_rows, project_insights
from .path_priority import is_test_path, iter_python_files, path_priority


HTTP_METHOD_DECORATORS = {"get", "post", "put", "delete", "patch", "options", "head"}


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_root(str(payload["root"]))
    max_files = int(payload.get("max_files", 50))
    max_bytes = int(payload.get("max_bytes_per_file", 200_000))
    files = []
    imports: set[str] = set()
    import_details = []
    routes = []
    all_functions = []
    discovered_python_files = 0
    discovered_test_files = 0
    skipped = []
    for path in iter_python_files(root):
        rel_path = path.relative_to(root).as_posix()
        discovered_python_files += 1
        if is_test_path(rel_path):
            discovered_test_files += 1
        if len(files) >= max_files:
            skipped.append({"path": rel_path, "reason": "max_files_exceeded"})
            continue
        size = path.stat().st_size
        if size > max_bytes:
            skipped.append({"path": rel_path, "reason": "too_large", "size_bytes": size})
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=rel_path)
        except SyntaxError as exc:
            skipped.append({"path": rel_path, "reason": "SyntaxError", "line": exc.lineno})
            continue
        summary = _summarize_file(tree, rel_path, size)
        imports.update(summary.get("imports", []))
        import_details.extend(summary.pop("import_details"))
        routes.extend(summary.pop("routes"))
        all_functions.extend(summary.get("functions", []))
        files.append(summary)
    insights = project_insights(files, import_details)
    insights["test_surface"]["python_files_seen"] = discovered_python_files
    insights["test_surface"]["test_files_seen"] = discovered_test_files
    return {
        "root": root.as_posix(),
        "files": files,
        "imports": sorted(imports),
        "routes": routes,
        "central_nodes": _central_nodes(all_functions),
        "domain_flow_anchors": domain_flow_anchors(all_functions),
        "wide_functions": _wide_functions(all_functions),
        "pure_transform_candidates": _pure_transform_candidates(all_functions),
        "contracts": _contracts(files),
        "external_dependencies": _external_dependencies(imports),
        "project_insights": insights,
        "skipped": skipped,
    }


def _summarize_file(tree: ast.AST, rel_path: str, size: int) -> dict[str, Any]:
    imports: set[str] = set()
    imports_detail = import_rows(tree, rel_path)
    classes = []
    functions = []
    routes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "line": node.lineno, "methods": _class_methods(node), "fields": class_fields(node)})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "loc": max(1, getattr(node, "end_lineno", node.lineno) - node.lineno + 1),
                    "decorators": _decorator_names(node),
                    "args": _function_args(node),
                    "returns": _annotation_name(node.returns),
                    "docstring": bool(ast.get_docstring(node)),
                    "calls": sorted(_call_names(node))[:40],
                    "side_effects": _function_side_effects(node),
                    "error_profile": function_error_profile(node),
                }
            )
            if path_priority(rel_path) < 8:
                routes.extend(_route_rows(node, rel_path))
    for function in functions:
        function["path"] = rel_path
    return {
        "path": rel_path,
        "size_bytes": size,
        "classes": classes,
        "functions": functions,
        "imports": sorted(imports),
        "import_details": imports_detail,
        "routes": routes,
    }


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [_expr_name(decorator) for decorator in node.decorator_list if _expr_name(decorator)]


def _class_methods(node: ast.ClassDef) -> list[str]:
    return [child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _function_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, str]]:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg:
        args.append(node.args.vararg)
    if node.args.kwarg:
        args.append(node.args.kwarg)
    return [{"name": arg.arg, "annotation": _annotation_name(arg.annotation)} for arg in args]


def _annotation_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _annotation_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    if isinstance(node, ast.Constant):
        return str(node.value)
    return _expr_name(node)


def _call_names(node: ast.AST) -> set[str]:
    calls = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _expr_name(child.func)
            if name:
                calls.add(name)
    return calls


def _function_side_effects(node: ast.AST) -> list[str]:
    calls = _call_names(node)
    effects = set()
    for call in calls:
        lower = call.lower()
        if (
            lower in {"open", "print", "json.dump"}
            or lower.startswith(("path.write", "shutil.", "os.remove", "os.unlink"))
        ):
            effects.add("filesystem")
        if lower.startswith(("path.read", "json.load")):
            effects.add("filesystem_read")
        if lower.startswith(("requests.", "httpx.", "openai.")):
            effects.add("network")
        if lower.startswith(("subprocess.", "popen")):
            effects.add("subprocess")
        if "execute" in lower or lower.startswith("sqlite3."):
            effects.add("database")
        if lower.endswith((".append", ".extend", ".setdefault", ".pop")) or lower in {"setattr", "delattr"}:
            effects.add("memory_state")
    return sorted(effects)


def _route_rows(node: ast.FunctionDef | ast.AsyncFunctionDef, rel_path: str) -> list[dict[str, Any]]:
    rows = []
    for decorator in node.decorator_list:
        name = _expr_name(decorator)
        if not name:
            continue
        route_kind = _route_kind(name)
        if not route_kind:
            continue
        route = None
        methods: list[str] = []
        if isinstance(decorator, ast.Call):
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                route = str(decorator.args[0].value)
            for keyword in decorator.keywords:
                if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    methods = [str(item.value) for item in keyword.value.elts if isinstance(item, ast.Constant)]
        if route_kind != "route" and not methods:
            methods = [route_kind.upper()]
        rows.append({"path": rel_path, "function": node.name, "line": node.lineno, "route": route, "methods": methods})
    return rows


def _route_kind(name: str) -> str:
    tail = name.rsplit(".", 1)[-1]
    if tail == "route":
        return "route"
    if tail in HTTP_METHOD_DECORATORS:
        return tail
    return ""


def _expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _expr_name(node.func)
    if isinstance(node, ast.Attribute):
        base = _expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _central_nodes(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        functions,
        key=lambda item: (
            path_priority(str(item.get("path", ""))),
            -len(item.get("calls", [])),
            -int(item.get("loc", 0)),
            str(item.get("path", "")),
            str(item.get("name", "")),
        ),
    )
    return [
        {
            "path": item.get("path"),
            "name": item.get("name"),
            "line": item.get("line"),
            "loc": item.get("loc"),
            "call_count": len(item.get("calls", [])),
            "side_effects": item.get("side_effects", []),
        }
        for item in ranked[:12]
    ]


def _wide_functions(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "path": item.get("path"),
            "name": item.get("name"),
            "line": item.get("line"),
            "loc": item.get("loc"),
            "call_count": len(item.get("calls", [])),
            "side_effects": item.get("side_effects", []),
        }
        for item in sorted(
            functions,
            key=lambda item: (
                path_priority(str(item.get("path", ""))),
                -int(item.get("loc", 0)),
                str(item.get("path", "")),
                str(item.get("name", "")),
            ),
        )
        if item.get("loc", 0) >= 80 or len(item.get("calls", [])) >= 18
    ][:12]


def _pure_transform_candidates(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    side_effect_names = {str(item.get("name")) for item in functions if item.get("side_effects")}
    for item in functions:
        name = str(item.get("name", ""))
        if item.get("side_effects"):
            continue
        calls = {str(call).rsplit(".", 1)[-1] for call in item.get("calls", [])}
        if calls & side_effect_names:
            continue
        if name.startswith("_"):
            continue
        if not item.get("args") or item.get("loc", 0) > 80:
            continue
        candidates.append(
            {
                "path": item.get("path"),
                "name": name,
                "line": item.get("line"),
                "loc": item.get("loc"),
                "args": item.get("args", []),
                "returns": item.get("returns", ""),
            }
        )
    return sorted(candidates, key=_candidate_priority)[:20]


def _candidate_priority(item: dict[str, Any]) -> tuple[int, int, str, str]:
    path = str(item.get("path", ""))
    name = str(item.get("name", ""))
    return (path_priority(path), _symbol_extraction_priority(name), "", "")


def _symbol_extraction_priority(name: str) -> int:
    lowered = name.lower()
    if any(token in lowered for token in ("build_key", "cache_key")):
        return 0
    if lowered.startswith(("get_cached", "store_", "flush")):
        return 7
    if any(token in lowered for token in ("free_port", "listener_pid", "process_pid", "socket")):
        return 8
    return 4


def _contracts(files: list[dict[str, Any]]) -> dict[str, Any]:
    typed_functions = []
    untyped_functions = []
    schema_like_classes = []
    for file_summary in files:
        for class_summary in file_summary.get("classes", []):
            name = str(class_summary.get("name", ""))
            if name.endswith(("Model", "Request", "Response", "Config", "Schema")):
                schema_like_classes.append({"path": file_summary.get("path"), "name": name, "line": class_summary.get("line")})
        for function in file_summary.get("functions", []):
            args = function.get("args", [])
            has_arg_types = any(arg.get("annotation") for arg in args)
            has_return = bool(function.get("returns"))
            row = {
                "path": file_summary.get("path"),
                "name": function.get("name"),
                "line": function.get("line"),
                "args": args,
                "returns": function.get("returns", ""),
            }
            if has_arg_types or has_return:
                typed_functions.append(row)
            else:
                untyped_functions.append(row)
    return {
        "typed_functions": typed_functions[:20],
        "untyped_functions": untyped_functions[:20],
        "schema_like_classes": schema_like_classes[:20],
    }


def _external_dependencies(imports: set[str]) -> dict[str, list[str]]:
    categories = {
        "network": {"requests", "httpx", "openai", "urllib"},
        "database": {"sqlite3", "sqlalchemy"},
        "filesystem": {"os", "pathlib", "shutil", "zipfile", "io"},
        "subprocess": {"subprocess"},
        "llm": {"openai", "gigachat"},
        "web": {"flask", "fastapi"},
        "concurrency": {"asyncio", "concurrent", "threading"},
    }
    return {name: sorted(imports & values) for name, values in categories.items() if imports & values}


def _resolve_scoped_root(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("extract_python_structure root must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("extract_python_structure root is outside the allowed project scope")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
