"""Run local Implementer curriculum against teacher-reference artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.implementer_curriculum import run_implementer_curriculum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--curriculum-dir", default="curricula/implementer_local_3")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    curriculum_dir = Path(args.curriculum_dir)
    if not curriculum_dir.is_absolute():
        curriculum_dir = root / curriculum_dir
    report = run_implementer_curriculum(root=root, curriculum_dir=curriculum_dir.resolve(), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
