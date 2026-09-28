from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from tests.runtime.test_executable_acceptance import _plan


def _run(tmp_path: Path, source: str, target: str):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(source, encoding="utf-8")
    return run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan(target, {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )


def test_executes_qualified_classmethod_target(tmp_path: Path):
    result = _run(
        tmp_path,
        "class Parser:\n    @classmethod\n    def from_cli(cls, value: str) -> str:\n        return value.strip()\n",
        "main.py:Parser.from_cli",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_infers_required_mapping_for_method_sample(tmp_path: Path):
    result = _run(
        tmp_path,
        "class Parser:\n    @staticmethod\n    def parse(value):\n        return {'parsed_url': value['url']}\n",
        "main.py:parse",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:parse"]
    assert evidence["value"]["source"] == "ast_required_mapping_keys"


def test_qualified_method_falls_back_when_class_decorator_replaces_class(tmp_path: Path):
    result = _run(
        tmp_path,
        "def public(value):\n    return lambda *args, **kwargs: None\n\n@public\nclass Parser:\n    def __init__(self, value):\n        self.value = value\n    @classmethod\n    def from_cli(cls, value):\n        return cls(value)\n",
        "main.py:Parser.from_cli",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["main.py:Parser.from_cli"]


def test_infers_empty_mapping_for_items_protocol(tmp_path: Path):
    result = _run(
        tmp_path,
        "def render(writer, environment):\n    for key, value in environment.items():\n        writer(key, value)\n",
        "main.py:render",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:render"]
    assert evidence["environment"]["source"] == "ast_mapping_protocol:items"


def test_infers_empty_mapping_for_get_protocol(tmp_path: Path):
    result = _run(
        tmp_path,
        "def render_claims(claims):\n    return claims.get('subject', 'missing')\n",
        "main.py:render_claims",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:render_claims"]
    assert evidence["claims"]["source"] == "ast_mapping_protocol:get"


def test_infers_callable_for_inspect_signature(tmp_path: Path):
    result = _run(
        tmp_path,
        "import inspect\n\ndef varnames(func):\n    return tuple(inspect.signature(func).parameters)\n",
        "main.py:varnames",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:varnames"]
    assert evidence["func"]["source"] == "ast_qualified_call:inspect.signature"


def test_infers_callable_for_introspection_predicates(tmp_path: Path):
    result = _run(
        tmp_path,
        "import inspect\n\ndef varnames(func):\n"
        "    if inspect.isclass(func):\n        return ()\n"
        "    if not inspect.isroutine(func):\n        func = getattr(func, '__call__', func)\n"
        "    func = inspect.unwrap(func)\n"
        "    return func.__code__.co_varnames\n",
        "main.py:varnames",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:varnames"]
    assert evidence["func"]["source"].startswith("ast_qualified_call:inspect.")


def test_field_fixture_supplies_valid_indented_list_contents(tmp_path: Path):
    result = _run(
        tmp_path,
        "import inspect\n\ndef indented_list(contents: str) -> list[str]:\n"
        "    assert not contents.startswith(' '), contents\n"
        "    assert not contents.startswith('\\n'), contents\n"
        "    ret = []\n"
        "    for line in contents.splitlines(keepends=True):\n"
        "        if line.strip() and not line.startswith(' '):\n            ret.append(line)\n"
        "        else:\n            ret[-1] += line\n"
        "    return [inspect.cleandoc(item) for item in ret]\n",
        "main.py:indented_list",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:indented_list"]
    assert evidence["contents"]["source"] == "ast_literal_buffer:assert_not_startswith"


def test_generated_harness_does_not_execute_installed_shadow_module(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pluggy"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "_hooks.py").write_text(
        "def varnames(func, *, legacy_noself=False):\n"
        "    return (('value',), ()) if callable(func) else ((), ())\n",
        encoding="utf-8",
    )
    plan = _plan(
        "src/pluggy/_hooks.py:varnames",
        {"func": {"__fixture__": "callable_identity"}, "legacy_noself": True},
        malformed=False,
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=plan,
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["command"]["status"] == "passed"


def test_mapping_protocol_overrides_name_based_model_fixture(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def render(writer, environment):\n    for key, value in environment.items():\n        writer(key, value)\n",
        encoding="utf-8",
    )
    plan = _plan("main.py:render", {"value": "sample"}, malformed=False)
    for row in plan["executable_acceptance"]["obligations"]:
        if row["kind"] == "positive_contract_case":
            row["given"] = {
                "writer": "sample",
                "environment": {"__fixture__": "hatch_environment_minimal"},
            }

    result = run_executable_acceptance(
        root=tmp_path, project_dir=project, test_plan=plan, work_dir=tmp_path / "work"
    )

    assert result["summary"]["signal_strength"] == "executable_callable"


def test_explicit_mapping_literal_outranks_empty_structural_sample(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def present_values(values):\n"
        "    return {key: value for key, value in values.items() if value is not None}\n",
        encoding="utf-8",
    )
    plan = _plan("main.py:present_values", {"value": "sample"}, malformed=False)
    for row in plan["executable_acceptance"]["obligations"]:
        if row["kind"] == "positive_contract_case":
            row["given"] = {"values": {"a": 1, "b": None}}
            row["expect"] = {"return_value": {"a": 1}}

    result = run_executable_acceptance(
        root=tmp_path, project_dir=project, test_plan=plan, work_dir=tmp_path / "work"
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_overrides"] == {}


def test_executes_tensor_window_shape_contract_with_linked_samples(tmp_path: Path):
    result = _run(
        tmp_path,
        "import torch\n\n"
        "def window_unpartition(windows: torch.Tensor, window_size: int, pad_hw: tuple[int, int], hw: tuple[int, int]) -> torch.Tensor:\n"
        "    Hp, Wp = pad_hw\n"
        "    H, W = hw\n"
        "    B = windows.shape[0] // (Hp * Wp // window_size // window_size)\n"
        "    x = windows.view(B, Hp // window_size, Wp // window_size, window_size, window_size, -1)\n"
        "    x = x.permute(0, 1, 3, 2, 4, 5).contiguous().view(B, Hp, Wp, -1)\n"
        "    return x[:, :H, :W, :].contiguous()\n",
        "main.py:window_unpartition",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:window_unpartition"]
    assert set(evidence) == {"windows", "window_size", "pad_hw", "hw"}
    assert {row["source"] for row in evidence.values()} == {"ast_tensor_window_contract"}
