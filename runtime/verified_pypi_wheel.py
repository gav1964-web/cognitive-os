"""Download and install compatible PyPI wheels with hash verification."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename
from packaging.version import InvalidVersion, Version


def install_verified_wheels(
    *, env_dir: Path, packages: list[str], resolved_versions: dict[str, str],
    policy: dict[str, Any], timeout_seconds: int,
) -> dict[str, Any]:
    if not policy.get("enabled") or not packages:
        return {"status": "skipped", "reason": "fallback_disabled_or_empty"}
    cache = env_dir.parent.parent / str(policy["cache_dir_name"])
    cache.mkdir(parents=True, exist_ok=True)
    installed = []
    try:
        for package in packages:
            normalized = _normalize(package)
            if normalized not in resolved_versions:
                raise RuntimeError(f"resolver did not expose an exact wheel version for {package}")
            metadata = _package_metadata(package, policy)
            wheel = _compatible_wheel(metadata, version=Version(resolved_versions[normalized]))
            path = _download_verified(wheel, cache, policy)
            result = subprocess.run(
                [
                    str(_pip_path(env_dir)), "install", "--disable-pip-version-check",
                    "--no-deps", "--only-binary=:all:", str(path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            if result.returncode != 0:
                return {"status": "error", "phase": "wheel_install", "stderr": result.stderr[-1200:]}
            selected_version = str(parse_wheel_filename(path.name)[1])
            actual_version = _installed_version(env_dir, package)
            if actual_version != selected_version:
                return {
                    "status": "error",
                    "phase": "wheel_install_verification",
                    "reason": f"installed {actual_version or 'unknown'} instead of {selected_version}",
                }
            installed.append({
                "package": package,
                "version": actual_version,
                "filename": path.name,
                "sha256": wheel["digests"]["sha256"],
            })
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        return {"status": "error", "phase": "verified_wheel_fallback", "reason": str(exc)}
    return {"status": "installed", "artifacts": installed}


def _package_metadata(package: str, policy: dict[str, Any]) -> dict[str, Any]:
    url = str(policy["metadata_url_template"]).format(package=package)
    with urllib.request.urlopen(url, timeout=int(policy["download_timeout_seconds"])) as response:
        return dict(json.load(response))


def resolved_wheel_versions(output: str, packages: list[str]) -> dict[str, str]:
    expected = {_normalize(package) for package in packages}
    resolved = {}
    for token in str(output or "").replace("(", " ").replace(")", " ").split():
        filename = token.rstrip(".,")
        if not filename.endswith(".whl"):
            continue
        filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        try:
            distribution, version, _, _ = parse_wheel_filename(filename)
        except ValueError:
            continue
        normalized = _normalize(str(distribution))
        if normalized in expected:
            resolved[normalized] = str(version)
    return resolved


def _compatible_wheel(
    metadata: dict[str, Any], *, version: Version | None = None,
) -> dict[str, Any]:
    supported = set(sys_tags())
    python_version = Version(platform.python_version())
    releases = []
    for raw_version, files in dict(metadata.get("releases") or {}).items():
        try:
            parsed_version = Version(str(raw_version))
        except InvalidVersion:
            continue
        if files and not parsed_version.is_prerelease:
            releases.append((parsed_version, list(files)))
    for release_version, files in sorted(releases, reverse=True):
        if version is not None and release_version != version:
            continue
        for item in files:
            row = dict(item)
            if row.get("packagetype") != "bdist_wheel":
                continue
            requires_python = str(row.get("requires_python") or "")
            if requires_python and python_version not in SpecifierSet(requires_python):
                continue
            try:
                tags = parse_wheel_filename(str(row["filename"]))[3]
            except (KeyError, ValueError):
                continue
            if supported.intersection(tags):
                return row
    raise RuntimeError("no compatible wheel found")


def _download_verified(
    wheel: dict[str, Any], cache: Path, policy: dict[str, Any],
) -> Path:
    url = str(wheel["url"])
    if urlparse(url).hostname not in set(policy["trusted_file_hosts"]):
        raise RuntimeError("wheel host is not trusted")
    destination = cache / str(wheel["filename"])
    expected = str(dict(wheel["digests"])["sha256"]).lower()
    if destination.is_file() and _sha256(destination) == expected:
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    with urllib.request.urlopen(
        request, timeout=int(policy["download_timeout_seconds"])
    ) as response:
        append = offset > 0 and getattr(response, "status", None) == 206
        with partial.open("ab" if append else "wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    if _sha256(partial) != expected:
        raise RuntimeError("wheel checksum mismatch")
    partial.replace(destination)
    return destination


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _pip_path(env_dir: Path) -> Path:
    return env_dir / ("Scripts/pip.exe" if platform.system() == "Windows" else "bin/pip")


def _installed_version(env_dir: Path, package: str) -> str:
    python = env_dir / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")
    result = subprocess.run(
        [
            str(python), "-c",
            "import importlib.metadata as m,sys;print(m.version(sys.argv[1]))",
            package,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _normalize(package: str) -> str:
    return str(package).replace("_", "-").replace(".", "-").lower()
