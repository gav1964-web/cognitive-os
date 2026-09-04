from __future__ import annotations

from tests.runtime.project_development_helper_extraction_helpers import *

def test_mixed_responsibility_uses_concrete_json_extraction_reducer():
    policy = load_project_development_policy()
    transform = development_delta_transform(
        {
            "selected_issue": {"rule_id": "mixed_responsibility"},
            "selected_option": {"option_id": "OPT-JSON"},
        },
        policy,
    )

    result = transform({
        "artifact_type": "ImplementationPlan",
        "implementation_delta": {"status": "semantic_synthesis_required"},
    })

    assert result["implementation_delta"]["intent"]["operator_id"] == "extract_json_dumps_helper"
    assert result["implementation_delta"]["intent"]["allowed_operator_ids"] == [
        "extract_json_dumps_helper",
        "extract_json_loads_helper",
        "extract_splitlines_helper",
        "extract_append_mapping_helper",
    ]


def test_development_json_extraction_is_sandbox_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def write_json(path: str, value: object) -> None:\n"
        "    Path(path).write_text(json.dumps(value), encoding='utf-8')\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_json_dumps_helper"),
        test_plan={},
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_json_dumps_helper"
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def serialize_json(value):" in patched
    assert "write_text(serialize_json(value), encoding='utf-8')" in patched


def test_development_json_extraction_rejects_ambiguous_pattern(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def write_json(path: str, value: object) -> None:\n"
        "    Path(path).write_text(json.dumps(value), encoding='utf-8')\n"
        "    Path(path + '.bak').write_text(json.dumps(value), encoding='utf-8')\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_json_dumps_helper"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "json_dumps_helper_pattern_not_proven"
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_unknown_development_extraction_operator_is_stopped(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "writer.py").write_text("def write_json():\n    return None\n", encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_unverified_helper"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "unsupported_development_helper_extraction"
    assert package["patches"] == []


def test_development_json_loads_extraction_is_sandbox_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def read_json(path: str) -> object:\n"
        "    return json.loads(Path(path).read_text(encoding='utf-8'))\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_json_loads_helper", target="writer.py:read_json"),
        test_plan={},
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_json_loads_helper"
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def parse_json(text):" in patched
    assert "parse_json(Path(path).read_text(encoding='utf-8'))" in patched


def test_development_json_loads_rejects_multiple_sites(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def read_json(path: str) -> tuple[object, object]:\n"
        "    primary = json.loads(Path(path).read_text(encoding='utf-8'))\n"
        "    backup = json.loads(Path(path + '.bak').read_text(encoding='utf-8'))\n"
        "    return primary, backup\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_json_loads_helper", target="writer.py:read_json"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "json_loads_helper_pattern_not_proven"
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_helper_selection_rejects_cross_reducer_ambiguity(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def move_json(source: str, destination: str, value: object) -> object:\n"
        "    Path(destination).write_text(json.dumps(value), encoding='utf-8')\n"
        "    return json.loads(Path(source).read_text(encoding='utf-8'))\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "extract_json_dumps_helper",
            target="writer.py:move_json",
            allowed=["extract_json_dumps_helper", "extract_json_loads_helper"],
        ),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "ambiguous_development_helper_extraction"
    assert len(package["reducer_selection"]["attempts"]) == 2
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_splitlines_matcher_selects_unique_reducer(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "from pathlib import Path\n\n"
        "def read_lines(path: str) -> list[str]:\n"
        "    return Path(path).read_text(encoding='utf-8').splitlines()\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "extract_json_dumps_helper",
            target="writer.py:read_lines",
            allowed=[
                "extract_json_dumps_helper",
                "extract_json_loads_helper",
                "extract_splitlines_helper",
            ],
        ),
        test_plan={},
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_splitlines_helper"
    assert package["reducer_selection"]["status"] == "unique"
    assert [row["status"] for row in package["reducer_selection"]["attempts"]] == [
        "skipped", "skipped", "prepared",
    ]
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def split_lines(text):" in patched
    assert "split_lines(Path(path).read_text(encoding='utf-8'))" in patched


def test_development_splitlines_rejects_multiple_sites(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "from pathlib import Path\n\n"
        "def read_lines(path: str) -> tuple[list[str], list[str]]:\n"
        "    primary = Path(path).read_text(encoding='utf-8').splitlines()\n"
        "    backup = Path(path + '.bak').read_text(encoding='utf-8').splitlines()\n"
        "    return primary, backup\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan("extract_splitlines_helper", target="writer.py:read_lines"),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "splitlines_helper_pattern_not_proven"
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_append_mapping_matcher_selects_unique_reducer(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_rows(rows: list[list[str]]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        normalized.append({'name': row[0].strip(), 'value': row[-1].strip()})\n"
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
    assert package["patches"][0]["mapping_source"] == "inline_append"
    assert package["reducer_selection"]["status"] == "unique"
    assert [row["status"] for row in package["reducer_selection"]["attempts"]] == [
        "skipped", "skipped", "skipped", "prepared",
    ]
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def normalize_record(row):" in patched
    assert "normalized.append(normalize_record(row))" in patched


def test_development_append_mapping_rejects_multiple_sites(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_rows(rows: list[list[str]]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        normalized.append({'name': row[0].strip()})\n"
        "        normalized.append({'value': row[-1].strip()})\n"
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
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_development_mapping_rejects_cross_reducer_ambiguity(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = (
        "def normalize_text(text: str) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in text.splitlines():\n"
        "        normalized.append({'name': row.strip()})\n"
        "    return normalized\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")

    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "extract_splitlines_helper",
            target="writer.py:normalize_text",
            allowed=["extract_splitlines_helper", "extract_append_mapping_helper"],
        ),
        test_plan={},
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "ambiguous_development_helper_extraction"
    assert [row["status"] for row in package["reducer_selection"]["attempts"]] == [
        "prepared", "prepared",
    ]
    assert (project / "writer.py").read_text(encoding="utf-8") == source
