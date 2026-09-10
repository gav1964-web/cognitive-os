"""Deepen approved local snapshots after a measured history shortage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from runtime.local_historical_defect_evidence import inside
from runtime.local_history_acquisition import acquire_local_history


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--per-type", type=int, default=6)
    parser.add_argument("--deepen", type=int, default=160)
    parser.add_argument("--project-type", action="append", choices=(
        "cli_local_tool", "library_pure_transform",
    ))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    manifest = json.loads(inside(root, args.manifest).read_text(encoding="utf-8"))
    report = acquire_local_history(
        root=root, manifest=manifest, per_type=args.per_type,
        deepen=args.deepen, project_types=tuple(args.project_type or ()),
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
