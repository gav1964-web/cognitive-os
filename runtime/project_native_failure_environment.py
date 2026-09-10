"""Sandbox and interpreter preparation for project-native intake."""

from __future__ import annotations

import configparser
import hashlib
import os
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any

from .project_native_failure_regression import existing_regression_targets
from .project_native_setup_identity import setup_py_distribution_name

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 controller compatibility.
    import tomli as tomllib

from .project_native_failure_process import (
    _copy_git_build_metadata,
    _copy_project,
    _git_metadata_source,
    _project_digest,
    _project_version_hint,
    _run_bounded_process,
    _slug,
    _terminate_process_tree,
)

def _prepare_local_project(project: Path, intake: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    base_python = Path(str(intake.get("interpreter_path") or sys.executable))
    if not bool(intake.get("local_editable_install", True)) or not any(
        (project / name).is_file() for name in ("pyproject.toml", "setup.py", "setup.cfg")
    ):
        return base_python, {"status": "not_required", "network_allowed": False}
    environment = project.parent / "probe_env"
    if base_python.resolve() == Path(sys.executable).resolve():
        venv.EnvBuilder(with_pip=True, system_site_packages=True, clear=True).create(environment)
    else:
        try:
            created = _run_bounded_process(
                [str(base_python), "-m", "venv", "--system-site-packages", "--clear", str(environment)],
                cwd=project,
                env=dict(os.environ),
                timeout=max(1, int(intake.get("local_install_timeout_seconds") or 90)),
            )
        except subprocess.TimeoutExpired:
            return base_python, {
                "status": "failed",
                "reason": "selected_interpreter_venv_timeout",
                "network_allowed": False,
            }
        if created.returncode != 0:
            return base_python, {
                "status": "failed",
                "exit_code": created.returncode,
                "reason": "selected_interpreter_venv_failed",
                "network_allowed": False,
                "output_tail": ((created.stdout or "") + "\n" + (created.stderr or ""))[-2000:],
            }
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _write_probe_path_bootstrap(environment, project, intake)
    env = dict(os.environ)
    env.update({
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    version_hint = str(intake.get("project_version_hint") or "")
    if version_hint:
        env["SETUPTOOLS_SCM_PRETEND_VERSION"] = version_hint
    env.update(_hermetic_user_environment(project, intake))
    if intake.get("dependency_overlay_path"):
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [
            str(intake["dependency_overlay_path"]),
            str(intake.get("tool_overlay_path") or ""),
            env.get("PYTHONPATH", ""),
        ]))
    command = [
        str(python), "-m", "pip", "install", "--no-deps", "--no-build-isolation",
        "--disable-pip-version-check", "-e", ".",
    ]
    try:
        completed = _run_bounded_process(
            command,
            cwd=project,
            env=env,
            timeout=max(1, int(intake.get("local_install_timeout_seconds") or 90)),
        )
    except subprocess.TimeoutExpired:
        return python, {"status": "failed", "reason": "local_editable_install_timeout", "network_allowed": False}
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        fallback_command = [
            str(python), "-m", "pip", "install", "--no-deps", "--no-build-isolation",
            "--disable-pip-version-check", ".",
        ]
        try:
            fallback = _run_bounded_process(
                fallback_command,
                cwd=project,
                env=env,
                timeout=max(1, int(intake.get("local_install_timeout_seconds") or 90)),
            )
        except subprocess.TimeoutExpired:
            fallback = None
        fallback_output = (
            (fallback.stdout or "") + "\n" + (fallback.stderr or "")
            if fallback is not None else "local non-editable install timed out"
        )
        if fallback is not None and fallback.returncode == 0:
            return python, {
                "status": "ready",
                "exit_code": fallback.returncode,
                "reason": "local_non_editable_install_ready",
                "network_allowed": False,
                "dependencies_installed": False,
                "project_version_hint": version_hint or None,
                "git_build_metadata_preserved": bool(intake.get("git_build_metadata_preserved")),
                "editable_install_exit_code": completed.returncode,
                "output_tail": fallback_output[-2000:],
            }
        fallback_python = python if bool(intake.get("probe_path_bootstrap", True)) else Path(sys.executable)
        return fallback_python, {
            "status": "source_path_fallback",
            "exit_code": completed.returncode,
            "reason": "local_editable_install_unavailable_source_path_used",
            "network_allowed": False,
            "dependencies_installed": False,
            "project_version_hint": version_hint or None,
            "git_build_metadata_preserved": bool(intake.get("git_build_metadata_preserved")),
            "output_tail": (output + "\nNON_EDITABLE_FALLBACK:\n" + fallback_output)[-2000:],
        }
    return python, {
        "status": "ready",
        "exit_code": completed.returncode,
        "reason": "local_editable_install_ready",
        "network_allowed": False,
        "dependencies_installed": False,
        "project_version_hint": version_hint or None,
        "git_build_metadata_preserved": bool(intake.get("git_build_metadata_preserved")),
        "output_tail": output[-2000:],
    }

def _pytest_arguments(project: Path, intake: dict[str, Any]) -> list[str]:
    raw = [str(value) for value in intake.get("pytest_arguments") or []]
    result: list[str] = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value.startswith("--basetemp="):
            configured = Path(value.split("=", 1)[1])
            target = _pytest_basetemp_target(project, configured, intake)
            result.append(f"--basetemp={target.resolve()}")
        elif value == "--basetemp" and index + 1 < len(raw):
            configured = Path(raw[index + 1])
            target = _pytest_basetemp_target(project, configured, intake)
            result.extend((value, str(target.resolve())))
            index += 1
        else:
            result.append(value)
        index += 1
    return result

def _configure_short_basetemp(root: Path, intake: dict[str, Any]) -> None:
    configured = Path(str(intake.get("short_basetemp_directory") or ".nft"))
    target = configured if configured.is_absolute() else root / configured
    target.mkdir(parents=True, exist_ok=True)
    intake["short_basetemp_path"] = str(target.resolve())

def _pytest_basetemp_target(project: Path, configured: Path, intake: dict[str, Any]) -> Path:
    if configured.is_absolute():
        return configured
    short_root = str(intake.get("short_basetemp_path") or "")
    if not short_root:
        return project.parent / configured
    identity = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(short_root) / identity

def _project_specific_intake(project: Path, intake: dict[str, Any]) -> dict[str, Any]:
    selected = dict(intake)
    identity = _project_distribution_name(project)
    project_settings = dict(intake.get("project_probe_settings") or {}).get(identity.lower()) or {}
    boolean_settings = {
        "local_editable_install",
        "probe_path_bootstrap",
    }
    applied_settings: dict[str, Any] = {
        str(key): value
        for key, value in dict(project_settings).items()
        if str(key) in boolean_settings and isinstance(value, bool)
    }
    timeout = project_settings.get("timeout_seconds")
    if isinstance(timeout, int) and 1 <= timeout <= 600:
        applied_settings["timeout_seconds"] = timeout
    if applied_settings:
        selected.update(applied_settings)
        selected["project_probe_settings_applied"] = applied_settings
    overlays = dict(intake.get("project_dependency_overlay_paths") or {})
    path = overlays.get(identity.lower()) or overlays.get(project.name.lower())
    if path:
        shared_overlay = str(selected.get("dependency_overlay_path") or "")
        selected["dependency_overlay_path"] = str(path)
        selected["dependency_overlay_identity"] = identity
        if shared_overlay and shared_overlay != str(path):
            selected["tool_overlay_path"] = shared_overlay
    project_arguments = list(
        dict(intake.get("project_pytest_arguments") or {}).get(identity.lower()) or []
    )
    if project_arguments:
        selected["pytest_arguments"] = [
            *[str(value) for value in selected.get("pytest_arguments") or []],
            *[str(value) for value in project_arguments],
        ]
        selected["project_pytest_arguments_applied"] = [
            str(value) for value in project_arguments
        ]
    regression_targets = existing_regression_targets(project, list(
        dict(intake.get("project_regression_targets") or {}).get(identity.lower()) or []
    ))
    if regression_targets:
        selected["regression_targets"] = [str(value) for value in regression_targets]
    plugins = list(dict(intake.get("project_pytest_plugins") or {}).get(identity.lower()) or [])
    if plugins:
        arguments = [str(value) for value in selected.get("pytest_arguments") or []]
        for plugin in plugins:
            plugin_name = str(plugin)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", plugin_name):
                continue
            arguments.extend(("-p", plugin_name))
        selected["pytest_arguments"] = arguments
        selected["explicit_pytest_plugins"] = [
            str(plugin) for plugin in plugins
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", str(plugin))
        ]
    nested_plugins = list(
        dict(intake.get("project_nested_pytest_plugins") or {}).get(identity.lower()) or []
    )
    if nested_plugins:
        selected["nested_pytest_plugins"] = [
            str(plugin) for plugin in nested_plugins
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", str(plugin))
        ]
    resolution = _resolve_project_interpreter(identity, intake)
    selected["interpreter_resolution"] = resolution
    if resolution.get("status") == "ready":
        selected["interpreter_path"] = str(resolution["executable"])
    return selected

from cognitive_replay.metadata import _project_distribution_name

def _resolve_project_interpreter(identity: str, intake: dict[str, Any]) -> dict[str, Any]:
    profiles = dict(intake.get("project_interpreter_profiles") or {})
    profile = dict(profiles.get(identity.lower()) or {})
    if not profile:
        return {
            "status": "ready",
            "source": "current_interpreter_default",
            "executable": str(Path(sys.executable).resolve()),
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "required": False,
        }
    major = int(profile.get("major") or 0)
    minor = int(profile.get("minor") or 0)
    for candidate in _interpreter_candidates(major, minor):
        version = _probe_python_version(candidate)
        if version and version[:2] == (major, minor):
            return {
                "status": "ready",
                "source": "configured_project_interpreter",
                "executable": str(candidate.resolve()),
                "version": ".".join(str(value) for value in version),
                "required": True,
                "requested": f"{major}.{minor}",
            }
    return {
        "status": "unavailable",
        "source": "configured_project_interpreter",
        "required": True,
        "requested": f"{major}.{minor}",
        "fallback_allowed": False,
    }

def _interpreter_candidates(major: int, minor: int) -> list[Path]:
    candidates = [Path(sys.executable)]
    for name in (f"python{major}.{minor}", f"python{major}{minor}"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Programs" / "Python" / f"Python{major}{minor}" / "python.exe"
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if candidate.is_file() and key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique

def _probe_python_version(executable: Path) -> tuple[int, int, int] | None:
    try:
        completed = _run_bounded_process(
            [str(executable), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            cwd=executable.parent,
            env=dict(os.environ),
            timeout=10,
        )
        values = tuple(int(value) for value in (completed.stdout or "").strip().split("."))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return values if completed.returncode == 0 and len(values) == 3 else None

def _write_probe_path_bootstrap(environment: Path, project: Path, intake: dict[str, Any]) -> Path | None:
    if not bool(intake.get("probe_path_bootstrap", True)):
        return None
    site_packages = environment / ("Lib/site-packages" if os.name == "nt" else "lib")
    if os.name != "nt":
        candidates = sorted(site_packages.glob("python*/site-packages"))
        if not candidates:
            return None
        site_packages = candidates[0]
    site_packages.mkdir(parents=True, exist_ok=True)
    paths = [project]
    if (project / "src").is_dir():
        paths.insert(0, project / "src")
    overlay = str(intake.get("dependency_overlay_path") or "")
    if overlay:
        paths.append(Path(overlay))
    tool_overlay = str(intake.get("tool_overlay_path") or "")
    if tool_overlay and tool_overlay != overlay:
        paths.append(Path(tool_overlay))
    serialized = ", ".join(repr(str(path.resolve())) for path in paths)
    bootstrap = site_packages / "cognitive_os_probe_paths.pth"
    bootstrap.write_text(f"import sys; sys.path[:0] = [{serialized}]\n", encoding="utf-8")
    return bootstrap

def _hermetic_user_environment(project: Path, intake: dict[str, Any]) -> dict[str, str]:
    if not bool(intake.get("hermetic_user_environment", True)):
        return {}
    home = project.parent / ".native-user"
    roaming = home / "AppData" / "Roaming"
    local = home / "AppData" / "Local"
    cache = home / ".cache"
    config = home / ".config"
    data = home / ".local" / "share"
    virtualenv_data = project.parent / ".va"
    for directory in (home, roaming, local, cache, config, data, virtualenv_data):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(roaming),
        "LOCALAPPDATA": str(local),
        "GIT_CEILING_DIRECTORIES": str(project.parent.resolve()),
        "XDG_CACHE_HOME": str(cache),
        "XDG_CONFIG_HOME": str(config),
        "XDG_DATA_HOME": str(data),
        "VIRTUALENV_OVERRIDE_APP_DATA": str(virtualenv_data),
        "VIRTUALENV_SEEDER": "pip",
        "VIRTUALENV_SYMLINK_APP_DATA": "0",
    }
