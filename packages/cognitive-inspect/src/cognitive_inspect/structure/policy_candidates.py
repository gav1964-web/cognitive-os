"""Detect bounded, reproducible boolean policy decisions."""

from __future__ import annotations

from typing import Any


NONDETERMINISTIC_CALL_TOKENS = ("random", "randint", "choice", "time", "datetime.now", "uuid")


def bounded_policy_candidates(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [_candidate(item) for item in functions if _is_candidate(item)]
    return sorted(rows, key=lambda row: (-_policy_score(row), str(row["path"]), str(row["name"])))[:12]


def _is_candidate(item: dict[str, Any]) -> bool:
    name = str(item.get("name") or "").lower()
    returns = str(item.get("returns") or "").lower()
    calls = " ".join(str(call).lower() for call in item.get("calls", []))
    args = [arg for arg in item.get("args", []) if str(arg.get("name") or "") not in {"self", "cls"}]
    policy_name = name.startswith(("can_", "should_", "allow_")) or "eligible" in name or name.endswith("_allowed")
    return bool(
        policy_name
        and returns in {"bool", "builtins.bool"}
        and 2 <= int(item.get("loc") or 0) <= 60
        and len(args) >= 2
        and not item.get("side_effects")
        and not any(token in calls for token in NONDETERMINISTIC_CALL_TOKENS)
    )


def _candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": item.get("path"),
        "name": item.get("name"),
        "line": item.get("line"),
        "loc": item.get("loc"),
        "args": item.get("args", []),
        "returns": item.get("returns", ""),
        "calls": item.get("calls", []),
        "side_effects": item.get("side_effects", []),
    }


def _policy_score(item: dict[str, Any]) -> int:
    typed_args = sum(bool(arg.get("annotation")) for arg in item.get("args", []))
    return 40 + min(int(item.get("loc") or 0), 30) + typed_args * 4
