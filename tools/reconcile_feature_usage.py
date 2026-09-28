"""Derive missing usage totals from saved provider counts, preserving original ledgers."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.feature_usage import reconcile_feature_usage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ledger', 'calls', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile_feature_usage(args.ledger, args.calls, args.output), indent=2))


if __name__ == '__main__':
    main()
