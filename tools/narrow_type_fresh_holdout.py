"""Validate a frozen narrow-role project holdout before consuming it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.narrow_type_fresh_holdout import validate_fresh_holdout_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    manifest_path = (root / args.manifest).resolve()
    manifest_path.relative_to(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = validate_fresh_holdout_manifest(root=root, manifest=manifest)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = (root / args.output).resolve()
        output.relative_to(root)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
