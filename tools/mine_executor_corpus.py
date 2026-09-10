"""Mine executor reports for staged playbook and fixture candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.executor_corpus_miner import mine_executor_corpus, write_mining_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("reports", nargs="+")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    paths = [Path(item) if Path(item).is_absolute() else root / item for item in args.reports]
    report = mine_executor_corpus([path.resolve() for path in paths], max_candidates=args.max_candidates)
    if args.write:
        report["report_path"] = write_mining_report(report, root=root).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
