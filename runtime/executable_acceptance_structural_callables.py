"""Callable and unpack structural samples for executable acceptance."""

from __future__ import annotations

import ast
from typing import Any

from .executable_acceptance_structural_common import (
    Candidates,
    FunctionNode,
    _direct_parameter,
    _literal,
    _priority,
    _settings,
)
from .executable_acceptance_structural_shapes import _root_parameter, _unpack_count


def _parameter_unpack_samples(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    policy = dict(_settings().get("unpack_samples") or {})
    maximum = int(policy.get("maximum_items") or 0)
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        name = _direct_parameter(item.value, parameters)
        count = max((_unpack_count(target) for target in targets), default=0)
        if name and 1 < count <= maximum:
            sample = [policy.get("element")] * count
            candidates[name].append((_priority("parameter_unpack"), sample, "ast_parameter_unpack"))


def _parameter_callable_samples(
    node: FunctionNode, parameters: set[str], candidates: Candidates
) -> None:
    fixture = str(_settings().get("parameter_callable_fixture") or "")
    if not fixture:
        return
    guarded_optional = _guarded_optional_callable_parameters(node)
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        name = _direct_parameter(item.func, parameters)
        if name and name not in guarded_optional:
            candidates[name].append(
                (_priority("parameter_callable"), {"__fixture__": fixture}, "ast_parameter_callable")
            )


def _guarded_optional_callable_parameters(node: FunctionNode) -> set[str]:
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = {
        argument.arg: default
        for argument, default in zip(positional[-len(node.args.defaults):], node.args.defaults)
    } if node.args.defaults else {}
    defaults.update({
        argument.arg: default
        for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
        if default is not None
    })
    optional = {
        name for name, default in defaults.items()
        if isinstance(default, ast.Constant) and default.value is None
    }
    guarded: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Compare) or len(item.ops) != 1 or len(item.comparators) != 1:
            continue
        if not isinstance(item.ops[0], (ast.IsNot, ast.NotEq)):
            continue
        expressions = [item.left, item.comparators[0]]
        name = next((part.id for part in expressions if isinstance(part, ast.Name)), "")
        has_none = any(isinstance(part, ast.Constant) and part.value is None for part in expressions)
        if has_none and name in optional:
            guarded.add(name)
    return guarded


def _split_unpack_samples(node: FunctionNode, parameters: set[str], candidates: Candidates) -> None:
    policy = dict(_settings().get("unpack_samples") or {})
    methods = set(policy.get("split_methods") or [])
    maximum = int(policy.get("maximum_items") or 0)
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)) or not isinstance(item.value, ast.Call):
            continue
        call = item.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr not in methods or not call.args:
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        count = max((_unpack_count(target) for target in targets), default=0)
        name = _root_parameter(call.func.value, parameters)
        delimiter = _literal(call.args[0])
        if name and isinstance(delimiter, str) and delimiter and 1 < count <= maximum:
            part = str(policy.get("split_part") or "sample")
            candidates[name].append((_priority("split_unpack"), delimiter.join([part] * count), "ast_split_unpack"))
