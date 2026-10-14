"""Cross-module function/callback execution ancestry in one native failed call."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_function_catalog import function_catalog
from repair_target_trace_probe import TracePlugin, code_digest


class FunctionTracePlugin(TracePlugin):
    def __init__(self, project, target, source_files):
        self.project, self.target = project, target
        self.catalog, self.verified = function_catalog(project, source_files, target)
        self.paths = {(project / p).resolve(): p for p in source_files}
        self.by_code = {(r['target'].partition(':')[0], r['code_line'],
                         r['target'].partition(':')[2], r['code_digest']): r
                        for r in self.catalog.values()}
        self.rows, self.selected = [], []
        self.current = self.active = self.old_profile = None

    def identity(self, frame):
        path = self.paths.get(Path(frame.f_code.co_filename))
        if path is None:
            return None, True
        code = frame.f_code
        key = (code.co_firstlineno, code.co_name, code_digest(code))
        return self.by_code.get((path, *key)), key in self.verified[path]

    def profile(self, frame, event, arg):
        if self.current is None or event not in ('call', 'return'):
            return
        if event == 'return':
            if self.active is not None and frame is self.active['frame']:
                self.active = None
            return
        identity, verified = self.identity(frame)
        if identity and identity['target'] == self.target:
            if self.active is not None or len(self.current['invocations']) >= 128:
                self.current['unsupported'] = True
                return
            caller = frame.f_back
            while caller and Path(caller.f_code.co_filename) != self.current['test_path']:
                caller = caller.f_back
            if caller is None:
                return
            row = {'test_line': caller.f_lineno, 'methods': [self.target], 'edges': [],
                   'unsupported': False, 'unsupported_calls': []}
            self.current['invocations'].append(row)
            self.active = {'frame': frame, 'row': row, 'calls': 0}
        elif self.active is not None:
            self.active['calls'] += 1
            if self.active['calls'] > 50000:
                self.reject(frame, 'trace_call_budget_exceeded')
                return
            if not verified:
                self.reject(frame, 'unrecognized_source_code')
                return
            if identity is None:
                return
            caller, parent = frame.f_back, None
            while caller is not None:
                parent, valid = self.identity(caller)
                if not valid:
                    self.reject(caller, 'unrecognized_parent_code')
                    return
                if parent is not None:
                    break
                caller = caller.f_back
            if parent is None:
                self.reject(frame, 'missing_owned_ancestor')
                return
            row = self.active['row']
            if identity['target'] not in row['methods']:
                row['methods'].append(identity['target'])
            edge = [parent['target'], identity['target']]
            if edge not in row['edges']:
                row['edges'].append(edge)


def main():
    import pytest
    project, target, output, arguments, sources = sys.argv[1:]
    project = Path(project).resolve()
    sys.path[:0] = [str(project), str(project / 'src')]
    tracker = FunctionTracePlugin(project, target, json.loads(sources))

    class Hooks:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_call(self, item):
            tracker.begin_call(item)
            try:
                yield
            finally:
                tracker.end_call()

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            outcome = yield
            tracker.report(item, call, outcome.get_result())

    code = pytest.main(json.loads(arguments), plugins=[tracker, Hooks()])
    Path(output).write_text(json.dumps({'selected': tracker.selected, 'rows': tracker.rows}), encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
