"""Classify dependencies for project-to-capability extraction."""

from __future__ import annotations

import builtins
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "dependency_extraction_policy.json"


@lru_cache(maxsize=8)
def load_dependency_extraction_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path).resolve() if path else DEFAULT_POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "dependency_extraction_policy.v1" or payload.get("status") != "active":
        raise ValueError("dependency extraction policy must use active dependency_extraction_policy.v1")
    for field_name in (
        "stdlib_inline_imports",
        "unsafe_effects",
        "unsafe_call_roots",
        "safe_bare_calls",
        "safe_call_roots",
        "bound_method_argument_names",
    ):
        value = payload.get(field_name)
        if not isinstance(value, list) or not value:
            raise ValueError(f"dependency extraction policy requires non-empty {field_name}")
    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, dict) or not recommendations.get("blocked") or not recommendations.get("self_contained"):
        raise ValueError("dependency extraction policy requires recommendations")
    return payload


def _string_set(field_name: str) -> set[str]:
    return {str(item) for item in list(_POLICY[field_name])}


_POLICY = load_dependency_extraction_policy()
STDLIB_INLINE_IMPORTS = _string_set("stdlib_inline_imports")
UNSAFE_EFFECTS = _string_set("unsafe_effects")
UNSAFE_CALL_ROOTS = _string_set("unsafe_call_roots")
SAFE_BARE_CALLS = _string_set("safe_bare_calls")
SAFE_CALL_ROOTS = _string_set("safe_call_roots")
BOUND_METHOD_ARGUMENT_NAMES = _string_set("bound_method_argument_names")
RECOMMENDATIONS = {str(key): str(value) for key, value in dict(_POLICY["recommendations"]).items()}


@dataclass(frozen=True)
class DependencyDecision:
    status: str
    inline_imports: list[str]
    unresolved_calls: list[str]
    blockers: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_dependency_policy(function: dict[str, Any], functions: dict[tuple[str, str], dict[str, Any]]) -> DependencyDecision:
    path = str(function.get("path") or "")
    local_names = {name for file_path, name in functions if file_path == path}
    builtin_names = set(dir(builtins))
    inline_imports = _stdlib_imports(function)
    unresolved = []
    blockers = []
    args = list(function.get("args", []))
    if args and str(dict(args[0]).get("name") or "") in BOUND_METHOD_ARGUMENT_NAMES:
        blockers.append("instance/class-bound method requires explicit object adapter policy")
    effects = set(str(item) for item in function.get("side_effects", []))
    for effect in sorted(effects & UNSAFE_EFFECTS):
        blockers.append(f"unsafe side effect requires explicit isolation policy: {effect}")
    for call in function.get("calls", []):
        root = str(call).split(".", 1)[0]
        if root in UNSAFE_CALL_ROOTS:
            unresolved.append(str(call))
            continue
        if not root or root in builtin_names or root in inline_imports or root in SAFE_BARE_CALLS:
            continue
        if root in SAFE_CALL_ROOTS:
            continue
        if root in local_names:
            unresolved.append(str(call))
            continue
        if "." not in str(call):
            unresolved.append(str(call))
    blockers.extend(f"unresolved local/domain call: {call}" for call in sorted(set(unresolved)))
    return DependencyDecision(
        status="blocked" if blockers else "self_contained",
        inline_imports=sorted(inline_imports),
        unresolved_calls=sorted(set(unresolved)),
        blockers=blockers,
        recommendation=RECOMMENDATIONS["blocked" if blockers else "self_contained"],
    )


def _stdlib_imports(function: dict[str, Any]) -> set[str]:
    imports = set()
    for call in function.get("calls", []):
        root = str(call).split(".", 1)[0]
        if root in STDLIB_INLINE_IMPORTS:
            imports.add(root)
    return imports
