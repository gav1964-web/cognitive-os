"""Run Level 1 plugin contract checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.plugin_loader import load_capabilities

    capabilities = load_capabilities(root)
    test_paths = [str(root / "plugins" / capability_id / "tests") for capability_id in sorted(capabilities)]
    base_temp = root / ".pytest-tmp" / ("plugins-" + uuid.uuid4().hex[:10])
    process_temp = base_temp / 'process'
    process_temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"TMP": str(process_temp), "TEMP": str(process_temp), "TMPDIR": str(process_temp)})
    result = subprocess.run(
        [sys.executable, "-m", "pytest", f"--confcutdir={root}",
         f"--basetemp={base_temp / 'tests'}", *test_paths],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    payload = {
        "status": "ok" if result.returncode == 0 else "failed",
        "capabilities": sorted(capabilities),
        "pytest_returncode": result.returncode,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
