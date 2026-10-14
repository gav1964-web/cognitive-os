"""Audit the local exposed corpus for transferable exception pickle defects."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_candidate_audit import audit_exception_pickle_candidates


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus-index", required=True)
    parser.add_argument("--maximum-files-per-project", type=int, default=200)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    index_path = _resolve(root, args.corpus_index)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    report = audit_exception_pickle_candidates(
        projects=list(index.get("projects") or []),
        workspace_root=root,
        maximum_files_per_project=max(1, args.maximum_files_per_project),
    )
    if args.write:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = root / "artifacts" / "project_development" / f"exception_pickle_candidate_audit_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
