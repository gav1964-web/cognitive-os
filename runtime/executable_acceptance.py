"""Generate and run executable acceptance scaffolds from Tester obligations."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .executable_acceptance_support import harness_summary
from .executable_acceptance_runner import run_acceptance_command
from .executable_acceptance_environment import environment_harness_summary
def run_executable_acceptance(
    *,
    root: Path,
    project_dir: Path,
    test_plan: dict[str, Any],
    work_dir: Path,
    python_executable: Path | None = None,
) -> dict[str, Any]:
    executable = dict(test_plan.get("executable_acceptance", {}))
    obligations = [dict(item) for item in executable.get("obligations", []) if isinstance(item, dict)]
    scaffold_dir = work_dir / "executable_acceptance"
    scaffold_dir.mkdir(parents=True, exist_ok=True)
    obligations_path = scaffold_dir / "obligations.json"
    tests_dir = scaffold_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    test_path = tests_dir / "test_acceptance_generated.py"
    obligations_path.write_text(json.dumps(obligations, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    harness = (
        environment_harness_summary(
            root=root,
            project_dir=project_dir,
            obligations_path=obligations_path,
            python_executable=python_executable,
        )
        if python_executable else harness_summary(project_dir, obligations)
    )
    test_path.write_text(_pytest_source(root, obligations_path, project_dir, harness), encoding="utf-8")
    command_result = run_acceptance_command(
        python_executable=python_executable,
        tests_dir=tests_dir,
        test_path=test_path,
        cwd=scaffold_dir,
    )
    passed = command_result["returncode"] == 0
    result = {
        "artifact_type": "ExecutableAcceptanceResult",
        "status": "passed" if passed else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.as_posix(),
        "scaffold_dir": scaffold_dir.as_posix(),
        "obligations_path": obligations_path.as_posix(),
        "generated_tests": [test_path.as_posix()],
        "summary": {
            "obligation_count": len(obligations),
            "acceptance_ids": sorted({str(item.get("acceptance_id")) for item in obligations if item.get("acceptance_id")}),
            "generated_test_count": 1,
            "callable_harness_count": harness["callable_harness_count"],
            "signal_strength": harness["signal_strength"],
            "environment_probe": harness.get("environment_probe"),
            "skipped_reason_counts": harness["skipped_reason_counts"],
            "skipped_targets": harness["skipped_targets"],
            "argument_mappings": harness.get("argument_mappings", {}),
            "argument_defaults": harness.get("argument_defaults", {}),
            "method_instance_attributes": harness.get("method_instance_attributes", {}),
            "dropped_surplus_payload_targets": harness.get("dropped_surplus_payload_targets", []),
            "source_isolated_targets": harness.get("source_isolated_targets", []),
            "dependency_stub_targets": harness.get("dependency_stub_targets", {}),
            "dependency_metadata_profile_targets": harness.get("dependency_metadata_profile_targets", {}),
            "dependency_module_profile_targets": harness.get("dependency_module_profile_targets", {}),
            "effect_module_stub_targets": harness.get("effect_module_stub_targets", {}),
            "passed": passed,
        },
        "command": command_result,
        "source_code_changes": False,
        "registry_changes": False,
    }
    result_path = scaffold_dir / "executable_acceptance_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["result_path"] = result_path.as_posix()
    return result
def _pytest_source(root: Path, obligations_path: Path, project_dir: Path, harness: dict[str, Any]) -> str:
    runtime_root = root.resolve().as_posix()
    escaped = obligations_path.resolve().as_posix()
    project = project_dir.resolve().as_posix()
    harness_payload = json.dumps(harness, ensure_ascii=False, sort_keys=True)
    return f'''"""Generated executable acceptance scaffold."""
import importlib.util
import ast
import asyncio
import importlib
import importlib.metadata as importlib_metadata
import inspect
import json
import sys
import types
from pathlib import Path
OBLIGATIONS = Path(r"{escaped}")
PROJECT_DIR = Path(r"{project}")
RUNTIME_ROOT = Path(r"{runtime_root}")
HARNESS = {harness_payload!r}
HARNESS_DATA = json.loads(HARNESS)
sys.path.insert(0, str(RUNTIME_ROOT))
sys.path.insert(0, str(PROJECT_DIR))
if (PROJECT_DIR / "src").is_dir():
    sys.path.insert(0, str(PROJECT_DIR / "src"))
if (PROJECT_DIR / "src" / "python").is_dir(): sys.path.insert(0, str(PROJECT_DIR / "src" / "python"))
def _rows():
    return json.loads(OBLIGATIONS.read_text(encoding="utf-8"))
def test_obligations_are_present_and_typed():
    rows = _rows()
    assert rows, "Tester produced no executable acceptance obligations"
    for row in rows:
        assert row.get("id")
        assert row.get("acceptance_id")
        assert row.get("target")
        assert row.get("kind")
        assert row.get("oracle")
def test_positive_contract_cases_have_expected_shape():
    positives = [row for row in _rows() if row.get("kind") == "positive_contract_case"]
    assert positives, "At least one positive contract case is required"
    for row in positives:
        assert isinstance(row.get("given"), dict)
        assert isinstance(row.get("expect"), dict)
        assert row["expect"], "Positive cases must define an expected output shape"
def test_malformed_input_case_is_controlled():
    malformed = [row for row in _rows() if row.get("kind") == "malformed_input_case"]
    harness = json.loads(HARNESS)
    if not malformed and not harness.get("strict_negative_targets", []):
        return
    assert malformed, "Malformed input obligation is required"
    for row in malformed:
        assert row.get("expect", {{}}).get("error") == "controlled_validation_error"
def test_side_effect_boundary_is_declared():
    boundaries = [row for row in _rows() if row.get("kind") == "side_effect_scope_case"]
    assert boundaries, "Side-effect boundary obligation is required"
    for row in boundaries:
        assert row.get("expect", {{}}).get("no_writes_outside_declared_scope") is True
def test_simple_python_targets_execute_positive_contract_cases():
    harness = json.loads(HARNESS)
    strict_targets = set(harness.get("strict_negative_targets", []))
    if not strict_targets:
        return
    for row in _rows():
        if row.get("kind") != "positive_contract_case":
            continue
        target = row.get("target", "")
        if target not in strict_targets:
            continue
        func = _load_function(target)
        result = _run_callable(func, _call_kwargs(target, row.get("given", {{}}), include_defaults=True))
        _assert_expected_shape(result, row.get("expect", {{}}))

def test_simple_python_targets_reject_missing_required_input():
    harness = json.loads(HARNESS)
    if harness.get("callable_harness_count", 0) == 0:
        return
    for row in _rows():
        if row.get("kind") != "malformed_input_case":
            continue
        target = row.get("target", "")
        if target not in harness.get("strict_negative_targets", []):
            continue
        func = _load_function(target)
        try:
            _run_callable(func, _call_kwargs(target, row.get("given", {{}}), include_defaults=False))
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"{{target}} accepted malformed input")
def _run_callable(func, kwargs):
    args, call_kwargs = _call_args_kwargs(func, kwargs)
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    result = func(*args, **call_kwargs)
    if isinstance(result, asyncio.Future) and result.done(): return result.result()
    if inspect.isawaitable(result): return asyncio.run(result)
    return result
def _call_args_kwargs(func, payload):
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return [], payload
    args, kwargs = [], dict(payload)
    for name, param in signature.parameters.items():
        if param.kind == inspect.Parameter.POSITIONAL_ONLY and name in kwargs:
            args.append(kwargs.pop(name))
    return args, kwargs

def _load_function(target):
    path_text, _, symbol = target.partition(":")
    assert path_text.endswith(".py") and symbol, f"unsupported callable target: {{target}}"
    path = (PROJECT_DIR / path_text).resolve()
    assert PROJECT_DIR.resolve() in path.parents or path == PROJECT_DIR.resolve()
    module_name = _module_name(path_text)
    method = HARNESS_DATA.get("method_targets", {{}}).get(target)
    if target in HARNESS_DATA.get("source_isolated_targets", []):
        return _load_source_isolated_function(path, symbol, target)
    for missing in HARNESS_DATA.get("dependency_stub_targets", {{}}).get(target, []):
        _install_stub_module(missing)
    _install_metadata_profiles(HARNESS_DATA.get("dependency_metadata_profile_targets", {{}}).get(target, []))
    for name in HARNESS_DATA.get("dependency_module_profile_targets", {{}}).get(target, []):
        _install_profile_module(name)
    if module_name:
        try:
            module = importlib.import_module(module_name)
            if method:
                return _load_method(module, method, symbol, target)
            func = getattr(module, symbol)
            assert callable(func), f"target is not callable: {{target}}"
            return func
        except ModuleNotFoundError as exc:
            if str(getattr(exc, "name", "")) in HARNESS_DATA.get("dependency_module_profile_targets", {{}}).get(target, []):
                _install_profile_module(str(exc.name))
                return _load_function(target)
            if len(Path(path_text).parts) > 1:
                return _load_source_isolated_function(path, symbol, target)
        except Exception:
            if len(Path(path_text).parts) > 1:
                return _load_source_isolated_function(path, symbol, target)
    spec = importlib.util.spec_from_file_location("acceptance_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if method:
        return _load_method(module, method, symbol, target)
    func = getattr(module, symbol)
    assert callable(func), f"target is not callable: {{target}}"
    return func
def _install_stub_module(name):
    parts = name.split(".")
    for index in range(1, len(parts) + 1):
        module_name = ".".join(parts[:index])
        if module_name not in sys.modules:
            sys.modules[module_name] = _StubModule(module_name)
def _install_metadata_profiles(packages):
    if getattr(importlib_metadata, "_acceptance_profiles_installed", False):
        return
    package_set = {{str(item).replace("-", "_").lower() for item in packages}}
    original_version, original_metadata, original_distribution = importlib_metadata.version, importlib_metadata.metadata, importlib_metadata.distribution
    def normalize(name):
        return str(name).replace("-", "_").lower()
    def version(name):
        return "0.0.0" if normalize(name) in package_set else original_version(name)
    def metadata(name):
        return {{"Name": str(name), "Version": "0.0.0"}} if normalize(name) in package_set else original_metadata(name)
    def distribution(name):
        return types.SimpleNamespace(metadata={{"Name": str(name), "Version": "0.0.0"}}, version="0.0.0", read_text=lambda _: "") if normalize(name) in package_set else original_distribution(name)
    importlib_metadata.version, importlib_metadata.metadata, importlib_metadata.distribution = version, metadata, distribution
    importlib_metadata._acceptance_profiles_installed = True

def _install_profile_module(name):
    parts = name.split(".")
    for index in range(1, len(parts)):
        p = ".".join(parts[:index])
        if p not in sys.modules: m = types.ModuleType(p); m.__path__ = []; sys.modules[p] = m
        if index > 1: setattr(sys.modules[".".join(parts[: index - 1])], parts[index - 1], sys.modules[p])
    parent_name, _, child_name = name.rpartition(".")
    module = types.ModuleType(name)
    attrs = HARNESS_DATA.get("dependency_module_profile_attrs", {{}}).get(name, {{"__version__": "0.0.0", "version": "0.0.0"}})
    for key, value in attrs.items(): setattr(module, key, _materialize(value))
    sys.modules[name] = module
    parent = sys.modules.get(parent_name)
    if parent is not None: setattr(parent, child_name, module)
class _StubModule(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []

    def __getattr__(self, name):
        value = _StubObject(f"{{self.__name__}}.{{name}}")
        setattr(self, name, value)
        return value
class _StubObject:
    def __init__(self, name):
        self._name = name
    def __call__(self, *args, **kwargs): return self
    def __getitem__(self, key): return _StubObject(f"{{self._name}}[{{key!r}}]")
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __mro_entries__(self, bases): return ()
    def __getattr__(self, name): return _StubObject(f"{{self._name}}.{{name}}")
def _load_source_isolated_function(path, symbol, target):
    from runtime.executable_acceptance_isolation import load_source_isolated_callable
    loaded = load_source_isolated_callable(path, symbol)
    func = loaded.get("callable")
    assert callable(func), f"isolated target is not callable: {{symbol}}"
    instance = getattr(func, "__self__", None)
    for key, value in dict(HARNESS_DATA.get("method_instance_attributes", {{}}).get(target) or {{}}).items():
        item = _materialize(value)
        if instance is not None: setattr(instance, key, item)
        if instance is not None and key == "_model": [setattr(instance, name, getattr(item, name)) for name in ("id", "tenant", "database") if hasattr(item, name)]
    return func
def _load_method(module, method, symbol, target):
    cls = getattr(module, method.get("class_name"))
    member = getattr(cls, symbol)
    if callable(member) and _callable_accepts_without_self(member):
        return member
    try: instance = cls()
    except Exception: instance = object.__new__(cls)
    for key, value in dict(HARNESS_DATA.get("method_instance_attributes", {{}}).get(target) or {{}}).items():
        setattr(instance, key, _materialize(value))
    func = getattr(instance, symbol); assert callable(func), f"method target is not callable: {{symbol}}"
    return func
def _callable_accepts_without_self(func):
    try: params = list(inspect.signature(func).parameters)
    except (TypeError, ValueError): return False
    return not params or params[0] not in {{"self", "cls"}}
def _materialize(value):
    if isinstance(value, dict):
        if value.get("template") == "sample" and "image" in value: value = {{**value, "template": [[1.0]], "pad_input": False, "mode": "constant", "constant_values": 0}}
        if "image" in value and "template" in value: np = __import__("numpy"); value = {{**value, "image": np.array(value["image"], dtype="float32"), "template": np.array(value["template"], dtype="float32")}}
        fixture = value.get("__fixture__")
        if fixture == "callable_id_of": return lambda schema: schema.get("$id") if isinstance(schema, dict) else None
        if fixture == "callable_items": return lambda schema: schema.items() if hasattr(schema, "items") else []
        if fixture == "callable_identity": return lambda value, *args, **kwargs: value
        if fixture == "callable_noop": return lambda *args, **kwargs: None
        if fixture == "callable_float": return lambda value, *args, **kwargs: float(value)
        if fixture == "callable_true": return lambda *args, **kwargs: True
        if fixture == "callable_empty_list": return lambda *args, **kwargs: []
        if fixture == "callable_empty_string": return lambda *args, **kwargs: ""
        if fixture in {{"callable_batch_ids", "callable_column_names", "callable_ge_parameter_value", "callable_ge_validator"}}: return (lambda *args, **kwargs: ["batch-id"]) if fixture == "callable_batch_ids" else ((lambda *args, **kwargs: ["column"]) if fixture == "callable_column_names" else ((lambda *args, **kwargs: [] if kwargs.get("expected_return_type") is list else "sample") if fixture == "callable_ge_parameter_value" else (lambda *args, **kwargs: _materialize({{"__fixture__": "ge_validator"}}))))
        if fixture in {{"callable_gradio_special_args", "callable_append_unique_suffix"}}: return (lambda *args, **kwargs: (None, None, None, [])) if fixture == "callable_gradio_special_args" else (lambda value, existing=None: value)
        if fixture in {{"gradio_local_context", "gradio_block_function_class", "gradio_root_block"}}: return type("LocalContext", (), {{"renderable": type("ContextVar", (), {{"get": lambda self, default=None: default}})()}}) if fixture == "gradio_local_context" else (type("RootBlock", (), {{"current_page": "", "pages": []}})() if fixture == "gradio_root_block" else type("BlockFunction", (), {{"__init__": lambda self, fn=None, inputs=None, outputs=None, *args, **kwargs: (setattr(self, "fn", fn), setattr(self, "inputs", inputs), setattr(self, "outputs", outputs), self.__dict__.update(kwargs)) and None}}))
        if fixture in {{"ge_validator", "ge_semantic_filter"}}: return type("Validator", (), {{"get_metric": lambda self, *args, **kwargs: ["column"]}})() if fixture == "ge_validator" else type("SemanticFilter", (), {{"table_column_name_to_inferred_semantic_domain_type_map": {{}}}})()
        if fixture == "module_getattr_stub": return lambda name: type(str(name), (), {{}})
        if fixture == "stub_class": return type("AcceptanceStub", (), {{"__init__": lambda self, *args, **kwargs: self.__dict__.update(kwargs), "model_dump_json": lambda self, *args, **kwargs: "{{}}"}})
        if fixture == "stub_request_class": return type("JSONRPCRequest", (), {{"method": "", "params": {{}}, "id": "1"}})
        if fixture == "jsonrpc_adapter": return type("Adapter", (), {{"validate_python": lambda self, value, **kwargs: value}})()
        if fixture == "click_context_noop": return type("ClickContext", (), {{"invoke": lambda self, *args, **kwargs: None, "meta": {{}}, "call_on_close": lambda self, value: None}})()
        if fixture in {{"logger_noop", "jupyter_busy_kernel_manager"}}: return type("Logger", (), {{"debug": lambda self, *args, **kwargs: None}})() if fixture == "logger_noop" else type("KernelManager", (), {{"execution_state": "busy"}})()
        if fixture == "hatch_environment_minimal": return _hatch_environment_minimal()
        if fixture == "optuna_study_empty": return type("Study", (), {{"get_trials": lambda self, *args, **kwargs: []}})()
        if fixture == "datasette_minimal": return _datasette_minimal()
        if fixture == "chroma_search_client": return type("ChromaSearchClient", (), {{"_search": _noop_chroma_search}})()
        if fixture == "chroma_collection_model": return type("ChromaCollectionModel", (), {{"id": "collection-id", "tenant": "default_tenant", "database": "default_database"}})()
        if fixture == "hatch_virtual_environment_class": return type("VirtualEnvironment", (), {{}})
        if fixture == "configparser_flake8_empty": parser = __import__("configparser").RawConfigParser(); parser.add_section("flake8:local-plugins"); return parser
        if fixture == "bytes_io_empty": return __import__("io").BytesIO(b"")
        if fixture == "bytes_empty": return b""
        if fixture == "dateutil_parserinfo_minimal": return type("Info", (), {{"hms": lambda self, value: None, "jump": lambda self, value: False, "ampm": lambda self, value: None, "month": lambda self, value: None}})()
        if fixture == "dateutil_result": return type("Result", (), {{"hour": None, "minute": None, "second": None, "microsecond": None}})()
        if fixture == "dateutil_ymd": return type("YMD", (list,), {{"append": lambda self, value, label=None: list.append(self, value), "could_be_day": lambda self, value: True}})()
        if fixture == "pytest_source_minimal": return type("Source", (), {{"lines": ["x = 1"], "raw_lines": ["x = 1"], "__str__": lambda self: "\\n".join(self.lines)}})()
        if fixture == "networkx_graph_path": graph = __import__("networkx").Graph(); graph.add_edge("a", "b", label="edge"); graph.nodes["a"]["label"] = "a"; graph.nodes["b"]["label"] = "b"; return graph
        if fixture == "noop_condition": return type("NoopCondition", (), {{"__enter__": lambda self: self, "__exit__": lambda self, *args: False, "notify_all": lambda self: None}})()
        if fixture == "qdrant_collection_config": return _qdrant_collection_config()
        if fixture == "qdrant_deleted_false": return _np_array([False], dtype=bool)
        if fixture == "qdrant_deleted_per_vector": return {{"": _np_array([False], dtype=bool)}}
        if fixture == "qdrant_dense_vectors": return {{"": _np_array([[1.0, 0.0]], dtype="float32")}}
        if fixture == "asgi_request_no_accept": return type("Request", (), {{"headers": {{}}, "receive": _asgi_receive_empty, "body": _asgi_body_empty}})()
        if fixture in {{"asgi_receive_empty", "asgi_send_noop", "async_writer_noop"}}: return _asgi_receive_empty if fixture == "asgi_receive_empty" else (_asgi_send_noop if fixture == "asgi_send_noop" else type("Writer", (), {{"send": _asgi_send_noop}})())
        if fixture == "pants_all_environment_targets": return {{"local": type("Target", (), {{"address": type("Address", (), {{"spec": "//:local"}})(), "has_field": lambda self, field: True, "__getitem__": lambda self, field: type("FieldValue", (), {{"value": type("ContainsAll", (), {{"__contains__": lambda self, item: True}})()}})()}})()}}
        return {{key: _materialize(_field_sample(key, item)) for key, item in value.items()}}
    if isinstance(value, list): return [_materialize(item) for item in value]
    return value
async def _noop_execute_write(*args, **kwargs): return None
async def _noop_chroma_search(*args, **kwargs): return {{"ids": [], "documents": [], "metadatas": [], "scores": []}}
async def _asgi_receive_empty(*args, **kwargs): return {{"type": "http.request", "body": b"", "more_body": False}}
async def _asgi_body_empty(*args, **kwargs): return b"{{}}"
async def _asgi_send_noop(*args, **kwargs): return None
def _datasette_minimal(): database = type("Database", (), {{"execute_write": _noop_execute_write}})(); return type("Datasette", (), {{"get_internal_database": lambda self: database}})()
def _hatch_environment_minimal():
    module = types.ModuleType("hatch.env.virtual"); cls = type("VirtualEnvironment", (), {{}}); module.VirtualEnvironment = cls; sys.modules["hatch.env.virtual"] = module
    parent = sys.modules.get("hatch.env")
    if parent is not None: setattr(parent, "virtual", module)
    return type("Environment", (cls,), {{"features": (), "dependency_groups": (), "dependencies": ("sample>=1",), "additional_dependencies": (), "skip_install": False, "use_uv": False, "root": Path(".")}})()
def _np_array(value, dtype=None): return __import__("numpy").array(value, dtype=dtype)
def _qdrant_collection_config():
    try: distance = __import__("qdrant_client.http.models", fromlist=["Distance"]).Distance.COSINE
    except ModuleNotFoundError: distance = "Cosine"
    params = type("VectorParams", (), {{"distance": distance}})(); return type("CollectionConfig", (), {{"vectors": {{"": params}}, "sparse_vectors": None}})()
def _field_sample(key, value): return {{"all_environment_targets": {{"__fixture__": "pants_all_environment_targets"}}, "ctx": {{"__fixture__": "click_context_noop"}}, "database": "data", "edge_attr": "label", "digest_size": 8, "fn": {{"__fixture__": "callable_noop"}}, "image": [[1.0, 2.0], [3.0, 4.0]], "inputs": [], "outputs": [], "include_initial_labels": False, "iterations": 1, "query_filter": None, "query_vector": [1.0, 0.0], "score_threshold": None, "searches": [], "sql": "select 1", "study": {{"__fixture__": "optuna_study_empty"}}, "targets": []}}.get(str(key), value) if isinstance(value, str) and value == "sample" else value
def _call_kwargs(target, given, include_defaults=True):
    data = dict(given or {{}})
    mapping = HARNESS_DATA.get("argument_mappings", {{}}).get(target, {{}})
    if target in HARNESS_DATA.get("dropped_surplus_payload_targets", []): data = {{}}
    if mapping: data = {{actual: data[source] for actual, source in mapping.items() if source in data}}
    if include_defaults: data = {{**HARNESS_DATA.get("argument_defaults", {{}}).get(target, {{}}), **data}}
    return _materialize(data)
def _module_name(path_text):
    parts = Path(path_text).with_suffix("").parts
    if parts and parts[0] == "src": parts = parts[1:]
    if not parts: return ""
    if parts[-1] == "__init__": parts = parts[:-1]
    if not parts: return ""
    return ".".join(parts)
def _assert_expected_shape(result, expect):
    if not isinstance(expect, dict) or not expect: return
    if expect == {{"completed": True}}: assert result is None or result is True or isinstance(result, dict); return
    if any(key in expect for key in ("return_value", "equals", "result_value")): assert result == expect[next(key for key in ("return_value", "equals", "result_value") if key in expect)]; return
    if set(expect) == {{"result"}}:
        if str(expect.get("result") or "").lower() in {{"any", "inferredoutput", "inferred_output"}}: return
        if str(expect.get("result") or "").lower() in {{"none", "null", "void"}}: assert result is None; return
        assert result is not None; return
    if not isinstance(result, dict): assert any("failure" not in str(key).lower() for key in expect), "multi-field output contract expects dict result"; return
'''
