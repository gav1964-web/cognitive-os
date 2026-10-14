from pathlib import Path

from runtime._parts.role_foundation_field_trial_scope import _primary_language_scope
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.source_contract_semantics import infer_source_contract


def _contract(snippet: str, names: list[str]) -> dict:
    return infer_source_contract(
        {
            "signature": {"args": [{"name": name, "annotation": ""} for name in names], "returns": ""},
            "snippet": snippet,
        }
    )


def test_django_settings_only_package_is_out_of_scope(tmp_path: Path):
    package = tmp_path / "application"
    package.mkdir()
    for name in ("__init__.py", "settings.py", "urls.py", "wsgi.py"):
        (package / name).write_text("", encoding="utf-8")
    (tmp_path / "manage.py").write_text("print('manage')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("django\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_documentation_led_deployment_sample_is_out_of_scope(tmp_path: Path):
    backend = tmp_path / "backend" / "core"
    backend.mkdir(parents=True)
    (backend / "views.py").write_text("def health_check(request): return {'ok': True}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("deployment article\n" * 1500, encoding="utf-8")
    for name in ("Dockerfile", "docker-compose.yml", "stack.yml"):
        (tmp_path / name).write_text("deployment\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_native_dominated_monorepo_is_out_of_scope(tmp_path: Path):
    native = tmp_path / "native"
    python = tmp_path / "python"
    native.mkdir()
    python.mkdir()
    for index in range(500):
        (native / f"unit_{index}.c").write_text("int x;\n", encoding="utf-8")
    for index in range(10):
        (python / f"tool_{index}.py").write_text("print('tool')\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_fixture_only_python_surface_is_out_of_scope(tmp_path: Path):
    fixtures = tmp_path / "analyser" / "test-resources" / "test-project"
    fixtures.mkdir(parents=True)
    for index in range(4):
        (fixtures / f"sample_{index}.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pylint\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_scripts_only_native_project_is_out_of_scope(tmp_path: Path):
    scripts = tmp_path / "scripts"
    native = tmp_path / "src"
    scripts.mkdir()
    native.mkdir()
    (scripts / "fix_header.py").write_text("print('fix')\n", encoding="utf-8")
    (scripts / "generate.py").write_text("print('generate')\n", encoding="utf-8")
    (native / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_model_fit_result_is_training_history():
    evidence = _contract("def train(self, values):\n    return self.model.fit(values)", ["values"])

    assert evidence["inferred_output_type"] == "TrainingHistoryLike"


def test_tensor_reduction_result_is_array_like():
    evidence = _contract("def loss(pred):\n    value = pred.sum()\n    return value.mean()", ["pred"])

    assert evidence["argument_usage_types"]["pred"] == "ArrayLike"
    assert evidence["inferred_output_type"] == "ArrayLike"


def test_global_lookup_and_getattr_have_concrete_results():
    lookup = _contract("def embeddings(keys):\n    return model[keys]", ["keys"])
    setting = _contract("def overridable(name, default=None):\n    return getattr(settings, name, default)", ["name", "default"])

    assert lookup["inferred_output_type"] == "ItemLike"
    assert setting["inferred_output_type"] == "AttributeValue"


def test_middleware_and_visualization_contract_families_are_configured():
    middleware = contract_archetype_for_target("pkg/middleware.py:__call__")
    plot = contract_archetype_for_target("pkg/plots.py:plot_exec_log")
    training = contract_archetype_for_target("sde/sde_learning_network.py:train_model")

    assert middleware["contract_family"] == "web_request_middleware_boundary"
    assert plot["contract_family"] == "visualization_render_boundary"
    assert training["contract_family"] == "model_training_boundary"
