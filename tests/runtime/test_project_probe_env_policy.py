from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.project_probe_env_policy import load_project_probe_env_policy


ROOT = Path(__file__).resolve().parents[2]


def test_project_probe_env_policy_loads_current_catalog() -> None:
    policy = load_project_probe_env_policy(str(ROOT / "config" / "project_probe_env_policy.json"))

    assert policy["schema_version"] == "project_probe_env_policy.v1"
    assert policy["package_to_module"]["pyyaml"] == "yaml"
    assert "pyyaml" in policy["wheel_only_native_allowlist"]
    assert "pyparsing" in policy["low_risk_allowlist"]
    assert {"cycler", "fonttools", "python-dateutil", "six"} <= set(policy["low_risk_allowlist"])
    assert {"contourpy", "kiwisolver"} <= set(policy["wheel_only_native_allowlist"])


def test_project_probe_env_policy_rejects_wheel_package_not_marked_native(tmp_path: Path) -> None:
    source = ROOT / "config" / "project_probe_env_policy.json"
    policy = json.loads(source.read_text(encoding="utf-8"))
    policy["wheel_only_native_allowlist"].append("not-native")
    target = tmp_path / "policy.json"
    target.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="subset"):
        load_project_probe_env_policy(str(target))
