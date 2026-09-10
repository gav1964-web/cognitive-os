"""Run a bounded sandbox implementation attempt for an unsupported prompt."""

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

    from runtime.llm_sandbox_implementation import run_llm_sandbox_implementation

    parser = argparse.ArgumentParser(description="Create a verified sandbox implementation from a bounded prompt.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    report = run_llm_sandbox_implementation(
        root=root,
        prompt=args.prompt,
        output_dir=output_dir,
        use_model=args.use_model,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"planned", "sandbox_verified", "blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
