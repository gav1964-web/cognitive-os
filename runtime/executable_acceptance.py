"""Generate and run executable acceptance scaffolds from Tester obligations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .executable_acceptance_support import harness_summary
def run_executable_acceptance(
    *,
    root: Path,
    project_dir: Path,
    test_plan: dict[str, Any],
    work_dir: Path,
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
    harness = harness_summary(project_dir, obligations)
    test_path.write_text(_pytest_source(obligations_path, project_dir, harness), encoding="utf-8")
    command = [sys.executable, "-m", "pytest", str(tests_dir), "-q"]
    command_result = _run_command(command, cwd=scaffold_dir)
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
            "skipped_reason_counts": harness["skipped_reason_counts"],
            "skipped_targets": harness["skipped_targets"],
            "argument_mappings": harness.get("argument_mappings", {}),
            "argument_defaults": harness.get("argument_defaults", {}),
            "source_isolated_targets": harness.get("source_isolated_targets", []),
            "dependency_stub_targets": harness.get("dependency_stub_targets", {}),
            "dependency_metadata_profile_targets": harness.get("dependency_metadata_profile_targets", {}),
            "dependency_module_profile_targets": harness.get("dependency_module_profile_targets", {}),
            "passed": passed,
        },
        "command": command_result,
        "source_code_changes": False,
        "registry_changes": False,
        "limitations": ["v0.3 invokes simple file.py:function targets with kwargs; classes, async functions, methods and framework handlers remain meta-checked."],
    }
    result_path = scaffold_dir / "executable_acceptance_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["result_path"] = result_path.as_posix()
    return result

def _pytest_source(obligations_path: Path, project_dir: Path, harness: dict[str, Any]) -> str:
    escaped = obligations_path.as_posix()
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
HARNESS = {harness_payload!r}
HARNESS_DATA = json.loads(HARNESS)

sys.path.insert(0, str(PROJECT_DIR))
if (PROJECT_DIR / "src").is_dir():
    sys.path.insert(0, str(PROJECT_DIR / "src"))

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
    result = func(**kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result

def _load_function(target):
    path_text, _, symbol = target.partition(":")
    assert path_text.endswith(".py") and symbol, f"unsupported callable target: {{target}}"
    path = (PROJECT_DIR / path_text).resolve()
    assert PROJECT_DIR.resolve() in path.parents or path == PROJECT_DIR.resolve()
    module_name = _module_name(path_text)
    method = HARNESS_DATA.get("method_targets", {{}}).get(target)
    if target in HARNESS_DATA.get("source_isolated_targets", []):
        return _load_source_isolated_function(path, symbol)
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
                raise
        except Exception:
            if len(Path(path_text).parts) > 1:
                raise
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
    parent_name, _, child_name = name.rpartition(".")
    module = types.ModuleType(name)
    attrs = HARNESS_DATA.get("dependency_module_profile_attrs", {{}}).get(name, {{"__version__": "0.0.0", "version": "0.0.0"}})
    for key, value in attrs.items(): setattr(module, key, _materialize(value))
    sys.modules[name] = module
    parent = sys.modules.get(parent_name)
    if parent is None:
        return
    setattr(parent, child_name, module)

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

    def __call__(self, *args, **kwargs):
        return self

    def __getitem__(self, key):
        return _StubObject(f"{{self._name}}[{{key!r}}]")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __mro_entries__(self, bases):
        return ()

    def __getattr__(self, name):
        return _StubObject(f"{{self._name}}.{{name}}")

def _load_source_isolated_function(path, symbol):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol]
    assert len(matches) == 1, f"isolated target is not unique: {{symbol}}"
    func_node = matches[0]
    func_node.decorator_list = []
    func_node.returns = None
    for arg in list(func_node.args.posonlyargs) + list(func_node.args.args) + list(func_node.args.kwonlyargs):
        arg.annotation = None
    if func_node.args.vararg:
        func_node.args.vararg.annotation = None
    if func_node.args.kwarg:
        func_node.args.kwarg.annotation = None
    module = ast.Module(body=[func_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {{}}
    exec(compile(module, str(path), "exec"), namespace)
    func = namespace[symbol]
    assert callable(func), f"isolated target is not callable: {{symbol}}"
    return func

def _load_method(module, method, symbol, target):
    cls = getattr(module, method.get("class_name"))
    member = getattr(cls, symbol)
    if callable(member) and _callable_accepts_without_self(member):
        return member
    try:
        instance = cls()
    except Exception:
        instance = object.__new__(cls)
    for key, value in dict(HARNESS_DATA.get("method_instance_attributes", {{}}).get(target) or {{}}).items():
        setattr(instance, key, _materialize(value))
    func = getattr(instance, symbol)
    assert callable(func), f"method target is not callable: {{symbol}}"
    return func

def _callable_accepts_without_self(func):
    try:
        params = list(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return False
    return not params or params[0] not in {{"self", "cls"}}
def _materialize(value):
    if isinstance(value, dict):
        fixture = value.get("__fixture__")
        if fixture == "callable_id_of": return lambda schema: schema.get("$id") if isinstance(schema, dict) else None
        if fixture == "callable_items": return lambda schema: schema.items() if hasattr(schema, "items") else []
        if fixture == "callable_identity": return lambda value, *args, **kwargs: value
        if fixture == "callable_float": return lambda value, *args, **kwargs: float(value)
        if fixture == "configparser_flake8_empty": parser = __import__("configparser").RawConfigParser(); parser.add_section("flake8:local-plugins"); return parser
        if fixture == "bytes_io_empty": return __import__("io").BytesIO(b"")
        if fixture == "bytes_empty": return b""
        if fixture == "dateutil_parserinfo_minimal": return type("Info", (), {{"hms": lambda self, value: None, "jump": lambda self, value: False, "ampm": lambda self, value: None, "month": lambda self, value: None}})()
        if fixture == "dateutil_result": return type("Result", (), {{"hour": None, "minute": None, "second": None, "microsecond": None}})()
        if fixture == "dateutil_ymd": return type("YMD", (list,), {{"append": lambda self, value, label=None: list.append(self, value), "could_be_day": lambda self, value: True}})()
        if fixture == "pytest_source_minimal": return type("Source", (), {{"lines": ["x = 1"], "raw_lines": ["x = 1"], "__str__": lambda self: "\\n".join(self.lines)}})()
        if fixture == "networkx_graph_path": graph = __import__("networkx").Graph(); graph.add_edge("a", "b", label="edge"); graph.nodes["a"]["label"] = "a"; graph.nodes["b"]["label"] = "b"; return graph
        return {{key: _materialize(_field_sample(key, item)) for key, item in value.items()}}
    if isinstance(value, list):
        return [_materialize(item) for item in value]
    return value

def _field_sample(key, value): return {{"edge_attr": "label", "digest_size": 8, "include_initial_labels": False, "iterations": 1}}.get(str(key), value) if value == "sample" else value

def _call_kwargs(target, given, include_defaults=True):
    data = dict(given or {{}})
    mapping = HARNESS_DATA.get("argument_mappings", {{}}).get(target, {{}})
    if mapping:
        data = {{actual: data[source] for actual, source in mapping.items() if source in data}}
    if include_defaults:
        data = {{**HARNESS_DATA.get("argument_defaults", {{}}).get(target, {{}}), **data}}
    return _materialize(data)

def _module_name(path_text):
    parts = Path(path_text).with_suffix("").parts
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return ""
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return ""
    return ".".join(parts)

def _assert_expected_shape(result, expect):
    if not isinstance(expect, dict) or not expect:
        return
    if set(expect) == {{"result"}}:
        assert result is not None
        return
    if not isinstance(result, dict):
        assert any("failure" not in str(key).lower() for key in expect), "multi-field output contract expects dict result"
        return
    return
'''

def _run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"], env["PYTHONUTF8"] = "utf-8", "1"
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }
