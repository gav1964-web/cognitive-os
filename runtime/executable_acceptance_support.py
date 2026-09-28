"""Support analysis for generated executable acceptance harnesses."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .executable_acceptance_contract_inference import infer_argument_samples
from .executable_acceptance_isolation import load_source_isolated_callable
from .executable_acceptance_loading import (
    cleanup_dependency_stubs,
    import_path,
    install_dependency_profile_modules,
    load_supported_callable,
)
from .executable_acceptance_methods import load_method_callable, method_detail
from .executable_acceptance_module_path import package_import_target
from .executable_acceptance_policy import execution_context_policy, skipped_recovery_hint
from .executable_acceptance_samples import positive_samples_execute
from .executable_acceptance_support_binding import (
    ACCEPTED_PARAM_KINDS,
    _adapt_given_to_signature,
    _linked_contract_sources_requiring_override,
    _missing_required_samples,
    _signature_sample_value,
    _weaker_than_configured_fixture,
    positive_case_binding,
    signature_needs_negative_case,
)
from .executable_acceptance_support_results import module_profile_attrs as _module_profile_attrs
from .executable_acceptance_support_results import reason_counts as _reason_counts
from .executable_acceptance_support_results import unsupported as _unsupported
from .executable_acceptance_target_resolution import resolve_target_path
from .executable_acceptance_target_shape import ast_skip_reason


def harness_summary(project_dir: Path, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    targets: list[str] = []
    skipped: list[dict[str, str]] = []
    strict_negative: list[str] = []
    methods: dict[str, dict[str, str]] = {}
    method_attrs: dict[str, dict[str, Any]] = {}
    argument_mappings: dict[str, dict[str, str]] = {}
    argument_defaults: dict[str, dict[str, Any]] = {}
    argument_overrides: dict[str, dict[str, Any]] = {}
    sample_evidence: dict[str, dict[str, Any]] = {}
    dropped_payload: list[str] = []
    isolated: list[str] = []
    dependency_stubs: dict[str, list[str]] = {}
    metadata_profiles: dict[str, list[str]] = {}
    module_profiles: dict[str, list[str]] = {}
    effect_stubs: dict[str, list[str]] = {}
    resolved_paths: dict[str, str] = {}; target_imports: dict[str, dict[str, str]] = {}
    for row in obligations:
        target = str(row.get("target") or "")
        if not target or target in targets or any(item["target"] == target for item in skipped):
            continue
        resolution = resolve_target_path(project_dir, target.partition(":")[0])
        if not resolution["reason"] and resolution["path_text"] != target.partition(":")[0]:
            resolved_paths[target] = str(resolution["path_text"])
        support = callable_target_support(project_dir, target, obligations)
        if support["supported"]:
            module_name, import_root = package_import_target(Path(resolution["path"])); target_imports[target] = {"module": module_name, "root": str(import_root)} if module_name and import_root else {}
            targets.append(target)
            if support.get("method"):
                methods[target] = dict(support["method"])
            if support.get("method_instance_attributes"):
                method_attrs[target] = dict(support["method_instance_attributes"])
            if support.get("argument_mapping"):
                argument_mappings[target] = dict(support["argument_mapping"])
            if support.get("argument_defaults"):
                argument_defaults[target] = dict(support["argument_defaults"])
            if support.get("argument_overrides"):
                argument_overrides[target] = dict(support["argument_overrides"])
            if support.get("argument_sample_evidence"):
                sample_evidence[target] = dict(support["argument_sample_evidence"])
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
            if support.get("resolved_path_text"):
                resolved_paths[target] = str(support["resolved_path_text"])
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
        "execution_context": execution_context_policy(),
        "signal_strength": "executable_callable" if targets else "meta_only",
        "callable_harness_count": len(targets),
        "callable_targets": targets,
        "method_targets": methods,
        "method_instance_attributes": method_attrs,
        "argument_mappings": argument_mappings,
        "argument_defaults": argument_defaults,
        "argument_overrides": argument_overrides,
        "argument_sample_evidence": sample_evidence,
        "dropped_surplus_payload_targets": dropped_payload,
        "source_isolated_targets": isolated,
        "dependency_stub_targets": dependency_stubs,
        "dependency_metadata_profile_targets": metadata_profiles,
        "dependency_module_profile_targets": module_profiles,
        "dependency_module_profile_attrs": _module_profile_attrs(module_profiles),
        "effect_module_stub_targets": effect_stubs,
        "resolved_target_paths": resolved_paths,
        "target_imports": {key: value for key, value in target_imports.items() if value},
        "strict_negative_targets": strict_negative,
        "meta_checked_targets": [item["target"] for item in skipped],
        "skipped_targets": skipped,
        "skipped_reason_counts": _reason_counts(skipped),
    }


def callable_target_support(project_dir: Path, target: str, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    path_text, separator, symbol = target.partition(":")
    symbol_parts = symbol.split(".")
    if separator != ":" or not path_text.endswith(".py") or not symbol or len(symbol_parts) > 2:
        return _unsupported("unsupported_target_format")
    callable_symbol = symbol_parts[-1]
    resolution = resolve_target_path(project_dir, path_text)
    if resolution["reason"]:
        return _unsupported(str(resolution["reason"]), str(resolution.get("detail") or ""))
    path = Path(resolution["path"])
    path_text = str(resolution["path_text"])
    inferred = infer_argument_samples(path, symbol, project_root=project_dir)
    with import_path(project_dir, path):
        loaded = load_supported_callable(project_dir, path_text, callable_symbol, path)
    func = loaded.get("callable")
    if loaded.get("reason") == "target_not_callable":
        method = load_method_callable(path, symbol, loaded.get("module"))
        if callable(method.get("callable")):
            func = method["callable"]
            detail = method_detail(method)
            binding = positive_case_binding(func, target, obligations, inferred)
            if not binding["accepted"]:
                cleanup_dependency_stubs(loaded)
                isolated_support = _isolated_retry(path, symbol, target, obligations, inferred)
                if isolated_support.get("supported"):
                    return isolated_support
                return _unsupported("positive_signature_mismatch", detail)
            diagnostics: list[str] = []
            with import_path(project_dir, path):
                samples_ok = _positive_samples_execute_with_profiles(
                    func,
                    target,
                    obligations,
                    dict(binding["mapping"]),
                    dict(binding["defaults"]),
                    bool(binding.get("drop_surplus_payload")),
                    list(loaded.get("dependency_module_profiles") or []),
                    diagnostics,
                    dict(binding["overrides"]),
                )
            if not samples_ok:
                cleanup_dependency_stubs(loaded)
                isolated_support = _isolated_retry(path, symbol, target, obligations, inferred)
                if isolated_support.get("supported"):
                    return isolated_support
                return _unsupported(
                    "positive_sample_execution_failed", diagnostics[0] if diagnostics else detail
                )
            cleanup_dependency_stubs(loaded)
            return {
                "supported": True,
                "strict_negative": signature_needs_negative_case(
                    func, target, obligations, synthetic_input_keys={"receiver_state"}
                ),
                "reason": "",
                "method": method["method"],
                "method_instance_attributes": method.get("instance_attributes", {}),
                "dependency_stubs": list(loaded.get("dependency_stubs") or []),
                "dependency_metadata_profiles": list(loaded.get("dependency_metadata_profiles") or []),
                "dependency_module_profiles": list(loaded.get("dependency_module_profiles") or []),
                "argument_mapping": binding["mapping"],
                "argument_defaults": binding["defaults"],
                "argument_overrides": binding["overrides"],
                "argument_sample_evidence": binding["evidence"],
                "drop_surplus_payload": bool(binding.get("drop_surplus_payload")),
                "resolved_path_text": path_text,
            }
        isolated = load_source_isolated_callable(path, symbol)
        if callable(isolated.get("callable")):
            cleanup_dependency_stubs(loaded)
            return _source_isolated_support(isolated, target, obligations, inferred)
        cleanup_dependency_stubs(loaded)
        return _unsupported(ast_skip_reason(path, symbol), str(method.get("detail") or ""))
    if loaded.get("reason"):
        cleanup_dependency_stubs(loaded)
        if str(loaded["reason"]) in {
            "import_failed_import_error",
            "import_failed_missing_module",
            "import_failed_runtime_error",
        }:
            isolated = load_source_isolated_callable(path, symbol)
            if callable(isolated.get("callable")):
                return _source_isolated_support(isolated, target, obligations, inferred)
        return _unsupported(str(loaded["reason"]), str(loaded.get("detail") or ""))
    if not callable(func):
        cleanup_dependency_stubs(loaded)
        return _unsupported(ast_skip_reason(path, symbol))
    binding = positive_case_binding(func, target, obligations, inferred)
    if not binding["accepted"]:
        cleanup_dependency_stubs(loaded)
        isolated_support = {} if loaded.get("source_isolated") else _isolated_retry(path, symbol, target, obligations, inferred)
        if isolated_support.get("supported"):
            return isolated_support
        return _unsupported("positive_signature_mismatch")
    diagnostics = []
    with import_path(project_dir, path):
        samples_ok = _positive_samples_execute_with_profiles(
            func,
            target,
            obligations,
            dict(binding["mapping"]),
            dict(binding["defaults"]),
            bool(binding.get("drop_surplus_payload")),
            list(loaded.get("dependency_module_profiles") or []),
            diagnostics,
            dict(binding["overrides"]),
        )
    if not samples_ok:
        cleanup_dependency_stubs(loaded)
        if not loaded.get("source_isolated"):
            isolated_support = _isolated_retry(path, symbol, target, obligations, inferred)
            if isolated_support.get("supported"):
                return isolated_support
        return _unsupported("positive_sample_execution_failed", diagnostics[0] if diagnostics else "")
    cleanup_dependency_stubs(loaded)
    return {
        "supported": True,
        "strict_negative": signature_needs_negative_case(
            func,
            target,
            obligations,
            synthetic_input_keys={"receiver_state"} if loaded.get("method") else set(),
        ),
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
        "argument_overrides": binding["overrides"],
        "argument_sample_evidence": binding["evidence"],
        "drop_surplus_payload": bool(binding.get("drop_surplus_payload")),
    }


def _positive_samples_execute_with_profiles(
    func: object, target: str, obligations: list[dict[str, Any]], mapping: dict[str, str], defaults: dict[str, Any], drop: bool, profiles: list[str], diagnostics: list[str] | None = None, overrides: dict[str, Any] | None = None
) -> bool:
    created = install_dependency_profile_modules(profiles)
    try:
        return positive_samples_execute(func, target, obligations, mapping, defaults, drop, diagnostics, overrides)
    finally:
        for name in reversed(created):
            sys.modules.pop(str(name), None)


def _source_isolated_support(
    loaded: dict[str, Any],
    target: str,
    obligations: list[dict[str, Any]],
    inferred: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    func = loaded["callable"]
    path = Path(str(loaded.get("source_path") or ""))
    source_inferred = inferred or (infer_argument_samples(path, target.partition(":")[2]) if path.is_file() else {})
    binding = positive_case_binding(func, target, obligations, source_inferred)
    diagnostics: list[str] = []
    if not binding["accepted"] or not positive_samples_execute(func, target, obligations, dict(binding["mapping"]), dict(binding["defaults"]), bool(binding.get("drop_surplus_payload")), diagnostics, dict(binding["overrides"])):
        return _unsupported("positive_sample_execution_failed", diagnostics[0] if diagnostics else "")
    return {"supported": True, "strict_negative": signature_needs_negative_case(func, target, obligations, synthetic_input_keys={"receiver_state"} if loaded.get("method") else set()), "reason": "", "method": dict(loaded.get("method") or {}), "method_instance_attributes": dict(loaded.get("method_instance_attributes") or {}), "source_isolated": True, "effect_module_stubs": [*list(loaded.get("effect_module_stubs") or []), *[f"wildcard:{name}" for name in loaded.get("wildcard_import_stubs") or []]], "argument_mapping": binding["mapping"], "argument_defaults": binding["defaults"], "argument_overrides": binding["overrides"], "argument_sample_evidence": binding["evidence"], "drop_surplus_payload": bool(binding.get("drop_surplus_payload"))}


def _isolated_retry(
    path: Path,
    symbol: str,
    target: str,
    obligations: list[dict[str, Any]],
    inferred: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    isolated = load_source_isolated_callable(path, symbol)
    if not callable(isolated.get("callable")):
        return _unsupported(str(isolated.get("reason") or "target_not_callable"), str(isolated.get("detail") or ""))
    return _source_isolated_support(isolated, target, obligations, inferred)


__all__ = [
    "callable_target_support",
    "harness_summary",
    "positive_case_binding",
    "signature_needs_negative_case",
]
