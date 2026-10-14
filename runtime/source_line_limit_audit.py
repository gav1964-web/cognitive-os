"""Repo-level Python source line-limit audit."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 400
SOURCE_ROOTS = ("runtime", "tools", "plugins", "tests")
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "artifacts",
    "generated",
}


def run_source_line_limit_audit(
    *,
    root: Path,
    line_limit: int = DEFAULT_LIMIT,
    source_roots: tuple[str, ...] = SOURCE_ROOTS,
) -> dict[str, Any]:
    root = root.resolve()
    violations = []
    scanned_count = 0
    for file_path in _iter_python_files(root, source_roots):
        scanned_count += 1
        line_count = _line_count(file_path)
        if line_count <= line_limit:
            continue
        relative = file_path.relative_to(root).as_posix()
        violations.append({
            "path": relative,
            "line_count": line_count,
            "over_by": line_count - line_limit,
            "source_root": relative.split("/", 1)[0],
            "suggested_action": _suggested_action(relative),
        })
    violations.sort(key=lambda row: (-int(row["over_by"]), str(row["path"])))
    by_root = Counter(str(row["source_root"]) for row in violations)
    return {
        "artifact_type": "SourceLineLimitAudit",
        "schema_version": "source_line_limit_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if violations else "passed",
        "line_limit": line_limit,
        "source_roots": list(source_roots),
        "scanned_python_file_count": scanned_count,
        "violation_count": len(violations),
        "violation_summary_by_root": dict(sorted(by_root.items())),
        "top_violations": violations[:25],
        "violations": violations,
        "source_apply": False,
        "kb_promotion": False,
    }


def _iter_python_files(root: Path, source_roots: tuple[str, ...]):
    for source_root in source_roots:
        base = root / source_root
        if not base.exists():
            continue
        if base.is_file() and base.suffix == ".py":
            yield base
            continue
        for path in base.rglob("*.py"):
            if _is_source_file(path.relative_to(base)):
                yield path


def _is_source_file(path: Path) -> bool:
    return not any(part in EXCLUDED_PARTS or part.startswith(".pytest-tmp") for part in path.parts)


def _line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except UnicodeDecodeError:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)


def _suggested_action(relative_path: str) -> str:
    if relative_path.startswith("tests/"):
        return "split test scenarios by runtime component or behavior"
    if relative_path.startswith("tools/"):
        return "move reusable logic into runtime module and keep CLI thin"
    if relative_path.startswith("plugins/"):
        return "split capability implementation under plugin src package"
    if relative_path.startswith("runtime/_parts/"):
        return "split part module again or move templates into template assets"
    return "extract cohesive helpers into runtime submodules"
