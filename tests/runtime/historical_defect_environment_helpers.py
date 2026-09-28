"""Offline test wheels reconstructed from the installed pytest dependencies."""

from __future__ import annotations

import importlib.metadata as metadata
import io
import zipfile
from functools import lru_cache
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from runtime.historical_defect_environment import freeze_environment_profile
from runtime.local_historical_defect_evidence import evidence_digest


@lru_cache(maxsize=1)
def pytest_wheel_bytes() -> tuple[tuple[str, bytes], ...]:
    pending, seen, wheels = ["pytest"], set(), []
    while pending:
        name = canonicalize_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        dist = metadata.distribution(name)
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in dist.files or []:
                if ".." not in item.parts and "__pycache__" not in item.parts:
                    path = Path(dist.locate_file(item))
                    if path.is_file():
                        archive.write(path, str(item).replace("\\", "/"))
        filename = f"{name.replace('-', '_')}-{dist.version}-py3-none-any.whl"
        wheels.append((filename, buffer.getvalue()))
    return tuple(wheels)


def test_environment_profile(root: Path) -> dict:
    directory = root / ".wheels"
    directory.mkdir(exist_ok=True)
    paths = []
    for name, data in pytest_wheel_bytes():
        path = directory / name
        path.write_bytes(data)
        paths.append(path)
    return freeze_environment_profile(root=root, wheels=paths)


def environment_bundle(root: Path, public: dict) -> dict:
    profile = test_environment_profile(root)
    bundle = {
        "schema_version": "historical_defect_environment_bundle.v1",
        "public_manifest_digest": public["manifest_digest"],
        "profiles": {row["candidate_id"]: profile for row in public["cases"]},
    }
    bundle["bundle_digest"] = evidence_digest(bundle)
    return bundle
