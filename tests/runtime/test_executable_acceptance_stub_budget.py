from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_stub_budget import can_stub_missing, stub_attempt_budget


def _policy():
    return {
        "enabled": True,
        "stub_external_missing_modules": True,
        "max_missing_modules": 2,
        "max_namespace_modules_per_dependency": 4,
    }


def test_namespace_modules_share_one_external_root_budget(tmp_path):
    policy = _policy()
    stubbed = ["sdk", "sdk.engine", "sdk.orm", "other"]

    assert can_stub_missing(tmp_path, "sdk.sql", policy, stubbed) is True
    assert can_stub_missing(tmp_path, "third", policy, stubbed) is False
    assert stub_attempt_budget(policy) == 9


def test_local_package_cannot_be_hidden_by_dependency_stub(tmp_path):
    (tmp_path / "sdk").mkdir()

    assert can_stub_missing(tmp_path, "sdk.engine", _policy(), []) is False


def test_retry_clears_partially_imported_local_package_tree(tmp_path):
    project = tmp_path / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .worker import normalize\n", encoding="utf-8")
    (package / "worker.py").write_text(
        "from external_sdk.engine import Engine\n"
        "from external_sdk.orm import Session\n\n"
        "def normalize(value):\n    return value.strip().lower()\n",
        encoding="utf-8",
    )
    plan = {"executable_acceptance": {"obligations": [{
        "id": "EA-1", "target": "pkg/worker.py:normalize",
        "kind": "positive_contract_case", "given": {"value": " Sample "},
        "expect": {"return_value": "sample"},
    }]}}

    result = run_executable_acceptance(
        root=tmp_path, project_dir=project, test_plan=plan, work_dir=tmp_path / "work"
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dependency_stub_targets"] == {
        "pkg/worker.py:normalize": ["external_sdk", "external_sdk.engine", "external_sdk.orm"]
    }
