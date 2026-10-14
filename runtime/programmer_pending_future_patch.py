"""Bounded training proposal for unresolved futures at a disconnect boundary.

Only the exact cancel-writer/close-event callback shape is supported. Native
tests must validate actual Future semantics; annotations alone are not proof.
"""
from __future__ import annotations

import ast


def complete_pending_futures_on_disconnect(source: str, symbol: str) -> dict | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    parts = symbol.split('.')
    if len(parts) != 2 or parts[1] != 'connection_lost':
        return None
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]]
    if len(classes) != 1:
        return None
    owner = classes[0]
    callbacks = [node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == parts[1]]
    if len(callbacks) != 1:
        return None
    callback = callbacks[0]
    args = callback.args
    if (len(args.args) != 2 or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg
            or args.defaults or callback.decorator_list or args.args[0].arg != 'self'):
        return None
    error = args.args[1].arg
    body = list(callback.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if len(body) != 2 or not _cancel_then_close(body):
        return None
    maps = []
    for method in owner.body:
        if not isinstance(method, ast.FunctionDef) or method.name != '__init__':
            continue
        for node in method.body:
            if (isinstance(node, ast.AnnAssign) and _self_attribute(node.target)
                    and isinstance(node.value, ast.Dict) and not node.value.keys
                    and isinstance(node.annotation, ast.Subscript)
                    and ast.unparse(node.annotation.value) in {'dict', 'typing.Dict'}
                    and _future_annotation(node.annotation)):
                maps.append(ast.unparse(node.target))
    if len(maps) != 1 or not _has_future_insertion(owner, maps[0]):
        return None
    # Generated exception and loop variable must not resolve to project bindings.
    reserved = {'ConnectionError', 'pending_future'}
    for node in ast.walk(tree):
        if ((isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in reserved)
                or (isinstance(node, ast.arg) and node.arg in reserved)
                or (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in reserved)
                or (isinstance(node, ast.alias) and (node.asname or node.name.split('.')[0]) in reserved)):
            return None
    closing = body[-1]
    lines = source.splitlines(keepends=True)
    if closing.lineno != closing.end_lineno:
        return None
    line = lines[closing.lineno - 1]
    indent = line[:len(line) - len(line.lstrip())]
    newline = '\r\n' if line.endswith('\r\n') else '\n'
    added = [
        f'for pending_future in {maps[0]}.values():',
        '    if not pending_future.done():',
        f'        pending_future.set_exception({error} if {error} is not None else ConnectionError("Connection closed"))',
    ]
    patched = ''.join(lines[:closing.lineno - 1]) + ''.join(indent + row + newline for row in added)
    patched += ''.join(lines[closing.lineno - 1:])
    ast.parse(patched)
    return {'source': patched, 'affected_symbols': [symbol],
            'source_precondition': 'typed Future map insertion; writer cancellation followed by closed event; pending futures not settled',
            'scope': 'disconnect settlement only; requires component and native regression review'}


def _self_attribute(node) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self'


def _future_annotation(node) -> bool:
    return any(isinstance(item, ast.Attribute) and item.attr == 'Future' for item in ast.walk(node))


def _call_on_self(node, method) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == method
            and _self_attribute(node.value.func.value) and not node.value.args and not node.value.keywords)


def _cancel_then_close(body) -> bool:
    cancel, close = body
    if not (isinstance(cancel, ast.If) and len(cancel.body) == 1 and not cancel.orelse
            and _call_on_self(cancel.body[0], 'cancel') and _call_on_self(close, 'set')):
        return False
    test = cancel.test
    return (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.IsNot)
            and len(test.comparators) == 1 and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
            and ast.dump(test.left) == ast.dump(cancel.body[0].value.func.value))


def _has_future_insertion(owner, mapping) -> bool:
    for method in owner.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        futures = {arg.arg for arg in method.args.args if arg.annotation and _future_annotation(arg.annotation)}
        for node in method.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Subscript) and ast.unparse(node.targets[0].value) == mapping
                    and isinstance(node.value, ast.Name) and node.value.id in futures):
                return True
    return False
