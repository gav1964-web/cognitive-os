"""Recognize standard unittest observations without trusting arbitrary assert helpers."""
from __future__ import annotations

import ast

ARITY = {name: 2 for name in (
    "assertEqual", "assertNotEqual", "assertIs", "assertIsNot", "assertIn", "assertNotIn",
    "assertGreater", "assertGreaterEqual", "assertLess", "assertLessEqual",
    "assertDictEqual", "assertListEqual", "assertTupleEqual", "assertSetEqual",
    "assertSequenceEqual", "assertCountEqual",
)}
ARITY.update({name: 1 for name in ("assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone")})


def unittest_observations(owner, function, aliases, nodes) -> list[ast.expr]:
    """Only direct, unmodified TestCase methods; messages are not asserted data."""
    if owner is None or len(owner.bases) != 1 or not function.args.args:
        return []
    base = owner.bases[0]
    supported = (
        isinstance(base, ast.Name) and aliases.get(base.id) == ("unittest", "TestCase")
        or isinstance(base, ast.Attribute) and base.attr == "TestCase"
        and isinstance(base.value, ast.Name) and aliases.get(base.value.id) == ("unittest", None)
    )
    if not supported:
        return []
    receiver = function.args.args[0].arg
    # Local rebinding/monkeypatches invalidate knowledge of the assertion implementation.
    if any(isinstance(n, (ast.Name, ast.Attribute)) and isinstance(n.ctx, ast.Store)
           and (isinstance(n, ast.Name) and n.id == receiver
                or isinstance(n, ast.Attribute) and n.attr in ARITY) for n in nodes):
        return []
    overridden = {n.name for n in owner.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    overridden.update(n.id for statement in owner.body for n in ast.walk(statement)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in ARITY)
    result = []
    for node in nodes:
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == receiver
                and node.func.attr in ARITY and node.func.attr not in overridden):
            count = ARITY[node.func.attr]
            if len(node.args) >= count and not any(isinstance(arg, ast.Starred) for arg in node.args):
                result.extend(node.args[:count])
    return result
