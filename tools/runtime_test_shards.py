"""Run runtime pytest suite in deterministic shards."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--shard", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.shards < 1:
        raise SystemExit("--shards must be >= 1")
    report = run_shards(root=root, shard_count=args.shards, only_shard=args.shard)
    if args.write:
        report.update(write_report(root, report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_shards(*, root: Path, shard_count: int, only_shard: int | None = None) -> dict[str, Any]:
    tests = collect_tests(root)
    selected = [_run_shard(root, index, shard_count, _shard_tests(tests, index, shard_count)) for index in _indexes(shard_count, only_shard)]
    return {
        "artifact_type": "RuntimeTestShardReport",
        "status": "ok" if selected and all(row["status"] == "ok" for row in selected) else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": root.as_posix(),
        "total_collected": len(tests),
        "shard_count": shard_count,
        "selected_shards": selected,
        "summary": {
            "passed_shards": sum(row["status"] == "ok" for row in selected),
            "failed_shards": sum(row["status"] != "ok" for row in selected),
            "selected_tests": sum(row["test_count"] for row in selected),
        },
    }


def collect_tests(root: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/runtime", "--collect-only", "-q"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-2000:] + result.stderr[-2000:])
    return sorted(line.strip() for line in result.stdout.splitlines() if "::" in line)


def write_report(root: Path, report: dict[str, Any]) -> dict[str, str]:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"runtime_test_shards_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _run_shard(root: Path, index: int, shard_count: int, tests: list[str]) -> dict[str, Any]:
    if not tests:
        return {"shard": index, "status": "ok", "test_count": 0, "returncode": 0}
    base_temp = root / ".pytest-tmp" / f"runtime-shard-{index}"
    base_temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"TMP": str(base_temp), "TEMP": str(base_temp), "TMPDIR": str(base_temp)})
    result = subprocess.run(
        [sys.executable, "-m", "pytest", f"--basetemp={base_temp}", "-q", *tests],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return {
        "shard": index,
        "status": "ok" if result.returncode == 0 else "failed",
        "test_count": len(tests),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def _shard_tests(tests: list[str], index: int, shard_count: int) -> list[str]:
    return [test for position, test in enumerate(tests) if position % shard_count == index]


def _indexes(shard_count: int, only_shard: int | None) -> list[int]:
    if only_shard is None:
        return list(range(shard_count))
    if only_shard < 0 or only_shard >= shard_count:
        raise SystemExit("--shard must be between 0 and --shards - 1")
    return [only_shard]


if __name__ == "__main__":
    raise SystemExit(main())
