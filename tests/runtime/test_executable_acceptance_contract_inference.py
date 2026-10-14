from __future__ import annotations

from tests.runtime.executable_acceptance_contract_inference_helpers import *

def test_infers_numeric_string_from_runtime_conversion(tmp_path: Path):
    path = _source(tmp_path, "def parse(value):\n    return float(value)\n")

    assert infer_argument_samples(path, "parse") == {
        "value": {"value": "1.0", "source": "ast_conversion:float"}
    }


def test_infers_numeric_value_from_literal_comparison(tmp_path: Path):
    path = _source(tmp_path, "def schedule(epoch):\n    return 1 if epoch < 6 else 2\n")

    assert infer_argument_samples(path, "schedule") == {
        "epoch": {"value": 5, "source": "ast_comparison_literal"}
    }


def test_infers_datetime_string_from_strptime_format(tmp_path: Path):
    path = _source(
        tmp_path,
        "import datetime\n\ndef parse(value):\n"
        "    return datetime.datetime.strptime(value, '%Y%m%d%H%M')\n",
    )

    assert infer_argument_samples(path, "parse") == {
        "value": {"value": "202402030405", "source": "ast_strptime_format"}
    }


def test_infers_minimal_mapping_from_direct_literal_key_reads(tmp_path: Path):
    path = _source(
        tmp_path,
        "def build(data):\n    return len(data['Ability']) + len(data['Unit'])\n",
    )

    assert infer_argument_samples(path, "build") == {
        "data": {
            "value": {"Ability": [], "Unit": []},
            "source": "ast_required_mapping_keys",
        }
    }


def test_qualified_method_disambiguates_same_named_methods(tmp_path: Path):
    path = _source(
        tmp_path,
        "class First:\n"
        "    @staticmethod\n"
        "    def choose(payload):\n"
        "        return payload['first']\n"
        "class Second:\n"
        "    @staticmethod\n"
        "    def choose(payload):\n"
        "        return payload['second']\n",
    )

    assert infer_argument_samples(path, "Second.choose") == {
        "payload": {
            "value": {"second": []},
            "source": "ast_required_mapping_keys",
        }
    }


def test_infers_keyword_only_payload_read_from_var_kwargs(tmp_path: Path):
    path = _source(tmp_path, "def reload(*args, **kwargs):\n    return kwargs['setting']\n")

    assert infer_argument_samples(path, "reload") == {
        "setting": {"value": "setting", "source": "ast_required_keyword_payload"}
    }


def test_infers_sequence_shape_from_length_constraint(tmp_path: Path):
    path = _source(
        tmp_path,
        "def padding(value):\n"
        "    assert len(value) == 4\n"
        "    return tuple(value)\n",
    )

    assert infer_argument_samples(path, "padding") == {
        "value": {"value": [0, 0, 0, 0], "source": "ast_length_constraint"}
    }


def test_infers_string_sequence_when_index_is_compared_to_string(tmp_path: Path):
    path = _source(
        tmp_path,
        "def normalize(value):\n"
        "    if value[0] == '#': value = value[1:]\n"
        "    assert len(value) == 3\n"
        "    return value\n",
    )

    assert infer_argument_samples(path, "normalize") == {
        "value": {"value": "000", "source": "ast_length_constraint"}
    }


def test_infers_numeric_sequence_from_array_operation(tmp_path: Path):
    path = _source(tmp_path, "def energy(samples):\n    return np.absolute(samples)\n")

    assert infer_argument_samples(path, "energy") == {
        "samples": {"value": [0.0, 1.0], "source": "ast_numeric_sequence:absolute"}
    }


def test_infers_value_from_local_allowed_collection(tmp_path: Path):
    path = _source(
        tmp_path,
        "ALLOWED = {'mean', 'sum'}\n"
        "def validate(operations):\n"
        "    unsupported = set(operations).difference(ALLOWED)\n"
        "    if unsupported:\n"
        "        raise ValueError('unsupported')\n"
        "    return operations\n",
    )

    assert infer_argument_samples(path, "validate") == {
        "operations": {"value": ["mean"], "source": "ast_allowed_collection_domain"}
    }


def test_infers_value_from_literal_membership_after_normalization(tmp_path: Path):
    path = _source(
        tmp_path,
        "def validate(level):\n"
        "    assert level.lower() in ['low', 'medium', 'high']\n",
    )

    assert infer_argument_samples(path, "validate") == {
        "level": {"value": "high", "source": "ast_literal_membership_domain"}
    }


def test_numeric_arithmetic_overrides_string_conversion_sample(tmp_path: Path):
    path = _source(
        tmp_path,
        "def scale(threshold):\n"
        "    if int(threshold) != threshold:\n"
        "        return threshold * 2.0\n"
        "    return threshold\n",
    )

    assert infer_argument_samples(path, "scale") == {
        "threshold": {"value": 1, "source": "ast_numeric_arithmetic"}
    }


def test_infers_minimal_object_from_parameter_attribute_reads(tmp_path: Path):
    path = _source(
        tmp_path,
        "def lookup(meta):\n    return meta.key if meta.enabled else None\n",
    )

    assert infer_argument_samples(path, "lookup") == {
        "meta": {
            "value": {
                "__fixture__": "declared_model",
                "type": "AcceptanceInput",
                "fields": {"enabled": False, "key": "sample"},
            },
            "source": "ast_parameter_attributes",
        }
    }


def test_preserves_none_for_guarded_optional_callable(tmp_path: Path):
    path = _source(
        tmp_path,
        "def transform(values, encoder=None):\n"
        "    if encoder is not None:\n"
        "        return encoder().fit(values)\n"
        "    return values\n",
    )

    assert infer_argument_samples(path, "transform")["encoder"] == {
        "value": None,
        "source": "ast_declared_default",
    }


def test_negative_var_keyword_contract_accepts_key_error(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(project, "def reload(**kwargs):\n    return kwargs['setting']\n")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:reload", {"setting": "sample"}, malformed=True),
        work_dir=tmp_path / "work-key-error",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_infers_date_from_validation_error_format_hint(tmp_path: Path):
    path = _source(
        tmp_path,
        "def validate(value):\n"
        "    if not DATE_RE.match(value):\n"
        "        raise ValueError('Expected format YYYY-MM-DD')\n",
    )

    assert infer_argument_samples(path, "validate") == {
        "value": {"value": "2024-02-03", "source": "ast_validation_format_hint"}
    }


def test_infers_importable_python_module_path(tmp_path: Path):
    path = _source(
        tmp_path,
        "import importlib.util\n"
        "def load(path):\n"
        "    spec = importlib.util.spec_from_file_location('plugin', path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    if not hasattr(module, 'CONFIG'):\n"
        "        raise ValueError('missing config')\n"
        "    return getattr(module, 'CONFIG')\n",
    )

    assert infer_argument_samples(path, "load") == {
        "path": {
            "value": {"__fixture__": "python_module_path", "fields": {"CONFIG": {}}},
            "source": "ast_importable_module_path",
        }
    }


def test_infers_importable_module_path_through_path_alias(tmp_path: Path):
    path = _source(
        tmp_path,
        "from pathlib import Path\nimport importlib.util\n"
        "def load(source):\n"
        "    path = Path(source)\n"
        "    spec = importlib.util.spec_from_file_location('plugin', path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return getattr(module, 'CONFIG')\n",
    )

    result = infer_argument_samples(path, "load")

    assert result["source"]["source"] == "ast_importable_module_path"
    assert result["source"]["value"]["fields"] == {"CONFIG": {}}


def test_executable_acceptance_materializes_importable_module_path(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(
        project,
        "import importlib.util\n"
        "def load(path):\n"
        "    spec = importlib.util.spec_from_file_location('plugin', path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return getattr(module, 'CONFIG')\n",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:load", {"path": "sample"}, malformed=False),
        work_dir=tmp_path / "work-module-path",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_infers_anonymized_literal_from_upstream_test_call(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def parse(value):\n    return float(value)\n")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_parse.py").write_text(
        "def test_parse():\n    assert parse('2.5') == 2.5\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "2.5", "source": "upstream_test_call:literal"}
    }


def test_ignores_same_named_attribute_call_from_unrelated_object(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def parse(value):\n    return float(value)\n")
    (project / "test_other.py").write_text(
        "def test_other(parser):\n    assert parser.parse('wrong')\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "1.0", "source": "ast_conversion:float"}
    }


def test_accepts_qualified_call_only_when_import_points_to_target_module(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    path = package / "parser.py"
    path.write_text("def parse(value):\n    return float(value)\n", encoding="utf-8")
    (project / "test_parser.py").write_text(
        "from pkg import parser\n\ndef test_parse():\n    assert parser.parse('3.5') == 3.5\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "3.5", "source": "upstream_test_call:literal"}
    }


def test_preserves_none_literal_from_upstream_optional_call(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def normalize(value):\n    return value or 'default'\n")
    (project / "test_normalize.py").write_text(
        "def test_normalize():\n    assert normalize(None) == 'default'\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "normalize", project_root=project) == {
        "value": {"value": None, "source": "upstream_test_call:literal"}
    }


def test_rejects_upstream_factory_expression(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def parse(value):\n    return float(value)\n")
    (project / "test_parse.py").write_text(
        "def test_parse():\n    assert parse(make_value()) == 1.0\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "1.0", "source": "ast_conversion:float"}
    }
