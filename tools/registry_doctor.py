"""Check Capability Registry integrity against plugin directories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    result = check_registry(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


def check_registry(root: Path) -> dict[str, object]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.plugin_loader import load_capabilities

    diagnostics: list[str] = []
    loaded = load_capabilities(root)
    registry_path = root / "registry" / "capabilities.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"capabilities": []}
    registry_by_id = {str(item["id"]): item for item in registry.get("capabilities", [])}
    for capability_id, capability in sorted(loaded.items()):
        item = registry_by_id.get(capability_id)
        if item is None:
            diagnostics.append(f"missing_registry_record:{capability_id}")
            continue
        if item.get("version_hash") != capability.version_hash:
            diagnostics.append(f"hash_drift:{capability_id}")
        if item.get("lifecycle_status") not in {"active", "degraded", "quarantined", "rebuilding", "retired"}:
            diagnostics.append(f"invalid_status:{capability_id}")
    for capability_id in sorted(set(registry_by_id) - set(loaded)):
        diagnostics.append(f"orphan_registry_record:{capability_id}")
    return {"status": "ok" if not diagnostics else "failed", "diagnostics": diagnostics}


if __name__ == "__main__":
    raise SystemExit(main())

