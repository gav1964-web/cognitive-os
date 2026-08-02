"""Support analysis for generated executable acceptance harnesses."""

from __future__ import annotations

import inspect
import ast
import asyncio
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from .executable_acceptance_loading import cleanup_dependency_stubs, import_path, load_supported_callable
from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import dependency_stub_policy, method_fixture_policy, sample_value, skipped_recovery_hint


def harness_summary(project_dir: Path, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    targets: list[str] = []
    skipped: list[dict[str, str]] = []
    strict_negative: list[str] = []
    methods: dict[str, dict[str, str]] = {}
    method_attrs: dict[str, dict[str, Any]] = {}
    argument_mappings: dict[str, dict[str, str]] = {}
    argument_defaults: dict[str, dict[str, Any]] = {}
    isolated: list[str] = []
    dependency_stubs: dict[str, list[str]] = {}
    metadata_profiles: dict[str, list[str]] = {}
    module_profiles: dict[str, list[str]] = {}
    for row in obligations:
        target = str(row.get("target") or "")
        if not target or target in targets or any(item["target"] == target for item in skipped):
            continue
        support = callable_target_support(project_dir, target, obligations)
        if support["supported"]:
            targets.append(target)
            if support.get("method"):
                methods[target] = dict(support["method"])
            if support.get("method_instance_attributes"):
                method_attrs[target] = dict(support["method_instance_attributes"])
            if support.get("argument_mapping"):
                argument_mappings[target] = dict(support["argument_mapping"])
            if support.get("argument_defaults"):
                argument_defaults[target] = dict(support["argument_defaults"])
            if support.get("source_isolated"):
                isolated.append(target)
            if support.get("dependency_stubs"):
                dependency_stubs[target] = list(support["dependency_stubs"])
            if support.get("dependency_metadata_profiles"):
                metadata_profiles[target] = list(support["dependency_metadata_profiles"])
            if support.get("dependency_module_profiles"):
                module_profiles[target] = list(support["dependency_module_profiles"])
            if support["strict_negative"]:
                strict_negative.append(target)
        else:
            item = {"target": target, "reason": support["reason"]}
            if support.get("detail"):
                item["detail"] = support["detail"]
            recovery = skipped_recovery_hint(support["reason"])
            if recovery:
                item["recovery"] = recovery
            skipped.append(item)
    return {
        "version": "executable_acceptance_harness_v0.4",
        "signal_strength": "executable_callable" if targets else "meta_only",
        "callable_harness_count": len(targets),
        "callable_targets": targets,
        "method_targets": methods,
        "method_instance_attributes": method_attrs,
        "argument_mappings": argument_mappings,
        "argument_defaults": argument_defaults,
        "source_isolated_targets": isolated,
        "dependency_stub_targets": dependency_stubs,
        "dependency_metadata_profile_targets": metadata_profiles,
        "dependency_module_profile_targets": module_profiles,
        "dependency_module_profile_attrs": _module_profile_attrs(module_profiles),
        "strict_negative_targets": strict_negative,
        "meta_checked_targets": [item["target"] for item in skipped],
        "skipped_targets": skipped,
        "skipped_reason_counts": _reason_counts(skipped),
    }


def callable_target_support(project_dir: Path, target: str, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    path_text, separator, symbol = target.partition(":")
    if separator != ":" or not path_text.endswith(".py") or not symbol or "." in symbol:
        return _unsupported("unsupported_target_format")
    path = (project_dir / path_text).resolve()
    try:
        path.relative_to(project_dir.resolve())
    except ValueError:
        return _unsupported("target_outside_project")
    if not path.is_file():
        return _unsupported("target_file_missing")
    with import_path(project_dir):
        loaded = load_supported_callable(project_dir, path_text, symbol, path)
    func = loaded.get("callable")
    if loaded.get("reason") == "target_not_callable":
        method = _load_method_callable(path, symbol, loaded.get("module"))
        if callable(method.get("callable")):
            func = method["callable"]
            detail = _method_detail(method)
            binding = positive_case_binding(func, target, obligations)
            if not binding["accepted"]:
                cleanup_dependency_stubs(loaded)
                return _unsupported("positive_signature_mismatch", detail)
            if not positive_samples_execute(func, target, obligations, dict(binding["mapping"]), dict(binding["defaults"])):
                cleanup_dependency_stubs(loaded)
                return _unsupported("positive_sample_execution_failed", detail)
            cleanup_dependency_stubs(loaded)
            return {
                "supported": True,
                "strict_negative": signature_needs_negative_case(func, target, obligations),
                "reason": "",
                "method": method["method"],
                "method_instance_attributes": method.get("instance_attributes", {}),
                "dependency_stubs": list(loaded.get("dependency_stubs") or []),
                "dependency_metadata_profiles": list(loaded.get("dependency_metadata_profiles") or []),
                "dependency_module_profiles": list(loaded.get("dependency_module_profiles") or []),
                "argument_mapping": binding["mapping"],
                "argument_defaults": binding["defaults"],
            }
        cleanup_dependency_stubs(loaded)
        return _unsupported(_ast_skip_reason(path, symbol), str(method.get("detail") or ""))
    if loaded.get("reason"):
        cleanup_dependency_stubs(loaded)
        return _unsupported(str(loaded["reason"]), str(loaded.get("detail") or ""))
    if not callable(func):
        cleanup_dependency_stubs(loaded)
        return _unsupported(_ast_skip_reason(path, symbol))
    binding = positive_case_binding(func, target, obligations)
    if not binding["accepted"]:
        cleanup_dependency_stubs(loaded)
        return _unsupported("positive_signature_mismatch")
    if not positive_samples_execute(func, target, obligations, dict(binding["mapping"]), dict(binding["defaults"])):
        cleanup_dependency_stubs(loaded)
        if loaded.get("source_isolated") and loaded.get("fallback_reason"):
            return _unsupported(str(loaded["fallback_reason"]), str(loaded.get("fallback_detail") or ""))
        return _unsupported("positive_sample_execution_failed")
    cleanup_dependency_stubs(loaded)
    return {
        "supported": True,
        "strict_negative": signature_needs_negative_case(func, target, obligations),
        "reason": "",
        "source_isolated": bool(loaded.get("source_isolated")),
        "dependency_stubs": list(loaded.get("dependency_stubs") or []),
        "dependency_metadata_profiles": list(loaded.get("dependency_metadata_profiles") or []),
        "dependency_module_profiles": list(loaded.get("dependency_module_profiles") or []),
        "argument_mapping": binding["mapping"],
        "argument_defaults": binding["defaults"],
    }


def positive_case_binding(func: object, target: str, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return {"accepted": False, "mapping": {}, "defaults": {}}
    mapping: dict[str, str] = {}
    defaults: dict[str, Any] = {}
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        given = dict(row.get("given", {}))
        try:
            signature.bind(**given)
            mapping.update({key: key for key in given})
        except TypeError:
            adapted = _adapt_given_to_signature(signature, given)
            if adapted is None:
                return {"accepted": False, "mapping": {}, "defaults": {}}
            mapping.update({actual: source for actual, source in adapted.items()})
        defaults.update(_missing_required_samples(signature, mapping))
    return {"accepted": True, "mapping": mapping, "defaults": defaults}


def signature_accepts_positive_cases(func: object, target: str, obligations: list[dict[str, Any]]) -> bool:
    return bool(positive_case_binding(func, target, obligations)["accepted"])


def signature_needs_negative_case(func: object, target: str, obligations: list[dict[str, Any]]) -> bool:
    malformed = [row for row in obligations if row.get("target") == target and row.get("kind") == "malformed_input_case"]
    if not malformed:
        return False
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    positive_keys = {
        str(key)
        for row in obligations
        if row.get("target") == target and row.get("kind") == "positive_contract_case"
        for key in dict(row.get("given", {}))
    }
    explicit_params = {
        name
        for name, param in signature.parameters.items()
        if param.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    }
    for row in malformed:
        given = dict(row.get("given", {}))
        try:
            signature.bind(**given)
        except TypeError:
            return True
        if positive_keys - set(given) - explicit_params:
            return True
    return False


def positive_samples_execute(
    func: object,
    target: str,
    obligations: list[dict[str, Any]],
    mapping: dict[str, str] | None = None,
    defaults: dict[str, Any] | None = None,
) -> bool:
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                payload = {**dict(defaults or {}), **_mapped_given(dict(row.get("given", {})), mapping or {})}
                result = func(**materialize(payload))
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
                if not _positive_result_matches_expect(result, dict(row.get("expect") or {})):
                    return False
        except Exception:
            return False
    return True


def _positive_result_matches_expect(result: Any, expect: dict[str, Any]) -> bool:
    if set(expect) == {"result"}:
        return result is not None
    return True


def _adapt_given_to_signature(signature: inspect.Signature, given: dict[str, Any]) -> dict[str, str] | None:
    params = [
        name
        for name, param in signature.parameters.items()
        if param.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    ]
    if len(params) < len(given):
        return None
    return dict(zip(params, given))


def _missing_required_samples(signature: inspect.Signature, mapping: dict[str, str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if name in mapping or param.default is not inspect.Parameter.empty:
            continue
        if param.kind not in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}:
            continue
        defaults[name] = _signature_sample_value(name, str(param.annotation or ""))
    return defaults


def _signature_sample_value(name: str, annotation: str) -> Any:
    return sample_value(annotation, name, signature_mode=True)


def _mapped_given(given: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    if not mapping:
        return given
    return {actual: given[source] for actual, source in mapping.items() if source in given}


def _ast_skip_reason(path: Path, symbol: str) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return "target_not_callable"
    top_level = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol for node in tree.body)
    if top_level:
        return "target_not_callable"
    matches = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol]
    if len(matches) == 1:
        return "method_target_needs_instance_fixture"
    if len(matches) > 1:
        return "ambiguous_nested_callable_target"
    return "target_not_callable"


def _load_method_callable(path: Path, symbol: str, module: object | None) -> dict[str, Any]:
    policy = method_fixture_policy()
    if not policy.get("enabled"):
        return {"callable": None, "detail": "method_fixture_policy_disabled"}
    match = _unique_method_match(path, symbol)
    if not match or module is None:
        return {"callable": None, "detail": "method_match_missing_or_module_unloaded"}
    class_name = match["class_name"]
    cls = getattr(module, class_name, None)
    if cls is None:
        return {"callable": None, "detail": f"{class_name}.{symbol}: class_not_loaded"}
    member = getattr(cls, symbol, None)
    if callable(member) and _callable_accepts_without_self(member):
        return {"callable": member, "method": match}
    instance = None
    if policy.get("default_constructor_first"):
        try:
            instance = cls()
        except Exception:
            instance = None
    if instance is None and policy.get("safe_uninitialized_instance"):
        try:
            instance = object.__new__(cls)
        except Exception:
            instance = None
    if instance is None:
        return {"callable": None, "detail": f"{class_name}.{symbol}: instance_fixture_required"}
    attrs = dict(dict(policy.get("instance_attribute_profiles") or {}).get(f"{class_name}.{symbol}") or {})
    for key, value in attrs.items():
        setattr(instance, key, materialize(value))
    bound = getattr(instance, symbol, None)
    return {"callable": bound, "method": match, "instance_attributes": attrs} if callable(bound) else {"callable": None, "detail": f"{class_name}.{symbol}: method_not_bound"}


def _method_detail(method: dict[str, Any]) -> str:
    match = dict(method.get("method") or {})
    class_name = str(match.get("class_name") or "?")
    method_name = str(match.get("method_name") or "?")
    return f"{class_name}.{method_name}"


def _callable_accepts_without_self(func: object) -> bool:
    try:
        params = list(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return False
    return not params or params[0] not in {"self", "cls"}


def _unique_method_match(path: Path, symbol: str) -> dict[str, str] | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == symbol:
                matches.append({"class_name": node.name, "method_name": symbol})
    return matches[0] if len(matches) == 1 else None


def _module_profile_attrs(module_profiles: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    profiles = dict(dependency_stub_policy().get("generated_module_profiles") or {})
    names = {name for values in module_profiles.values() for name in values}
    return {name: dict(dict(profiles.get(name) or {}).get("attrs") or {}) for name in names}


def _unsupported(reason: str, detail: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"supported": False, "strict_negative": False, "reason": reason}
    if detail:
        result["detail"] = detail
    return result


def _reason_counts(skipped: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in skipped:
        reason = item["reason"]
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))
