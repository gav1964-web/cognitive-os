"""Run the Stage 2 Prompt Adequacy Gate."""

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

    from runtime.prompt_adequacy import evaluate_prompt_adequacy

    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    gate = evaluate_prompt_adequacy(args.prompt).to_dict()
    print(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if gate["status"] in {"ready", "needs_clarification", "unsupported", "too_broad"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
