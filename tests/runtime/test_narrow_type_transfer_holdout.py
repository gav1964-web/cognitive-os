from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runtime.project_native_failure_process import _project_digest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "narrow_type_transfer_holdout_20260908.json"


def test_transfer_holdout_is_owner_independent_and_digest_frozen() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["cases"]

    assert manifest["holdout_consumed"] is True
    assert len(cases) == 3
    assert len({case["source_owner"] for case in cases}) == len(cases)
    assert {case["project_stratum"] for case in cases} == {
        "library_pure_transform", "cli_local_tool", "framework_plugin_build"
    }
    for case in cases:
        project = ROOT / case["project_root"]
        intake = ROOT / case["failure_intake"]
        if project.is_dir():
            assert _project_digest(project) == case["frozen_project_digest"]
        if intake.is_file():
            digest = "sha256:" + hashlib.sha256(intake.read_bytes()).hexdigest()
            assert digest == case["failure_intake_digest"]


def test_transfer_holdout_has_no_preloaded_project_fix_pattern() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    searchable = list((ROOT / "knowledge").rglob("*repair_pattern*.json"))

    for case in manifest["cases"]:
        references = []
        for path in searchable:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if _contains_exact_value(payload, case["project"]):
                references.append(path)
        assert references == []


def _contains_exact_value(payload: object, expected: str) -> bool:
    if isinstance(payload, dict):
        return any(_contains_exact_value(value, expected) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_exact_value(value, expected) for value in payload)
    return payload == expected
