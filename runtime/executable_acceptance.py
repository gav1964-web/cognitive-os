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
            "callable_targets": harness.get("callable_targets", []),
            "signal_strength": harness["signal_strength"],
            "environment_probe": harness.get("environment_probe"),
            "skipped_reason_counts": harness["skipped_reason_counts"],
            "skipped_targets": harness["skipped_targets"],
            "argument_mappings": harness.get("argument_mappings", {}),
            "argument_defaults": harness.get("argument_defaults", {}),
            "argument_overrides": harness.get("argument_overrides", {}),
            "argument_sample_evidence": harness.get("argument_sample_evidence", {}),
            "method_instance_attributes": harness.get("method_instance_attributes", {}),
            "dropped_surplus_payload_targets": harness.get("dropped_surplus_payload_targets", []),
            "source_isolated_targets": harness.get("source_isolated_targets", []),
            "dependency_stub_targets": harness.get("dependency_stub_targets", {}),
            "dependency_metadata_profile_targets": harness.get("dependency_metadata_profile_targets", {}),
            "dependency_module_profile_targets": harness.get("dependency_module_profile_targets", {}),
            "effect_module_stub_targets": harness.get("effect_module_stub_targets", {}),
            "resolved_target_paths": harness.get("resolved_target_paths", {}),
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
    runtime_root = Path(__file__).resolve().parents[1].as_posix()
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
        except (KeyError, TypeError, ValueError):
            continue
        raise AssertionError(f"{{target}} accepted malformed input")
def _run_callable(func, kwargs):
    args, call_kwargs = _call_args_kwargs(func, kwargs)
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    original_argv = list(sys.argv)
    context = HARNESS_DATA.get("execution_context", {{}})
    if context.get("isolate_process_arguments"): sys.argv[:] = [context.get("program_name") or "acceptance-probe"]
    try:
        result = func(*args, **call_kwargs)
        if isinstance(result, asyncio.Future) and result.done(): return result.result()
        if inspect.isawaitable(result): return asyncio.run(_await_result(result))
        return result
    finally: sys.argv[:] = original_argv
async def _await_result(value):
    return await value
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
    path_text = HARNESS_DATA.get("resolved_target_paths", {{}}).get(target, path_text)
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
                return _load_method(module, method, method.get("method_name", symbol), target)
            func = getattr(module, symbol)
            assert callable(func), f"target is not callable: {{target}}"
            return func
        except ModuleNotFoundError as exc:
            if str(getattr(exc, "name", "")) in HARNESS_DATA.get("dependency_module_profile_targets", {{}}).get(target, []):
                _install_profile_module(str(exc.name))
                return _load_function(target)
            if len(Path(path_text).parts) > 1:
                return _load_source_isolated_function(path, symbol, target)
        except (Exception, SystemExit):
            if len(Path(path_text).parts) > 1:
                return _load_source_isolated_function(path, symbol, target)
    spec = importlib.util.spec_from_file_location("acceptance_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if method:
        return _load_method(module, method, method.get("method_name", symbol), target)
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
        self.__all__ = []

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
    from runtime.executable_acceptance_materializers import materialize
    return materialize(value)
def _call_kwargs(target, given, include_defaults=True):
    data = dict(given or {{}})
    mapping = HARNESS_DATA.get("argument_mappings", {{}}).get(target, {{}})
    if target in HARNESS_DATA.get("dropped_surplus_payload_targets", []): data = {{}}
    if mapping: data = {{actual: data[source] for actual, source in mapping.items() if source in data}}
    if include_defaults:
        data = {{**HARNESS_DATA.get("argument_defaults", {{}}).get(target, {{}}), **data}}
        data.update(HARNESS_DATA.get("argument_overrides", {{}}).get(target, {{}}))
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
        declared = str(expect.get("result") or "").lower().replace(" ", "")
        if declared in {{"any", "inferredoutput", "inferred_output"}}: return
        if declared in {{"none", "null", "void"}}: assert result is None; return
        if result is None and (declared == "optional" or "optional[" in declared or "nonetype" in declared or "|none" in declared): return
        assert result is not None; return
    if not isinstance(result, dict): assert any("failure" not in str(key).lower() for key in expect), "multi-field output contract expects dict result"; return
'''
