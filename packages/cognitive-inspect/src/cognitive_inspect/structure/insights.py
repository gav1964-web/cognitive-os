"""Additional AST insights for project analysis."""

from __future__ import annotations

import ast
from typing import Any


def class_fields(node: ast.ClassDef) -> list[dict[str, str]]:
    fields = []
    for child in node.body:
        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            fields.append({"name": child.target.id, "annotation": annotation_name(child.annotation)})
        elif isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    fields.append({"name": target.id, "annotation": ""})
    return fields[:40]


def function_error_profile(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    raises = []
    handlers = []
    has_try = False
    for child in ast.walk(node):
        if isinstance(child, ast.Raise):
            raises.append(expr_name(child.exc) if child.exc else "raise")
        elif isinstance(child, ast.Try):
            has_try = True
            for handler in child.handlers:
                handlers.append(expr_name(handler.type) if handler.type else "Exception")
    return {"raises": sorted(set(filter(None, raises)))[:20], "handlers": sorted(set(filter(None, handlers)))[:20], "has_try": has_try}


def import_rows(tree: ast.AST, rel_path: str) -> list[dict[str, str]]:
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                rows.append({"path": rel_path, "module": alias.name, "root": alias.name.split(".")[0], "kind": "import"})
        elif isinstance(node, ast.ImportFrom) and node.module:
            rows.append({"path": rel_path, "module": node.module, "root": node.module.split(".")[0], "kind": "from"})
    return rows


def project_insights(files: list[dict[str, Any]], import_details: list[dict[str, str]]) -> dict[str, Any]:
    paths = [str(file.get("path", "")) for file in files]
    local_roots = _local_roots(paths)
    internal_imports = [row for row in import_details if row.get("root") in local_roots]
    external_imports = [row for row in import_details if row.get("root") not in local_roots]
    return {
        "test_surface": _test_surface(files),
        "import_graph": _import_graph(internal_imports),
        "external_imports": _top_imports(external_imports),
        "error_handling": _error_handling(files),
        "schema_fields": _schema_fields(files),
    }


def annotation_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = annotation_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return annotation_name(node.value)
    if isinstance(node, ast.Constant):
        return str(node.value)
    return expr_name(node)


def expr_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Call):
        return expr_name(node.func)
    if isinstance(node, ast.Attribute):
        base = expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _local_roots(paths: list[str]) -> set[str]:
    roots = {path.split("/", 1)[0] for path in paths if "/" in path}
    return {root for root in roots if root not in {"tests", "tools", "docs", "examples", "scratch"}}


def _test_surface(files: list[dict[str, Any]]) -> dict[str, Any]:
    test_files = [file for file in files if str(file.get("path", "")).startswith("tests/") or "/test" in str(file.get("path", ""))]
    functions = [fn for file in test_files for fn in file.get("functions", [])]
    test_functions = [fn for fn in functions if str(fn.get("name", "")).startswith("test_")]
    return {"test_files": len(test_files), "test_functions": len(test_functions), "sample_tests": [f"{fn.get('path')}:{fn.get('name')}" for fn in test_functions[:12]]}


def _import_graph(imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_path: dict[str, set[str]] = {}
    for row in imports:
        by_path.setdefault(row["path"], set()).add(row["module"])
    return [{"path": path, "imports": sorted(modules)[:20], "internal_import_count": len(modules)} for path, modules in sorted(by_path.items(), key=lambda item: (-len(item[1]), item[0]))[:20]]


def _top_imports(imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in imports:
        counts[row["root"]] = counts.get(row["root"], 0) + 1
    return [{"module": module, "count": count} for module, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:20]]


def _error_handling(files: list[dict[str, Any]]) -> dict[str, Any]:
    raises = []
    handlers = []
    functions_with_try = []
    for file in files:
        for function in file.get("functions", []):
            profile = dict(function.get("error_profile", {}))
            raises.extend(profile.get("raises", []))
            handlers.extend(profile.get("handlers", []))
            if profile.get("has_try"):
                functions_with_try.append(f"{function.get('path')}:{function.get('name')}")
    return {"raises": sorted(set(raises))[:20], "handlers": sorted(set(handlers))[:20], "functions_with_try": functions_with_try[:20]}


def _schema_fields(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for file in files:
        for cls in file.get("classes", []):
            fields = cls.get("fields", [])
            if fields:
                rows.append({"path": file.get("path"), "class": cls.get("name"), "fields": fields[:20]})
    return rows[:20]
