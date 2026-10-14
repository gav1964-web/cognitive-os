"""Replace a literal text value inside scoped project files."""

from __future__ import annotations

from pathlib import Path


TEXT_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".ps1",
    ".rst",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_root(str(payload["root"]))
    old_value = str(payload["old_value"])
    new_value = str(payload["new_value"])
    if not old_value:
        raise ValueError("replace_text_in_project old_value must be non-empty")
    max_replacements = int(payload.get("max_replacements", 20))
    requested_paths = [str(item) for item in payload.get("paths", [])]  # type: ignore[arg-type]
    paths = _candidate_paths(root, requested_paths)
    changed_files = []
    skipped = []
    replacement_count = 0
    for path in paths:
        rel_path = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            skipped.append({"path": rel_path, "reason": type(exc).__name__})
            continue
        occurrences = text.count(old_value)
        if occurrences == 0:
            skipped.append({"path": rel_path, "reason": "old_value_not_found"})
            continue
        remaining = max_replacements - replacement_count
        if remaining <= 0:
            skipped.append({"path": rel_path, "reason": "max_replacements_reached"})
            continue
        to_replace = min(occurrences, remaining)
        updated = text.replace(old_value, new_value, to_replace)
        path.write_text(updated, encoding="utf-8")
        replacement_count += to_replace
        changed_files.append({"path": rel_path, "replacements": to_replace})
    return {
        "root": root.as_posix(),
        "old_value": old_value,
        "new_value": new_value,
        "replacement_count": replacement_count,
        "changed_files": changed_files,
        "skipped": skipped,
    }


def _candidate_paths(root: Path, requested_paths: list[str]) -> list[Path]:
    if requested_paths:
        return [_resolve_child(root, rel_path) for rel_path in requested_paths]
    return [path for path in _iter_files(root) if path.suffix.lower() in TEXT_EXTENSIONS]


def _iter_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        for item in sorted(current.iterdir(), key=lambda path: path.name.lower()):
            if item.is_dir():
                if item.name in EXCLUDED_DIRS or item.name.startswith("."):
                    continue
                stack.append(item)
            elif item.is_file():
                yield item


def _resolve_scoped_root(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("replace_text_in_project root must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("replace_text_in_project root is outside the allowed project scope")
    return resolved


def _resolve_child(root: Path, rel_path: str) -> Path:
    relative = Path(rel_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("replace_text_in_project paths must be root-relative")
    resolved = (root / relative).resolve()
    if not _is_relative_to(resolved, root) or not resolved.is_file():
        raise ValueError("replace_text_in_project path is outside root or not a file")
    if resolved.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("replace_text_in_project path must be a text file")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
