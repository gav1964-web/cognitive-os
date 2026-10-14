"""Validate a config mutation proposal without applying it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--proposal", required=True, help="Path to ConfigMutationProposal JSON")
    parser.add_argument("--write", action="store_true", help="Write sandbox report artifact")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.config_mutation_sandbox import validate_config_mutation

    report = validate_config_mutation(root=root, proposal_path=Path(args.proposal).resolve(), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
