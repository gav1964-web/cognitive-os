from __future__ import annotations

from pathlib import Path

from tools.executor_contract_transform_matrix_probe import run_matrix_probe


def test_executor_contract_transform_matrix_probe_runs_all_catalog_operators(tmp_path: Path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)

    report = run_matrix_probe(root=tmp_path, projects_dir=projects, label="test")

    assert report["status"] == "ok"
    assert report["summary"]["accepted"] == 12
    assert report["summary"]["transforms"]["sum_numbers"] == 1
    assert report["summary"]["transforms"]["unique_preserve_order"] == 1
