"""List reusable plan templates derived from goal reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--min-support", type=int, default=1)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    root = Path(args.root).resolve()

    from runtime.memory_index import MemoryIndex

    index = MemoryIndex(root)
    payload = index.rebuild() if args.rebuild else index.load()
    templates = [
        template
        for template in payload.get("templates", [])
        if int(template.get("support_count", 0)) >= args.min_support
    ]
    print(json.dumps({"status": "ok", "templates": templates}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
