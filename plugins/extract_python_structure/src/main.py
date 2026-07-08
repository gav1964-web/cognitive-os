"""Extract Python file structure using the stdlib AST parser."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .insights import class_fields, function_error_profile, import_rows, project_insights


EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
HTTP_METHOD_DECORATORS = {"get", "post", "put", "delete", "patch", "options", "head"}
LATE_DIRS = {"artifacts", "build", "dist", "docs", "examples", "generated", "scratch", "tests", "tools"}
EARLY_DIRS = {"app", "apps", "lib", "packages", "src"}
EARLY_FILES = {"app.py", "main.py", "server.py", "api.py", "__init__.py"}


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
    for path in _iter_python_files(root):
        rel_path = path.relative_to(root).as_posix()
        discovered_python_files += 1
        if _is_test_path(rel_path):
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
        imports.update(summary.pop("imports"))
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
            if _path_priority(rel_path) < 8: routes.extend(_route_rows(node, rel_path))
    for function in functions:
        function["path"] = rel_path
    return {
        "path": rel_path,
        "size_bytes": size,
        "classes": classes,
        "functions": functions,
        "imports": imports,
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
        if lower in {"open", "print"} or lower.startswith(("path.write", "json.dump", "shutil.", "os.remove", "os.unlink")):
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
        key=lambda item: (len(item.get("calls", [])), item.get("loc", 0), item.get("path", ""), item.get("name", "")),
        reverse=True,
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
        for item in sorted(functions, key=lambda item: item.get("loc", 0), reverse=True)
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
    return (_path_priority(str(item.get("path", ""))), 0, "", "")

def _path_priority(path: str) -> int:
    lowered = path.replace("\\", "/").lower()
    parts = lowered.split("/")
    name = parts[-1] if parts else lowered
    if any(
        part in {"tests", "test", "bench", "benchmarks", "ci_tools", "docs", "downstream", "examples", "failures-to-investigate", "integration", "scripts", "tasks", "tools"}
        for part in parts
    ):
        return 9
    helper_names = {"benchmark.py", "bench.py", "noxfile.py", "conftest.py", "testclient.py", "testing.py"}
    if parts[:2] == ["packaging", "pep517_backend"] or name.endswith(("_benchmark.py", "_bench.py")) or name in helper_names:
        return 8
    if lowered.startswith("src/"):
        return 0
    if lowered.startswith(("app/", "lib/", "packages/")) or "/" not in lowered and name in EARLY_FILES:
        return 1
    return 3


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


def _iter_python_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        dirs = []
        files = []
        for item in current.iterdir():
            if item.is_dir():
                if item.name in EXCLUDED_DIRS or item.name.startswith("."):
                    continue
                dirs.append(item)
            elif item.is_file() and item.suffix.lower() == ".py":
                files.append(item)
        for item in sorted(files, key=_traversal_key):
            yield item
        stack.extend(reversed(sorted(dirs, key=_traversal_key)))


def _is_test_path(path: str) -> bool:
    name = Path(path).name
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py")


def _traversal_key(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if path.is_dir():
        if name in EARLY_DIRS:
            return (0, name)
        if name in LATE_DIRS:
            return (9, name)
        return (3, name)
    if name in EARLY_FILES:
        return (0, name)
    return (3, name)


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
