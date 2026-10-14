"""Collect source line events without runtime values inside the observed call."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_target_trace_probe import TracePlugin, code_digest


class BranchPlugin(TracePlugin):
    def __init__(self, project, target, repair_target):
        super().__init__(project, target)
        self.repair = next(r for r in self.catalog.values() if r['target'] == repair_target)
        self.old_trace = None

    def trace_lines(self, frame, event, arg):
        if Path(frame.f_code.co_filename) != self.path:
            return None
        if event == 'call':
            if code_digest(frame.f_code) != self.repair['code_digest']:
                return None
            return self.trace_lines
        if self.active is not None and frame.f_locals.get('self') is self.active['receiver']:
            row = self.active['row']
            events = row.setdefault('repair_line_events', [])
            if len(events) >= 256:
                self.reject(frame, 'line_event_budget_exceeded')
            elif event in {'line', 'return', 'exception'}:
                events.append([event, frame.f_lineno])
        return self.trace_lines

    def begin_call(self, item):
        super().begin_call(item)
        self.old_trace = sys.gettrace()
        if self.old_trace is not None:
            self.current['unsupported'] = True
        sys.settrace(self.trace_lines)

    def end_call(self):
        if sys.gettrace() != self.trace_lines:
            self.current['unsupported'] = True
        sys.settrace(self.old_trace)
        super().end_call()


def main():
    import pytest
    project, target, output, arguments, repair_target = sys.argv[1:]
    project = Path(project).resolve()
    sys.path[:0] = [str(project), str(project / 'src')]
    tracker = BranchPlugin(project, target, repair_target)

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
