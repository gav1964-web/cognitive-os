"""Small result helpers shared by executable acceptance support analysis."""

from __future__ import annotations

from typing import Any

from .executable_acceptance_policy import dependency_stub_policy


def module_profile_attrs(module_profiles: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    profiles = dict(dependency_stub_policy().get("generated_module_profiles") or {})
    names = {name for values in module_profiles.values() for name in values}
    return {name: dict(dict(profiles.get(name) or {}).get("attrs") or {}) for name in names}


def unsupported(reason: str, detail: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"supported": False, "strict_negative": False, "reason": reason}
    if detail:
        result["detail"] = detail
    return result


def reason_counts(skipped: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in skipped:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return dict(sorted(counts.items()))
