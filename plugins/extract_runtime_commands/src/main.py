"""Extract likely runtime commands from project scripts."""

from __future__ import annotations

from pathlib import Path


SCRIPT_EXTENSIONS = {".bat", ".cmd", ".ps1", ".sh"}
EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_root(str(payload["root"]))
    commands = []
    skipped = []
    for script in _iter_scripts(root):
        rel_path = script.relative_to(root).as_posix()
        if script.stat().st_size > 100_000:
            skipped.append({"path": rel_path, "reason": "too_large"})
            continue
        lines = script.read_text(encoding="utf-8", errors="ignore").splitlines()
        command_lines = [_clean_line(line) for line in lines]
        command_lines = [
            line
            for line in command_lines
            if line and not _is_comment(line, script.suffix.lower()) and not _is_shell_noise(line)
        ]
        commands.append(
            {
                "path": rel_path,
                "commands": command_lines[:30],
                "purpose": _purpose(rel_path, command_lines),
            }
        )
    return {"root": root.as_posix(), "commands": commands, "skipped": skipped}


def _purpose(path: str, lines: list[str]) -> str:
    name = Path(path).name.lower()
    joined = " ".join(lines).lower()
    if "run" in name or "python app.py" in joined:
        return "run_application"
    if "install" in name or "pip install" in joined:
        return "install_dependencies"
    if "rebuild" in name:
        return "rebuild_data"
    return "script"


def _clean_line(line: str) -> str:
    return line.strip().lstrip("@").strip()


def _is_comment(line: str, suffix: str) -> bool:
    lower = line.lower()
    if suffix in {".bat", ".cmd"}:
        return lower.startswith("rem ") or lower.startswith("::")
    return lower.startswith("#")


def _is_shell_noise(line: str) -> bool:
    lower = line.lower()
    return lower in {"echo off", "setlocal", "endlocal", "pause"} or lower.startswith("cd /d ")


def _iter_scripts(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        for item in sorted(current.iterdir(), key=lambda path: path.name.lower()):
            if item.is_dir():
                if item.name in EXCLUDED_DIRS or item.name.startswith("."):
                    continue
                stack.append(item)
            elif item.is_file() and item.suffix.lower() in SCRIPT_EXTENSIONS:
                yield item


def _resolve_scoped_root(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("extract_runtime_commands root must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("extract_runtime_commands root is outside the allowed project scope")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
