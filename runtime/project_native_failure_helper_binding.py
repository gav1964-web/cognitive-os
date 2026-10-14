"""Bind transparent test wrappers to an observed API, never to a proved root cause."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .project_native_failure_module_resolution import _python_module_path
from .project_native_failure_source_symbols import _source_symbol_target
from .project_native_failure_test_imports import test_import_aliases


def helper_method_binding(project: Path, source: dict) -> dict:
    result = {"status": "unbound", "authority": "observed_api_only_not_root_cause"}
    try:
        helper_path = project / source["path"]
        text, tree, digest = _read(project, helper_path)
        if digest != source["file_sha256"] or not source.get("excerpt_complete"):
            raise ValueError("helper_source_changed_or_truncated")
        function = _unique(tree.body, source["symbol"], ast.FunctionDef)
        if function.decorator_list or not _single_binding(tree, function.name):
            raise ValueError("decorated_or_rebound_helper")
        constructor, method_name, defaults = _transparent_return(function)
        reject_method_mutation(tree, method_name)
        aliases = test_import_aliases(tree, project=project, test_path=helper_path)
        parts = _names(constructor.func)
        if not parts or parts[0] not in aliases or not _single_binding(tree, parts[0]):
            raise ValueError("constructor_import_not_unique")
        module, imported = aliases[parts[0]]
        symbols = ([imported] if imported else []) + parts[1:]
        path = _python_module_path(project, module.split("."))
        resolved = _source_symbol_target(project, path, ".".join(symbols)) if path and symbols else None
        if not resolved or "." in resolved[1]:
            raise ValueError("owned_constructor_not_resolved")
        class_path, class_name = resolved
        class_text, class_tree, class_digest = _read(project, class_path)
        owner = _unique(class_tree.body, class_name, ast.ClassDef)
        method = _ordinary_method(class_tree, owner, method_name)
        target = f"{class_path.relative_to(project).as_posix()}:{class_name}.{method_name}"
        return {**result, "status": "bound_observed_api", "target": target,
                "helper": {"path": source["path"], "symbol": source["symbol"], "file_sha256": digest},
                "target_file_sha256": class_digest, "constructor": class_name,
                "constructor_defaults": defaults,
                "input_mapping": "positional inputs forwarded unchanged; keyword options only supply constructor defaults",
                "result_mapping": "direct method return; no result transformation",
                "method_source": ast.get_source_segment(class_text, method),
                "limitations": "Static call provenance only. Dependencies, runtime mutation and internal defect location are not proved."}
    except (OSError, ValueError, SyntaxError, UnicodeError, KeyError) as exc:
        return {**result, "reason": str(exc)[:200]}


def _read(project: Path, path: Path) -> tuple[str, ast.Module, str]:
    if not path.resolve().is_relative_to(project.resolve()) or path.stat().st_size > 100_000:
        raise ValueError("source_outside_bounds")
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    return text, ast.parse(text), hashlib.sha256(raw).hexdigest()


def direct_constructor_method(project: Path, tree: ast.Module, function: ast.FunctionDef,
                              call: ast.Call, aliases: dict) -> str | None:
    """Resolve an observed Class(...).method() API with static dispatch only."""
    if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Call):
        return None
    constructor = call.func.value
    parts = _names(constructor.func)
    try:
        if not parts or parts[0] not in aliases or not _single_binding(tree, parts[0]):
            return None
        if any(isinstance(n, ast.arg) and n.arg == parts[0]
               or isinstance(n, ast.Name) and n.id == parts[0] and isinstance(n.ctx, (ast.Store, ast.Del))
               for n in ast.walk(function)):
            return None
        reject_method_mutation(tree, call.func.attr)
        module, imported = aliases[parts[0]]
        symbols = ([imported] if imported else []) + parts[1:]
        path = _python_module_path(project, module.split('.'))
        resolved = _source_symbol_target(project, path, '.'.join(symbols)) if path and symbols else None
        if not resolved or '.' in resolved[1]:
            return None
        class_path, name = resolved
        _, class_tree, _ = _read(project, class_path)
        owner = _unique(class_tree.body, name, ast.ClassDef)
        _ordinary_method(class_tree, owner, call.func.attr)
        return f'{class_path.relative_to(project).as_posix()}:{name}.{call.func.attr}'
    except (OSError, ValueError, SyntaxError, UnicodeError, KeyError):
        return None


def _unique(body: list, name: str, kind: type):
    matches = [n for n in body if isinstance(n, kind) and n.name == name]
    if len(matches) != 1:
        raise ValueError("definition_not_unique")
    return matches[0]


def _names(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        parent = _names(node.value)
        return [*parent, node.attr] if parent else []
    return []


def _single_binding(tree: ast.Module, name: str) -> bool:
    count = 0
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            count += statement.name == name
            continue
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == name:
                count += 1
            elif isinstance(node, ast.Import):
                count += sum((n.asname or n.name.split('.')[0]) == name for n in node.names)
            elif isinstance(node, ast.ImportFrom):
                if any(n.name == '*' for n in node.names):
                    return False
                count += sum((n.asname or n.name) == name for n in node.names)
    return count == 1


def _transparent_return(function: ast.FunctionDef) -> tuple[ast.Call, str, dict]:
    arguments = function.args
    if arguments.vararg or arguments.kwonlyargs:
        raise ValueError("variadic_or_keyword_only_input_unsupported")
    names = [arg.arg for arg in [*arguments.posonlyargs, *arguments.args]]
    for value in arguments.defaults:
        ast.literal_eval(value)
    options = arguments.kwarg.arg if arguments.kwarg else None
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    defaults = {}
    if body and isinstance(body[0], ast.Assign):
        assignment = body.pop(0)
        if not options or len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name) or assignment.targets[0].id != options:
            raise ValueError("helper_input_transformation")
        value = assignment.value
        if not isinstance(value, ast.Dict) or not value.keys or value.keys[-1] is not None or not isinstance(value.values[-1], ast.Name) or value.values[-1].id != options:
            raise ValueError("constructor_defaults_must_preserve_supplied_options")
        for key, item in zip(value.keys[:-1], value.values[:-1]):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                raise ValueError("constructor_default_key_not_literal")
            default = ast.literal_eval(item)
            if not isinstance(default, (str, int, float, bool, type(None))):
                raise ValueError("constructor_default_not_scalar")
            defaults[key.value] = default
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        raise ValueError("helper_must_directly_return_one_call")
    returned = body[0].value
    if not isinstance(returned, ast.Call) or not isinstance(returned.func, ast.Attribute) or not isinstance(returned.func.value, ast.Call):
        raise ValueError("fresh_constructor_method_return_required")
    if returned.keywords or not names or [n.id if isinstance(n, ast.Name) else None for n in returned.args] != names:
        raise ValueError("helper_method_inputs_not_forwarded_unchanged")
    constructor = returned.func.value
    if constructor.args or len(constructor.keywords) != (1 if options else 0):
        raise ValueError("constructor_arguments_unsupported")
    if options:
        item = constructor.keywords[0]
        if item.arg is not None or not isinstance(item.value, ast.Name) or item.value.id != options:
            raise ValueError("constructor_options_not_forwarded")
    if any(name in _names(constructor.func)[:1] for name in [*names, *([options] if options else [])]):
        raise ValueError("constructor_shadowed_by_parameter")
    return constructor, returned.func.attr, defaults


def _ordinary_method(tree: ast.Module, owner: ast.ClassDef, name: str) -> ast.FunctionDef:
    if owner.decorator_list or owner.keywords or not all(isinstance(b, ast.Name) and b.id == 'object' for b in owner.bases):
        raise ValueError("inherited_decorated_or_custom_metaclass")
    if not _single_binding(tree, owner.name):
        raise ValueError("class_binding_not_unique")
    if owner.bases and any(
        isinstance(n, ast.Name) and n.id == 'object' and isinstance(n.ctx, (ast.Store, ast.Del))
        or isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == 'object'
        or isinstance(n, ast.alias) and (n.asname or n.name) == 'object' for n in ast.walk(tree)
    ):
        raise ValueError("object_base_rebound")
    method = _unique(owner.body, name, ast.FunctionDef)
    if not _single_binding(ast.Module(body=owner.body, type_ignores=[]), name):
        raise ValueError("method_name_rebound")
    if method.decorator_list or method.end_lineno - method.lineno > 200:
        raise ValueError("decorated_or_unbounded_method")
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in
           {'__new__', '__getattribute__', '__getattr__'} for n in owner.body):
        raise ValueError("dynamic_instance_dispatch")
    reject_method_mutation(tree, name)
    return method


def reject_method_mutation(tree: ast.AST, name: str) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.attr == name:
            raise ValueError("method_attribute_mutated")
        if isinstance(node, ast.Call) and (isinstance(node.func, ast.Name) and node.func.id in {'setattr', 'delattr', 'exec'}
                or isinstance(node.func, ast.Attribute) and node.func.attr in {'setattr', 'delattr', '__setattr__', '__delattr__', 'patch'}):
            raise ValueError("dynamic_attribute_mutation")
        if isinstance(node, ast.Attribute) and node.attr == '__dict__':
            raise ValueError("dynamic_instance_dictionary")


def helper_call_scope_is_static(tree: ast.Module, function: ast.FunctionDef, call: ast.Call, binding: dict) -> bool:
    name = ast.unparse(call.func).split('.')[0]
    arguments = function.args
    if arguments.args or arguments.posonlyargs or arguments.kwonlyargs or function.decorator_list:
        return False
    if not _single_binding(tree, name):
        return False
    if any(isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)) and n.id == name for n in ast.walk(function)):
        return False
    try:
        reject_method_mutation(tree, binding['target'].rsplit('.', 1)[-1])
    except ValueError:
        return False
    return True
