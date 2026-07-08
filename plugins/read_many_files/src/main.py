"""Read multiple scoped text files with size and count limits."""

from __future__ import annotations

from pathlib import Path


TEXT_EXTENSIONS = {".bat", ".css", ".example", ".html", ".js", ".json", ".md", ".py", ".ps1", ".rst", ".sh", ".txt", ".toml", ".yaml", ".yml"}
EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
DISCOVERY_EXCLUDED_DIRS = {"artifacts", "generated", "reports", "scratch"}
HIGH_VALUE_NAMES = {
    ".env.example",
    "docker-compose.yml",
    "dockerfile",
    "install.bat",
    "makefile",
    "package.json",
    "pyproject.toml",
    "readme.md",
    "readme_package.md",
    "readme.rst",
    "requirements.txt",
    "run_map.bat",
    "setup.py",
}
HIGH_VALUE_PREFIXES = ("readme", "start_", "run_")


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_root(str(payload["root"]))
    paths = [str(item) for item in payload.get("paths", [])]  # type: ignore[arg-type]
    max_bytes = int(payload.get("max_bytes_per_file", 50_000))
    max_files = int(payload.get("max_files", 20))
    if not paths or bool(payload.get("auto_discover", False)):
        paths = _discover_readable_paths(root, max_files * 3)
    files = []
    skipped = []
    for rel_path in paths[:max_files]:
        try:
            path = _resolve_child(root, rel_path)
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                skipped.append({"path": rel_path, "reason": "non_text_extension"})
                continue
            size = path.stat().st_size
            if size > max_bytes:
                skipped.append({"path": rel_path, "reason": "too_large", "size_bytes": size})
                continue
            files.append(
                {
                    "path": rel_path,
                    "size_bytes": size,
                    "text": path.read_text(encoding="utf-8", errors="ignore"),
                }
            )
        except Exception as exc:
            skipped.append({"path": rel_path, "reason": type(exc).__name__})
    for rel_path in paths[max_files:]:
        skipped.append({"path": rel_path, "reason": "max_files_exceeded"})
    return {"root": root.as_posix(), "files": files, "skipped": skipped, "selected_paths": paths[:max_files]}


def _discover_readable_paths(root: Path, limit: int) -> list[str]:
    candidates = []
    for path in _iter_files(root):
        rel_path = path.relative_to(root).as_posix()
        name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix not in TEXT_EXTENSIONS and name not in HIGH_VALUE_NAMES:
            continue
        score = _candidate_score(path)
        if score < 100:
            candidates.append((score, rel_path))
    return [path for _, path in sorted(candidates)[:limit]]


def _candidate_score(path: Path) -> int:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    score = 50
    if name in HIGH_VALUE_NAMES or name.startswith(HIGH_VALUE_PREFIXES):
        score -= 40
    if name in {"pyproject.toml", "requirements.txt", "package.json", "readme.md", "readme.rst"}:
        score -= 20
    if name in {"app.py", "main.py", "server.py"}:
        score -= 15
    if path.suffix.lower() in {".bat", ".ps1", ".sh"}:
        score -= 10
    if parts & {"changes", "changelog", "downstream", "tests", "tools", "scratch", "examples", "docs"}:
        score += 25
    return score


def _iter_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        for item in sorted(current.iterdir(), key=lambda path: path.name.lower()):
            if item.is_dir():
                if item.name in EXCLUDED_DIRS or item.name in DISCOVERY_EXCLUDED_DIRS or item.name.startswith("."):
                    continue
                stack.append(item)
            elif item.is_file():
                yield item


def _resolve_scoped_root(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("read_many_files root must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("read_many_files root is outside the allowed project scope")
    return resolved


def _resolve_child(root: Path, rel_path: str) -> Path:
    relative = Path(rel_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("read_many_files paths must be root-relative")
    resolved = (root / relative).resolve()
    if not _is_relative_to(resolved, root) or not resolved.is_file():
        raise ValueError("read_many_files path is outside root or not a file")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
