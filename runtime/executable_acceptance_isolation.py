"""Source-isolated callable extraction for executable acceptance."""

from __future__ import annotations

import ast
import copy
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .executable_acceptance_isolation_globals import isolated_global_nodes
from .executable_acceptance_effect_stubs import configured_effect_stubs


def load_source_isolated_function(path: Path, symbol: str) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if symbol not in functions:
            return {"callable": None, "reason": "target_not_callable"}
        names = _isolated_function_names(functions, symbol)
        nodes = [_strip_annotations(copy.deepcopy(functions[name])) for name in functions if name in names]
        globals_body = isolated_global_nodes(tree, nodes, "")
        imports = _needed_import_nodes_for_nodes(tree, [*globals_body, *nodes])
        module = ast.Module(body=[*imports, *globals_body, *nodes], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict[str, Any] = _namespace_for(path)
        from .executable_acceptance_policy import method_fixture_policy
        local_stubs = symbol in set(method_fixture_policy().get("local_import_stub_functions") or [])
        with _source_import_path(path), _fresh_local_package(namespace):
            effect_stubs = _exec_with_stubs(module, path, namespace, local_import_stubs=local_stubs)
        func = namespace.get(symbol)
        return {"callable": func, "reason": "" if callable(func) else "target_not_callable", "effect_module_stubs": effect_stubs}
    except Exception as exc:
        return {"callable": None, "reason": _import_failure_reason(exc), "detail": _exception_detail(exc)}


def load_source_isolated_callable(path: Path, symbol: str) -> dict[str, Any]:
    loaded = load_source_isolated_function(path, symbol)
    if not loaded.get("reason"):
        return loaded
    method = load_source_isolated_method(path, symbol)
    if not method.get("reason"):
        return method
    return loaded


def load_source_isolated_method(path: Path, symbol: str) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        match = _unique_method_class(tree, symbol)
        if match is None:
            return {"callable": None, "reason": "target_not_callable"}
        class_node, method_names = match
        methods = {
            node.name: node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        selected = _isolated_method_names(methods, symbol)
        body = [
            _isolated_class_member(item)
            for item in class_node.body
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name in selected
            )
            or isinstance(item, (ast.Assign, ast.AnnAssign))
        ]
        globals_body = isolated_global_nodes(tree, body, class_node.name)
        isolated_class = ast.ClassDef(
            name=class_node.name,
            bases=[],
            keywords=[],
            body=body or [ast.Pass()],
            decorator_list=[],
        )
        imports = _needed_import_nodes_for_nodes(tree, [*globals_body, *body])
        module = ast.Module(body=[*imports, *globals_body, isolated_class], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict[str, Any] = _namespace_for(path)
        from .executable_acceptance_policy import method_fixture_policy
        local_stubs = f"{class_node.name}.{symbol}" in set(method_fixture_policy().get("local_import_stub_methods") or [])
        with _source_import_path(path), _fresh_local_package(namespace):
            effect_stubs = _exec_with_stubs(module, path, namespace, local_import_stubs=local_stubs)
        cls = namespace[class_node.name]
        member = getattr(cls, symbol, None)
        if callable(member) and _callable_accepts_without_self(member):
            func = member
        else:
            instance = object.__new__(cls)
            attrs = _method_instance_attrs(class_node.name, symbol)
            for key, value in attrs.items():
                setattr(instance, key, value)
            func = getattr(instance, symbol, None)
        return {
            "callable": func,
            "reason": "" if callable(func) else "target_not_callable",
            "method": {"class_name": class_node.name, "method_name": symbol},
            "method_instance_attributes": _raw_method_instance_attrs(class_node.name, symbol),
            "source_isolated": True,
            "source_isolated_method": True,
            "method_dependencies": sorted(method_names & selected),
            "effect_module_stubs": effect_stubs,
        }
    except Exception as exc:
        return {"callable": None, "reason": _import_failure_reason(exc), "detail": _exception_detail(exc)}


def _isolated_function_names(functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef], symbol: str) -> set[str]:
    selected = {symbol}
    changed = True
    while changed:
        changed = False
        for name in list(selected):
            for loaded in _loaded_names(functions[name]):
                if loaded in functions and loaded not in selected:
                    selected.add(loaded)
                    changed = True
    return selected


def _needed_import_nodes_for_nodes(tree: ast.Module, nodes: list[ast.AST]) -> list[ast.stmt]:
    loaded = {name for node in nodes for name in _loaded_names(node)}
    imports: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Import) and _import_bound_names(node) & loaded:
            imports.append(copy.deepcopy(node))
        elif isinstance(node, ast.ImportFrom) and _import_bound_names(node) & loaded:
            imports.append(copy.deepcopy(node))
    return imports


def _loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def _import_bound_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    return {alias.asname or alias.name.split(".", 1)[0] for alias in node.names}


def _strip_annotations(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    func_node.decorator_list = []
    func_node.returns = None
    for arg in list(func_node.args.posonlyargs) + list(func_node.args.args) + list(func_node.args.kwonlyargs):
        arg.annotation = None
    if func_node.args.vararg:
        func_node.args.vararg.annotation = None
    if func_node.args.kwarg:
        func_node.args.kwarg.annotation = None
    return func_node


def _isolated_class_member(item: ast.AST) -> ast.AST:
    copied = copy.deepcopy(item)
    if isinstance(copied, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _strip_annotations(copied)
    return copied


def _raw_method_instance_attrs(class_name: str, symbol: str) -> dict[str, Any]:
    from .executable_acceptance_policy import method_fixture_policy
    return dict(dict(method_fixture_policy().get("instance_attribute_profiles") or {}).get(f"{class_name}.{symbol}") or {})


def _method_instance_attrs(class_name: str, symbol: str) -> dict[str, Any]:
    from .executable_acceptance_materializers import materialize
    return {key: materialize(value) for key, value in _raw_method_instance_attrs(class_name, symbol).items()}


def _unique_method_class(tree: ast.Module, symbol: str) -> tuple[ast.ClassDef, set[str]] | None:
    matches: list[tuple[ast.ClassDef, set[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        method_names = {
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if symbol in method_names:
            matches.append((node, method_names))
    return matches[0] if len(matches) == 1 else None


def _isolated_method_names(functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef], symbol: str) -> set[str]:
    selected = {symbol}
    changed = True
    while changed:
        changed = False
        for name in list(selected):
            for loaded in _self_method_names(functions[name]):
                if loaded in functions and loaded not in selected:
                    selected.add(loaded)
                    changed = True
    return selected


def _self_method_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Attribute) or not isinstance(item.value, ast.Name):
            continue
        if item.value.id in {"self", "cls"} and isinstance(item.ctx, ast.Load):
            names.add(item.attr)
    return names


def _callable_accepts_without_self(func: object) -> bool:
    args = getattr(getattr(func, "__code__", None), "co_varnames", ())
    count = int(getattr(getattr(func, "__code__", None), "co_argcount", 0) or 0)
    return count == 0 or not args or args[0] not in {"self", "cls"}

def _exec_with_stubs(module: ast.Module, path: Path, namespace: dict[str, Any], *, local_import_stubs: bool) -> list[str]:
    code = compile(module, str(path), "exec")
    installed: list[str] = []
    if local_import_stubs:
        _install_local_import_stubs(module, namespace)
    _install_known_profile_modules(_imported_module_names(module))
    with configured_effect_stubs(_imported_module_names(module)) as effect_stubs:
        for _ in range(12):
            try:
                _install_lazy_loader_stub()
                exec(code, namespace)
                return effect_stubs
            except ModuleNotFoundError as exc:
                missing = str(getattr(exc, "name", "") or "")
                if not missing or missing in installed or _is_local_missing(missing, namespace):
                    raise
                if _install_profile_module(missing):
                    installed.append(missing)
                    continue
                _install_stub_module(missing)
                installed.append(missing)
        exec(code, namespace)
        return effect_stubs


def _imported_module_names(module: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _install_known_profile_modules(names: set[str]) -> None:
    for name in names:
        _install_profile_module(name)


def _install_local_import_stubs(module: ast.Module, namespace: dict[str, Any]) -> None:
    top = str(namespace.get("__package__") or "").split(".", 1)[0]
    if not top:
        return
    for name in _imported_module_names(module):
        if name != top and name.startswith(f"{top}."):
            _install_stub_module(name)


def _install_profile_module(name: str) -> bool:
    from .executable_acceptance_materializers import materialize
    from .executable_acceptance_policy import dependency_stub_policy
    profile = dict(dict(dependency_stub_policy().get("generated_module_profiles") or {}).get(name) or {})
    if not profile:
        return False
    _install_stub_module(name)
    module = sys.modules[name]
    for key, value in dict(profile.get("attrs") or {}).items():
        setattr(module, key, materialize(value))
    return True


def _install_lazy_loader_stub() -> None:
    module = sys.modules.get("lazy_loader") or types.ModuleType("lazy_loader")
    module.attach_stub = lambda *args, **kwargs: (lambda name: _StubObject(f"lazy_loader.{name}"), lambda: [], [])
    sys.modules["lazy_loader"] = module


def _namespace_for(path: Path) -> dict[str, Any]:
    package = _package_name(path)
    return {"__name__": f"{package}.__acceptance_isolated__" if package else "__acceptance_isolated__", "__package__": package}


def _package_name(path: Path) -> str:
    names: list[str] = []
    parent = path.resolve().parent
    while (parent / "__init__.py").is_file():
        names.append(parent.name)
        parent = parent.parent
    return ".".join(reversed(names))


@contextmanager
def _fresh_local_package(namespace: dict[str, Any]):
    top = str(namespace.get("__package__") or "").split(".", 1)[0]
    names = [name for name in list(sys.modules) if top and (name == top or name.startswith(f"{top}."))]
    saved = {name: sys.modules.pop(name) for name in names}
    try:
        yield
    finally:
        for name in [name for name in list(sys.modules) if top and (name == top or name.startswith(f"{top}."))]:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


def _install_stub_module(name: str) -> None:
    parts = name.split(".")
    for index in range(1, len(parts) + 1):
        module_name = ".".join(parts[:index])
        if module_name not in sys.modules:
            module = types.ModuleType(module_name)
            module.__path__ = []
            module.__getattr__ = lambda attr, prefix=module_name: _StubObject(f"{prefix}.{attr}")
            if module_name == "lazy_loader":
                module.attach_stub = lambda *args, **kwargs: (lambda name: _StubObject(f"lazy_loader.{name}"), lambda: [], [])
            sys.modules[module_name] = module
        if index > 1:
            setattr(sys.modules[".".join(parts[: index - 1])], parts[index - 1], sys.modules[module_name])


def _is_local_missing(missing: str, namespace: dict[str, Any]) -> bool:
    package = str(namespace.get("__package__") or "")
    return bool(package and missing.split(".", 1)[0] == package.split(".", 1)[0])


class _StubObject:
    def __init__(self, name: str):
        self._name = name
    def __call__(self, *args: Any, **kwargs: Any) -> "_StubObject": return self
    def __iter__(self): return iter(())
    def __bool__(self) -> bool: return False
    def __getitem__(self, key: Any) -> "_StubObject": return _StubObject(f"{self._name}[{key!r}]")
    def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[()]: return ()
    def __getattr__(self, name: str) -> "_StubObject": return _StubObject(f"{self._name}.{name}")


@contextmanager
def _source_import_path(path: Path):
    parts = path.resolve().parts
    entries = []
    if "src" in parts:
        src_index = len(parts) - 1 - list(reversed(parts)).index("src")
        src = Path(*parts[: src_index + 1])
        entries.append(str(src))
        if len(parts) > src_index + 1 and parts[src_index + 1] == "python":
            entries.insert(0, str(src / "python"))
    package_root = _package_root(path)
    if package_root and str(package_root) not in entries:
        entries.append(str(package_root))
    for entry in entries:
        sys.path.insert(0, entry)
    try:
        yield
    finally:
        for entry in entries:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _package_root(path: Path) -> Path | None:
    parent = path.resolve().parent
    while (parent / "__init__.py").is_file():
        parent = parent.parent
    return parent if parent != path.resolve().parent else None


def _import_failure_reason(exc: Exception) -> str:
    if isinstance(exc, ModuleNotFoundError):
        return "import_failed_missing_module"
    if isinstance(exc, ImportError):
        return "import_failed_import_error"
    return "import_failed_runtime_error"


def _exception_detail(exc: Exception) -> str:
    name = getattr(exc, "name", "") or ""
    message = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
    if name:
        return f"{name}: {message}"[:240]
    return message[:240]
