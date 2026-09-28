"""Run field trial prompts through the sandbox programmer route."""

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

    from runtime.sandbox_prompt_field_trial import run_sandbox_prompt_field_trial

    parser = argparse.ArgumentParser(description="Probe sandbox programmer prompt normalization.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompts-file", default=None, help="UTF-8 text file with one prompt per non-empty line.")
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    prompts = _read_prompts(Path(args.prompts_file)) if args.prompts_file else None
    report = run_sandbox_prompt_field_trial(
        root=Path(args.root).resolve(),
        prompts=prompts,
        use_model=args.use_model,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _read_prompts(path: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


if __name__ == "__main__":
    raise SystemExit(main())
