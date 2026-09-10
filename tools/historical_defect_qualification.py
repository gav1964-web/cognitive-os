"""Qualify public historical defect candidates against a sealed oracle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from runtime.historical_defect_qualification import (
    qualify_historical_defects,
    read_qualification_inputs,
)
from runtime.local_historical_defect_evidence import inside


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--public", required=True)
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--environments", required=True, help="Frozen per-case environment bundle")
    parser.add_argument("--timeout", type=int, default=180, help="Deadline in seconds for each subprocess")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    public, oracle = read_qualification_inputs(root, args.public, args.oracle)
    environments = json.loads(inside(root, args.environments).read_text(encoding="utf-8"))
    result = qualify_historical_defects(
        root=root, public=public, oracle=oracle, timeout=args.timeout, write=args.write,
        environments=environments,
    )
    output = {"public_receipt": result["public_receipt"], "paths": result["paths"]}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["public_receipt"]["status"] == "ready_for_role_evaluation" else 2


if __name__ == "__main__":
    raise SystemExit(main())
