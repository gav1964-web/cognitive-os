"""Create a safe first extraction proposal from a Python project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.extraction_proposal import build_extraction_proposal, write_extraction_proposal
from runtime.project_benchmark import analyze_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-spec", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = (root / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    outputs = analyze_project(project_dir)
    proposal = build_extraction_proposal(
        project_dir=project_dir,
        analyzer_outputs=outputs,
        write_spec=args.write_spec,
        root=root,
    )
    if args.write:
        proposal["proposal_path"] = write_extraction_proposal(root, proposal).as_posix()
    print(json.dumps(proposal, ensure_ascii=False, indent=2))
    return 0 if proposal.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
