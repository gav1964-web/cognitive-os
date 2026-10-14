from __future__ import annotations

from tests.runtime.project_development_helper_extraction_helpers import *

def test_development_append_mapping_accepts_loop_local_conditional(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_rows(rows: list[str]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        normalized.append({'name': row.strip() if row.strip() else 'unknown'})\n"
        "    return normalized\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "extract_json_dumps_helper",
            target="writer.py:normalize_rows",
            allowed=[
                "extract_json_dumps_helper",
                "extract_json_loads_helper",
                "extract_splitlines_helper",
                "extract_append_mapping_helper",
            ],
        ),
        test_plan={},
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_append_mapping_helper"
    assert package["reducer_selection"]["status"] == "unique"
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def normalize_record(row):" in patched
    assert "row.strip() if row.strip() else 'unknown'" in patched


def test_development_append_mapping_rejects_external_free_variable(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_rows(rows: list[str], default_name: str) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        normalized.append({'name': row.strip() if row.strip() else default_name})\n"
        "    return normalized\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_append_mapping_helper", target="writer.py:normalize_rows"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "append_mapping_helper_pattern_not_proven"
    assert package["patches"] == []
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_append_mapping_accepts_preceding_assignment(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_rows(rows: list[str]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        record = {'name': row.strip()}\n"
        "        normalized.append(record)\n"
        "    return normalized\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "extract_json_dumps_helper",
            target="writer.py:normalize_rows",
            allowed=[
                "extract_json_dumps_helper",
                "extract_json_loads_helper",
                "extract_splitlines_helper",
                "extract_append_mapping_helper",
            ],
        ),
        test_plan={},
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_append_mapping_helper"
    assert package["patches"][0]["mapping_source"] == "preceding_assignment"
    assert package["reducer_selection"]["status"] == "unique"
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def normalize_record(row):" in patched
    assert "record = normalize_record(row)" in patched
    assert "normalized.append(record)" in patched


def test_development_append_mapping_rejects_reused_temporary(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_rows(rows: list[str]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        record = {'name': row.strip()}\n"
        "        normalized.append(record)\n"
        "        record['accepted'] = 'yes'\n"
        "    return normalized\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_append_mapping_helper", target="writer.py:normalize_rows"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "append_mapping_helper_pattern_not_proven"
    assert package["patches"] == []
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_append_mapping_accepts_configured_field_limit(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = _mapping_source(12)
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_append_mapping_helper", target="writer.py:normalize_rows"),
        test_plan={},
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_append_mapping_helper"
    assert package["patches"][0]["mapping_field_count"] == 12
    assert package["patches"][0]["mapping_source"] == "inline_append"
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_append_mapping_rejects_field_count_above_limit(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = _mapping_source(13)
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_append_mapping_helper", target="writer.py:normalize_rows"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "append_mapping_helper_pattern_not_proven"
    assert package["patches"] == []
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_append_mapping_rejects_nested_loop(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_batches(batches: list[list[str]]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for batch in batches:\n"
        "        for row in batch:\n"
        "            normalized.append({'name': row.strip()})\n"
        "    return normalized\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_append_mapping_helper", target="writer.py:normalize_batches"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "append_mapping_helper_pattern_not_proven"
    assert package["patches"] == []
    assert (project / "writer.py").read_text(encoding="utf-8") == source
