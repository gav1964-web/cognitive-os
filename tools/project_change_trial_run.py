"""Run a declarative project-change trial scenario."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_change_scenario import run_project_change_scenario


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = run_project_change_scenario(
        root=Path(args.root).resolve(),
        scenario_path=Path(args.scenario).resolve(),
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
