"""Apply a configured deterministic project change recipe."""

from __future__ import annotations

from pathlib import Path

from runtime.project_change_recipes import get_project_change_recipe


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_root(str(payload["root"]))
    recipe_id = str(payload["recipe_id"])
    recipe = get_project_change_recipe(recipe_id)
    changed_files = []
    skipped = []
    replacement_count = 0
    for rel_path, replacements in dict(recipe.get("files") or {}).items():
        path = _resolve_child(root, rel_path)
        text = path.read_text(encoding="utf-8")
        original = text
        file_count = 0
        for replacement in replacements:
            old = str(dict(replacement).get("old") or "")
            new = str(dict(replacement).get("new") or "")
            if old not in text:
                if new in text:
                    skipped.append({"path": rel_path, "reason": "already_applied"})
                    continue
                raise ValueError(f"expected snippet not found: {rel_path}")
            text = text.replace(old, new, 1)
            file_count += 1
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed_files.append({"path": rel_path, "replacements": file_count})
            replacement_count += file_count
    return {
        "root": root.as_posix(),
        "changed_files": changed_files,
        "skipped": skipped,
        "replacement_count": replacement_count,
        "contract": str(recipe.get("contract") or recipe_id),
    }


def _resolve_scoped_root(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("root must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("root is outside the allowed project scope")
    return resolved


def _resolve_child(root: Path, rel_path: str) -> Path:
    relative = Path(rel_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("paths must be root-relative")
    resolved = (root / relative).resolve()
    if not _is_relative_to(resolved, root) or not resolved.is_file():
        raise ValueError("path is outside root or not a file")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
