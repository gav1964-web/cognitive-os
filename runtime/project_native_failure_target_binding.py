"""Production target binding for project-native pytest failures."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .project_native_failure_module_resolution import (
    _is_production_path,
    _project_relative_traceback_path,
    _python_module_path,
    _python_module_path_any,
)
from .project_native_failure_source_symbols import _source_defines_symbol, _source_symbol_target, _symbol_at_line

_TRACEBACK_REF = re.compile(r"(?m)^((?:[A-Za-z]:)?[^\r\n:]+\.py):(\d+)(?::|\s)")
_NAMED_INIT_TYPE_ERROR = re.compile(
    r"TypeError:\s+([A-Za-z_][A-Za-z0-9_]*)\.__init__\(\)"
)

def _production_targets(project: Path, output: str) -> list[str]:
    result = []
    failure_section = re.split(
        r"(?m)^=+\s+warnings summary\s+=+\s*$", output, maxsplit=1,
    )[0]
    for raw_path, raw_line in _TRACEBACK_REF.findall(failure_section):
        normalized = _project_relative_traceback_path(project, raw_path)
        if normalized is None:
            continue
        lowered_parts = {part.lower() for part in Path(normalized).parts}
        if lowered_parts.intersection({"test", "tests", "testing", "site-packages"}) or Path(normalized).name.startswith("test_"):
            continue
        path = project / normalized
        if not path.is_file():
            continue
        symbol = _symbol_at_line(path, int(raw_line))
        target = f"{normalized}:{symbol}" if symbol else f"{normalized}:line@{raw_line}"
        if target not in result:
            result.append(target)
    return result

def _named_constructor_failure_target(project: Path, output: str) -> str | None:
    names = set(_NAMED_INIT_TYPE_ERROR.findall(output))
    if len(names) != 1:
        return None
    class_name = next(iter(names))
    candidates: list[str] = []
    files_scanned = 0
    for path in sorted(project.rglob("*.py")):
        if files_scanned >= 500 or not path.is_file() or not _is_production_path(project, path):
            continue
        files_scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        owner = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name),
            None,
        )
        if owner is None or not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__"
            for node in owner.body
        ):
            continue
        candidates.append(
            f"{path.relative_to(project).as_posix()}:{class_name}.__init__"
        )
    return candidates[0] if len(candidates) == 1 else None

def _direct_test_call_targets(project: Path, nodeids: list[str]) -> list[str]:
    return list(_test_assertion_causal_analysis(project, nodeids)["production_targets"])

def _test_assertion_causal_analysis(project: Path, nodeids: list[str]) -> dict[str, Any]:
    targets: list[str] = []
    excluded: list[dict[str, str]] = []
    for nodeid in nodeids:
        parts = str(nodeid).replace("\\", "/").split("::")
        if len(parts) < 2:
            continue
        test_path = project / parts[0]
        test_name = parts[-1].split("[", 1)[0]
        if not test_path.is_file():
            continue
        try:
            tree = ast.parse(test_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        scope = tree.body
        if len(parts) >= 3:
            class_name = parts[-2].split("[", 1)[0]
            owner = next(
                (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name), None
            )
            scope = owner.body if owner is not None else []
        function = next((node for node in scope if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_name), None)
        if function is None:
            continue
        aliases = _test_import_aliases(tree)
        calls = _assertion_causal_calls(function, project, aliases)
        for call, authoritative in calls:
            candidate = _imported_call_target(project, call.func, aliases)
            if candidate and authoritative and candidate not in targets:
                targets.append(candidate)
                continue
            reason = (
                "opaque_observer_descendant"
                if candidate and not authoritative
                else _excluded_call_reason(project, call.func, aliases)
            )
            label = ".".join(_attribute_names(call.func)) or type(call.func).__name__
            evidence = {"call": label, "reason": reason}
            if evidence not in excluded:
                excluded.append(evidence)
        if not targets:
            state_target = _unique_state_transition_target(
                project=project,
                tree=tree,
                function=function,
                aliases=aliases,
            )
            if state_target:
                targets.append(state_target)
    return {
        "production_targets": targets if len(targets) == 1 else [],
        "candidate_targets": targets,
        "excluded_calls": excluded[:12],
        "reason": (
            "unique_project_production_target"
            if len(targets) == 1
            else "multiple_project_production_targets"
            if len(targets) > 1
            else "no_project_production_target_in_assertion_slice"
        ),
    }

def _unique_state_transition_target(
    *,
    project: Path,
    tree: ast.Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    aliases: dict[str, tuple[str, str | None]],
) -> str | None:
    local_classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    instances: dict[str, ast.ClassDef] = {}
    for node in _lexical_function_nodes(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
            continue
        owner = local_classes.get(value.func.id)
        if owner is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            for name in _assignment_names(target):
                instances[name] = owner

    assertions = [node for node in _lexical_function_nodes(function) if isinstance(node, ast.Assert)]
    candidates: set[str] = set()
    for assertion in assertions:
        observed_receivers = {
            call.func.value.id
            for call in ast.walk(assertion.test)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in instances
        }
        for receiver in observed_receivers:
            owner = instances[receiver]
            production_bases = [
                base.id
                for base in owner.bases
                if isinstance(base, ast.Name) and base.id in aliases
            ]
            if len(production_bases) != 1:
                continue
            base_name = production_bases[0]
            prior_targets = {
                target
                for call in _lexical_function_nodes(function)
                if isinstance(call, ast.Call)
                and int(getattr(call, "lineno", 0)) < int(assertion.lineno)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == receiver
                for target in [
                    _imported_call_target(
                        project,
                        ast.Attribute(
                            value=ast.Name(id=base_name, ctx=ast.Load()),
                            attr=call.func.attr,
                            ctx=ast.Load(),
                        ),
                        aliases,
                    )
                ]
                if target is not None
            }
            if len(prior_targets) == 1:
                candidates.update(prior_targets)
    return next(iter(candidates)) if len(candidates) == 1 else None

def _assertion_causal_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    project: Path,
    aliases: dict[str, tuple[str, str | None]],
) -> list[tuple[ast.Call, bool]]:
    assignments: dict[str, ast.expr] = {}
    assertions: list[ast.expr] = []
    for node in _lexical_function_nodes(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            for name in _assignment_names(node.targets[0]):
                assignments[name] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            assignments[node.target.id] = node.value
        elif isinstance(node, ast.Assert):
            assertions.append(node.test)

    roots = assertions or [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    ]
    calls: dict[ast.Call, bool] = {}
    visited_names: set[str] = set()

    def visit(expression: ast.AST, authoritative: bool = True) -> None:
        if isinstance(expression, ast.Name):
            if expression.id in assignments and expression.id not in visited_names:
                visited_names.add(expression.id)
                visit(assignments[expression.id], authoritative)
            return
        if isinstance(expression, ast.Call):
            calls[expression] = calls.get(expression, False) or authoritative
            candidate = _imported_call_target(project, expression.func, aliases)
            reason = _excluded_call_reason(project, expression.func, aliases)
            if candidate is not None:
                return
            if candidate is None and reason in {
                "test_support_call",
                "external_dependency_call",
                "dynamic_call",
            }:
                for argument in [*expression.args, *[item.value for item in expression.keywords]]:
                    visit(argument, False)
                return
            if candidate is None and reason == "local_or_instance_call":
                if isinstance(expression.func, ast.Attribute):
                    visit(expression.func.value, authoritative)
                for argument in [*expression.args, *[item.value for item in expression.keywords]]:
                    visit(argument, False)
                return
        for child in ast.iter_child_nodes(expression):
            visit(child, authoritative)

    for root in roots:
        visit(root)
    return list(calls.items())

def _lexical_function_nodes(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    """Walk one function body without leaking names from nested scopes."""
    result: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(function.body))
    while stack:
        node = stack.pop()
        result.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))
    return result

def _assignment_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [] if target.id == "_" else [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [
            name
            for item in target.elts
            for name in _assignment_names(item)
        ]
    return []

def _excluded_call_reason(
    project: Path, function: ast.expr, aliases: dict[str, tuple[str, str | None]]
) -> str:
    names = _attribute_names(function)
    if not names:
        return "dynamic_call"
    binding = aliases.get(names[0])
    if binding is None:
        return "local_or_instance_call"
    module, imported = binding
    parts = module.split(".")
    if imported and _python_module_path_any(project, [*parts, imported]) is not None:
        parts.append(imported)
    path = _python_module_path_any(project, parts)
    if path is None:
        return "external_dependency_call"
    return "test_support_call" if not _is_production_path(project, path) else "unresolved_project_call"

def _test_import_aliases(tree: ast.Module) -> dict[str, tuple[str, str | None]]:
    aliases: dict[str, tuple[str, str | None]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[str(item.asname or item.name.split(".", 1)[0])] = (str(item.name), None)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[str(item.asname or item.name)] = (str(node.module), str(item.name))
    return aliases

def _imported_call_target(
    project: Path, function: ast.expr, aliases: dict[str, tuple[str, str | None]]
) -> str | None:
    names = _attribute_names(function)
    if not names or names[0] not in aliases:
        return None
    module, imported = aliases[names[0]]
    tail = names[1:]
    module_parts = module.split(".")
    symbol_parts: list[str] = []
    if imported:
        imported_module = [*module_parts, imported]
        if _python_module_path(project, imported_module):
            module_parts = imported_module
            symbol_parts = tail
        else:
            symbol_parts = [imported, *tail]
    else:
        symbol_parts = tail
    while symbol_parts and _python_module_path(project, [*module_parts, symbol_parts[0]]):
        module_parts.append(symbol_parts.pop(0))
    path = _python_module_path(project, module_parts)
    if path is None or not symbol_parts:
        return None
    symbol = ".".join(symbol_parts)
    resolved = _source_symbol_target(project, path, symbol)
    if resolved is None:
        return None
    target_path, target_symbol = resolved
    return f"{target_path.relative_to(project).as_posix()}:{target_symbol}"

def _attribute_names(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        parent = _attribute_names(node.value)
        return [*parent, node.attr] if parent else []
    return []
