"""Classify dependencies for project-to-capability extraction."""

from __future__ import annotations

import builtins
from dataclasses import asdict, dataclass
from typing import Any


STDLIB_INLINE_IMPORTS = {"base64", "binascii", "codecs", "hashlib", "json", "math", "re", "uuid"}
UNSAFE_EFFECTS = {"subprocess", "network", "filesystem_write", "database_side_effect", "secrets"}
UNSAFE_CALL_ROOTS = {"subprocess", "requests", "socket"}
SAFE_BARE_CALLS = {
    "join",
    "split",
    "strip",
    "lstrip",
    "rstrip",
    "lower",
    "upper",
    "replace",
    "startswith",
    "endswith",
    "items",
    "keys",
    "values",
}


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
    if args and str(dict(args[0]).get("name") or "") in {"self", "cls"}:
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
        if root in {"json", "SimpleNamespace"}:
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
        recommendation="choose a more self-contained candidate or add dependency bundling policy" if blockers else "safe to sandbox",
    )


def _stdlib_imports(function: dict[str, Any]) -> set[str]:
    imports = set()
    for call in function.get("calls", []):
        root = str(call).split(".", 1)[0]
        if root in STDLIB_INLINE_IMPORTS:
            imports.add(root)
    return imports
