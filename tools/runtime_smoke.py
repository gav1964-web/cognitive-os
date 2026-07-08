"""Run the standard Cognitive OS runtime smoke suite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    commands: list[list[str]] = []
    if not args.skip_pytest:
        commands.append([sys.executable, "-m", "pytest", "tests"])
    commands.extend(
        [
            [sys.executable, "-m", "compileall", "runtime", "tools", "plugins", "skills", "tests", "run_mvp.py"],
            [sys.executable, "tools/check_plugins.py", "--root", "."],
            [sys.executable, "tools/registry_doctor.py", "--root", "."],
            [sys.executable, "run_mvp.py", "--scenario", "happy", "--reset-registry"],
            [sys.executable, "run_mvp.py", "--scenario", "quarantine", "--reset-registry"],
            [sys.executable, "run_mvp.py", "--scenario", "happy", "--reset-registry"],
            [sys.executable, "tools/registry_doctor.py", "--root", "."],
        ]
    )
    results = []
    for command in commands:
        proc = subprocess.run(command, cwd=root, capture_output=True, text=True)
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-1000:],
                "stderr_tail": proc.stderr[-1000:],
            }
        )
        if proc.returncode != 0:
            print(json.dumps({"status": "failed", "results": results}, ensure_ascii=False, indent=2))
            return proc.returncode
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
