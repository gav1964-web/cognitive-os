from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the no-safe-candidate recovery field trial")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--project",
        default="benchmarks/project_analyzer/projects/legacy_script_dump",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.no_safe_candidate_recovery_field_trial import (
        run_no_safe_candidate_recovery_field_trial,
    )

    report = run_no_safe_candidate_recovery_field_trial(
        root,
        project_dir=(root / args.project).resolve(),
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
