"""Run the strict 9.5 foundation-role gate."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_foundation_excellence import run_role_foundation_excellence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--github-projects-dir", default="benchmarks/github_architect_10")
    parser.add_argument("--target-score", type=float, default=9.5)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    github_dir = Path(args.github_projects_dir)
    if not github_dir.is_absolute():
        github_dir = root / github_dir
    report = run_role_foundation_excellence(root=root, github_dir=github_dir.resolve(), target_score=args.target_score)
    if args.write:
        report["report_path"] = _write_report(root, report).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def _write_report(root: Path, report: dict[str, object]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_foundation_excellence_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
