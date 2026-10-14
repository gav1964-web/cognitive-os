from __future__ import annotations

import importlib


def test_high_risk_tool_facades_load_without_owned_symbol_collisions():
    github = importlib.import_module("tools.github_full_chain_probe")
    executor = importlib.import_module("tools.executor_profile_safe_role_probe")

    assert github._SPLIT_COLLISIONS == []
    assert executor._SPLIT_COLLISIONS == []
    assert callable(github.run_probe)
    assert callable(executor.run_profile_safe_role_probe)
