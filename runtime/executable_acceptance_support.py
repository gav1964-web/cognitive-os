"""Support analysis for generated executable acceptance harnesses."""

from __future__ import annotations

import asyncio, inspect, io, sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from .executable_acceptance_loading import cleanup_dependency_stubs, import_path, install_dependency_profile_modules, load_supported_callable
from .executable_acceptance_isolation import load_source_isolated_callable
from .executable_acceptance_methods import load_method_callable, method_detail
from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import dependency_stub_policy, sample_value, skipped_recovery_hint
from .executable_acceptance_support_results import module_profile_attrs as _module_profile_attrs
from .executable_acceptance_support_results import reason_counts as _reason_counts
from .executable_acceptance_support_results import unsupported as _unsupported
from .executable_acceptance_target_shape import ast_skip_reason

ACCEPTED_PARAM_KINDS = {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}


def harness_summary(project_dir: Path, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    targets: list[str] = []
    skipped: list[dict[str, str]] = []
    strict_negative: list[str] = []
    methods: dict[str, dict[str, str]] = {}
    method_attrs: dict[str, dict[str, Any]] = {}
    argument_mappings: dict[str, dict[str, str]] = {}
    argument_defaults: dict[str, dict[str, Any]] = {}
    dropped_payload: list[str] = []
    isolated: list[str] = []
    dependency_stubs: dict[str, list[str]] = {}
    metadata_profiles: dict[str, list[str]] = {}
    module_profiles: dict[str, list[str]] = {}
    effect_stubs: dict[str, list[str]] = {}
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
            if support.get("drop_surplus_payload"):
                dropped_payload.append(target)
            if support.get("source_isolated"):
                isolated.append(target)
            if support.get("dependency_stubs"):
                dependency_stubs[target] = list(support["dependency_stubs"])
            if support.get("dependency_metadata_profiles"):
                metadata_profiles[target] = list(support["dependency_metadata_profiles"])
            if support.get("dependency_module_profiles"):
                module_profiles[target] = list(support["dependency_module_profiles"])
            if support.get("effect_module_stubs"):
                effect_stubs[target] = list(support["effect_module_stubs"])
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
        "dropped_surplus_payload_targets": dropped_payload,
        "source_isolated_targets": isolated,
        "dependency_stub_targets": dependency_stubs,
        "dependency_metadata_profile_targets": metadata_profiles,
        "dependency_module_profile_targets": module_profiles,
        "dependency_module_profile_attrs": _module_profile_attrs(module_profiles),
        "effect_module_stub_targets": effect_stubs,
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
        method = load_method_callable(path, symbol, loaded.get("module"))
        if callable(method.get("callable")):
            func = method["callable"]
            detail = method_detail(method)
            binding = positive_case_binding(func, target, obligations)
            if not binding["accepted"]:
                cleanup_dependency_stubs(loaded)
                return _unsupported("positive_signature_mismatch", detail)
            with import_path(project_dir):
                samples_ok = _positive_samples_execute_with_profiles(
                    func,
                    target,
                    obligations,
                    dict(binding["mapping"]),
                    dict(binding["defaults"]),
                    bool(binding.get("drop_surplus_payload")),
                    list(loaded.get("dependency_module_profiles") or []),
                )
            if not samples_ok:
                cleanup_dependency_stubs(loaded)
                isolated_support = _isolated_retry(path, symbol, target, obligations)
                if isolated_support.get("supported"):
                    return isolated_support
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
                "drop_surplus_payload": bool(binding.get("drop_surplus_payload")),
            }
        isolated = load_source_isolated_callable(path, symbol)
        if callable(isolated.get("callable")):
            cleanup_dependency_stubs(loaded)
            return _source_isolated_support(isolated, target, obligations)
        cleanup_dependency_stubs(loaded)
        return _unsupported(ast_skip_reason(path, symbol), str(method.get("detail") or ""))
    if loaded.get("reason"):
        cleanup_dependency_stubs(loaded)
        if str(loaded["reason"]) in {"import_failed_missing_module", "import_failed_runtime_error"}:
            isolated = load_source_isolated_callable(path, symbol)
            if callable(isolated.get("callable")):
                return _source_isolated_support(isolated, target, obligations)
        return _unsupported(str(loaded["reason"]), str(loaded.get("detail") or ""))
    if not callable(func):
        cleanup_dependency_stubs(loaded)
        return _unsupported(ast_skip_reason(path, symbol))
    binding = positive_case_binding(func, target, obligations)
    if not binding["accepted"]:
        cleanup_dependency_stubs(loaded)
        return _unsupported("positive_signature_mismatch")
    with import_path(project_dir):
        samples_ok = _positive_samples_execute_with_profiles(
            func,
            target,
            obligations,
            dict(binding["mapping"]),
            dict(binding["defaults"]),
            bool(binding.get("drop_surplus_payload")),
            list(loaded.get("dependency_module_profiles") or []),
        )
    if not samples_ok:
        cleanup_dependency_stubs(loaded)
        if not loaded.get("source_isolated"):
            isolated_support = _isolated_retry(path, symbol, target, obligations)
            if isolated_support.get("supported"):
                return isolated_support
        if loaded.get("source_isolated") and loaded.get("fallback_reason"):
            return _unsupported(str(loaded["fallback_reason"]), str(loaded.get("fallback_detail") or ""))
        return _unsupported("positive_sample_execution_failed")
    cleanup_dependency_stubs(loaded)
    return {
        "supported": True,
        "strict_negative": signature_needs_negative_case(func, target, obligations),
        "reason": "",
        "method": dict(loaded.get("method") or {}),
        "method_instance_attributes": dict(loaded.get("method_instance_attributes") or {}),
        "source_isolated": bool(loaded.get("source_isolated")),
        "dependency_stubs": list(loaded.get("dependency_stubs") or []),
        "dependency_metadata_profiles": list(loaded.get("dependency_metadata_profiles") or []),
        "dependency_module_profiles": list(loaded.get("dependency_module_profiles") or []),
        "effect_module_stubs": [*list(loaded.get("effect_module_stubs") or []), *[f"wildcard:{name}" for name in loaded.get("wildcard_import_stubs") or []]],
        "argument_mapping": binding["mapping"],
        "argument_defaults": binding["defaults"],
        "drop_surplus_payload": bool(binding.get("drop_surplus_payload")),
    }


def _positive_samples_execute_with_profiles(
    func: object, target: str, obligations: list[dict[str, Any]], mapping: dict[str, str], defaults: dict[str, Any], drop: bool, profiles: list[str]
) -> bool:
    created = install_dependency_profile_modules(profiles)
    try:
        return positive_samples_execute(func, target, obligations, mapping, defaults, drop)
    finally:
        for name in reversed(created):
            sys.modules.pop(str(name), None)


def _source_isolated_support(loaded: dict[str, Any], target: str, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    func = loaded["callable"]
    binding = positive_case_binding(func, target, obligations)
    if not binding["accepted"] or not positive_samples_execute(func, target, obligations, dict(binding["mapping"]), dict(binding["defaults"]), bool(binding.get("drop_surplus_payload"))):
        return _unsupported("positive_sample_execution_failed")
    return {"supported": True, "strict_negative": signature_needs_negative_case(func, target, obligations), "reason": "", "method": dict(loaded.get("method") or {}), "method_instance_attributes": dict(loaded.get("method_instance_attributes") or {}), "source_isolated": True, "effect_module_stubs": [*list(loaded.get("effect_module_stubs") or []), *[f"wildcard:{name}" for name in loaded.get("wildcard_import_stubs") or []]], "argument_mapping": binding["mapping"], "argument_defaults": binding["defaults"], "drop_surplus_payload": bool(binding.get("drop_surplus_payload"))}


def _isolated_retry(path: Path, symbol: str, target: str, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    isolated = load_source_isolated_callable(path, symbol)
    if not callable(isolated.get("callable")):
        return _unsupported(str(isolated.get("reason") or "target_not_callable"), str(isolated.get("detail") or ""))
    return _source_isolated_support(isolated, target, obligations)


def positive_case_binding(func: object, target: str, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return {"accepted": False, "mapping": {}, "defaults": {}, "drop_surplus_payload": False}
    mapping: dict[str, str] = {}
    defaults: dict[str, Any] = {}
    drop_surplus = False
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
                return {"accepted": False, "mapping": {}, "defaults": {}, "drop_surplus_payload": False}
            drop_surplus = drop_surplus or (not adapted and bool(given))
            mapping.update({actual: source for actual, source in adapted.items()})
        defaults.update(_missing_required_samples(signature, mapping))
    return {"accepted": True, "mapping": mapping, "defaults": defaults, "drop_surplus_payload": drop_surplus}


def signature_needs_negative_case(func: object, target: str, obligations: list[dict[str, Any]]) -> bool:
    malformed = [row for row in obligations if row.get("target") == target and row.get("kind") == "malformed_input_case"]
    if not malformed:
        return False
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    if positive_case_binding(func, target, obligations).get("drop_surplus_payload"):
        return False
    positive_rows = [row for row in obligations if row.get("target") == target and row.get("kind") == "positive_contract_case"]
    positive_keys = {str(key) for row in positive_rows for key in dict(row.get("given", {}))}
    explicit_params = {name for name, param in signature.parameters.items() if param.kind in ACCEPTED_PARAM_KINDS}
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
    drop_surplus_payload: bool = False,
) -> bool:
    seen: set[str] = set()
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        marker = repr((row.get("given", {}), row.get("expect", {})))
        if marker in seen:
            continue
        seen.add(marker)
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                given = _mapped_given(dict(row.get("given", {})), mapping or {}, drop_surplus_payload)
                payload = {**dict(defaults or {}), **given}
                args, kwargs = _call_args_kwargs(func, materialize(payload))
                try: asyncio.get_event_loop()
                except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
                result = func(*args, **kwargs)
                if isinstance(result, asyncio.Future) and result.done():
                    result = result.result()
                elif inspect.isawaitable(result):
                    result = asyncio.run(result)
                if not _positive_result_matches_expect(result, dict(row.get("expect") or {})):
                    return False
        except (Exception, SystemExit):
            return False
    return True


def _positive_result_matches_expect(result: Any, expect: dict[str, Any]) -> bool:
    if expect == {"completed": True}:
        return result is None or result is True or isinstance(result, dict)
    if any(key in expect for key in ("return_value", "equals", "result_value")):
        return result == expect[next(key for key in ("return_value", "equals", "result_value") if key in expect)]
    if set(expect) == {"result"}:
        return _matches_declared_result(result, str(expect.get("result") or ""))
    return True


def _matches_declared_result(result: Any, declared: str) -> bool:
    if isinstance(result, dict) and "result" in result:
        return _matches_declared_result(result["result"], declared)
    normalized = declared.lower()
    if normalized in {"str", "string"}:
        return isinstance(result, str)
    if normalized in {"int", "integer"}:
        return isinstance(result, int) and not isinstance(result, bool)
    if normalized in {"bool", "boolean"}:
        return isinstance(result, bool)
    if normalized in {"list", "array", "sequence"}:
        return isinstance(result, list)
    if normalized in {"dict", "mapping", "object"}:
        return isinstance(result, dict)
    if normalized in {"any", "inferredoutput", "inferred_output"}:
        return True
    if normalized in {"none", "null", "void"}:
        return result is None
    return result is not None
def _adapt_given_to_signature(signature: inspect.Signature, given: dict[str, Any]) -> dict[str, str] | None:
    params = [name for name, param in signature.parameters.items() if param.kind in ACCEPTED_PARAM_KINDS]
    if not params:
        return {}
    if set(given) <= set(params):
        return {key: key for key in given}
    exact = {name: name for name in params if name in given}
    required = {
        name
        for name, param in signature.parameters.items()
        if param.kind in ACCEPTED_PARAM_KINDS and param.default is inspect.Parameter.empty
    }
    if required <= set(exact):
        return exact
    if len(params) < len(given):
        return None
    return dict(zip(params, given))

def _missing_required_samples(signature: inspect.Signature, mapping: dict[str, str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if name in mapping or param.default is not inspect.Parameter.empty:
            continue
        if param.kind not in ACCEPTED_PARAM_KINDS:
            continue
        defaults[name] = _signature_sample_value(name, str(param.annotation or ""))
    return defaults


def _signature_sample_value(name: str, annotation: str) -> Any:
    return sample_value(annotation, name, signature_mode=True)

def _mapped_given(given: dict[str, Any], mapping: dict[str, str], drop_surplus_payload: bool = False) -> dict[str, Any]:
    if drop_surplus_payload:
        return {}
    if not mapping:
        return given
    return {actual: given[source] for actual, source in mapping.items() if source in given}

def _call_args_kwargs(func: object, payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return [], payload
    args: list[Any] = []
    kwargs = dict(payload)
    for name, param in signature.parameters.items():
        if param.kind != inspect.Parameter.POSITIONAL_ONLY or name not in kwargs:
            continue
        args.append(kwargs.pop(name))
    return args, kwargs
