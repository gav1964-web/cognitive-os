"""Probe environment readiness diagnostics."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path
from typing import Any

from .project_probe_env_policy import (
    HEAVY_OR_EXTERNAL,
    INTERNAL_PROBE_STUBS,
    LOW_RISK_ALLOWLIST,
    NATIVE_OR_COMPILED,
    PACKAGE_COMPANIONS,
    PACKAGE_TO_MODULE,
    WHEEL_ONLY_NATIVE_ALLOWLIST,
)


def probe_env_readiness(project_dir: Path, behavior: dict[str, Any]) -> dict[str, Any]:
    missing = _dependency_modules(behavior)
    hints = _dependency_install_hints(behavior)
    requirements, dependency_files = _declared_packages(project_dir)
    candidates = []
    for module in missing:
        package = _package_for_module(module, requirements)
        candidates.append(
            {
                "module": module,
                "package": package,
                "declared": package in requirements,
                "install_hint": package in hints,
                "installed": False,
                "risk": _dependency_risk(package),
            }
        )
    known_packages = {str(row["package"]) for row in candidates}
    for package in hints:
        if package not in known_packages:
            _append_package_candidate(candidates, package, requirements)
            known_packages.add(package)
        for companion in PACKAGE_COMPANIONS.get(package, []):
            if companion not in known_packages:
                _append_package_candidate(candidates, companion, requirements)
                known_packages.add(companion)
    blocking = [row for row in candidates if not row["installed"]]
    return {
        "status": "blocked" if blocking else "ready",
        "dependency_files": dependency_files,
        "requirements_files": [path.as_posix() for path in project_dir.glob("requirements*.txt")],
        "declared_packages": sorted(requirements),
        "install_hints": sorted(hints),
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
        created = subprocess.run([sys.executable, "-m", "venv", str(env_dir)], capture_output=True, text=True, timeout=120)
        if created.returncode != 0:
            return {"status": "error", "phase": "venv", "stderr": created.stderr[-1000:], "env_dir": env_dir.as_posix()}
    pip = _pip_path(env_dir)
    try:
        installed = _install_probe_packages(pip, packages, wheel)
    except subprocess.TimeoutExpired as exc:
        stderr = (exc.stderr or b"").decode(errors="ignore") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return {"status": "error", "phase": "pip", "reason": "timeout", "stderr": stderr[-1200:], "allowed_packages": packages, "wheel_packages": wheel, "env_dir": env_dir.as_posix()}
    if installed.returncode != 0:
        return {"status": "error", "phase": "pip", "stderr": installed.stderr[-1200:], "allowed_packages": packages, "wheel_packages": wheel, "env_dir": env_dir.as_posix()}
    return {
        "status": "prepared",
        "allowed_packages": packages,
        "wheel_packages": wheel,
        "blocked_packages": blocked,
        "review_packages": review,
        "native_packages": native,
        "env_dir": env_dir.as_posix(),
        "python": _python_path(env_dir).as_posix(),
    }


def _install_probe_packages(pip: Path, packages: list[str], wheel: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.CompletedProcess([], 0, "", "")
    if packages:
        result = subprocess.run([str(pip), "install", "--disable-pip-version-check", *packages], capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            return result
    if wheel:
        result = subprocess.run(
            [str(pip), "install", "--disable-pip-version-check", "--only-binary=:all:", *wheel],
            capture_output=True,
            text=True,
            timeout=240,
        )
    return result


def _dependency_modules(behavior: dict[str, Any]) -> list[str]:
    result = []
    pattern = re.compile(r"No module named ['\"]([^'\"]+)['\"]")
    for case in behavior.get("cases", []):
        source = dict(case.get("source") or {})
        reason = str(source.get("reason") or "")
        match = pattern.search(reason)
        if match and match.group(1) not in result:
            result.append(match.group(1))
        for stub in source.get("dependency_stubs", []):
            module = str(stub)
            if module and module not in INTERNAL_PROBE_STUBS and module not in result:
                result.append(module)
    return result


def _dependency_install_hints(behavior: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    pattern = re.compile(r"\bpip\s+install\s+([A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?)")
    for case in behavior.get("cases", []):
        reason = str(dict(case.get("source") or {}).get("reason") or "")
        for match in pattern.finditer(reason):
            token = match.group(1)
            if "[" in token:
                continue
            name = _package_name(token)
            if name:
                result.add(name)
    return result


def _append_package_candidate(candidates: list[dict[str, Any]], package: str, requirements: set[str]) -> None:
    candidates.append(
        {
            "module": PACKAGE_TO_MODULE.get(package, package.replace("-", "_")),
            "package": package,
            "declared": package in requirements,
            "install_hint": True,
            "installed": False,
            "risk": _dependency_risk(package),
        }
    )


def _declared_packages(project_dir: Path) -> tuple[set[str], list[str]]:
    requirements = _requirements(project_dir)
    pyproject = _pyproject_dependencies(project_dir)
    setup_cfg = _setup_cfg_dependencies(project_dir)
    setup_py = _setup_py_dependencies(project_dir)
    files = [path.as_posix() for path in _requirement_files(project_dir)]
    if (project_dir / "pyproject.toml").exists():
        files.append((project_dir / "pyproject.toml").as_posix())
    for name in ("setup.cfg", "setup.py"):
        if (project_dir / name).exists():
            files.append((project_dir / name).as_posix())
    return requirements | pyproject | setup_cfg | setup_py, sorted(files)


def _requirements(project_dir: Path) -> set[str]:
    packages: set[str] = set()
    for path in _requirement_files(project_dir):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            name = _package_name(line)
            if name:
                packages.add(name)
    return packages


def _requirement_files(project_dir: Path) -> list[Path]:
    root_files = list(project_dir.glob("requirements*.txt"))
    nested_files = list((project_dir / "requirements").glob("*.txt")) if (project_dir / "requirements").exists() else []
    nested_root_files = list(project_dir.glob("*/requirements*.txt"))
    return sorted(set(root_files + nested_files + nested_root_files))


def _pyproject_dependencies(project_dir: Path) -> set[str]:
    path = project_dir / "pyproject.toml"
    if not path.exists():
        return set()
    packages = set()
    section = ""
    collecting = False
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            collecting = False
            continue
        starts_dependencies = section == "project" and line.startswith("dependencies")
        optional_dependencies = section == "project.optional-dependencies" and "=" in line
        if starts_dependencies or optional_dependencies:
            collecting = "[" in line and "]" not in line
            _add_dependency_strings(packages, line)
            continue
        if collecting:
            _add_dependency_strings(packages, line)
            if "]" in line:
                collecting = False
    return packages


def _setup_cfg_dependencies(project_dir: Path) -> set[str]:
    path = project_dir / "setup.cfg"
    if not path.exists():
        return set()
    parser = ConfigParser()
    parser.read(path, encoding="utf-8")
    packages: set[str] = set()
    for section in parser.sections():
        if section != "options" and not section.startswith("options."):
            continue
        for key in ("install_requires", "requires"):
            if parser.has_option(section, key):
                for line in parser.get(section, key).splitlines():
                    name = _package_name(line)
                    if name:
                        packages.add(name)
    return packages


def _setup_py_dependencies(project_dir: Path) -> set[str]:
    path = project_dir / "setup.py"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    packages: set[str] = set()
    aliases = _setup_py_dependency_aliases(text)
    fields = r"(?:install_requires|requirements|tests_require)"
    for match in re.finditer(fields + r"\s*=\s*\[([^\]]{0,4000})\]", text, flags=re.S):
        body = match.group(1)
        _add_dependency_strings(packages, body)
        for token in re.findall(r"\b[A-Za-z_]\w*\b", body):
            if token in aliases:
                packages.add(aliases[token])
    return packages


def _setup_py_dependency_aliases(text: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for match in re.finditer(r"^([A-Za-z_]\w*)\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.M):
        name = _package_name(match.group(2))
        if name:
            aliases[match.group(1)] = name
    return aliases


def _add_dependency_strings(packages: set[str], line: str) -> None:
    for match in re.finditer(r"['\"]([^'\"]+)['\"]", line):
        name = _package_name(match.group(1))
        if name:
            packages.add(name)


def _module_installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _package_name(line: str) -> str:
    value = line.split("#", 1)[0].strip()
    if not value or value.startswith(("-", "git+", "http:", "https:")):
        return ""
    value = value.split("[", 1)[0]
    return re.split(r"[<>=!~; ]", value, maxsplit=1)[0].strip().lower()


def _package_for_module(module: str, requirements: set[str]) -> str:
    if module in {"yaml", "_yaml"} and "pyyaml" in requirements:
        return "pyyaml"
    for package, mapped in PACKAGE_TO_MODULE.items():
        if mapped == module and package in requirements:
            return package
    root_module = module.split(".", 1)[0]
    for package, mapped in PACKAGE_TO_MODULE.items():
        if mapped == root_module and package in requirements:
            return package
    normalized = module.replace("_", "-").lower()
    if normalized in requirements:
        return normalized
    normalized_root = root_module.replace("_", "-").lower()
    if normalized_root in requirements:
        return normalized_root
    if module.lower() in requirements:
        return module.lower()
    if root_module.lower() in requirements:
        return root_module.lower()
    return normalized


def _dependency_risk(package: str) -> str:
    normalized = package.replace("_", "-").lower()
    if normalized in NATIVE_OR_COMPILED:
        return "native"
    if normalized in HEAVY_OR_EXTERNAL:
        return "high"
    if normalized in LOW_RISK_ALLOWLIST:
        return "low"
    return "medium"


def _install_plan(candidates: list[dict[str, Any]], requirements: set[str]) -> dict[str, Any]:
    allowed = []
    blocked = []
    review = []
    native = []
    wheel = []
    for row in candidates:
        package = str(row.get("package") or "")
        if row.get("installed"):
            continue
        risk = str(row.get("risk") or "")
        trusted = row.get("declared") or row.get("install_hint")
        if trusted and risk == "low" and package.replace("_", "-").lower() in LOW_RISK_ALLOWLIST:
            allowed.append(package)
        elif trusted and risk == "native" and package.replace("_", "-").lower() in WHEEL_ONLY_NATIVE_ALLOWLIST:
            wheel.append(package)
        elif trusted and risk == "native":
            native.append(package)
        elif trusted:
            review.append(package)
        else:
            blocked.append(package)
    return {
        "allowed_packages": sorted(set(allowed)),
        "wheel_packages": sorted(set(wheel)),
        "blocked_packages": sorted(set(blocked)),
        "review_packages": sorted(set(review)),
        "native_packages": sorted(set(native)),
        "policy": "declared low-risk dependencies install normally; selected native dependencies install wheel-only; native/heavy/unknown require review",
    }


def _python_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _pip_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
