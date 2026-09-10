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


def test_foundation_pipeline_clamps_class_qualified_method(tmp_path):
    project = tmp_path / "method_project"
    project.mkdir()
    (project / "store.py").write_text(
        "class Store:\n"
        "    def set_value(self, value: str):\n"
        "        self.value = value\n\n"
        "def normalize(value: str) -> str:\n"
        "    return value.strip()\n",
        encoding="utf-8",
    )

    result = run_role_foundation_pipeline(
        root=Path(__file__).resolve().parents[2],
        project_dir=project,
        goal="Evaluate exact method target",
        write=False,
        _evaluation_target="store.py:Store.set_value",
    )

    assert result["selected_extraction_candidate"] == "store.py:Store.set_value"


def test_evaluation_target_is_not_replaced_by_preflight_policy(tmp_path):
    project = tmp_path / "policy_project"
    project.mkdir()
    (project / "app.py").write_text(
        "def weak_hook(value):\n"
        "    print(value)\n\n"
        "def normalize_name(value: str) -> str:\n"
        "    return value.strip().lower()\n",
        encoding="utf-8",
    )

    result = run_role_foundation_pipeline(
        root=Path(__file__).resolve().parents[2],
        project_dir=project,
        goal="Keep Architect feedback target authoritative",
        write=False,
        _evaluation_target="app.py:normalize_name",
    )

    assert result["selected_extraction_candidate"] == "app.py:normalize_name"
