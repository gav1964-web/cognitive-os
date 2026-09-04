from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit repeated mixed-effect recovery patterns")
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus", action="append")
    parser.add_argument("--max-files", type=int, default=2500)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.recovery_pattern_audit import run_recovery_pattern_audit

    corpora = args.corpus or [
        "benchmarks/project_analyzer/projects",
        "benchmarks/nasty_local_projects/projects",
        "benchmarks/github_architect_10",
        "plugins",
    ]
    report = run_recovery_pattern_audit(
        root,
        corpus_roots=[(root / item).resolve() for item in corpora],
        max_files=args.max_files,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
