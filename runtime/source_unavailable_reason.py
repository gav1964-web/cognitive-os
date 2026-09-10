"""Classify source probe unavailability without hiding failures."""

from __future__ import annotations


def source_unavailable_reason(reason: str) -> str:
    lowered = reason.lower()
    if "no module named" in lowered:
        return "missing_dependency"
    if "packagenotfounderror" in lowered or "no package metadata" in lowered:
        return "missing_package_metadata"
    if "incompatible" in lowered or ("datetime" in lowered and "utc" in lowered):
        return "runtime_version_mismatch"
    if "syntaxerror" in lowered:
        return "context_syntax_error"
    if "didnotenable" in lowered or "is not installed" in lowered:
        return "optional_integration_dependency"
    if "cannot import name" in lowered:
        return "import_boundary_coupling"
    if "no supported app adapter" in lowered:
        return "unsupported_web_app_adapter"
    if "extensionmanager" in lowered or "object is not iterable" in lowered:
        return "plugin_loader_side_effect"
    if lowered.startswith("assertionerror"):
        return "import_time_assertion"
    if "functionnamespace" in lowered:
        return "import_time_side_effect"
    return "other"


def count_source_unavailable_reason(reasons: dict[str, int], source: dict[str, object]) -> None:
    reason = str(source.get("reason") or "")
    key = source_unavailable_reason(reason)
    reasons[key] = reasons.get(key, 0) + 1
