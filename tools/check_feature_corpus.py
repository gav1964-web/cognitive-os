"""Run existing corpus tests against the original and saved COS candidate copies."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.feature_corpus_checks import run_corpus_checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--input', action='append', required=True)
    parser.add_argument('--test-target', action='append', required=True)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--baseline-receipt', help='Reuse a passing same-input previous candidate as the exact current baseline')
    args = parser.parse_args()
    result = run_corpus_checks(project=args.project_dir, checkpoint=args.checkpoint,
        work=args.output, python=args.python, inputs=args.input, targets=args.test_target,
        timeout=args.timeout, baseline_receipt=args.baseline_receipt)
    print(json.dumps({'status': result['status'], 'regressions': result['regressions'],
                      'checks': {k: v['counts'] for k, v in result['checks'].items()}}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
