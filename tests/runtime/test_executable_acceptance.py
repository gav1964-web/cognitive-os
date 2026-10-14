from __future__ import annotations

from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.test_plan_builder import build_test_plan


def _plan(target: str, given: dict[str, str], *, malformed: bool = True) -> dict[str, dict[str, list[dict[str, object]]]]:
    obligations: list[dict[str, object]] = [
        {
            "id": "OBL-001",
            "acceptance_id": "AC-001",
            "target": target,
            "kind": "positive_contract_case",
            "given": given,
            "expect": {"parsed_url": "ParsedURL"},
            "oracle": "output_schema_and_acceptance_criterion",
        },
        {
            "id": "OBL-003",
            "acceptance_id": "side_effect_boundary",
            "target": target,
            "kind": "side_effect_scope_case",
            "given": {},
            "expect": {"no_writes_outside_declared_scope": True},
            "oracle": "changed_file_list_is_subset_of_writable_scope",
        },
    ]
    if malformed:
        obligations.insert(
            1,
            {
                "id": "OBL-002",
                "acceptance_id": "contract_negative_missing_input",
                "target": target,
                "kind": "malformed_input_case",
                "given": {},
                "expect": {"error": "controlled_validation_error"},
                "oracle": "missing_required_input_rejected",
            },
        )
    return {"executable_acceptance": {"obligations": obligations}}


def test_executable_acceptance_skips_negative_for_defaulted_input(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def parse(url: str = ''):\n    return {'parsed_url': url}\n", encoding="utf-8")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:parse", {"url": "sample"}),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"


def test_executable_acceptance_meta_checks_nested_import_failure(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg" / "util"
    package.mkdir(parents=True)
    (project / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "url.py").write_text(
        "from ..missing import Missing\n\n"
        "def parse_url(url: str):\n"
        "    return {'parsed_url': Missing(url)}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/util/url.py:parse_url", {"url": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["callable_harness_count"] == 0
    assert result["summary"]["signal_strength"] == "meta_only"
    assert result["summary"]["skipped_reason_counts"] == {"import_failed_missing_module": 1}
    assert "pkg.missing" in result["summary"]["skipped_targets"][0]["detail"]


def test_executable_acceptance_executes_isolated_function_when_import_dependency_is_missing(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "url.py").write_text(
        "from missing_lib import helper\n\n"
        "def parse_url(url: str):\n"
        "    return {'parsed_url': url}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/url.py:parse_url", {"url": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["skipped_reason_counts"] == {}


def test_executable_acceptance_uses_controlled_stub_for_external_missing_module(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "url.py").write_text(
        "from external_missing import helper\n\n"
        "def parse_url(url: str):\n"
        "    return {'parsed_url': helper(url) or url}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/url.py:parse_url", {"url": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dependency_stub_targets"] == {"src/pkg/url.py:parse_url": ["external_missing"]}


def test_executable_acceptance_executes_isolated_async_function_when_import_dependency_is_missing(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tasks.py").write_text(
        "from missing_lib import helper\n\n"
        "async def run_task(name: str):\n"
        "    return {'parsed_url': name}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/tasks.py:run_task", {"name": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_materializes_callable_fixture(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def create(meta_schema, id_of):\n"
        "    return {'result': id_of(meta_schema) or 'missing'}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "main.py:create",
                        "kind": "positive_contract_case",
                        "given": {"meta_schema": {"$id": "urn:test"}, "id_of": {"__fixture__": "callable_id_of"}},
                        "expect": {"result": "string"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "contract_negative_missing_input",
                        "target": "main.py:create",
                        "kind": "malformed_input_case",
                        "given": {},
                        "expect": {"error": "controlled_validation_error"},
                        "oracle": "missing_required_input_rejected",
                    },
                    {
                        "id": "OBL-003",
                        "acceptance_id": "side_effect_boundary",
                        "target": "main.py:create",
                        "kind": "side_effect_scope_case",
                        "given": {},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ]
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_reports_method_target_needs_fixture(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "class Parser:\n"
        "    def parse(self, value):\n"
        "        return {'parsed_url': value}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:parse", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_executes_static_method_target(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "class Parser:\n"
        "    @staticmethod\n"
        "    def parse(value):\n"
        "        return {'parsed_url': value}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:parse", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_maps_semantic_argument_names_to_signature(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def make_response(rv):\n"
        "    return {'parsed_url': rv}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:make_response", {"return_value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_mappings"]["main.py:make_response"] == {"rv": "return_value"}


def test_executable_acceptance_synthesizes_missing_positive_kwonly_arguments(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def parse(value, *, flag):\n"
        "    return {'parsed_url': value if flag is False else 'bad'}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:parse", {"value": "sample"}),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["main.py:parse"] == {"flag": False}


def test_executable_acceptance_uses_non_none_defaults_for_required_annotation_and_value(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def analyze(*, param_name, annotation, value, is_path_param):\n"
        "    if annotation is None or value is None:\n"
        "        raise ValueError('required')\n"
        "    return {'parsed_url': param_name}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:analyze", {"param_name": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["main.py:analyze"] == {
        "annotation": "sample",
        "is_path_param": False,
        "value": "sample",
    }


def test_executable_acceptance_executes_method_with_uninitialized_instance_when_safe(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "class Parser:\n"
        "    def __init__(self, config):\n"
        "        self.config = config\n"
        "    def parse(self, value):\n"
        "        return {'parsed_url': value}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:parse", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_test_plan_builder_uses_type_aware_json_fixtures():
    plan = build_test_plan(
        technical_spec={"acceptance_criteria": [{"id": "AC-001", "criterion": "callable fixture"}]},
        implementation_plan={
            "implementation_target": {"candidate": "main.py:create"},
            "patch_scope": ["main.py"],
            "writable_scope": ["main.py:create"],
            "contract_binding": {
                "binding_status": "bound_to_extraction_contract",
                "input_contract": {
                    "validators": "Mapping[str, Callable] | Iterable[tuple[str, Callable]]",
                    "id_of": "Callable[[dict], str]",
                    "applicable_validators": "ApplicableValidators",
                },
                "output_contract": {"result": "type[Validator]"},
            },
        },
    )

    given = plan["executable_acceptance"]["obligations"][0]["given"]
    assert given["validators"] == {}
    assert given["id_of"] == {"__fixture__": "callable_id_of"}
    assert given["applicable_validators"] == {"__fixture__": "callable_items"}
