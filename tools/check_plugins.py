"""Run Level 1 plugin contract checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.plugin_loader import load_capabilities
    from tools.plugin_test_paths import resolve_plugin_test_paths, TestOwnershipError

    capabilities = load_capabilities(root)
    try:
        owners = resolve_plugin_test_paths(root, capabilities)
    except TestOwnershipError as exc:
        print(json.dumps({'status': 'failed', 'reason': str(exc),
                          'capabilities': sorted(capabilities), 'pytest_invoked': False},
                         ensure_ascii=False, indent=2))
        return 2
    test_paths = list(dict.fromkeys(str(path) for paths in owners.values() for path in paths))
    # A staged workspace can already be several levels deep. Nesting test copies
    # underneath it exceeds Windows path limits; use the caller's process temp.
    base_temp = Path(tempfile.mkdtemp(prefix="cp-"))
    process_temp = base_temp / 'process'
    process_temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"TMP": str(process_temp), "TEMP": str(process_temp), "TMPDIR": str(process_temp)})
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--import-mode=importlib", f"--confcutdir={root}",
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
        "pytest_basetemp": str(base_temp / 'tests'),
        "test_owners": {name: [p.relative_to(root).as_posix() for p in paths]
                        for name, paths in owners.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
