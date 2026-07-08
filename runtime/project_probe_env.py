"""Probe environment readiness diagnostics."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PACKAGE_TO_MODULE = {
    "pydantic-settings": "pydantic_settings",
    "python-multipart": "multipart",
    "scikit-learn": "sklearn",
}

HEAVY_OR_EXTERNAL = {"akshare", "yfinance", "tushare", "xgboost", "lightgbm", "fredapi", "mcp"}
LOW_RISK_ALLOWLIST = {
    "aiofiles",
    "aiohttp",
    "fastapi",
    "flask",
    "httpx",
    "loguru",
    "pydantic",
    "pydantic-settings",
    "python-multipart",
    "uvicorn",
}


def probe_env_readiness(project_dir: Path, behavior: dict[str, Any]) -> dict[str, Any]:
    missing = _missing_modules(behavior)
    requirements = _requirements(project_dir)
    candidates = []
    for module in missing:
        package = _package_for_module(module, requirements)
        candidates.append(
            {
                "module": module,
                "package": package,
                "declared": package in requirements,
                "installed": importlib.util.find_spec(module) is not None,
                "risk": "high" if package in HEAVY_OR_EXTERNAL else "low",
            }
        )
    blocking = [row for row in candidates if not row["installed"]]
    return {
        "status": "blocked" if blocking else "ready",
        "requirements_files": [path.as_posix() for path in project_dir.glob("requirements*.txt")],
        "declared_packages": sorted(requirements),
        "missing_modules": missing,
        "install_candidates": candidates,
        "install_plan": _install_plan(candidates, requirements),
        "policy": {
            "auto_install": False,
            "reason": "External project dependencies are diagnosed but not installed without an explicit controlled environment policy.",
        },
    }


def prepare_probe_env(*, env_dir: Path, readiness: dict[str, Any], allow_install: bool = False) -> dict[str, Any]:
    plan = dict(readiness.get("install_plan") or {})
    packages = [str(item) for item in plan.get("allowed_packages", [])]
    blocked = [str(item) for item in plan.get("blocked_packages", [])]
    if not packages:
        return {"status": "skipped", "reason": "no allowed packages", "blocked_packages": blocked}
    if not allow_install:
        return {"status": "planned", "allowed_packages": packages, "blocked_packages": blocked, "env_dir": env_dir.as_posix()}
    env_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (env_dir / "pyvenv.cfg").exists():
        created = subprocess.run([sys.executable, "-m", "venv", str(env_dir)], capture_output=True, text=True, timeout=120)
        if created.returncode != 0:
            return {"status": "error", "phase": "venv", "stderr": created.stderr[-1000:], "env_dir": env_dir.as_posix()}
    pip = _pip_path(env_dir)
    installed = subprocess.run([str(pip), "install", "--disable-pip-version-check", *packages], capture_output=True, text=True, timeout=240)
    if installed.returncode != 0:
        return {"status": "error", "phase": "pip", "stderr": installed.stderr[-1200:], "allowed_packages": packages, "env_dir": env_dir.as_posix()}
    return {"status": "prepared", "allowed_packages": packages, "blocked_packages": blocked, "env_dir": env_dir.as_posix(), "python": _python_path(env_dir).as_posix()}


def _missing_modules(behavior: dict[str, Any]) -> list[str]:
    result = []
    pattern = re.compile(r"No module named ['\"]([^'\"]+)['\"]")
    for case in behavior.get("cases", []):
        for side in ("source", "target"):
            reason = str(dict(case.get(side) or {}).get("reason") or "")
            match = pattern.search(reason)
            if match and match.group(1) not in result:
                result.append(match.group(1))
    return result


def _requirements(project_dir: Path) -> set[str]:
    packages: set[str] = set()
    for path in project_dir.glob("requirements*.txt"):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            name = _package_name(line)
            if name:
                packages.add(name)
    return packages


def _package_name(line: str) -> str:
    value = line.split("#", 1)[0].strip()
    if not value or value.startswith(("-", "git+", "http:", "https:")):
        return ""
    value = value.split("[", 1)[0]
    return re.split(r"[<>=!~; ]", value, maxsplit=1)[0].strip().lower()


def _package_for_module(module: str, requirements: set[str]) -> str:
    for package, mapped in PACKAGE_TO_MODULE.items():
        if mapped == module and package in requirements:
            return package
    normalized = module.replace("_", "-").lower()
    if normalized in requirements:
        return normalized
    if module.lower() in requirements:
        return module.lower()
    return normalized


def _install_plan(candidates: list[dict[str, Any]], requirements: set[str]) -> dict[str, Any]:
    allowed = [package for package in requirements if package in LOW_RISK_ALLOWLIST]
    blocked = []
    for row in candidates:
        package = str(row.get("package") or "")
        if row.get("installed"):
            continue
        if row.get("declared") and row.get("risk") == "low" and package in LOW_RISK_ALLOWLIST:
            allowed.append(package)
        else:
            blocked.append(package)
    return {
        "allowed_packages": sorted(set(allowed)),
        "blocked_packages": sorted(set(blocked)),
        "policy": "declared low-risk allowlist only",
    }


def _python_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _pip_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
