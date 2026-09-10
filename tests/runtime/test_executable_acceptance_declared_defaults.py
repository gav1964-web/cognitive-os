from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_contract_inference import infer_argument_samples
from tests.runtime.test_executable_acceptance import _plan


def _source(root: Path) -> Path:
    path = root / "module.py"
    path.write_text(
        "def build_description(node=None):\n"
        "    if node is None:\n"
        "        return 'root'\n"
        "    name, logger, children = node\n"
        "    return name\n",
        encoding="utf-8",
    )
    return path


def test_infers_literal_declared_default(tmp_path: Path):
    path = _source(tmp_path)

    assert infer_argument_samples(path, "build_description") == {
        "node": {"value": None, "source": "ast_declared_default"}
    }


def test_declared_default_overrides_generic_positive_sample(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(project)

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:build_description", {"node": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_overrides"] == {
        "module.py:build_description": {"node": None}
    }


def test_rejected_nullable_default_is_not_used_for_positive_sample(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "def require_token(token=None):\n"
        "    if not token:\n"
        "        raise ValueError('token required')\n"
        "    return token\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "require_token") == {}


def test_nullable_default_is_kept_when_non_null_value_is_rejected(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "def require_empty(token=None):\n"
        "    if token is not None:\n"
        "        raise ValueError('token must be empty')\n"
        "    return token\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "require_empty") == {
        "token": {"source": "ast_declared_default", "value": None},
    }
