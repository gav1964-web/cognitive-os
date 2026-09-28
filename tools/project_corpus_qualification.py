from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from runtime.project_corpus_qualification import qualify_project_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify a discovered corpus before full role-chain execution")
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--expected-stratum")
    parser.add_argument("--minimum-qualified", type=int)
    parser.add_argument("--label", default="project_corpus_qualification")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    projects_dir = _resolve(root, args.projects_dir)
    report = qualify_project_corpus(
        root=root,
        projects_dir=projects_dir,
        expected_stratum=args.expected_stratum,
        minimum_qualified=args.minimum_qualified,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    if args.write:
        out = root / "artifacts" / "field_trials"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"{args.label}_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ready" else 2


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
