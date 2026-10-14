"""Audit a saved COS description and prepare bounded evidence without a model."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.description_offline_review import audit_saved_description


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source, target = Path(args.report), Path(args.output)
    if source.resolve() == target.resolve():
        parser.error('output must differ from the original report')
    try:
        report = json.loads(source.read_text(encoding='utf-8'))
        result = audit_saved_description(report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Description audit failed: {exc}', file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(target), 'status': result['review_audit']['status'],
                      'pending_reviews': len(result['review_tasks']), 'model_requests': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
