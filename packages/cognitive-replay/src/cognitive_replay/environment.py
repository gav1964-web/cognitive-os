"""Prepare isolated qualification environments from digest-bound local wheels."""

from __future__ import annotations

import json
import platform
import re
import sys
from pathlib import Path
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename

from .process import isolated_environment, run_command
from .evidence import evidence_digest, file_digest, inside
from .metadata import _project_distribution_name, tomllib


SCHEMA = "historical_defect_environment.v1"


def freeze_environment_profile(
    *, root: Path, wheels: list[Path], pytest_plugins: list[str] | None = None,
) -> dict[str, Any]:
    base = root.resolve()
    rows = []
    for path in sorted(wheels):
        wheel = inside(base, str(path.resolve()))
        name, version, _build, _tags = parse_wheel_filename(wheel.name)
        rows.append({"name": str(name), "version": str(version),
                     "path": wheel.relative_to(base).as_posix(), "sha256": file_digest(wheel)})
    profile = {"schema_version": SCHEMA, "python_version": platform.python_version(),
               "wheels": rows, "pytest_plugins": list(pytest_plugins or [])}
    profile["profile_digest"] = evidence_digest(profile)
    validate_environment_profile(base, profile)
    return profile


def validate_environment_profile(root: Path, profile: dict[str, Any]) -> None:
    if profile.get("schema_version") != SCHEMA:
        raise ValueError("qualification environment profile required")
    body = {key: value for key, value in profile.items() if key != "profile_digest"}
    if evidence_digest(body) != profile.get("profile_digest"):
        raise ValueError("qualification environment profile digest mismatch")
    if profile.get("python_version") != platform.python_version():
        raise ValueError("qualification Python version differs from frozen environment")
    rows = profile.get("wheels") or []
    if not 1 <= len(rows) <= 100:
        raise ValueError("qualification wheel count is outside bounded limits")
    names = []
    for row in rows:
        path = inside(root, str(row["path"]))
        name, version, _build, _tags = parse_wheel_filename(path.name)
        if str(name) != row.get("name") or str(version) != row.get("version"):
            raise ValueError("qualification wheel identity mismatch")
        if file_digest(path) != row.get("sha256"):
            raise ValueError("qualification wheel digest mismatch")
        names.append(str(name))
    if "pytest" not in names or len(names) != len(set(names)):
        raise ValueError("qualification wheels require pytest and unique distributions")
    if any(not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", value)
           for value in profile.get("pytest_plugins") or []):
        raise ValueError("qualification pytest plugin name is invalid")


def prepare_environment(
    *, root: Path, project: Path, directory: Path,
    profile: dict[str, Any], timeout: int,
) -> tuple[Path, dict[str, Any]]:
    validate_environment_profile(root, profile)
    _check_project_python(project)
    project_name = canonicalize_name(_project_distribution_name(project))
    if any(row["name"] == project_name for row in profile["wheels"]):
        raise ValueError("qualification environment must not install the project under test")
    directory.mkdir(parents=True, exist_ok=False)
    python = directory / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    env = isolated_environment(directory / "tmp", python)
    _require_success(run_command(
        [sys.executable, "-I", "-m", "venv", "--without-pip", str(directory / "venv")],
        cwd=directory, env=env, timeout=timeout,
    ), "qualification venv creation")
    staged = directory / "wheels"
    staged.mkdir()
    paths = []
    for row in profile["wheels"]:
        original = inside(root, str(row["path"]))
        copied = staged / original.name
        copied.write_bytes(original.read_bytes())
        if file_digest(copied) != row["sha256"]:
            raise ValueError("qualification wheel changed while staging")
        paths.append(str(copied))
    pip = [sys.executable, "-I", "-m", "pip", "--isolated", "--python", str(python)]
    _require_success(run_command(
        [*pip, "install", "--no-index", "--no-deps", "--no-compile", "--no-cache-dir",
         "--disable-pip-version-check", *paths],
        cwd=directory, env=env, timeout=timeout,
    ), "qualification offline wheel install")
    _require_success(run_command([*pip, "check"], cwd=directory, env=env, timeout=timeout),
                     "qualification dependency closure")
    inventory_run = run_command(
        [str(python), "-I", "-c",
         "import importlib.metadata as m,json,sys,site; "
         "print(json.dumps({'packages':{d.metadata['Name']:d.version for d in m.distributions()},"
         "'isolated':sys.prefix!=sys.base_prefix and not site.ENABLE_USER_SITE}))"],
        cwd=directory, env=env, timeout=timeout,
    )
    _require_success(inventory_run, "qualification environment inventory")
    inventory = json.loads(inventory_run["stdout"])
    installed = {canonicalize_name(name): version for name, version in inventory["packages"].items()}
    expected = {row["name"]: row["version"] for row in profile["wheels"]}
    if installed != expected or inventory.get("isolated") is not True:
        raise ValueError("qualification installed environment differs from frozen wheels")
    receipt = {"status": "ready", "kind": "isolated_venv", "network_install": False,
               "python_version": profile["python_version"], "packages": installed,
               "profile_digest": profile["profile_digest"], "dependency_check": "passed"}
    receipt["environment_digest"] = evidence_digest(receipt)
    return python, receipt


def _check_project_python(project: Path) -> None:
    path = project / "pyproject.toml"
    if path.is_file():
        metadata = tomllib.loads(path.read_text(encoding="utf-8"))
        required = str(metadata.get("project", {}).get("requires-python") or "")
        if required and platform.python_version() not in SpecifierSet(required):
            raise ValueError(f"project_requires_python:{required};available:{platform.python_version()}")


def _require_success(run: dict[str, Any], action: str) -> None:
    if run["returncode"] != 0:
        detail = (str(run.get("stdout") or "") + " " + str(run.get("stderr") or ""))[-1000:]
        raise ValueError(f"{action} failed:{detail}")
