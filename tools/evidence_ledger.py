"""CLI for promoting and verifying content-addressed evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = _parser()
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.evidence_ledger import promote_evidence, verify_evidence_entry

    if args.command == "promote":
        result = promote_evidence(
            root=root,
            source=root / args.source,
            producer_fingerprint=args.producer,
            evaluator_fingerprint=args.evaluator,
            replay_command=args.replay,
        )
        status = "promoted"
    else:
        result = verify_evidence_entry(root=root, ledger_path=Path(args.entry))
        status = result["status"]
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status in {"promoted", "verified"} else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    promote = subparsers.add_parser("promote")
    promote.add_argument("--source", required=True)
    promote.add_argument("--producer", required=True)
    promote.add_argument("--evaluator", required=True)
    promote.add_argument("--replay", nargs=argparse.REMAINDER, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--entry", required=True)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
