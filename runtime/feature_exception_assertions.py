"""Observe explicit exception contracts without treating arbitrary crashes as assertions.

Loaded as a pytest plugin by the isolated acceptance runner. Recognition is
deliberately bounded: pytest.raises context manager, a builtin expected type,
and a traceback entering project production code from its body.
"""
import ast
import builtins
import json
from pathlib import Path


def expected_exception_contract(item, call, project):
    if call.when != 'call' or call.excinfo is None:
        return False
    if isinstance(call.excinfo.value, (ImportError, NameError, SyntaxError, AttributeError)):
        return False
    path = Path(str(item.path)).resolve()
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeError):
        return False
    aliases = {a.asname or a.name for n in tree.body if isinstance(n, ast.Import)
               for a in n.names if a.name == 'pytest'}
    direct = {a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom)
              and n.module == 'pytest' for a in n.names if a.name == 'raises'}
    frames = list(call.excinfo.traceback)
    for index, frame in enumerate(frames):
        if Path(str(frame.path)).resolve() != path:
            continue
        line = frame.lineno + 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.With) or not node.body:
                continue
            if not node.body[0].lineno <= line <= node.body[-1].end_lineno:
                continue
            for entry in node.items:
                expr = entry.context_expr
                if not isinstance(expr, ast.Call) or not expr.args:
                    continue
                func = expr.func
                raises = (isinstance(func, ast.Name) and func.id in direct or
                          isinstance(func, ast.Attribute) and func.attr == 'raises'
                          and isinstance(func.value, ast.Name) and func.value.id in aliases)
                arg = expr.args[0]
                names = arg.elts if isinstance(arg, ast.Tuple) else [arg]
                types = [getattr(builtins, n.id, None) if isinstance(n, ast.Name)
                         else None for n in names]
                if not raises or not types or not all(isinstance(t, type)
                        and issubclass(t, Exception) for t in types):
                    continue
                for downstream in frames[index + 1:]:
                    source = Path(str(downstream.path)).resolve()
                    if not source.is_relative_to(project) or not source.is_file():
                        continue
                    rel = source.relative_to(project)
                    if (source.suffix == '.py' and 'tests' not in rel.parts
                            and not source.name.startswith('test_')
                            and source.name != 'conftest.py'):
                        return True
    return False


class ExceptionContracts:
    def __init__(self, project, receipt):
        self.project = Path(project).resolve()
        self.receipt = Path(receipt)
        self.identities = []

    def pytest_runtest_makereport(self, item, call):
        if expected_exception_contract(item, call, self.project):
            parts = item.nodeid.split('::')
            module = parts[0].replace('\\', '/').removesuffix('.py').replace('/', '.')
            self.identities.append('.'.join([module, *parts[1:-1]]) + '::' + parts[-1])

    def pytest_sessionfinish(self, session, exitstatus):
        self.receipt.write_text(json.dumps(self.identities), encoding='utf-8')
