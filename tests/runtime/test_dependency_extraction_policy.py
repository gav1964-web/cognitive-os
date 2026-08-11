from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.dependency_extraction_policy import load_dependency_extraction_policy


ROOT = Path(__file__).resolve().parents[2]


def test_dependency_extraction_policy_loads_current_catalog() -> None:
    policy = load_dependency_extraction_policy(str(ROOT / "config" / "dependency_extraction_policy.json"))

    assert "subprocess" in policy["unsafe_call_roots"]
    assert "json" in policy["stdlib_inline_imports"]
    assert policy["recommendations"]["self_contained"] == "safe to sandbox"


def test_dependency_extraction_policy_requires_recommendations(tmp_path: Path) -> None:
    source = ROOT / "config" / "dependency_extraction_policy.json"
    policy = json.loads(source.read_text(encoding="utf-8"))
    policy["recommendations"] = {}
    target = tmp_path / "policy.json"
    target.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="recommendations"):
        load_dependency_extraction_policy(str(target))
