"""Run a source-project rebuild trial into a generated project scaffold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.project_rebuild import run_project_rebuild_trial
    from runtime.project_probe_env import prepare_probe_env

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prepare-probe-env", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    source_dir = Path(args.source_dir)
    if not source_dir.is_absolute():
        source_dir = root / source_dir
    output_dir = Path(args.output_dir) if args.output_dir else root / "artifacts" / "rebuild_projects" / f"{source_dir.name}_x"
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    result = run_project_rebuild_trial(
        root=root,
        source_dir=source_dir.resolve(),
        output_dir=output_dir.resolve(),
        force=args.force,
    )
    if args.prepare_probe_env:
        prepared = prepare_probe_env(
            env_dir=root / "artifacts" / "probe_envs" / source_dir.name,
            readiness=dict(dict(result.get("comparison", {})).get("probe_env", {})),
            allow_install=True,
        )
        result["probe_env_prepare"] = prepared
        if prepared.get("status") == "prepared" and prepared.get("python"):
            result = run_project_rebuild_trial(
                root=root,
                source_dir=source_dir.resolve(),
                output_dir=output_dir.resolve(),
                force=True,
                source_python=Path(str(prepared["python"])),
            )
            result["probe_env_prepare"] = prepared
            result["probe_env_rerun"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"ok", "needs_work"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
