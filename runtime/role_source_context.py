"""Source context builder for role-level LLM advisory."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .source_contract_semantics import infer_source_contract
from .role_source_capability_facts import capability_facts
from .source_side_effect_inference import infer_ast_side_effects, selection_side_effects
from .transitive_side_effects import infer_transitive_side_effects
from .project_transitive_effects import project_transitive_effects
from .python_source_files import is_python_source_file, iter_python_source_files
from .python_parser_compatibility import parse_compatible_source
from .source_dependency_readiness import source_dependency_readiness
from .role_source_symbols import symbol_matches
from .module_script_contract import module_script_contract
from .source_standalone_dependencies import blocking_runtime_names, standalone_dependency_facts

def build_source_context(
    *,
    project_root: str,
    project_report: dict[str, Any],
    sources: list[str],
    function_scoped_dependencies: bool = False,
) -> dict[str, dict[str, Any]]:
    root = Path(project_root)
    context = {}
    facts = _facts_by_source(project_report)
    graph = _call_graph(root)
    project_effects = project_transitive_effects(root)
    flow = _flow_by_source(project_report)
    central = _central_by_source(project_report)
    for source in sources:
        row: dict[str, Any] = {"source": source}
        row.update(facts.get(source, {}))
        row.update(graph.get(source, {}))
        row.update(project_effects.get(source, {}))
        row.update(flow.get(source, {}))
        row.update(central.get(source, {}))
        if ":" in source:
            path_text, symbol = source.split(":", 1)
            module_context = _module_context(root / path_text)
            if module_context:
                context.setdefault(path_text, {"source": path_text}).update(module_context)
                class_names = {item["name"] for item in module_context.get("module_classes", [])}
                function_names = {item["name"] for item in module_context.get("module_functions", [])}
                if symbol in class_names or symbol in function_names:
                    row["node_kind"] = "class" if symbol in class_names else "function"
            snippet = _symbol_snippet(root / path_text, symbol)
            if snippet:
                dependency = source_dependency_readiness(
                    root, path_text, symbol if function_scoped_dependencies else None
                )
                unresolved = blocking_runtime_names(list(snippet.get("unresolved_runtime_names") or []))
                if dependency.get("status") == "ready" and unresolved:
                    dependency.update({
                        "status": "source_context_required",
                        "unresolved_runtime_names": unresolved,
                        "analysis": "function has unresolved runtime names outside its standalone scope",
                    })
                row["dependency_readiness"] = dependency
                row["snippet"] = snippet
                if "signature" not in row and snippet.get("signature"):
                    row["signature"] = snippet["signature"]
                snippet_effects = list(snippet.get("side_effects", []))
                if snippet_effects:
                    row["contract_side_effects"] = sorted(set(list(row.get("side_effects", [])) + snippet_effects))
                selection_effects = list(snippet.get("selection_side_effects", []))
                if selection_effects:
                    row["side_effects"] = sorted(set(list(row.get("side_effects", [])) + selection_effects))
                transitive_effects = list(row.get("transitive_side_effects", []))
                if transitive_effects:
                    row["side_effects"] = sorted(set(list(row.get("side_effects", [])) + transitive_effects))
        elif is_python_source_file(root / source):
            module_context = _module_context(root / source)
            if module_context:
                row.update(module_context)
                row["kind"] = "module_script"
                row["snippet"] = module_context.get("module_snippet", "")
                row["side_effects"] = module_context.get("module_side_effects", [])
        elif source == "ProjectMapReport.risks":
            row["facts"] = project_report.get("risks", [])[:5]
        if len(row) > 1:
            context[source] = row
    return context
def _module_context(path: Path) -> dict[str, Any] | None:
    if not is_python_source_file(path):
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree, _ = parse_compatible_source(text, path.as_posix())
    except SyntaxError:
        return None
    imports: set[str] = set()
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                {
                    "name": node.name,
                    "line": int(getattr(node, "lineno", 0) or 0),
                    "signature": _ast_signature(node),
                }
            )
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "line": int(getattr(node, "lineno", 0) or 0)})
    doc = ast.get_docstring(tree) or ""
    script_contract = module_script_contract(tree, imports)
    result: dict[str, Any] = {
        "path": path.name,
        "module_imports": sorted(imports)[:16],
        "module_functions": functions[:12],
        "module_classes": classes[:12],
        "module_snippet": text[:1200],
        "module_side_effects": script_contract["side_effects"],
        **script_contract,
    }
    if doc:
        result["module_docstring"] = doc[:600]
    return {key: value for key, value in result.items() if value not in ("", [], None)}
def _call_graph(root: Path) -> dict[str, dict[str, Any]]:
    functions: dict[str, set[str]] = {}
    unresolved: dict[str, set[str]] = {}
    by_file: dict[str, set[str]] = {}
    for path in _python_source_paths(root):
        rel = path.relative_to(root).as_posix()
        try:
            tree, _ = parse_compatible_source(path.read_text(encoding="utf-8", errors="replace"), path.as_posix())
        except SyntaxError:
            continue
        local_defs = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        by_file[rel] = local_defs
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            source = f"{rel}:{node.name}"
            for call in _call_names(node):
                if call in local_defs:
                    functions.setdefault(source, set()).add(f"{rel}:{call}")
                else:
                    unresolved.setdefault(source, set()).add(call)
    callers: dict[str, set[str]] = {}
    for source, callees in functions.items():
        for callee in callees:
            callers.setdefault(callee, set()).add(source)
    graph = {}
    for source in set(functions) | set(callers) | set(unresolved):
        graph[source] = {
            "callers": sorted(callers.get(source, set()))[:8],
            "callees": sorted(functions.get(source, set()))[:8],
            "unresolved_calls": sorted(unresolved.get(source, set()))[:12],
        }
    return graph


def _python_source_paths(root: Path) -> list[Path]:
    return list(iter_python_source_files(root, limit=80))


def _call_names(node: ast.AST) -> set[str]:
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name:
                names.add(name)
    return names


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _flow_by_source(project_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    result: dict[str, dict[str, Any]] = {}
    for row in _list(readiness.get("dataflows")):
        entrypoint = str(row.get("entrypoint") or "")
        path = entrypoint.split(":", 1)[0] if ":" in entrypoint else ""
        for step in _list(row.get("flow")):
            function = str(step.get("function") or "")
            source = f"{path}:{function}" if path and function else entrypoint
            _merge(
                result,
                source,
                {
                    "dataflow_steps": [
                        {
                            "entrypoint": entrypoint,
                            "step": step.get("step"),
                            "evidence": step.get("evidence"),
                            "confidence": row.get("confidence"),
                        }
                    ]
                },
            )
    return result


def _central_by_source(project_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answers = dict(project_report.get("answers", {}))
    execution = dict(answers.get("2_execution", {}))
    result = {}
    for row in _list(execution.get("central_flow_nodes")):
        _merge(
            result,
            _source(row),
            {
                "central_flow_node": {
                    "line": row.get("line"),
                    "loc": row.get("loc"),
                    "call_count": row.get("call_count"),
                    "side_effects": row.get("side_effects", []),
                }
            },
        )
    return result


def _facts_by_source(project_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    facts = capability_facts(answers, readiness)
    for row in _list(readiness.get("mixed_responsibility_functions")):
        _merge(
            facts,
            _source(row),
            {
                "mixed_responsibilities": row.get("responsibilities", []),
                "mixed_reason": row.get("reason"),
            },
        )
    for row in _list(readiness.get("idempotency_risks")):
        _merge(
            facts,
            str(row.get("target")),
            {
                "idempotency_risk": row.get("risk"),
                "side_effects": row.get("side_effects", []),
                "mitigation": row.get("mitigation"),
            },
        )
    for row in _list(readiness.get("process_boundary_candidates")):
        _merge(facts, str(row.get("target")), {"process_boundary_reasons": row.get("reasons", [])})
    for row in _list(readiness.get("long_lived_state")):
        evidence = str(row.get("evidence") or "")
        _merge(
            facts,
            evidence,
            {
                "long_lived_state": row.get("kind"),
                "checkpoint_need": row.get("checkpoint_need"),
            },
        )
    for claim in _list(readiness.get("evidence_claims")):
        for item in _list(claim.get("evidence")):
            source = f"{item.get('file')}:{item.get('symbol')}"
            _merge(
                facts,
                source,
                {
                    "claims": [
                        {
                            "claim": claim.get("claim"),
                            "kind": claim.get("kind"),
                            "reason": item.get("reason"),
                            "confidence": claim.get("confidence"),
                        }
                    ]
                },
            )
    return facts


def _symbol_snippet(path: Path, symbol: str) -> dict[str, Any] | None:
    if not is_python_source_file(path):
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        tree, _ = parse_compatible_source("\n".join(lines), path.as_posix())
    except SyntaxError:
        return None
    owner_class, separator, method_symbol = symbol.rpartition(".")
    method_symbol = method_symbol if separator else symbol
    matches = symbol_matches(tree, method_symbol, owner_class or None)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == method_symbol
            and matches
            and int(getattr(node, "lineno", 0) or 0) == int(matches[0].get("line") or 0)
        ):
            start = max(1, int(getattr(node, "lineno", 1)))
            end = min(len(lines), int(getattr(node, "end_lineno", start)))
            node_text = "\n".join(lines[start - 1 : end])
            side_effects = infer_transitive_side_effects(tree, node)
            direct_effects = infer_ast_side_effects(node, node_text)
            decorators = [_call_name(item.func if isinstance(item, ast.Call) else item)
                          for item in getattr(node, "decorator_list", [])]
            result = {
                "path": path.name,
                "symbol": method_symbol,
                "start_line": start,
                "end_line": end,
                "text": node_text[:900],
                "signature": _ast_signature(node),
                "decorators": decorators,
                "side_effects": side_effects["effects"],
                "selection_side_effects": selection_side_effects(direct_effects),
                "side_effect_chains": side_effects["chains"],
                "structural_contract": infer_source_contract(
                    {"signature": _ast_signature(node), "snippet": node_text, "decorators": decorators}
                ),
                **standalone_dependency_facts(tree, node),
            }
            if len(matches) > 1:
                result["symbol_occurrences"] = matches[:8]
                if all(item.get("kind") == "method" for item in matches):
                    result["target_binding"] = "ambiguous_method_symbol"
            elif matches and matches[0].get("kind") == "method":
                result["target_binding"] = "method_symbol"
                result["owner_class"] = matches[0].get("class_name")
                result["structural_contract"]["owner_class"] = matches[0].get("class_name")
            elif matches and matches[0].get("kind") == "nested_function":
                result.update({"target_binding": "nested_function", "parent_function": matches[0].get("parent_name")})
            elif matches:
                result["target_binding"] = "function_symbol"
            return result
    return None


def _ast_signature(node: ast.AST) -> dict[str, Any]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    args = []
    for arg in [*node.args.posonlyargs, *node.args.args]:
        if arg.arg in {"self", "cls"}:
            continue
        args.append({"name": arg.arg, "annotation": _annotation(arg.annotation)})
    kwonlyargs = [
        {"name": arg.arg, "annotation": _annotation(arg.annotation)}
        for arg in node.args.kwonlyargs
    ]
    return {"args": args, "kwonlyargs": kwonlyargs, "returns": _annotation(node.returns)}


def _annotation(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _source(row: dict[str, Any]) -> str:
    return f"{row.get('path')}:{row.get('name')}"


def _signature(row: dict[str, Any]) -> dict[str, Any]:
    return {"args": row.get("args", []), "returns": row.get("returns")}


def _merge(target: dict[str, dict[str, Any]], source: str, value: dict[str, Any]) -> None:
    if not source or source == "None":
        return
    row = target.setdefault(source, {})
    for key, item in value.items():
        if item in (None, "", []):
            continue
        if key == "claims":
            row.setdefault(key, []).extend(item)
        elif key == "dataflow_steps":
            row.setdefault(key, []).extend(item)
        else:
            row[key] = item


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
