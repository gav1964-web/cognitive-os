from __future__ import annotations

from pathlib import Path

from tools.executor_string_transform_probe import run_transform_probe


def test_executor_string_transform_probe_uses_real_identity_source(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "api.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")

    report = run_transform_probe(root=tmp_path, projects_dir=projects, limit=5, label="test")

    assert report["status"] == "ok"
    assert report["summary"]["accepted"] == 1
    assert report["summary"]["patch_reasons"] == {"contract_transform_identity_return_synthesized": 1}
    assert report["summary"]["patch_quality_levels"] == {"contract_backed_identity_transform": 1}
    assert report["summary"]["transforms"] == {"strip_lower": 1}
