from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.framework_plugin_readiness import build_framework_plugin_readiness
from runtime.self_development_prospective_detection import run_prospective_detection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--evaluation", default="artifacts/field_trials/role_project_type_evaluation_20260830T161442270918Z.json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    evaluation = json.loads((root / args.evaluation).read_text(encoding="utf-8"))
    report = build_framework_plugin_readiness(
        evaluation=evaluation, detection=run_prospective_detection(root=root, write=False)
    )
    if args.write:
        directory = root / "artifacts" / "self_development"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = directory / f"framework_plugin_readiness_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.relative_to(root).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
