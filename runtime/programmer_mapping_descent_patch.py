"""Bounded training proposal for a mapping lookup that returns a leaf too early."""
from __future__ import annotations

import ast


def guard_mapping_path_descent(source: str, symbol: str) -> dict | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    scope = tree.body
    function = None
    for name in symbol.split('.'):
        found = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name]
        if len(found) != 1:
            return None
        function = found[0]
        scope = function.body
    if not isinstance(function, ast.FunctionDef) or function.decorator_list:
        return None
    # This proposal relies on the ordinary builtins, not user-defined replacements.
    if any((isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in {'dict', 'isinstance'})
           or (isinstance(n, ast.arg) and n.arg in {'dict', 'isinstance'})
           or (isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in {'dict', 'isinstance'})
           or (isinstance(n, ast.alias) and (n.asname or n.name.split('.')[0]) in {'dict', 'isinstance', '*'})
           for n in ast.walk(tree)):
        return None
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 4:
        return None
    parts, current, loop, final = body
    if not (isinstance(parts, ast.Assign) and len(parts.targets) == 1
            and isinstance(parts.targets[0], ast.Name) and isinstance(loop, ast.For)
            and isinstance(loop.target, ast.Name) and not loop.orelse
            and isinstance(final, ast.Return) and isinstance(final.value, ast.Name)):
        return None
    if isinstance(current, ast.AnnAssign):
        cursor, initial = current.target, current.value
    elif isinstance(current, ast.Assign) and len(current.targets) == 1:
        cursor, initial = current.targets[0], current.value
    else:
        return None
    if not (isinstance(cursor, ast.Name) and isinstance(initial, ast.Attribute)
            and isinstance(initial.value, ast.Name) and initial.value.id == 'self'
            and final.value.id == cursor.id):
        return None
    args = function.args
    if (args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg
            or [a.arg for a in args.args] != ['self', 'path', 'default']):
        return None
    expected_parts = ast.parse('parts = path.strip("/").split("/")').body[0].value
    if ast.dump(parts.value) != ast.dump(expected_parts):
        return None
    if len(loop.body) != 4 or not isinstance(loop.body[1], ast.Assign):
        return None
    assignment = loop.body[1]
    if len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name):
        return None
    p, c, k, value = parts.targets[0].id, cursor.id, loop.target.id, assignment.targets[0].id
    if len({p, c, k, value, 'self', 'path', 'default'}) != 7:
        return None
    old = (f'for {k} in {p}:\n'
           f'    if {k} not in {c}:\n        return default\n'
           f'    {value} = {c}[{k}]\n'
           f'    if not isinstance({value}, dict):\n        return {value}\n'
           f'    {c} = {value}\n')
    if ast.dump(loop) != ast.dump(ast.parse(old).body[0]):
        return None
    new = (f'for {k} in {p}:\n'
           f'    if not isinstance({c}, dict) or {k} not in {c}:\n        return default\n'
           f'    {c} = {c}[{k}]\n')
    lines = source.splitlines(keepends=True)
    indent = lines[loop.lineno - 1][:loop.col_offset]
    newline = '\r\n' if '\r\n' in source else '\n'
    replacement = ''.join(indent + line + newline for line in new.splitlines())
    patched = ''.join(lines[:loop.lineno - 1]) + replacement + ''.join(lines[loop.end_lineno:])
    ast.parse(patched)
    return {'source': patched, 'affected_symbols': [symbol],
            'source_precondition': ast.get_source_segment(source, loop)}
