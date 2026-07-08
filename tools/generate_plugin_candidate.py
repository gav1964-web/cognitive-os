"""Create a plugin candidate directory without registering it."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="Candidate plugin id, for example normalize_text")
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing candidate")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    candidate_id = args.id.strip()
    if not _PLUGIN_ID_RE.match(candidate_id):
        raise SystemExit("candidate id must match ^[a-z][a-z0-9_]*$")

    candidate_dir = root / "generated" / "candidates" / candidate_id
    if candidate_dir.exists() and not args.force:
        raise SystemExit(f"candidate already exists: {candidate_dir}")

    _write_candidate(candidate_dir, candidate_id)
    print(json.dumps({"status": "created", "candidate": candidate_dir.as_posix()}, ensure_ascii=False, indent=2))
    return 0


def _write_candidate(candidate_dir: Path, candidate_id: str) -> None:
    (candidate_dir / "schemas").mkdir(parents=True, exist_ok=True)
    (candidate_dir / "src").mkdir(parents=True, exist_ok=True)
    (candidate_dir / "tests").mkdir(parents=True, exist_ok=True)

    _write_json(
        candidate_dir / "plugin.json",
        {
            "id": candidate_id,
            "version": "0.1.0",
            "entrypoint": f"plugins.{candidate_id}.src.main:run",
            "determinism_grade": "C",
            "side_effects": {"filesystem": "none", "network": "none", "secrets": "none"},
            "lifecycle_status": "rebuilding",
            "version_hash": "sha256:candidate",
        },
    )
    _write_json(
        candidate_dir / "spec.json",
        {
            "id": candidate_id,
            "purpose": "Echo a string value for candidate scaffolding.",
            "input_contract": {"value": "string"},
            "output_contract": {"value": "string"},
            "error_policy": {"missing_value": "raise KeyError"},
            "side_effects": {"filesystem": "none", "network": "none", "secrets": "none"},
            "quality_gate": {
                "sample_input": {"value": "hello"},
                "expected_output": {"value": "hello"}
            },
            "reusable": True,
        },
    )
    _write_text(candidate_dir / "requirements.lock", "# no external dependencies\n")
    _write_json(
        candidate_dir / "schemas" / "input.json",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    _write_json(
        candidate_dir / "schemas" / "output.json",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    _write_text(candidate_dir / "src" / "__init__.py", f'"""{candidate_id} candidate implementation package."""\n')
    _write_text(
        candidate_dir / "src" / "main.py",
        '"""Generated candidate entrypoint. Replace behavior before promotion."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def run(payload: dict[str, object]) -> dict[str, object]:\n"
        "    return {\"value\": str(payload[\"value\"])}\n",
    )
    _write_text(
        candidate_dir / "tests" / "test_contract.py",
        "from pathlib import Path\n"
        "import sys\n\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\n"
        "from src.main import run\n\n\n"
        "def test_candidate_contract():\n"
        "    assert run({\"value\": \"hello\"}) == {\"value\": \"hello\"}\n",
    )
    _write_text(
        candidate_dir / "tests" / "test_negative.py",
        "from pathlib import Path\n"
        "import sys\n\n"
        "import pytest\n\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\n"
        "from src.main import run\n\n\n"
        "def test_candidate_rejects_missing_value():\n"
        "    with pytest.raises(KeyError):\n"
        "        run({})\n",
    )
    _write_text(
        candidate_dir / "README.md",
        f"# {candidate_id}\n\nCandidate plugin. It is not registered and cannot be used by runtime until PROMOTE.\n",
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
