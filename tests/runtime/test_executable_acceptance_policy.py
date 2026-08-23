from __future__ import annotations

import gc
from pathlib import Path

from runtime.executable_acceptance_policy import (
    dependency_stub_policy,
    external_call_tokens,
    load_executable_acceptance_policy,
    method_fixture_policy,
    source_isolation_policy,
    sample_value,
    skipped_recovery_hint,
    structural_sample_policy,
    temporary_executable_acceptance_policy,
)
from runtime.executable_acceptance_materializers import materialize


def test_executable_acceptance_policy_drives_samples_dependency_tokens_and_stubs():
    assert "provider" in external_call_tokens()
    structural = structural_sample_policy()
    assert structural["priorities"]["importable_module_path"] == 110
    assert "asarray" in structural["numeric_sequence_calls"]


def test_temporary_policy_is_scoped_and_restored():
    original = structural_sample_policy()
    candidate = load_executable_acceptance_policy()
    candidate["structural_sample_policy"]["maximum_inferred_length"] = 7

    with temporary_executable_acceptance_policy(candidate):
        assert structural_sample_policy()["maximum_inferred_length"] == 7

    assert structural_sample_policy() == original
    assert dependency_stub_policy()["max_missing_modules"] == 6
    assert dependency_stub_policy()["max_namespace_modules_per_dependency"] == 8
    assert "stevedore" in dependency_stub_policy()["pre_stub_modules"]
    assert "mro_entries" in dependency_stub_policy()["stub_object_features"]
    assert "cookiecutter" in dependency_stub_policy()["metadata_packages"]
    assert "invoke" in dependency_stub_policy()["metadata_packages"]
    assert "paramiko" in dependency_stub_policy()["metadata_packages"]
    assert "borg._version" in dependency_stub_policy()["generated_module_profiles"]
    assert "virtualenv.version" in dependency_stub_policy()["generated_module_profiles"]
    assert "urllib3._version" in dependency_stub_policy()["generated_module_profiles"]
    assert method_fixture_policy()["safe_uninitialized_instance"] is True
    assert "determine_local_workspace_environment" in method_fixture_policy()["local_import_stub_functions"]
    assert "BlocksConfig.set_event_trigger" in method_fixture_policy()["local_import_stub_methods"]
    assert "StreamableHTTPServerTransport._handle_post_request" in method_fixture_policy()["local_import_stub_methods"]
    assert "gradio.helpers" in dependency_stub_policy()["generated_module_profiles"]
    assert "great_expectations.util" in dependency_stub_policy()["generated_module_profiles"]
    assert "passlib.context" in dependency_stub_policy()["generated_module_profiles"]
    assert "WsgiToAsgiInstance.build_environ" in method_fixture_policy()["instance_attribute_profiles"]
    assert "DataProfilerColumnDomainBuilder._get_domains" in method_fixture_policy()["instance_attribute_profiles"]
    assert "socket" in source_isolation_policy()["effect_module_stubs"]
    assert "logging.Handler" in source_isolation_policy()["preserved_stdlib_class_bases"]
    assert "optional dependency" in skipped_recovery_hint("import_failed_missing_module")
    assert "closure" in skipped_recovery_hint("nested_function_requires_closure")
    assert sample_value("Callable[[dict], str]", "id_of") == {"__fixture__": "callable_id_of"}
    assert sample_value("ParseFloat", "parse_float") == {"__fixture__": "callable_float"}
    assert sample_value("ConfigParser", "cfg") == {"__fixture__": "configparser_flake8_empty"}
    assert sample_value("Graph", "G") == {"__fixture__": "networkx_graph_path"}
    assert sample_value("int", "iterations") == 1
    assert sample_value("", "batch_size", signature_mode=True) == 1
    assert sample_value("", "beta", signature_mode=True) == 1
    assert sample_value("bool", "include_initial_labels") is False
    assert sample_value("BytesIO", "body") == {"__fixture__": "bytes_io_empty"}
    assert sample_value("parserinfo", "info") == {"__fixture__": "dateutil_parserinfo_minimal"}
    assert sample_value("_ymd", "ymd") == {"__fixture__": "dateutil_ymd"}
    assert sample_value("ast.AST | None", "astnode") is None
    assert sample_value("str", "src") == '"sample"'
    assert sample_value("", "fn") == {"__fixture__": "callable_noop"}
    assert sample_value("", "targets") == []
    assert sample_value("", "inputs") == []
    assert sample_value("", "outputs") == []
    assert sample_value("", "trigger_mode") == "once"
    assert sample_value("ProtocolLike", "row") == {"__fixture__": "record_row_empty"}
    assert sample_value("int", "row") == 1
    assert sample_value("PathLike", "filename") == "acceptance-output.tmp"
    assert sample_value("PathLike", "image_path") == {"__fixture__": "readable_temp_path"}
    assert sample_value("", "api_visibility") == "public"
    assert sample_value("", "cancels") == []
    assert sample_value("bool", "enabled") is True
    assert sample_value("bool", "enabled", signature_mode=True) is False
    assert sample_value("bytes", "payload") == {"__fixture__": "bytes_empty"}
    assert sample_value("IndexableLike", "data") == {}
    assert sample_value("", "function") == {"__fixture__": "callable_identity"}
    assert sample_value("", "arity") == 1
    assert materialize({"iterations": "sample", "digest_size": "sample"}) == {"iterations": 1, "digest_size": 8}
    row = materialize({"__fixture__": "record_row_empty"})
    assert row.data == {} and row.get("missing") is None


def test_crypt_context_fixture_preserves_password_helper_return_shapes():
    context_class = materialize({"__fixture__": "crypt_context_class"})
    context = context_class(schemes=["bcrypt"], deprecated="auto")

    assert context.verify("plain", "encoded") is True
    assert isinstance(context.hash("plain"), str)


def test_readable_temp_path_fixture_is_ephemeral():
    fixture = materialize(sample_value("PathLike", "image_path"))
    path = Path(fixture)

    assert path.read_bytes() == b"sample"
    del fixture
    gc.collect()
    assert not path.exists()
