"""Source context builder for role-level LLM advisory."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .source_side_effect_inference import infer_ast_side_effects


def build_source_context(
    *,
    project_root: str,
    project_report: dict[str, Any],
    sources: list[str],
) -> dict[str, dict[str, Any]]:
    root = Path(project_root)
    context = {}
    facts = _facts_by_source(project_report)
    graph = _call_graph(root)
    flow = _flow_by_source(project_report)
    central = _central_by_source(project_report)
    for source in sources:
        row: dict[str, Any] = {"source": source}
        row.update(facts.get(source, {}))
        row.update(graph.get(source, {}))
        row.update(flow.get(source, {}))
        row.update(central.get(source, {}))
        if ":" in source:
            path_text, symbol = source.split(":", 1)
            module_context = _module_context(root / path_text)
            if module_context:
                context.setdefault(path_text, {"source": path_text}).update(module_context)
            snippet = _symbol_snippet(root / path_text, symbol)
            if snippet:
                row["snippet"] = snippet
                if "signature" not in row and snippet.get("signature"):
                    row["signature"] = snippet["signature"]
                snippet_effects = list(snippet.get("side_effects", []))
                if snippet_effects:
                    row["side_effects"] = sorted(set(list(row.get("side_effects", [])) + snippet_effects))
        elif source.endswith(".py"):
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
    if not path.exists() or path.suffix != ".py":
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
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
    result: dict[str, Any] = {
        "path": path.name,
        "module_imports": sorted(imports)[:16],
        "module_functions": functions[:12],
        "module_classes": classes[:12],
        "module_snippet": text[:1200],
        "module_side_effects": _module_side_effects(tree),
    }
    if doc:
        result["module_docstring"] = doc[:600]
    return {key: value for key, value in result.items() if value not in ("", [], None)}


def _module_side_effects(tree: ast.AST) -> list[str]:
    effects = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = _call_name(node.func)
        lowered = call.lower()
        if lowered in {"open", "path.open"} or "imread" in lowered or "imwrite" in lowered:
            effects.add("filesystem")
        if any(token in lowered for token in ("request", "urlopen", "subprocess", "popen")):
            effects.add("process_boundary")
    return sorted(effects)


def _call_graph(root: Path) -> dict[str, dict[str, Any]]:
    functions: dict[str, set[str]] = {}
    unresolved: dict[str, set[str]] = {}
    by_file: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py"))[:80]:
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
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
    capabilities = dict(answers.get("3_capabilities", {}))
    facts: dict[str, dict[str, Any]] = {}
    for row in _list(capabilities.get("pure_transforms")):
        _merge(facts, _source(row), {"kind": "pure_transform", "signature": _signature(row)})
    for row in _list(capabilities.get("too_broad_functions")):
        _merge(facts, _source(row), {"kind": "broad_function", "loc": row.get("loc")})
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
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    for row in _list(plan.get("capabilities_to_extract")):
        _merge(
            facts,
            str(row.get("capability")),
            {
                "candidate_level": row.get("candidate_level"),
                "candidate_score": row.get("candidate_score"),
                "first_contract": row.get("first_contract"),
            },
        )
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
    if not path.exists() or path.suffix != ".py":
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return None
    matches = _symbol_matches(tree, symbol)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            start = max(1, int(getattr(node, "lineno", 1)))
            end = min(len(lines), int(getattr(node, "end_lineno", start)))
            node_text = "\n".join(lines[start - 1 : end])
            result = {
                "path": path.name,
                "symbol": symbol,
                "start_line": start,
                "end_line": end,
                "text": node_text[:900],
                "signature": _ast_signature(node),
                "side_effects": infer_ast_side_effects(node, node_text),
            }
            if len(matches) > 1:
                result["symbol_occurrences"] = matches[:8]
                if all(item.get("kind") == "method" for item in matches):
                    result["target_binding"] = "ambiguous_method_symbol"
            elif matches and matches[0].get("kind") == "method":
                result["target_binding"] = "method_symbol"
                result["owner_class"] = matches[0].get("class_name")
            return result
    return None


def _symbol_matches(tree: ast.AST, symbol: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for parent in ast.walk(tree):
        body = getattr(parent, "body", None)
        if not isinstance(body, list):
            continue
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name != symbol:
                continue
            row = {"kind": "function", "line": int(getattr(node, "lineno", 0) or 0)}
            if isinstance(parent, ast.ClassDef):
                row.update({"kind": "method", "class_name": parent.name})
            elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                row.update({"kind": "nested_function", "parent_name": parent.name})
            matches.append(row)
    return matches


def _ast_signature(node: ast.AST) -> dict[str, Any]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    args = []
    for arg in node.args.args:
        if arg.arg in {"self", "cls"}:
            continue
        args.append({"name": arg.arg, "annotation": _annotation(arg.annotation)})
    return {"args": args, "returns": _annotation(node.returns)}


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
