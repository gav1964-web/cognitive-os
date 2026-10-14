"""Minimize an explicit data fixture while preserving repeated selected test failures."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.failure_input_reduction import reduce_failure_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--test-target', action='append', required=True)
    parser.add_argument('--max-attempts', type=int, default=24)
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--pytest-plugin', action='append', default=[])
    args = parser.parse_args()
    report = reduce_failure_fixture(Path(args.project), fixture=args.fixture, tests=args.test_target,
                                     max_attempts=args.max_attempts, timeout=args.timeout,
                                     pytest_plugins=args.pytest_plugin)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'reduced' else 1


if __name__ == '__main__':
    raise SystemExit(main())
