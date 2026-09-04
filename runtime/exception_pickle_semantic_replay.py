"""Semantic replay harness for exception-pickle reconstruction."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .exception_pickle_source_samples import (
    _constructor_sample_call,
    _sample_constructor_value_for_source_file,
)

def _verify_project_native_semantic_replay(
    *,
    sandbox: Path,
    source_row: dict[str, Any],
    state_attributes: list[str],
    object_contracts: dict[str, Any] | None = None,
    allow_target_import_stubs: bool = True,
    prefer_direct_file_import: bool = False,
) -> dict[str, Any]:
    required = [str(value) for value in source_row.get("required_constructor_parameters") or []]
    source_file = sandbox / str(source_row.get("path") or "")
    class_name = str(source_row.get("class_name") or "")
    samples = [
        _sample_constructor_value_for_source_file(
            name,
            source_file=source_file,
            class_name=class_name,
            object_contracts=object_contracts,
        )
        for name in required
    ]
    if any(sample is None for sample in samples):
        return {
            "status": "blocked",
            "reason": "unsupported_constructor_sample",
            "required_constructor_parameters": required,
        }
    constructor_args, constructor_kwargs = _constructor_sample_call(
        source_file=source_file,
        class_name=class_name,
        required=required,
        samples=samples,
    )
    module_name = _module_name(str(source_row.get("path") or ""))
    attributes = [name for name in state_attributes if name.isidentifier()]
    if not module_name or not class_name.isidentifier() or len(attributes) != len(state_attributes):
        return {"status": "blocked", "reason": "unsafe_target_shape"}
    payload = json.dumps(
        {
            "module": module_name,
            "module_file": str(source_row.get("path") or "").replace("\\", "/"),
            "import_stubs": _target_import_stub_modules(
                sandbox / str(source_row.get("path") or ""),
                module_name=module_name,
            )
            if allow_target_import_stubs
            else [],
            "prefer_direct_file_import": prefer_direct_file_import,
            "pythonpath_entries": _pythonpath_entries_for_sandbox(sandbox),
            "class_name": class_name,
            "constructor_args": constructor_args,
            "constructor_kwargs": constructor_kwargs,
            "state_attributes": attributes,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    script = "\n".join((
        "import builtins,enum,importlib,importlib.abc,importlib.machinery,importlib.util,json,pathlib,pickle,subprocess,sys,tempfile,types,typing",
        "p=json.loads(sys.argv[1])",
        "if not hasattr(types, 'GenericAlias'): types.GenericAlias=object",
        "if not hasattr(typing, 'Self'): typing.Self=object",
        "if not hasattr(typing, 'override'): typing.override=lambda value: value",
        "if not hasattr(builtins, 'ExceptionGroup'):",
        "    class ExceptionGroup(Exception): pass",
        "    builtins.ExceptionGroup=ExceptionGroup",
        "if not hasattr(enum, 'StrEnum'):",
        "    class StrEnum(str, enum.Enum): pass",
        "    enum.StrEnum=StrEnum",
        "if not hasattr(builtins, 'frozendict'):",
        "    class frozendict(dict):",
        "        def __hash__(self): return hash(tuple(sorted(self.items())))",
        "    builtins.frozendict=frozendict",
        "class _ReplayStubLoader(importlib.abc.Loader):",
        "    def create_module(self, spec): return types.ModuleType(spec.name)",
        "    def exec_module(self, module):",
        "        module.__path__=[]",
        "        class _ReplayStubValue:",
        "            def __init__(self, name): self.name=name; self.value=name",
        "            def __repr__(self): return self.name",
        "            def __hash__(self): return hash(self.name)",
        "            def __eq__(self, other): return getattr(other, 'name', other)==self.name",
        "            def __truediv__(self, other): return pathlib.Path(tempfile.gettempdir()) / str(other)",
        "            def __rtruediv__(self, other): return pathlib.Path(str(other)) / self.name",
        "            def __call__(self, *args, **kwargs):",
        "                if len(args)==1 and callable(args[0]) and not kwargs:",
        "                    return args[0]",
        "                return self",
        "            def __iter__(self): return iter(())",
        "        class _ReplayStubMeta(type):",
        "            def __getattr__(cls, name):",
        "                return _ReplayStubValue(name)",
        "        def _stub_init(self, *args, **kwargs):",
        "            Exception.__init__(self, *args)",
        "        def _stub_call(self, *args, **kwargs):",
        "            if len(args)==1 and callable(args[0]) and not kwargs:",
        "                return args[0]",
        "            return self",
        "        def __getattr__(name):",
        "            if name == '__all__':",
        "                return []",
        "            if name == 'T' or name.endswith('T') or name.endswith('_co') or name.endswith('_contra'):",
        "                return typing.TypeVar(name)",
        "            return _ReplayStubMeta(name, (Exception,), {'__module__': module.__name__, '__init__': _stub_init, '__call__': _stub_call})",
        "        module.__getattr__=__getattr__",
        "        module.__all__=[]",
        "class _ReplayStubFinder(importlib.abc.MetaPathFinder):",
        "    def __init__(self, allowed): self.allowed=set(allowed)",
        "    def find_spec(self, fullname, path=None, target=None):",
        "        if fullname in self.allowed:",
        "            return importlib.machinery.ModuleSpec(fullname, _ReplayStubLoader(), is_package=True)",
        "        return None",
        "class _ReplayResponseObject:",
        "    def __init__(self, payload):",
        "        self.status_code=payload['status_code']; self.url=payload['url']; self.content=payload['content'].encode('utf-8'); self.text=payload['text']; self._json=payload['json']",
        "    def json(self): return self._json",
        "    def __repr__(self): return f\"<response {self.status_code} {self.url}>\"",
        "def install_stub_imports():",
        "    allowed=set(p.get('import_stubs') or [])",
        "    if allowed:",
        "        sys.meta_path.insert(0, _ReplayStubFinder(allowed))",
        "def val(v):",
        "    if isinstance(v,list): return [val(item) for item in v]",
        "    if isinstance(v,tuple): return tuple(val(item) for item in v)",
        "    if isinstance(v,dict) and v.get('__sample__')=='excinfo':",
        "        return types.SimpleNamespace(formatted=v['formatted'],type=RuntimeError,msg=v['msg'],errdisplay=v['errdisplay'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='named_object':",
        "        return types.SimpleNamespace(**{k:val(item) for k,item in v.items() if k!='__sample__'})",
        "    if isinstance(v,dict) and v.get('__sample__')=='method_object':",
        "        class MethodObject:",
        "            def __init__(self, methods): self._methods=methods",
        "            def __getattr__(self, name):",
        "                if name not in self._methods: raise AttributeError(name)",
        "                value=self._methods[name]",
        "                return lambda *a, **k: value",
        "        return MethodObject(v['methods'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='response':",
        "        return _ReplayResponseObject(v)",
        "    if isinstance(v,dict) and v.get('__sample__')=='bytes':",
        "        return v['value'].encode('utf-8')",
        "    if isinstance(v,dict) and v.get('__sample__')=='format_object':",
        "        class FormatObject:",
        "            def __init__(self, text): self._text=text",
        "            def format(self, *args, **kwargs): return self._text",
        "            def __str__(self): return self._text",
        "        return FormatObject(v['value'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='cooldown':",
        "        return types.SimpleNamespace(rate=v['rate'], per=v['per'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='path':",
        "        return pathlib.Path(v['value'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='exception':",
        "        return RuntimeError(v['message'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='os_error':",
        "        return OSError(v['errno'], v['message'])",
        "    if isinstance(v,dict) and v.get('__sample__')=='called_process_error':",
        "        return subprocess.CalledProcessError(v['returncode'], v['cmd'], output=v['stdout'], stderr=v['stderr'])",
        "    return v",
        "args=[val(v) for v in p['constructor_args']]",
        "kwargs={k:val(v) for k,v in p.get('constructor_kwargs',{}).items()}",
        "for entry in reversed(p.get('pythonpath_entries') or []):",
        "    if entry and entry not in sys.path:",
        "        sys.path.insert(0, entry)",
        "import_error=None",
        "import_strategy='module_import'",
        "def load_direct_file():",
        "    path=pathlib.Path(p['module_file'])",
        "    spec=importlib.util.spec_from_file_location(p['module'], path)",
        "    if spec is None or spec.loader is None:",
        "        raise",
        "    module=importlib.util.module_from_spec(spec)",
        "    sys.modules[p['module']]=module",
        "    install_stub_imports()",
        "    spec.loader.exec_module(module)",
        "    return module,'direct_file_import'",
        "if p.get('prefer_direct_file_import'):",
        "    import_error='preferred_direct_file_import'",
        "    module,import_strategy=load_direct_file()",
        "else:",
        "    try:",
        "        module=importlib.import_module(p['module'])",
        "    except Exception as exc:",
        "        import_error=repr(exc)",
        "        module,import_strategy=load_direct_file()",
        "install_stub_imports()",
        "cls=getattr(module,p['class_name'])",
        "before=cls(*args, **kwargs)",
        "after=pickle.loads(pickle.dumps(before))",
        "attrs={a:[repr(getattr(before,a,None)),repr(getattr(after,a,None))] for a in p['state_attributes']}",
        "def norm_args(owner):",
        "    return ['<self>' if item is owner else repr(item) for item in owner.args]",
        "def safe_args(owner):",
        "    result=[]",
        "    for item in owner.args:",
        "        if item is owner:",
        "            result.append('<self>')",
        "        elif isinstance(item,(str,int,float,bool)) or item is None:",
        "            result.append(item)",
        "        else:",
        "            try:",
        "                result.append(repr(item))",
        "            except RecursionError:",
        "                result.append('<recursive-repr>')",
        "    return result",
        "def safe_text(value):",
        "    try:",
        "        return str(value)",
        "    except RecursionError:",
        "        return '<recursive-str>'",
        "args_equal=before.args==after.args or norm_args(before)==norm_args(after)",
        "ok=type(after) is type(before) and args_equal and all(v[0]==v[1] for v in attrs.values())",
        "print(json.dumps({'ok':ok,'import_strategy':import_strategy,'import_error':import_error,'before':safe_text(before),'after':safe_text(after),'args_before':safe_args(before),'args_after':safe_args(after),'normalized_args_before':norm_args(before),'normalized_args_after':norm_args(after),'attributes':attrs}, default=repr))",
        "raise SystemExit(0 if ok else 1)",
    ))
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": "",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script, payload],
            cwd=sandbox,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "blocked", "reason": type(exc).__name__}
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "module": module_name,
        "class_name": class_name,
        "required_constructor_parameters": required,
        "state_attributes": attributes,
        "stdout": (completed.stdout or "").strip()[-2000:],
        "stderr": (completed.stderr or "").strip()[-2000:],
    }

def _target_import_stub_modules(path: Path, *, module_name: str = "") -> list[str]:
    if not path.is_file():
        return []
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    modules: set[str] = set()
    modules.update(_module_parent_prefixes(module_name))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_stdlib_module(alias.name):
                    continue
                modules.update(_module_prefixes(alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if _is_stdlib_module(node.module):
                continue
            modules.update(_module_prefixes(node.module))
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            modules.update(_relative_import_modules(module_name, node))
    return sorted(modules)


def _is_stdlib_module(name: str) -> bool:
    root = name.split(".", 1)[0]
    return root in getattr(sys, "stdlib_module_names", set()) or root == "__future__"


def _module_prefixes(name: str) -> set[str]:
    parts = [part for part in name.split(".") if part.isidentifier()]
    return {".".join(parts[:index]) for index in range(1, len(parts) + 1)}


def _module_parent_prefixes(module_name: str) -> set[str]:
    parts = [part for part in module_name.split(".")[:-1] if part.isidentifier()]
    return {".".join(parts[:index]) for index in range(1, len(parts) + 1)}


def _relative_import_modules(module_name: str, node: ast.ImportFrom) -> set[str]:
    package_parts = [part for part in module_name.split(".")[:-1] if part.isidentifier()]
    if node.level <= 0 or node.level > len(package_parts) + 1:
        return set()
    base_parts = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        base_parts.extend(part for part in node.module.split(".") if part.isidentifier())
    if not base_parts:
        return set()
    base = ".".join(base_parts)
    modules = set(_module_prefixes(base))
    for alias in node.names:
        if alias.name == "*":
            continue
        modules.update(_module_prefixes(base + "." + alias.name))
    return modules

def _module_name(path: str) -> str:
    module = path.replace("\\", "/").removeprefix("src/").removesuffix(".py")
    if module.endswith("/__init__"):
        module = module[: -len("/__init__")]
    return module.replace("/", ".")


def _pythonpath_entries_for_sandbox(sandbox: Path) -> list[str]:
    entries = [sandbox / "src", sandbox]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        entries.append(Path(existing))
    return [str(path) for path in entries]


def _pythonpath_for_sandbox(sandbox: Path) -> str:
    return os.pathsep.join(_pythonpath_entries_for_sandbox(sandbox))
