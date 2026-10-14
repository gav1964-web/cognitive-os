"""Version hints from bounded Git metadata and project declarations."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

def _project_version_hint(project: Path) -> str | None:
    resolved = project.resolve()
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={resolved.as_posix()}",
                "-C",
                str(resolved),
                "describe",
                "--tags",
                "--exact-match",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        tag = (completed.stdout or "").strip()
        if completed.returncode == 0 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+!-]*", tag):
            return tag.removeprefix("v")
        described = subprocess.run(
            [
                "git", "-c", f"safe.directory={resolved.as_posix()}", "-C", str(resolved),
                "describe", "--tags", "--long", "--always", "HEAD",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=5, check=False,
        )
        match = re.fullmatch(
            r"v?([0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.]*)?)-(\d+)-g([0-9a-f]+)",
            (described.stdout or "").strip(),
        )
        if described.returncode == 0 and match:
            base, distance, revision = match.groups()
            return f"{base}.dev{distance}+g{revision}"
    except (OSError, subprocess.TimeoutExpired):
        pass

    pyproject = project / "pyproject.toml"
    try:
        content = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"(?m)^version\s*=\s*['\"]([^'\"]+)['\"]\s*$", content)
    if match:
        return match.group(1)
    vcs_markers = ("hatch-vcs", "[tool.setuptools_scm]", "setuptools-git-versioning")
    return "0.0.0" if any(marker in content for marker in vcs_markers) else None

