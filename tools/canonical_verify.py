"""Run the canonical deterministic verification scopes for Cognitive OS."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_verification(root=root, include_tests=not args.skip_tests)
    if args.write:
        path = root / "artifacts" / "verification" / "canonical_latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        report["report_path"] = path.relative_to(root).as_posix()
        encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        path.write_bytes(encoded)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_verification(*, root: Path, include_tests: bool = True) -> dict[str, Any]:
    run_id = f"v-{uuid.uuid4().hex[:8]}"
    checks = verification_commands(include_tests=include_tests, run_id=run_id)
    results = [
        _run(root=root, name=name, command=command, run_id=run_id)
        for name, command in checks
    ]
    return {
        "artifact_type": "CanonicalVerificationReport",
        "status": "ok" if all(row["status"] == "ok" for row in results) else "failed",
        "root": root.as_posix(),
        "results": results,
        "summary": {
            "checks": len(results),
            "passed": sum(row["status"] == "ok" for row in results),
            "failed": sum(row["status"] != "ok" for row in results),
        },
    }


def verification_commands(
    *, include_tests: bool = True, run_id: str = "verification-test"
) -> list[tuple[str, list[str]]]:
    commands = [
        ("registry_doctor", [sys.executable, "tools/registry_doctor.py", "--root", "."]),
        ("config_doctor", [sys.executable, "tools/config_doctor.py", "--root", "."]),
        ("repo_lint", [sys.executable, "tools/check_repo_lint.py", "--root", "."]),
        ("project_boundaries", [sys.executable, "tools/project_context.py", "--root", ".", "--check"]),
        (
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "runtime", "tools", "plugins", "tests", "packages"],
        ),
    ]
    if include_tests:
        commands.extend(
            [
                (
                    "core_tests",
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "tests",
                        "-q",
                        f"--basetemp=.pytest-tmp/{run_id}/c",
                    ],
                ),
                (
                    "package_tests",
                    [sys.executable, "-m", "pytest", "packages", "-q", "--import-mode=importlib",
                     f"--basetemp=.pytest-tmp/{run_id}/pkg"],
                ),
                (
                    "plugin_tests",
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "plugins",
                        "-q",
                        f"--basetemp=.pytest-tmp/{run_id}/p",
                    ],
                ),
            ]
        )
    return commands


def _run(*, root: Path, name: str, command: list[str], run_id: str) -> dict[str, Any]:
    temp_aliases = {
        "registry_doctor": "rd",
        "config_doctor": "cd",
        "repo_lint": "rl",
        "project_boundaries": "pb",
        "compileall": "ca",
        "core_tests": "ct",
        "plugin_tests": "pt",
        "package_tests": "pkg",
    }
    temp_dir = root / ".pytest-tmp" / run_id / temp_aliases[name]
    temp_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"TMP": str(temp_dir), "TEMP": str(temp_dir), "TMPDIR": str(temp_dir)})
    completed = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "name": name,
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "command": command,
        "stdout_tail": completed.stdout[-1600:],
        "stderr_tail": completed.stderr[-1600:],
    }


if __name__ == "__main__":
    raise SystemExit(main())
