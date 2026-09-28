"""Fixture builders used by executable-acceptance materialization."""

from __future__ import annotations

import enum
from typing import Any

from .executable_acceptance_policy import sample_value


class _AcceptanceStrEnum(str, enum.Enum):
    pass


def _stub_init(self: Any, *args: Any, **kwargs: Any) -> None:
    self.__dict__.update(kwargs)


class _TensorShapeProxy:
    def __init__(self, shape: tuple[int, ...]) -> None:
        self.shape = shape

    def view(self, *shape: int) -> "_TensorShapeProxy":
        known = 1
        for item in shape:
            if item != -1:
                known *= item
        total = 1
        for item in self.shape:
            total *= item
        resolved = tuple(total // known if item == -1 else item for item in shape)
        return _TensorShapeProxy(resolved)

    def permute(self, *axes: int) -> "_TensorShapeProxy":
        return _TensorShapeProxy(tuple(self.shape[index] for index in axes))

    def contiguous(self) -> "_TensorShapeProxy":
        return self

    def __getitem__(self, key: Any) -> "_TensorShapeProxy":
        keys = key if isinstance(key, tuple) else (key,)
        shape = list(self.shape)
        for index, item in enumerate(keys):
            if index >= len(shape):
                break
            if isinstance(item, int):
                shape[index] = 0
            elif isinstance(item, slice) and item.stop is not None:
                shape[index] = min(shape[index], int(item.stop))
        return _TensorShapeProxy(tuple(item for item in shape if item > 0))


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
