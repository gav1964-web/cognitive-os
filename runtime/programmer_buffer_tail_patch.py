"""Propose a bounded training edit; native tests must establish its validity."""
from __future__ import annotations

import ast


def preserve_split_buffer_tail(source: str, symbol: str) -> dict | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    scope = tree.body
    function = None
    for part in symbol.split("."):
        matches = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == part]
        if len(matches) != 1:
            return None
        function = matches[0]
        scope = function.body
    if not isinstance(function, ast.FunctionDef) or not function.body:
        return None
    last = function.body[-1]
    if not (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call)
            and isinstance(last.value.func, ast.Attribute) and last.value.func.attr == "clear"
            and not last.value.args and not last.value.keywords):
        return None
    buffer = last.value.func.value
    if not isinstance(buffer, ast.Attribute) or not isinstance(buffer.value, ast.Name):
        return None
    name = ast.unparse(buffer)
    splits = []
    for index, node in enumerate(function.body[:-1]):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Tuple) and len(node.targets[0].elts) == 2
                and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2):
            continue
        head_target, tail_target = node.targets[0].elts
        head, tail = node.value.elts
        if not isinstance(head_target, ast.Name) or ast.unparse(tail_target) != name:
            continue
        if not all(isinstance(n, ast.Subscript) and ast.unparse(n.value) == name
                   and isinstance(n.slice, ast.Slice) for n in (head, tail)):
            continue
        a, b = head.slice, tail.slice
        if (a.lower is not None or a.upper is None or a.step is not None
                or b.lower is None or b.upper is not None or b.step is not None
                or ast.dump(a.upper) != ast.dump(b.lower)):
            continue
        # No intervening operation may inspect, mutate, alias or rebind the retained tail.
        if any(isinstance(n, ast.Attribute) and ast.unparse(n) == name
               for statement in function.body[index + 1:-1] for n in ast.walk(statement)):
            continue
        splits.append(node)
    if len(splits) != 1:
        return None
    lines = source.splitlines(keepends=True)
    if last.lineno != last.end_lineno or lines[last.lineno - 1].strip().split("#", 1)[0].strip() != name + ".clear()":
        return None
    patched = "".join(lines[:last.lineno - 1] + lines[last.end_lineno:])
    ast.parse(patched)
    return {"source": patched, "affected_symbols": [symbol],
            "source_precondition": ast.get_source_segment(source, splits[0]) + " -> terminal " + name + ".clear()"}
