"""Collect GitHub repository-search evidence as a KnowledgeArtifact."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.knowledge import github_repository_knowledge


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--query", default="python xlsx csv conversion")
    parser.add_argument("--needed-for", default="spreadsheet conversion design")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        report = github_repository_knowledge(args.query, needed_for=args.needed_for, limit=args.limit)
    except Exception as exc:
        report = {"status": "failed", "error": str(exc), "query": args.query}
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    if args.write:
        path = _write_report(root, report)
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "no_results"} else 1


def _write_report(root: Path, report: dict[str, object]) -> Path:
    out_dir = root / "artifacts" / "knowledge"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"github_knowledge_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
