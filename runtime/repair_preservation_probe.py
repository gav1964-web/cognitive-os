"""Record selected native test outcomes and bounded literal pytest parameters."""
import json
import math
import sys
from pathlib import Path


def literal(value, depth=0):
    if depth > 8:
        raise ValueError('parameter_depth')
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list and len(value) <= 64:
        return [literal(v, depth + 1) for v in value]
    if type(value) is dict and len(value) <= 64 and all(type(k) is str for k in value):
        return {k: literal(v, depth + 1) for k, v in value.items()}
    raise ValueError('nonliteral_test_parameter')


def main():
    import pytest
    project, output, arguments = sys.argv[1:]
    sys.path[:0] = [project, str(Path(project) / 'src')]
    rows, reports = [], []

    class Hooks:
        def pytest_collection_finish(self, session):
            for item in session.items:
                row = {'nodeid': item.nodeid, 'parameters': {}, 'supported': True}
                try:
                    row['parameters'] = literal(getattr(getattr(item, 'callspec', None), 'params', {}))
                    if len(json.dumps(row['parameters'], ensure_ascii=False)) > 4000:
                        raise ValueError('parameter_budget')
                except ValueError as exc:
                    row.update(supported=False, parameters={}, reason=str(exc))
                rows.append(row)

        def pytest_runtest_logreport(self, report):
            reports.append({'nodeid': report.nodeid, 'when': report.when,
                            'outcome': report.outcome, 'xfail': hasattr(report, 'wasxfail')})

    code = pytest.main(json.loads(arguments), plugins=[Hooks()])
    Path(output).write_text(json.dumps({'cases': rows, 'reports': reports}), encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
