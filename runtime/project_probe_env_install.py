"""Prepare an isolated environment from an approved dependency plan."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .project_probe_env_policy import load_project_probe_env_policy
from .verified_pypi_wheel import install_verified_wheels, resolved_wheel_versions


def prepare_probe_env(
    *, env_dir: Path, readiness: dict[str, Any], allow_install: bool = False,
    install_timeout_seconds: int = 240, prefer_binary: bool = False,
) -> dict[str, Any]:
    plan = dict(readiness.get("install_plan") or {})
    packages = [str(item) for item in plan.get("allowed_packages", [])]
    blocked = [str(item) for item in plan.get("blocked_packages", [])]
    review = [str(item) for item in plan.get("review_packages", [])]
    native = [str(item) for item in plan.get("native_packages", [])]
    wheel = [str(item) for item in plan.get("wheel_packages", [])]
    if not packages and not wheel:
        return {
            "status": "skipped",
            "reason": "no allowed packages",
            "blocked_packages": blocked,
            "review_packages": review,
            "native_packages": native,
            "wheel_packages": wheel,
        }
    if not allow_install:
        return {
            "status": "planned",
            "allowed_packages": packages,
            "wheel_packages": wheel,
            "blocked_packages": blocked,
            "review_packages": review,
            "native_packages": native,
            "env_dir": env_dir.as_posix(),
        }
    env_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (env_dir / "pyvenv.cfg").exists():
        created = subprocess.run(
            [sys.executable, "-m", "venv", str(env_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if created.returncode != 0:
            return {
                "status": "error",
                "phase": "venv",
                "stderr": created.stderr[-1000:],
                "env_dir": env_dir.as_posix(),
            }
    already_installed = _installed_package_names(env_dir)
    pending_packages = [item for item in packages if _normalize(item) not in already_installed]
    pending_wheel = [item for item in wheel if _normalize(item) not in already_installed]
    pip = _pip_path(env_dir)
    try:
        installed = _install_probe_packages(
            pip,
            pending_packages,
            pending_wheel,
            timeout_seconds=install_timeout_seconds,
            prefer_binary=prefer_binary,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        stdout = _timeout_text(exc.stdout)
        fallback = install_verified_wheels(
            env_dir=env_dir,
            packages=pending_packages + pending_wheel,
            resolved_versions=resolved_wheel_versions(
                stdout, pending_packages + pending_wheel,
            ),
            policy=dict(load_project_probe_env_policy()["verified_wheel_fallback"]),
            timeout_seconds=install_timeout_seconds,
        )
        if fallback.get("status") == "installed":
            return {
                "status": "prepared",
                "allowed_packages": packages,
                "wheel_packages": wheel,
                "blocked_packages": blocked,
                "review_packages": review,
                "native_packages": native,
                "already_installed": sorted(
                    item for item in packages + wheel if _normalize(item) in already_installed
                ),
                "installer": "verified_pypi_wheel_fallback",
                "verified_wheels": list(fallback.get("artifacts") or []),
                "env_dir": env_dir.as_posix(),
                "python": _python_path(env_dir).as_posix(),
            }
        return {
            "status": "error",
            "phase": "pip",
            "reason": "timeout",
            "stdout": stdout[-1200:],
            "stderr": stderr[-1200:],
            "allowed_packages": packages,
            "wheel_packages": wheel,
            "env_dir": env_dir.as_posix(),
            "fallback_result": fallback,
        }
    if installed.returncode != 0:
        return {
            "status": "error",
            "phase": "pip",
            "stderr": installed.stderr[-1200:],
            "allowed_packages": packages,
            "wheel_packages": wheel,
            "env_dir": env_dir.as_posix(),
        }
    return {
        "status": "prepared",
        "allowed_packages": packages,
        "wheel_packages": wheel,
        "blocked_packages": blocked,
        "review_packages": review,
        "native_packages": native,
        "already_installed": sorted(
            item for item in packages + wheel if _normalize(item) in already_installed
        ),
        "env_dir": env_dir.as_posix(),
        "python": _python_path(env_dir).as_posix(),
    }


def _install_probe_packages(
    pip: Path, packages: list[str], wheel: list[str], *,
    timeout_seconds: int, prefer_binary: bool,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.CompletedProcess([], 0, "", "")
    if packages:
        binary_args = ["--prefer-binary"] if prefer_binary else []
        result = subprocess.run(
            [str(pip), "install", "--disable-pip-version-check", "--no-deps", *binary_args, *packages],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            return result
    if wheel:
        result = subprocess.run(
            [str(pip), "install", "--disable-pip-version-check", "--no-deps", "--only-binary=:all:", *wheel],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    return result


def _timeout_text(value: str | bytes | None) -> str:
    return value.decode(errors="ignore") if isinstance(value, bytes) else str(value or "")


def _installed_package_names(env_dir: Path) -> set[str]:
    python = _python_path(env_dir)
    if not python.is_file():
        return set()
    script = (
        "import importlib.metadata as m,json;"
        "print(json.dumps([d.metadata['Name'] for d in m.distributions() if d.metadata['Name']]))"
    )
    result = subprocess.run(
        [str(python), "-c", script], capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return set()
    try:
        return {_normalize(item) for item in json.loads(result.stdout)}
    except (json.JSONDecodeError, TypeError):
        return set()


def _normalize(package: str) -> str:
    return str(package).replace("_", "-").replace(".", "-").lower()


def _python_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _pip_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
