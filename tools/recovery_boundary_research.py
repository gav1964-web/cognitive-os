from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Researcher hypotheses for recovery boundaries")
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.recovery_boundary_research import build_recovery_boundary_research
    from runtime.recovery_pattern_audit import run_recovery_pattern_audit

    corpora = [
        root / "benchmarks" / "project_analyzer" / "projects",
        root / "benchmarks" / "nasty_local_projects" / "projects",
        root / "benchmarks" / "github_architect_10",
        root / "plugins",
    ]
    audit = run_recovery_pattern_audit(root, corpus_roots=corpora, write=args.write)
    report = build_recovery_boundary_research(audit, root=root, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
