"""Initialize evaluation corpus tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.evaluation_corpus import ensure_evaluation_corpus

    parser = argparse.ArgumentParser(description="Create evaluation task skeletons.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = ensure_evaluation_corpus(root=Path(args.root).resolve(), count=args.count, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
