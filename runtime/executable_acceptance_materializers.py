"""Materialize config-backed executable acceptance fixtures."""

from __future__ import annotations

from typing import Any

from .executable_acceptance_policy import sample_value


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
        if fixture == "callable_noop":
            return lambda *args, **kwargs: None
        if fixture == "callable_float":
            return lambda value, *args, **kwargs: float(value)
        if fixture == "callable_true":
            return lambda *args, **kwargs: True
        if fixture == "callable_empty_list":
            return lambda *args, **kwargs: []
        if fixture == "callable_empty_string":
            return lambda *args, **kwargs: ""
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
        if fixture == "stub_request_class":
            return type("JSONRPCRequest", (), {"method": "", "params": {}, "id": "1"})
        if fixture == "declared_model":
            fields = {str(key): materialize(item) for key, item in dict(value.get("fields") or {}).items()}
            return type(str(value.get("type") or "AcceptanceModel"), (), fields)()
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
        if fixture == "bytes_empty":
            return b""
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


def _stub_init(self: Any, *args: Any, **kwargs: Any) -> None:
    self.__dict__.update(kwargs)


def _verify_secret(self: Any, plain: Any, encoded: Any, *args: Any, **kwargs: Any) -> bool:
    return bool(plain) and bool(encoded)


def _hash_secret(self: Any, value: Any, *args: Any, **kwargs: Any) -> str:
    return f"acceptance-hash:{value}"


def _gradio_block_function_init(self: Any, fn: Any = None, inputs: Any = None, outputs: Any = None, *args: Any, **kwargs: Any) -> None:
    self.fn, self.inputs, self.outputs = fn, inputs, outputs
    self.__dict__.update(kwargs)


async def _asgi_receive_empty(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _asgi_body_empty(*args: Any, **kwargs: Any) -> bytes:
    return b"{}"


async def _asgi_send_noop(*args: Any, **kwargs: Any) -> None:
    return None


def _domain_coerced_payload(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("template") == "sample" and "image" in value:
        value = {**value, "template": [[1.0]], "pad_input": False, "mode": "constant", "constant_values": 0}
    if "image" in value and "template" in value:
        np = __import__("numpy")
        value = {**value, "image": np.array(value["image"], dtype="float32"), "template": np.array(value["template"], dtype="float32")}
    return value


def _coerced_field_value(field_name: str, value: Any) -> Any:
    placeholder = value == "sample" if isinstance(value, str) else isinstance(value, (dict, list)) and not value
    if not placeholder:
        return value
    replacement = sample_value("", field_name)
    configured = replacement != "sample" if isinstance(replacement, str) else not (
        isinstance(replacement, (dict, list)) and not replacement
    )
    return replacement if configured else value


def _source_text(self: Any) -> str:
    return "\n".join(self.lines)


def _networkx_graph_path() -> Any:
    graph = __import__("networkx").Graph()
    graph.add_edge("a", "b", label="edge")
    graph.nodes["a"]["label"] = "a"
    graph.nodes["b"]["label"] = "b"
    return graph


def _hatch_environment_minimal() -> Any:
    virtual_environment = _install_hatch_virtual_profile()
    return type(
        "Environment",
        (virtual_environment,),
        {
            "features": (),
            "dependency_groups": (),
            "dependencies": ("sample>=1",),
            "additional_dependencies": (),
            "skip_install": False,
            "use_uv": False,
            "root": __import__("pathlib").Path("."),
        },
    )()


def _install_hatch_virtual_profile() -> type:
    import sys
    import types

    module = types.ModuleType("hatch.env.virtual")
    cls = type("VirtualEnvironment", (), {})
    module.VirtualEnvironment = cls
    sys.modules["hatch.env.virtual"] = module
    parent = sys.modules.get("hatch.env")
    if parent is not None:
        setattr(parent, "virtual", module)
    return cls


def _optuna_study_empty() -> Any:
    return type("Study", (), {"get_trials": lambda self, *args, **kwargs: []})()


async def _noop_execute_write(*args: Any, **kwargs: Any) -> None:
    return None


def _datasette_minimal() -> Any:
    database = type("Database", (), {"execute_write": _noop_execute_write})()
    return type("Datasette", (), {"get_internal_database": lambda self: database})()


async def _noop_chroma_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ids": [], "documents": [], "metadatas": [], "scores": []}


def _chroma_search_client() -> Any:
    return type("ChromaSearchClient", (), {"_search": _noop_chroma_search})()


def _resource_collection_client() -> Any:
    projects = type("Projects", (), {"list": lambda self, *args, **kwargs: []})()
    group = type("Group", (), {"projects": projects})()
    groups = type("Groups", (), {"get": lambda self, group_id: group})()
    return type("ResourceClient", (), {"groups": groups})()


def _multinode_host_inventory() -> dict[str, dict[str, str]]:
    return {
        f"node-{index}": {
            "public": f"192.0.2.{index}",
            "internal": f"10.0.0.{index}",
            "data": f"10.1.0.{index}",
        }
        for index in range(1, 4)
    }


def _qdrant_collection_config() -> Any:
    try:
        distance = __import__("qdrant_client.http.models", fromlist=["Distance"]).Distance.COSINE
    except ModuleNotFoundError:
        distance = "Cosine"
    params = type("VectorParams", (), {"distance": distance})()
    return type("CollectionConfig", (), {"vectors": {"": params}, "sparse_vectors": None})()


def _qdrant_deleted_false() -> Any:
    return __import__("numpy").array([False], dtype=bool)


_PARSERINFO_METHODS = {
    "hms": lambda self, value: None,
    "jump": lambda self, value: False,
    "ampm": lambda self, value: None,
    "month": lambda self, value: None,
}
_YMD_METHODS = {
    "append": lambda self, value, label=None: list.append(self, value),
    "could_be_day": lambda self, value: True,
}


class _NoopCondition:
    def __enter__(self) -> "_NoopCondition":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def notify_all(self) -> None:
        return None


class _SafeMethodAttribute:
    def __init__(self, operation: str = "") -> None:
        self.operation = operation

    def __call__(self, *args: Any, **kwargs: Any) -> "_SafeMethodAttribute":
        if self.operation in {"read", "recv", "receive"}:
            return None
        return self

    def __getattr__(self, name: str) -> "_SafeMethodAttribute":
        return _SafeMethodAttribute(name)

    def __getitem__(self, key: Any) -> "_SafeMethodAttribute":
        return self

    def __iter__(self):
        return iter(())

    def __next__(self):
        raise StopIteration

    def __bool__(self) -> bool:
        return False

    def __await__(self):
        async def completed() -> "_SafeMethodAttribute":
            return self

        return completed().__await__()


class _SafeSymbolicAttribute(_SafeMethodAttribute):
    def __call__(self, *args: Any, **kwargs: Any) -> "_SafeSymbolicAttribute":
        return self

    def __getattr__(self, name: str) -> "_SafeSymbolicAttribute":
        return self

    def __mul__(self, other: Any) -> "_SafeSymbolicAttribute":
        return self

    __rmul__ = __mul__
    __add__ = __mul__
    __radd__ = __mul__
    __sub__ = __mul__
    __rsub__ = __mul__
    __truediv__ = __mul__
    __rtruediv__ = __mul__


class _ContainsAll:
    def __contains__(self, item: Any) -> bool:
        return True


class _PantsTarget:
    address = type("Address", (), {"spec": "//:local"})()
    def has_field(self, field: Any) -> bool:
        return True
    def __getitem__(self, field: Any) -> Any:
        return type("FieldValue", (), {"value": _ContainsAll()})()
