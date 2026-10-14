"""Static package identity; never execute setup.py."""
from __future__ import annotations
import configparser
from pathlib import Path
from .setup_identity import setup_py_distribution_name
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

def _project_distribution_name(project: Path) -> str:
    pyproject = project / "pyproject.toml"
    if pyproject.is_file():
        try:
            payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            name = str(dict(payload.get("project") or {}).get("name") or "").strip()
            if name:
                return name
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            pass
    setup_cfg = project / "setup.cfg"
    if setup_cfg.is_file():
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(setup_cfg, encoding="utf-8")
            name = parser.get("metadata", "name", fallback="").strip()
            if name:
                return name
        except (configparser.Error, OSError, UnicodeError):
            pass
    return setup_py_distribution_name(project) or project.name

