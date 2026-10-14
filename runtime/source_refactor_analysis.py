"""Conservative source facts for moving independent top-level functions."""
from __future__ import annotations

import ast
import hashlib
import symtable
from pathlib import Path

SAFE_BUILTINS = set('abs all any ascii bin bool bytearray bytes chr complex dict divmod enumerate '
                    'filter float format frozenset hash hex int isinstance issubclass iter len list '
                    'map max min next oct ord pow range repr reversed round set slice sorted str sum '
                    'tuple zip ArithmeticError AssertionError Exception IndexError KeyError LookupError '
                    'NotImplementedError OverflowError RuntimeError StopIteration TypeError ValueError ZeroDivisionError'.split())
DYNAMIC_NAMES = {'globals', 'locals', 'eval', 'exec', 'compile', '__import__', 'vars', '__builtins__'}
DYNAMIC_ATTRS = {'__globals__', '__code__', '__getattr__', '__getattribute__', '_getframe', 'currentframe'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def analyze_module(root: Path, relative: str, *, max_lines: int = 400) -> dict:
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('source_outside_project')
    raw = path.read_bytes()
    result = {'path': relative, 'sha256': digest(raw), 'candidates': [], 'rejected': [],
              'max_lines': max_lines, 'line_count': len(raw.splitlines())}
    if len(raw) > 120_000 or result['line_count'] > 2400:
        return {**result, 'reason': 'module_exceeds_context_budget'}
    if path.name == '__init__.py' or path.name.startswith('test_') or path.name.endswith('_test.py'):
        return {**result, 'reason': 'entrypoint_or_test_module_requires_manual_design'}
    if path.parent != root and not (path.parent / '__init__.py').is_file():
        return {**result, 'reason': 'package_boundary_required'}
    try:
        source = raw.decode('utf-8')
        tree = ast.parse(source)
        symbols = symtable.symtable(source, relative, 'exec')
    except (UnicodeError, SyntaxError, ValueError):
        return {**result, 'reason': 'unsupported_source_encoding_or_syntax'}
    if any((isinstance(n, ast.Name) and n.id in DYNAMIC_NAMES)
           or (isinstance(n, ast.Attribute) and n.attr in DYNAMIC_ATTRS)
           for n in ast.walk(tree)):
        return {**result, 'reason': 'dynamic_namespace_observation'}
    if any(isinstance(n, ast.ImportFrom) and any(a.name == '*' for a in n.names)
           for n in ast.walk(tree)):
        return {**result, 'reason': 'wildcard_namespace'}
    if path.parent != root and any(isinstance(n, ast.Name) and n.id == '__name__'
                                   for statement in tree.body if isinstance(statement, ast.If)
                                   for n in ast.walk(statement.test)):
        return {**result, 'reason': 'dual_script_and_package_execution'}
    module_names = {s.get_name() for s in symbols.get_symbols() if s.is_assigned() or s.is_imported()}
    lines = source.splitlines(keepends=True)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        reason = _reject_function(node, symbols, module_names)
        if node.end_lineno - node.lineno + 6 > max_lines:
            reason = 'individual_function_requires_internal_refactor'
        if reason:
            result['rejected'].append({'name': node.name, 'reason': reason})
            continue
        text = ''.join(lines[node.lineno - 1:node.end_lineno])
        result['candidates'].append({'name': node.name, 'start': node.lineno,
            'end': node.end_lineno, 'lines': node.end_lineno - node.lineno + 1,
            'source': text, 'sha256': digest(text.encode('utf-8'))})
    result['reason'] = 'candidates_available' if result['candidates'] else 'no_supported_function_group'
    return result


def _reject_function(node: ast.FunctionDef, symbols, module_names: set[str]) -> str | None:
    if not isinstance(node, ast.FunctionDef) or node.decorator_list or node.name.startswith('__'):
        return 'async_decorated_or_special_function'
    if node.end_lineno - node.lineno < 4:
        return 'function_too_small_to_extract'
    if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom, ast.ClassDef,
                          ast.AsyncFunctionDef, ast.Yield, ast.YieldFrom)) for n in ast.walk(node)):
        return 'stateful_or_nested_scope'
    if sum(isinstance(n, ast.FunctionDef) for n in ast.walk(node)) != 1:
        return 'nested_function'
    defaults = [*node.args.defaults, *[v for v in node.args.kw_defaults if v is not None]]
    if any(not _immutable_literal(value) for value in defaults):
        return 'nonliteral_default'
    annotations = [n.annotation for n in ast.walk(node) if isinstance(n, ast.arg) and n.annotation]
    if node.returns:
        annotations.append(node.returns)
    if any(not _annotation_allowed(value, module_names) for value in annotations):
        return 'annotation_dependency'
    scopes = [s for s in symbols.get_children() if s.get_name() == node.name]
    if len(scopes) != 1:
        return 'redefined_symbol'
    globals_used = _globals(scopes[0])
    if globals_used - SAFE_BUILTINS or globals_used & module_names:
        return 'module_global_dependency'
    return None


def _globals(scope) -> set[str]:
    found = {s.get_name() for s in scope.get_symbols() if s.is_global() and s.is_referenced()}
    return found | set().union(*[_globals(child) for child in scope.get_children()])


def _immutable_literal(node: ast.AST) -> bool:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return False
    def immutable(item):
        return isinstance(item, (str, bytes, int, float, complex, bool, type(None))) or (
            isinstance(item, tuple) and all(immutable(v) for v in item))
    return immutable(value)


def _annotation_allowed(node: ast.AST, module_names: set[str]) -> bool:
    if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in SAFE_BUILTINS - module_names
           for n in ast.walk(node)):
        return False
    return all(isinstance(n, (ast.Name, ast.Constant, ast.Subscript, ast.Tuple, ast.Load,
                             ast.BinOp, ast.BitOr)) and
               (not isinstance(n, ast.Name) or n.id in SAFE_BUILTINS - module_names)
               for n in ast.walk(node))
