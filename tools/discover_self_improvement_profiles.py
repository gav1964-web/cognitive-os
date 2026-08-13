"""Discover evidence-supported self-improvement profile candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_improvement_contract_profile import discover_contract_profile_candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--limit-projects", type=int, default=100)
    parser.add_argument("--limit-candidates", type=int, default=20)
    parser.add_argument("--max-files", type=int, default=800)
    args = parser.parse_args()
    corpus = Path(args.corpus).resolve()
    projects_root = corpus / "src" if (corpus / "src").is_dir() else corpus
    rows = []
    for project in sorted(path for path in projects_root.iterdir() if path.is_dir())[: args.limit_projects]:
        candidates = discover_contract_profile_candidates(
            project, limit=args.limit_candidates, max_files=args.max_files
        )
        if candidates:
            rows.append({"project": project.name, "project_dir": project.as_posix(), "candidates": candidates})
    print(json.dumps({
        "corpus": corpus.as_posix(),
        "projects": rows,
        "scan_policy": {"max_files_per_project": args.max_files, "max_candidates_per_project": args.limit_candidates},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
