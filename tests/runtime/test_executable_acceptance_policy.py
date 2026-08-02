from __future__ import annotations

from runtime.executable_acceptance_policy import (
    dependency_stub_policy,
    external_call_tokens,
    method_fixture_policy,
    sample_value,
    skipped_recovery_hint,
)
from runtime.executable_acceptance_materializers import materialize


def test_executable_acceptance_policy_drives_samples_dependency_tokens_and_stubs():
    assert "provider" in external_call_tokens()
    assert dependency_stub_policy()["max_missing_modules"] == 3
    assert "mro_entries" in dependency_stub_policy()["stub_object_features"]
    assert "cookiecutter" in dependency_stub_policy()["metadata_packages"]
    assert "invoke" in dependency_stub_policy()["metadata_packages"]
    assert "paramiko" in dependency_stub_policy()["metadata_packages"]
    assert "borg._version" in dependency_stub_policy()["generated_module_profiles"]
    assert "virtualenv.version" in dependency_stub_policy()["generated_module_profiles"]
    assert "urllib3._version" in dependency_stub_policy()["generated_module_profiles"]
    assert method_fixture_policy()["safe_uninitialized_instance"] is True
    assert "WsgiToAsgiInstance.build_environ" in method_fixture_policy()["instance_attribute_profiles"]
    assert "optional dependency" in skipped_recovery_hint("import_failed_missing_module")
    assert sample_value("Callable[[dict], str]", "id_of") == {"__fixture__": "callable_id_of"}
    assert sample_value("ParseFloat", "parse_float") == {"__fixture__": "callable_float"}
    assert sample_value("ConfigParser", "cfg") == {"__fixture__": "configparser_flake8_empty"}
    assert sample_value("Graph", "G") == {"__fixture__": "networkx_graph_path"}
    assert sample_value("int", "iterations") == 1
    assert sample_value("bool", "include_initial_labels") is False
    assert sample_value("BytesIO", "body") == {"__fixture__": "bytes_io_empty"}
    assert sample_value("parserinfo", "info") == {"__fixture__": "dateutil_parserinfo_minimal"}
    assert sample_value("_ymd", "ymd") == {"__fixture__": "dateutil_ymd"}
    assert sample_value("ast.AST | None", "astnode") is None
    assert sample_value("str", "src") == '"sample"'
    assert sample_value("bool", "enabled") is True
    assert sample_value("bool", "enabled", signature_mode=True) is False
    assert materialize({"iterations": "sample", "digest_size": "sample"}) == {"iterations": 1, "digest_size": 8}
