"""Materialize config-backed executable acceptance fixtures."""

from __future__ import annotations

from typing import Any

from .executable_acceptance_materializer_fixtures import (
    _AcceptanceStrEnum,
    _ContainsAll,
    _NoopCondition,
    _PantsTarget,
    _SafeMethodAttribute,
    _SafeSymbolicAttribute,
    _TensorShapeProxy,
    _asgi_body_empty,
    _asgi_receive_empty,
    _asgi_send_noop,
    _chroma_search_client,
    _coerced_field_value,
    _datasette_minimal,
    _domain_coerced_payload,
    _gradio_block_function_init,
    _hash_secret,
    _hatch_environment_minimal,
    _multinode_host_inventory,
    _networkx_graph_path,
    _optuna_study_empty,
    _PARSERINFO_METHODS,
    _qdrant_collection_config,
    _qdrant_deleted_false,
    _resource_collection_client,
    _source_text,
    _stub_init,
    _verify_secret,
    _YMD_METHODS,
)


def materialize(value: Any) -> Any:
    if isinstance(value, dict):
        value = _domain_coerced_payload(value)
        fixture = value.get("__fixture__")
        if fixture == "callable_id_of":
            return lambda schema: schema.get("$id") if isinstance(schema, dict) else None
        if fixture == "callable_items":
            return lambda schema: schema.items() if hasattr(schema, "items") else []
        if fixture == "callable_identity":
            return lambda value, *args, **kwargs: value
        if fixture == "callable_logging_record_message":
            return lambda record, *args, **kwargs: record.getMessage() if hasattr(record, "getMessage") else str(record)
        if fixture == "callable_noop":
            return lambda *args, **kwargs: None
        if fixture == "callable_float":
            return lambda value, *args, **kwargs: float(value)
        if fixture == "callable_true":
            return lambda *args, **kwargs: True
        if fixture == "callable_false":
            return lambda *args, **kwargs: False
        if fixture == "callable_empty_list":
            return lambda *args, **kwargs: []
        if fixture == "callable_empty_string":
            return lambda *args, **kwargs: ""
        if fixture == "empty_mapping":
            return {}
        if fixture == "callable_transport_result":
            return lambda *args, **kwargs: {"accepted": True}
        if fixture == "callable_declared_model":
            payload = {"__fixture__": "declared_model", "fields": value.get("fields", {})}
            return lambda *args, **kwargs: materialize(payload)
        if fixture == "safe_method_attribute":
            return _SafeMethodAttribute()
        if fixture == "safe_symbolic_attribute":
            return _SafeSymbolicAttribute()
        if fixture == "event_detail_envelope":
            return type("Event", (), {"detail": {"module_name": "not_loaded"}})()
        if fixture == "resource_collection_client":
            return _resource_collection_client()
        if fixture == "multinode_host_inventory":
            return _multinode_host_inventory()
        if fixture == "callable_batch_ids":
            return lambda *args, **kwargs: ["batch-id"]
        if fixture == "callable_column_names":
            return lambda *args, **kwargs: ["column"]
        if fixture == "callable_ge_parameter_value":
            return lambda *args, **kwargs: [] if kwargs.get("expected_return_type") is list else "sample"
        if fixture == "callable_ge_validator":
            return lambda *args, **kwargs: materialize({"__fixture__": "ge_validator"})
        if fixture == "callable_gradio_special_args":
            return lambda *args, **kwargs: (None, None, None, [])
        if fixture == "callable_append_unique_suffix":
            return lambda value, existing=None: value
        if fixture == "gradio_local_context":
            return type("LocalContext", (), {"renderable": type("ContextVar", (), {"get": lambda self, default=None: default})()})
        if fixture == "gradio_block_function_class":
            return type("BlockFunction", (), {"__init__": _gradio_block_function_init})
        if fixture == "gradio_root_block":
            return type("RootBlock", (), {"current_page": "", "pages": []})()
        if fixture == "ge_validator":
            return type("Validator", (), {"get_metric": lambda self, *args, **kwargs: ["column"]})()
        if fixture == "ge_semantic_filter":
            return type("SemanticFilter", (), {"table_column_name_to_inferred_semantic_domain_type_map": {}})()
        if fixture == "module_getattr_stub":
            return lambda name: type(str(name), (), {})
        if fixture == "stub_class":
            return type("AcceptanceStub", (), {"__init__": _stub_init, "model_dump_json": lambda self, *args, **kwargs: "{}"})
        if fixture == "str_enum_class":
            return _AcceptanceStrEnum
        if fixture == "stub_request_class":
            return type("JSONRPCRequest", (), {"method": "", "params": {}, "id": "1"})
        if fixture == "declared_model":
            fields = {str(key): materialize(item) for key, item in dict(value.get("fields") or {}).items()}
            return type(str(value.get("type") or "AcceptanceModel"), (), fields)()
        if fixture == "logging_log_record":
            return __import__("logging").LogRecord("acceptance", 20, "", 0, "sample", (), None)
        if fixture == "jsonrpc_adapter":
            return type("Adapter", (), {"validate_python": lambda self, value, **kwargs: value})()
        if fixture == "click_context_noop":
            return type("ClickContext", (), {"invoke": lambda self, *args, **kwargs: None, "meta": {}, "call_on_close": lambda self, value: None})()
        if fixture == "logger_noop":
            return type("Logger", (), {"debug": lambda self, *args, **kwargs: None})()
        if fixture == "jupyter_busy_kernel_manager":
            return type("KernelManager", (), {"execution_state": "busy"})()
        if fixture == "hatch_environment_minimal":
            return _hatch_environment_minimal()
        if fixture == "optuna_study_empty":
            return _optuna_study_empty()
        if fixture == "datasette_minimal":
            return _datasette_minimal()
        if fixture == "chroma_search_client":
            return _chroma_search_client()
        if fixture == "chroma_collection_model":
            return type("ChromaCollectionModel", (), {"id": "collection-id", "tenant": "default_tenant", "database": "default_database"})()
        if fixture == "hatch_virtual_environment_class":
            return type("VirtualEnvironment", (), {})
        if fixture == "crypt_context_class":
            return type("CryptContext", (), {"__init__": _stub_init, "verify": _verify_secret, "hash": _hash_secret})
        if fixture == "configparser_flake8_empty":
            parser = __import__("configparser").RawConfigParser()
            parser.add_section("flake8:local-plugins")
            return parser
        if fixture == "bytes_io_empty":
            return __import__("io").BytesIO(b"")
        if fixture == "datetime_utc":
            return __import__("datetime").datetime(2026, 1, 2, 3, 4, 5, tzinfo=__import__("datetime").timezone.utc)
        if fixture == "python_type_str":
            return str
        if fixture in {"bytes_empty", "bytes_literal"}:
            return bytes.fromhex(str(value.get("hex") or ""))
        if fixture == "numpy_array":
            return __import__("numpy").asarray(value.get("items") or [0.0, 1.0])
        if fixture == "pandas_dataframe":
            pandas = __import__("pandas")
            return pandas.DataFrame({"numeric": [1.0, 2.0], "category": ["a", "b"]})
        if fixture == "http_response_ok":
            return type("AcceptanceResponse", (), {"status_code": 200})()
        if fixture == "torch_tensor_zeros":
            shape = tuple(int(item) for item in value.get("shape") or [1])
            try:
                return __import__("torch").zeros(shape)
            except (ImportError, RuntimeError):
                return _TensorShapeProxy(shape)
        if fixture == "dateutil_parserinfo_minimal":
            return type("Info", (), _PARSERINFO_METHODS)()
        if fixture == "dateutil_result":
            return type("Result", (), {"hour": None, "minute": None, "second": None, "microsecond": None})()
        if fixture == "dateutil_ymd":
            return type("YMD", (list,), _YMD_METHODS)()
        if fixture == "pytest_source_minimal":
            return type("Source", (), {"lines": ["x = 1"], "raw_lines": ["x = 1"], "__str__": _source_text})()
        if fixture == "networkx_graph_path":
            return _networkx_graph_path()
        if fixture == "record_row_empty":
            row = type("RecordRow", (dict,), {})()
            row.data = {}
            return row
        if fixture == "readable_temp_path":
            from .executable_acceptance_path_fixtures import readable_temp_path
            return readable_temp_path()
        if fixture == "temporary_directory":
            return __import__("runtime.executable_acceptance_path_fixtures", fromlist=["temporary_directory"]).temporary_directory()
        if fixture == "delimited_text_path":
            from .executable_acceptance_path_fixtures import delimited_text_path
            return delimited_text_path(str(value.get("delimiter") or ","), int(value.get("columns") or 1))
        if fixture == "python_module_path":
            from .executable_acceptance_path_fixtures import python_module_path
            return python_module_path(dict(value.get("fields") or {}))
        if fixture == "noop_condition":
            return _NoopCondition()
        if fixture == "qdrant_collection_config":
            return _qdrant_collection_config()
        if fixture == "qdrant_deleted_false":
            return _qdrant_deleted_false()
        if fixture == "qdrant_deleted_per_vector":
            return {"": _qdrant_deleted_false()}
        if fixture == "qdrant_dense_vectors":
            return {"": __import__("numpy").array([[1.0, 0.0]], dtype="float32")}
        if fixture == "numpy_cube":
            return __import__("numpy").array([[[0.0], [1.0]], [[0.0], [0.0]]], dtype="float32")
        if fixture == "asgi_request_no_accept":
            return type(
                "Request",
                (),
                {
                    "method": "GET",
                    "POST": {},
                    "headers": {},
                    "receive": _asgi_receive_empty,
                    "body": _asgi_body_empty,
                },
            )()
        if fixture == "asgi_receive_empty":
            return _asgi_receive_empty
        if fixture == "asgi_send_noop":
            return _asgi_send_noop
        if fixture == "async_writer_noop":
            return type("Writer", (), {"send": _asgi_send_noop})()
        if fixture == "pants_all_environment_targets":
            return {"local": _PantsTarget()}
        return {key: materialize(_coerced_field_value(str(key), item)) for key, item in value.items()}
    if isinstance(value, list):
        return [materialize(item) for item in value]
    return value


__all__ = ["materialize"]
