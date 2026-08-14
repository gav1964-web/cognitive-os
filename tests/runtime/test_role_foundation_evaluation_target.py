from pathlib import Path

from runtime.role_foundation_pipeline import run_role_foundation_pipeline


def test_foundation_pipeline_clamps_existing_source_for_evaluation(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text(
        "def parse_primary(payload: dict) -> dict:\n"
        "    return {'primary': payload['value']}\n\n"
        "def normalize_name(value: str) -> str:\n"
        "    return value.strip().lower()\n",
        encoding="utf-8",
    )

    result = run_role_foundation_pipeline(
        root=Path(__file__).resolve().parents[2],
        project_dir=project,
        goal="Evaluate exact source target",
        write=False,
        _evaluation_target="app.py:normalize_name",
    )

    assert result["selected_extraction_candidate"] == "app.py:normalize_name"
    assert result["safety"]["source_code_changes"] is False
