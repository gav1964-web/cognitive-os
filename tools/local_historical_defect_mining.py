"""Mine fresh historical defect baselines from the existing local corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from runtime.local_historical_defect_mining import TARGET_TYPES, load_historical_mining_policy, mine_historical_defect_candidates
from runtime.local_historical_defect_evidence import inside


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus-index", help="Explicit workspace-local eligibility index")
    parser.add_argument("--project-type", action="append", choices=TARGET_TYPES)
    parser.add_argument("--scan-limit", type=int, help="Maximum local projects to inspect (1..10000)")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.scan_limit is not None and not 1 <= args.scan_limit <= 10000:
        parser.error("--scan-limit must be between 1 and 10000")
    root = Path(args.root).resolve()
    policy = dict(load_historical_mining_policy(str(root / "config" / "local_historical_defect_mining.json")))
    if args.corpus_index:
        policy["corpus_index"] = inside(root, args.corpus_index).relative_to(root).as_posix()
    if args.scan_limit is not None:
        policy["scan_limit"] = args.scan_limit
    result = mine_historical_defect_candidates(
        root=root, policy=policy, write=args.write,
        project_types=tuple(args.project_type) if args.project_type else TARGET_TYPES,
    )
    public = result["public_manifest"]
    output = {"public_manifest": public, "paths": result["paths"]}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if public["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
