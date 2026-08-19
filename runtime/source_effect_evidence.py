"""Conservative AST evidence for observable callable side effects."""

from __future__ import annotations

import ast
from typing import Any

from runtime.source_side_effect_inference import infer_ast_side_effects, load_source_side_effect_policy
from runtime.source_ast_scope import callable_scope_walk, nested_definitions


_UNIT_OF_WORK_NAMES = {"con", "conn", "connection", "session", "db", "database", "unit_of_work", "uow"}
_DATABASE_WRITE_CALLS = {"add", "append", "delete", "execute", "execute_write", "executemany", "flush", "commit"}
def observed_side_effects(function: ast.AST | None, args: list[dict[str, Any]]) -> list[str]:
    if function is None:
        return []
    argument_names = {str(row.get("name") or "").lower() for row in args}
    memory_policy = dict(load_source_side_effect_policy().get("memory_state") or {})
    mutation_calls = {str(value).lower() for value in memory_policy.get("argument_mutation_calls", [])}
    effects = set(infer_ast_side_effects(function, ast.unparse(function)))
    for node in callable_scope_walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}:
            effects.add("memory_state")
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        owner = _root_name(node.func.value).lower()
        operation = node.func.attr.lower()
        if owner in argument_names & _UNIT_OF_WORK_NAMES and operation in _DATABASE_WRITE_CALLS:
            effects.add("database")
        database_mutation = owner in argument_names & _UNIT_OF_WORK_NAMES and operation in _DATABASE_WRITE_CALLS
        argument_mutation = owner in argument_names and operation in mutation_calls and not database_mutation
        owned_mutation = owner in {"self", "cls"} and isinstance(node.func.value, (ast.Attribute, ast.Subscript))
        if operation in mutation_calls and (argument_mutation or owned_mutation):
            effects.add("memory_state")
    for definition in nested_definitions(function):
        for decorator in definition.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if _root_name(target).lower() in argument_names | {"self", "cls"}:
                effects.add("memory_state")
    return sorted(effects)


def _root_name(node: ast.AST) -> str:
    while isinstance(node, (ast.Attribute, ast.Call)):
        node = node.value if isinstance(node, ast.Attribute) else node.func
    return node.id if isinstance(node, ast.Name) else ""
