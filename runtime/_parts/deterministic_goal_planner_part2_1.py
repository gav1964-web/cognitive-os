from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _deterministic_goal_plans() -> dict[tuple[str, ...], dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / "config" / "deterministic_goal_plans.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        tuple(row["capabilities"]): dict(row["proposal"])
        for row in payload.get("plans", [])
        if isinstance(row, dict)
    }


def _proposal_for(goal: str, required_capabilities: list[str]) -> dict[str, Any] | None:
    capabilities = tuple(required_capabilities)
    if capabilities == ("translate_text",):
        return {
            "id": "deterministic_translate_text",
            "version": "0.1.0",
            "steps": [
                {
                    "id": "translate_text",
                    "capability": "translate_text",
                    "input": {"text": "$input.text", "target_language": _target_language_for_goal(goal)},
                },
            ],
            "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
        }
    return _deterministic_goal_plans().get(capabilities)
