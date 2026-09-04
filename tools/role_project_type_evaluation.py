"""Build a role-by-project-type maturity heatmap from field-trial reports."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_project_type_evaluation import (
    build_role_project_type_evaluation,
    render_role_project_type_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", action="append", default=[], help="Field-trial JSON report")
    parser.add_argument(
        "--baseline-evaluation",
        help="Prior evaluation whose source reports and blind flags are reused",
    )
    parser.add_argument(
        "--blind-report", action="append", default=[],
        help="Field-trial JSON report whose cases are independent blind evidence",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.report and not args.blind_report and not args.baseline_evaluation:
        parser.error("at least one report or --baseline-evaluation is required")
    root = Path(args.root).resolve()
    baseline_ordinary, baseline_blind = _baseline_sources(
        root, Path(args.baseline_evaluation) if args.baseline_evaluation else None
    )
    ordinary = [*baseline_ordinary, *[Path(value) for value in args.report]]
    blind = [*baseline_blind, *[Path(value) for value in args.blind_report]]
    blind_keys = {_source_key(root, path) for path in blind}
    all_paths = _unique_paths(root, [*ordinary, *blind])
    report = build_role_project_type_evaluation(
        root=root,
        report_paths=all_paths,
        blind_report_paths=[path for path in all_paths if _source_key(root, path) in blind_keys],
    )
    if args.write:
        report["report_path"] = _write_report(root, report).as_posix()
    if args.format == "markdown":
        print(render_role_project_type_markdown(report), end="")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _baseline_sources(root: Path, path: Path | None) -> tuple[list[Path], list[Path]]:
    if path is None:
        return [], []
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    ordinary: list[Path] = []
    blind: list[Path] = []
    for row in payload.get("sources") or []:
        if not isinstance(row, dict) or not row.get("path"):
            continue
        source = Path(str(row["path"]))
        (blind if row.get("blind") is True else ordinary).append(source)
    return ordinary, blind


def _source_key(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else root / path
    return resolved.resolve().as_posix().lower()


def _unique_paths(root: Path, paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = _source_key(root, path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _write_report(root: Path, report: dict[str, object]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_project_type_evaluation_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
