"""Instantiate a memory-derived plan template through deterministic validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    root = Path(args.root).resolve()

    from runtime.memory_index import MemoryIndex
    from runtime.registry import CapabilityRegistry
    from runtime.template_instantiator import TemplateInstantiationError, plan_from_memory_template

    registry = CapabilityRegistry(root)
    registry.load()
    index = MemoryIndex(root)
    if args.rebuild:
        index.rebuild()
    memory_preflight = index.search(args.goal, limit=3)
    try:
        planned = plan_from_memory_template(args.goal, memory_preflight, registry)
    except TemplateInstantiationError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if planned is None:
        print(json.dumps({"status": "skipped", "reason": "no matching reusable template"}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(planned, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
