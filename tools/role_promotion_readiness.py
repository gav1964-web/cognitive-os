"""CLI for first-four role promotion readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_promotion_readiness import build_role_promotion_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", action="append", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = build_role_promotion_readiness(
        root,
        [Path(item) for item in args.report],
        evidence=list(args.evidence),
    )
    if args.write:
        output = _write_report(root, report)
        report["report_path"] = output.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ready_for_9_7" else 1


def _write_report(root: Path, report: dict) -> Path:
    out_dir = root / "artifacts" / "role_promotion"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "first_four_role_promotion_readiness.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
