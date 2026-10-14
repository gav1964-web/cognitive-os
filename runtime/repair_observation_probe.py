"""Standalone isolated equality probes; no native-suite or hostile-code authority."""
import ast
import json
import sys
from pathlib import Path

if __package__:
    from .repair_target_trace_probe import method_catalog, code_digest
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from repair_target_trace_probe import method_catalog, code_digest


def safe_value(value):
    kind = type(value)
    if kind in (str, int, bool, type(None)):
        if kind is str and len(value) > 400:
            return {'type': 'str', 'length': len(value), 'value_omitted': True}
        if kind is int and value.bit_length() > 256:
            return {'type': 'int', 'value_omitted': True}
        return {'type': kind.__name__, 'value': value}
    if kind in (set, frozenset, list, tuple):
        if len(value) <= 16 and all(type(v) is str and len(v) <= 80 for v in value):
            return {'type': kind.__name__, 'value': sorted(value) if kind in (set, frozenset) else list(value)}
        return {'type': kind.__name__, 'length': len(value), 'value_omitted': True}
    return {'type': 'opaque', 'value_omitted': True}


class MethodTrace:
    def __init__(self, project, target, fields):
        self.path = (project / target.partition(':')[0]).resolve()
        catalog = method_catalog(self.path.read_text(encoding='utf-8'), target)
        self.method = next(v for v in catalog.values() if v['target'] == target)
        args = ast.parse(self.method['source']).body[0].args
        allowed = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]} - {'self'}
        if len(fields) > 8 or set(fields) - allowed or len(set(fields)) != len(fields):
            raise ValueError('explicit_method_argument_names_required')
        self.fields, self.calls, self.frames = fields, [], {}

    def trace(self, frame, event, arg):
        if event == 'call':
            if Path(frame.f_code.co_filename) != self.path or code_digest(frame.f_code) != self.method['code_digest']:
                return None
            if len(self.calls) >= 32:
                raise ValueError('observation_call_budget_exceeded')
            row = {'arguments': {k: safe_value(frame.f_locals[k]) for k in self.fields}, 'events': []}
            self.calls.append(row)
            self.frames[id(frame)] = row
        row = self.frames.get(id(frame))
        if row is not None and event in {'line', 'return', 'exception'}:
            if len(row['events']) >= 128:
                raise ValueError('observation_line_budget_exceeded')
            row['events'].append([event, frame.f_lineno])
            if event == 'return':
                row['return'] = safe_value(arg)
                self.frames.pop(id(frame), None)
        return self.trace


def observe(project, request):
    import pytest
    selected = []
    class Hooks:
        def pytest_collection_finish(self, session):
            selected.extend(session.items)
    code = pytest.main(request['pytest_arguments'], plugins=[Hooks()])
    if code != 0 or len(selected) != 1 or selected[0].nodeid != request['nodeid']:
        raise ValueError('unique_collected_test_required')
    item = selected[0]
    if item.fixturenames or Path(item.obj.__code__.co_filename).resolve() != (project / request['test_path']).resolve():
        raise ValueError('fixture_free_source_owned_test_required')
    tree = ast.parse(request['excerpt'])
    function = tree.body[0]
    if (not isinstance(function, ast.FunctionDef) or function.decorator_list or function.args.args
            or function.args.posonlyargs or function.args.kwonlyargs or function.args.vararg or function.args.kwarg
            or any(not isinstance(s, ast.Assert) for s in function.body)):
        raise ValueError('independent_assertion_only_test_required')
    statement = next(n for n in function.body if n.lineno == request['excerpt_line'])
    if ast.get_source_segment(request['excerpt'], statement) != request['assertion']:
        raise ValueError('assertion_source_mismatch')
    test = statement.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        raise ValueError('single_equality_assertion_required')
    tracker = MethodTrace(project, request['target'], request['argument_names'])
    if sys.gettrace() is not None or sys.getprofile() is not None:
        raise ValueError('existing_instrumentation_unsupported')
    result = {'id': request['id'], 'outcome': 'error', 'calls': tracker.calls}
    sys.settrace(tracker.trace)
    try:
        actual = eval(compile(ast.Expression(test.left), str(item.path), 'eval'), item.obj.__globals__)
        expected = eval(compile(ast.Expression(test.comparators[0]), str(item.path), 'eval'), item.obj.__globals__)
        result.update(actual=safe_value(actual), expected=safe_value(expected),
            outcome='passed' if actual == expected else 'failed')
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    finally:
        intact = sys.gettrace() == tracker.trace
        sys.settrace(None)
    if not intact or sys.getprofile() is not None:
        raise ValueError('instrumentation_changed')
    return result


def main():
    project, request_path, output = (Path(p).resolve() for p in sys.argv[1:])
    sys.path[:0] = [str(project), str(project / 'src')]
    result = observe(project, json.loads(request_path.read_text(encoding='utf-8')))
    output.write_text(json.dumps(result), encoding='utf-8')


if __name__ == '__main__':
    main()
