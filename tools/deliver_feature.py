"""Recheck and optionally install a connected chain of reviewed COS patches."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.feature_delivery import deliver_feature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--checkpoint', action='append', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--corpus-receipt')
    parser.add_argument('--apply-source', action='store_true')
    args = parser.parse_args()
    result = deliver_feature(project=args.project_dir, checkpoints=args.checkpoint,
        work=args.output, python=args.python, corpus_receipt=args.corpus_receipt,
        apply_source=args.apply_source)
    print(json.dumps({k: result.get(k) for k in ('status', 'source_apply', 'installation')}, ensure_ascii=False))
    return 0 if result['status'] in ('verified', 'installed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
