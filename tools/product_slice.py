"""Build a Stage 3 ProductSliceSpec from a bounded prompt."""

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

    from runtime.product_slice import build_product_slice_spec

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--curriculum-dir", default="curricula/programmer_prompt_stage2")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    curriculum_dir = Path(args.curriculum_dir)
    if not curriculum_dir.is_absolute():
        curriculum_dir = root / curriculum_dir
    report = build_product_slice_spec(
        root=root,
        prompt=args.prompt,
        curriculum_dir=curriculum_dir,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
