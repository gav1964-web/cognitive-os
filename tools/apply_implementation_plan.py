"""Apply an ImplementationPlan into an isolated programmer-executor package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.programmer_executor import run_programmer_executor

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--test-plan", required=True)
    parser.add_argument("--run-verification", action="store_true")
    parser.add_argument("--max-commands", type=int, default=3)
    parser.add_argument("--apply-source", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = root / project_dir
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir.resolve(),
        technical_spec=_load_json(root, args.spec),
        implementation_plan=_load_json(root, args.plan),
        test_plan=_load_json(root, args.test_plan),
        run_verification=args.run_verification,
        apply_source=args.apply_source,
        max_commands=args.max_commands,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"ok", "blocked"} else 2


def _load_json(root: Path, value: str) -> dict[str, object]:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
