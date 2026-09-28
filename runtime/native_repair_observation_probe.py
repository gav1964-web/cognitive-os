"""Observe original pytest calls with fixtures; never reevaluate assertions."""
import ast
import dis
import json
import sys
import types
from pathlib import Path

if __package__:
    from .repair_observation_probe import safe_value
    from .repair_target_trace_probe import method_catalog, code_digest
    from .repair_function_catalog import function_catalog
    from .native_observation_values import state_value
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from repair_observation_probe import safe_value
    from repair_target_trace_probe import method_catalog, code_digest
    from repair_function_catalog import function_catalog
    from native_observation_values import state_value


def selected_fields(source, fields):
    node = ast.parse(source).body[0]
    allowed = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    allowed.update(n.arg for n in ast.walk(node.args) if isinstance(n, ast.arg))
    if (not isinstance(fields, list) or len(fields) > 8 or any(not isinstance(f, str) for f in fields)
            or len(set(fields)) != len(fields) or set(fields) - (allowed - {'self'})):
        raise ValueError('explicit_source_local_names_required')


def observation_catalog(source, target):
    """Observe module functions too; keep class repair nomination unchanged."""
    path, separator, symbol = target.partition(':')
    if '.' in symbol:
        return method_catalog(source, target)
    if not separator or not symbol.isidentifier() or len(source.encode('utf-8')) > 1_000_000:
        raise ValueError('bounded_function_target_required')
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbol]
    if len(nodes) != 1:
        raise ValueError('unique_module_function_required')
    node = nodes[0]
    if (not isinstance(node, ast.FunctionDef) or node.decorator_list
            or any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)) for n in ast.walk(node))):
        raise ValueError('ordinary_module_function_required')
    codes = [c for c in compile(source, path, 'exec', dont_inherit=True).co_consts
             if isinstance(c, types.CodeType) and c.co_name == symbol and c.co_firstlineno == node.lineno]
    if len(codes) != 1:
        raise ValueError('unique_module_function_code_required')
    return {symbol: {'target': target, 'line_start': node.lineno, 'line_end': node.end_lineno,
                     'code_digest': code_digest(codes[0]), 'source': ast.get_source_segment(source, node)}}


class NativeTracker:
    def __init__(self, project, request):
        self.project, self.request = project, request
        self.path = (project / request['observed_target'].partition(':')[0]).resolve()
        catalog = (function_catalog(project, request['source_files'], request['observed_target'])[0]
                   if 'source_files' in request else
                   observation_catalog(self.path.read_text(encoding='utf-8'), request['observed_target']))
        by_target = {m['target']: m for m in catalog.values()}
        self.callables = {(str((project / m['target'].partition(':')[0]).resolve()),
                           m['target'].partition(':')[2].rsplit('.', 1)[-1]): m for m in catalog.values()}
        fields = request['method_fields']
        if not isinstance(fields, dict) or not 1 <= len(fields) <= 4 or set(fields) - set(by_target):
            raise ValueError('bounded_owned_methods_required')
        self.methods = {}
        for target, names in fields.items():
            method = by_target[target]
            selected_fields(method['source'], names)
            key = (str((project / target.partition(':')[0]).resolve()), target.partition(':')[2].rsplit('.', 1)[-1])
            self.methods[key] = {**method, 'fields': names}
        self.selected, self.rows = [], []
        self.active = None
        self.frames, self.tick = {}, 0

    def pytest_collection_finish(self, session):
        self.selected = [item.nodeid for item in session.items]

    def start(self, item):
        if sys.gettrace() is not None or sys.getprofile() is not None:
            raise ValueError('existing_instrumentation_unsupported')
        bound = next(r for r in self.request['tests'] if r['nodeid'] == item.nodeid)
        path = (self.project / bound['path']).resolve()
        tree = ast.parse(path.read_text(encoding='utf-8'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == item.originalname]
        if (len(functions) != 1 or Path(item.obj.__code__.co_filename).resolve() != path
                or item.obj.__code__.co_name != functions[0].name):
            raise ValueError('source_owned_test_function_required')
        function = functions[0]
        selected_fields(ast.get_source_segment(path.read_text(encoding='utf-8'), function),
                        self.request['test_local_names'])
        assertions = [n for n in function.body if isinstance(n, ast.Assert)]
        if not assertions or len(assertions) != sum(isinstance(n, ast.Assert) for n in ast.walk(function)):
            raise ValueError('direct_native_assertions_required')
        self.active = {'nodeid': item.nodeid, 'calls': [], 'assertions': [
            {'line': n.lineno, 'end_line': n.end_lineno, 'reachability': 'not_reached', 'snapshots': []}
            for n in assertions], 'test_outcome': 'unknown'}
        self.test_code = item.obj.__code__
        self.frames, self.tick = {}, 0
        sys.settrace(self.trace)

    def values(self, frame, names):
        return {name: self.value(frame.f_locals[name]) if name in frame.f_locals else {'type': 'unbound'}
                for name in names}

    def value(self, value):
        return state_value(value, self.callables) if self.request.get('structured_values') else safe_value(value)

    def trace(self, frame, event, arg):
        if self.active is None:
            return None
        self.tick += 1
        if self.tick > 100000:
            raise ValueError('native_observation_event_budget_exceeded')
        if frame.f_code is self.test_code and event == 'line':
            for assertion in self.active['assertions']:
                if assertion['line'] <= frame.f_lineno <= assertion['end_line']:
                    assertion['reachability'] = 'reached'
                    if len(assertion['snapshots']) >= 8:
                        raise ValueError('assertion_observation_budget_exceeded')
                    assertion['snapshots'].append({'sequence': self.tick, 'line': frame.f_lineno,
                        'locals': self.values(frame, self.request['test_local_names'])})
        if event == 'call' and id(frame) not in self.frames:
            method = self.methods.get((frame.f_code.co_filename, frame.f_code.co_name))
            if method:
                if code_digest(frame.f_code) != method['code_digest']:
                    raise ValueError('observed_method_code_changed')
                if len(self.active['calls']) >= 32:
                    raise ValueError('native_observation_call_budget_exceeded')
                row = {'target': method['target'], 'events': []}
                self.active['calls'].append(row)
                self.frames[id(frame)] = row, method['fields'], frame
        tracked = self.frames.get(id(frame))
        if tracked and event in {'line', 'return', 'exception'}:
            row, names, _ = tracked
            if len(row['events']) >= 128:
                raise ValueError('native_observation_line_budget_exceeded')
            suspended = event == 'return' and dis.opname[frame.f_code.co_code[frame.f_lasti]] in {'YIELD_VALUE', 'YIELD_FROM'}
            row['events'].append({'sequence': self.tick, 'event': 'yield' if suspended else event, 'line': frame.f_lineno,
                                  'locals': self.values(frame, names)})
            if suspended:
                row['events'][-1]['yielded'] = self.value(arg)
            elif event == 'return':
                row['return'] = self.value(arg)
                self.frames.pop(id(frame), None)
        return self.trace

    def stop(self):
        intact = sys.gettrace() == self.trace and sys.getprofile() is None
        sys.settrace(None)
        self.frames.clear()
        if not intact:
            raise ValueError('native_instrumentation_changed')

    def report(self, call, report):
        if call.when != 'call' or self.active is None:
            return
        self.active['test_outcome'] = report.outcome
        if self.request.get('structured_values'):
            self.active['xfail'] = hasattr(report, 'wasxfail')
        self.rows.append(self.active)
        self.active = None


def main():
    import pytest
    project, request_path, output = [Path(p).resolve() for p in sys.argv[1:]]
    sys.path[:0] = [str(project), str(project / 'src')]
    request = json.loads(request_path.read_text(encoding='utf-8'))
    tracker = NativeTracker(project, request)

    class Hooks:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_call(self, item):
            tracker.start(item)
            try:
                yield
            finally:
                tracker.stop()

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            result = yield
            tracker.report(call, result.get_result())

    code = pytest.main(request['pytest_arguments'], plugins=[tracker, Hooks()])
    result = {'selected': tracker.selected, 'rows': tracker.rows}
    encoded = json.dumps(result)
    if len(encoded) > (240000 if request.get('structured_values') else 32000):
        raise ValueError('native_observation_output_budget_exceeded')
    output.write_text(encoded, encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
