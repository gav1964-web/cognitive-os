"""Repository-level static lint gates for source-size invariants."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


MAX_PYTHON_LINES = 400
DEFAULT_EXCLUDED_PARTS = {
    ".git",
    ".nfi",
    ".nft",
    ".pytest_cache",
    ".pytest-tmp",
    ".pytest-tmp-100",
    "__pycache__",
    "artifacts",
    "benchmarks",
    "curricula",
    "evaluation",
    "generated",
}
DEFAULT_ALLOWED_GENERATED_SUBPATHS = {
    ("generated", "specs"),
}


class RepoLintError(RuntimeError):
    """Raised when repository source violates static architecture rules."""


@dataclass(frozen=True)
class RepoLintViolation:
    path: str
    line_count: int
    limit: int
    rule: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line_count": self.line_count,
            "limit": self.limit,
            "rule": self.rule,
        }


def lint_repository(root: Path, *, max_python_lines: int = MAX_PYTHON_LINES) -> list[RepoLintViolation]:
    root = root.resolve()
    violations: list[RepoLintViolation] = []
    for path in _python_source_paths(root):
        line_count = _line_count(path)
        if line_count > max_python_lines:
            violations.append(
                RepoLintViolation(
                    path=path.relative_to(root).as_posix(),
                    line_count=line_count,
                    limit=max_python_lines,
                    rule="python_file_max_lines",
                )
            )
    return violations


def _python_source_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        dirnames[:] = [
            name
            for name in dirnames
            if not _is_excluded(root, current_path / name)
        ]
        for filename in filenames:
            if filename.endswith(".py"):
                path = current_path / filename
                if not _is_excluded(root, path):
                    paths.append(path)
    return sorted(paths)


def assert_repository_lint(root: Path, *, max_python_lines: int = MAX_PYTHON_LINES) -> None:
    violations = lint_repository(root, max_python_lines=max_python_lines)
    if violations:
        details = ", ".join(f"{item.path}:{item.line_count}" for item in violations[:5])
        raise RepoLintError(f"repository python files exceed {max_python_lines} lines: {details}")


def _is_excluded(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(part.startswith((".pytest-tmp", ".nfi", ".nft")) for part in parts):
        return True
    if any(part in DEFAULT_EXCLUDED_PARTS for part in parts):
        return not _is_allowed_generated_subpath(parts)
    return False


def _is_allowed_generated_subpath(parts: tuple[str, ...]) -> bool:
    return any(parts[: len(prefix)] == prefix for prefix in DEFAULT_ALLOWED_GENERATED_SUBPATHS)


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except FileNotFoundError:
        return 0
