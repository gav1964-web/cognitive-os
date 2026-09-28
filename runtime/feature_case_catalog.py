"""A source-derived menu of existing functions with declared JSON data interfaces."""
import ast
from pathlib import Path

from .feature_workspace import owned_path, read_sources, merge_reads


def _json_type(node, *, nested=False, input_subset=False):
    if isinstance(node, ast.Name):
        return node.id in {'str', 'int', 'float', 'bool', 'dict', 'list', 'tuple', 'None'} or nested and node.id == 'Any'
    if isinstance(node, ast.Constant):
        return node.value is None or node.value is Ellipsis
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        values = [_json_type(part, nested=nested, input_subset=input_subset) for part in (node.left, node.right)]
        return any(values) if input_subset else all(values)
    if isinstance(node, ast.Subscript):
        name = node.value.id if isinstance(node.value, ast.Name) else getattr(node.value, 'attr', '')
        if name not in {'dict', 'list', 'tuple', 'Dict', 'List', 'Tuple', 'Mapping', 'Sequence', 'Optional', 'Union'}:
            return False
        parts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        values = [_json_type(part, nested=name not in {'Optional', 'Union'} or nested,
                             input_subset=input_subset) for part in parts]
        return any(values) if input_subset and name in {'Optional', 'Union'} else all(values)
    return False


def case_catalog(project, expected, scope):
    result = []
    for name in sorted(scope):
        if name not in expected or not name.endswith('.py'):
            continue
        module = name.removeprefix('src/')[:-3].replace('/', '.')
        if not all(p.isidentifier() and not p.startswith('_') for p in module.split('.')):
            continue
        tree = ast.parse(owned_path(Path(project), name).read_text(encoding='utf-8-sig'))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith('_'):
                continue
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            path_inputs = any(isinstance(n, ast.Name) and n.id in {'Path', 'PathLike'}
                              or isinstance(n, ast.Attribute) and n.attr in {'Path', 'PathLike'}
                              for arg in args if arg.annotation for n in ast.walk(arg.annotation))
            if (node.args.vararg or node.args.kwarg or not _json_type(node.returns)
                    or path_inputs or not all(_json_type(arg.annotation, input_subset=True) for arg in args)):
                continue
            result.append({'api': f'api_{len(result)}', 'entrypoint': module + '.' + node.name,
                           'signature': '(' + ast.unparse(node.args) + ') -> ' + ast.unparse(node.returns),
                           'path': name, 'start': node.lineno, 'end': node.end_lineno})
    return result


def contract_sources(project, expected, menu):
    """Supply complete menu functions and their direct local helper bodies."""
    rows = []
    for path in sorted({entry['path'] for entry in menu}):
        tree = ast.parse(owned_path(Path(project), path).read_text(encoding='utf-8-sig'))
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        names = {entry['entrypoint'].rsplit('.', 1)[1] for entry in menu if entry['path'] == path}
        helpers = {n.func.id for name in names for n in ast.walk(functions[name])
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in functions}
        for name in sorted(names | helpers, key=lambda n: functions[n].lineno):
            node = functions[name]
            rows.extend(read_sources(Path(project), expected, [
                {'path': path, 'start': node.lineno, 'end': node.end_lineno}], max_bytes=26000))
    return merge_reads([], rows)
