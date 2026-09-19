"""Exact syntax index of user-facing surfaces; no inferred domain classification."""
import ast

from .excerpts import VisibleText, redact_literals


def source_surface(text, suffix):
    if suffix != '.py':
        return {}
    try:
        tree = ast.parse(redact_literals(text))
    except SyntaxError:
        return {}
    routes, patterns, options, labels = [], [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, 'attr', getattr(node.func, 'id', ''))
            args = [x.value for x in node.args if isinstance(x, ast.Constant) and isinstance(x.value, str)]
            if name in {'route', 'get', 'post', 'put', 'delete'} and args and args[0].startswith('/'):
                routes.append(args[0])
            elif name in {'glob', 'rglob'}:
                patterns.extend(args)
            elif name == 'add_argument':
                options.extend(args)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and '<html' in node.value.lower():
            parser = VisibleText()
            try:
                parser.feed(node.value)
            except Exception:
                continue
            labels.extend(parser.text)
    return {'route_literals': list(dict.fromkeys(routes))[:60],
            'file_glob_literals': list(dict.fromkeys(patterns))[:30],
            'cli_arguments': list(dict.fromkeys(options))[:40],
            'visible_ui_text': list(dict.fromkeys(labels))[:60],
            'authority': 'syntax_only; endpoints alone do not establish a browser workflow'}
