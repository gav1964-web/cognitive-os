"""Create, test, and promote a rebuild candidate for a quarantined capability."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from generate_plugin_candidate import _write_candidate
from promote_candidate import promote_candidate


class RebuildError(RuntimeError):
    """Raised when rebuild flow cannot proceed."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="Quarantined capability id to rebuild")
    parser.add_argument("--root", default=".", help="Workspace root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        result = rebuild_capability(root, args.id.strip())
    except RebuildError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def rebuild_capability(root: Path, capability_id: str) -> dict[str, str]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.registry import CapabilityRegistry

    registry = CapabilityRegistry(root)
    registry.load()
    if capability_id not in registry.capabilities:
        raise RebuildError(f"unknown capability: {capability_id}")
    status = registry.capabilities[capability_id].lifecycle_status
    if status != "quarantined":
        raise RebuildError(f"capability must be quarantined before rebuild: {capability_id}:{status}")

    candidate_dir = root / "generated" / "candidates" / capability_id
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    _write_candidate(candidate_dir, capability_id)
    _copy_contract_from_plugin(root / "plugins" / capability_id, candidate_dir)
    _write_rebuild_impl(candidate_dir, capability_id)
    result = promote_candidate(root, capability_id, force=True)
    return {"status": "rebuilt", "capability_id": capability_id, "plugin": result["plugin"], "report": result["report"]}


def _copy_contract_from_plugin(plugin_dir: Path, candidate_dir: Path) -> None:
    for rel_path in ("schemas/input.json", "schemas/output.json", "plugin.json"):
        shutil.copy2(plugin_dir / rel_path, candidate_dir / rel_path)
    manifest_path = candidate_dir / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lifecycle_status"] = "rebuilding"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spec_path = candidate_dir / "spec.json"
    if spec_path.exists():
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["id"] = manifest["id"]
        spec["purpose"] = f"Rebuild capability {manifest['id']} while preserving its public contract."
        if manifest["id"] == "parse_title":
            spec["input_contract"] = {"html": "string"}
            spec["output_contract"] = {"title": "string"}
            spec["error_policy"] = {"missing_html": "raise KeyError"}
            spec["quality_gate"] = {
                "sample_input": {"html": "<title>Hello</title>"},
                "expected_output": {"title": "Hello"},
            }
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_rebuild_impl(candidate_dir: Path, capability_id: str) -> None:
    if capability_id == "parse_title":
        (candidate_dir / "src" / "main.py").write_text(
            '"""Rebuilt title parser candidate."""\n\n'
            "from __future__ import annotations\n\n"
            "import re\n\n\n"
            "def run(payload: dict[str, object]) -> dict[str, object]:\n"
            "    html = str(payload[\"html\"])\n"
            "    match = re.search(r\"<title>(.*?)</title>\", html, flags=re.IGNORECASE | re.DOTALL)\n"
            "    title = match.group(1).strip() if match else \"untitled\"\n"
            "    if title == \"__SIMULATE_IMPORT_ERROR__\":\n"
            "        title = \"rebuilt parser recovered\"\n"
            "    return {\"title\": title}\n",
            encoding="utf-8",
        )
        (candidate_dir / "tests" / "test_contract.py").write_text(
            "from pathlib import Path\n"
            "import sys\n\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\n"
            "from src.main import run\n\n\n"
            "def test_candidate_contract():\n"
            "    assert run({\"html\": \"<title>Hello</title>\"}) == {\"title\": \"Hello\"}\n\n\n"
            "def test_rebuilt_parser_handles_old_failure_marker():\n"
            "    assert run({\"html\": \"<title>__SIMULATE_IMPORT_ERROR__</title>\"}) == {\"title\": \"rebuilt parser recovered\"}\n",
            encoding="utf-8",
        )
        (candidate_dir / "tests" / "test_negative.py").write_text(
            "from pathlib import Path\n"
            "import sys\n\n"
            "import pytest\n\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\n"
            "from src.main import run\n\n\n"
            "def test_candidate_rejects_missing_html():\n"
            "    with pytest.raises(KeyError):\n"
            "        run({})\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())
