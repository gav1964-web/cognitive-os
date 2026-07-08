"""Generate a typed capability spec skeleton."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not _PLUGIN_ID_RE.match(args.id):
        raise SystemExit("spec id must match ^[a-z][a-z0-9_]*$")
    root = Path(args.root).resolve()
    path = root / "generated" / "specs" / f"{args.id}.json"
    if path.exists() and not args.force:
        raise SystemExit(f"spec already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = {
        "id": args.id,
        "purpose": args.purpose,
        "input_contract": {"value": "string"},
        "output_contract": {"value": "string"},
        "error_policy": {"missing_value": "raise KeyError"},
        "side_effects": {"filesystem": "none", "network": "none", "secrets": "none"},
        "quality_gate": {"sample_input": {"value": "hello"}, "expected_output": {"value": "hello"}},
        "reusable": True,
    }
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "spec": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
