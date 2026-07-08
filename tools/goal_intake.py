"""Inspect user prompt intake as GoalSpec."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.goal_intake import build_goal_spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input-json", default="{}")
    args = parser.parse_args()
    root_input = json.loads(args.input_json)
    if not isinstance(root_input, dict):
        print(json.dumps({"status": "failed", "error": "--input-json must decode to object"}, ensure_ascii=False, indent=2))
        return 2
    spec = build_goal_spec(args.prompt, root_input=root_input)
    print(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
