"""Infer bounded callable contract facts from source evidence."""

from __future__ import annotations

import ast
import textwrap
from typing import Any

from runtime.source_contract_helpers import is_file_extension_policy, literal_return_only, local_type_factories, target_mutates_external_state, yield_path_count
from runtime.source_contract_types import all_contract_shapes_concrete, concrete_output, concrete_type
from runtime.source_ast_scope import callable_scope_walk, nested_definitions
from runtime.source_contract_docstrings import documented_output_shape, docstring_argument_types
from runtime.source_dispatch_evidence import has_receiver_request_dispatch
from runtime.source_effect_evidence import observed_side_effects
from runtime.source_expression_shapes import assignment_shapes, expression_shape
from runtime.python_parser_compatibility import parse_compatible_source
from runtime.source_contract_argument_semantics import (
    argument_constraint_types as _argument_constraint_types,
    argument_default_types as _argument_default_types,
    argument_names as _argument_names,
    argument_usage_types as _argument_usage_types,
    call_name as _call_name,
)

def infer_source_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    precomputed = candidate.get("structural_contract")
    if isinstance(precomputed, dict) and precomputed:
        return {
            **precomputed,
            "decorators": sorted(str(value) for value in candidate.get("decorators", []) if value),
            **({"owner_class": candidate["owner_class"]} if candidate.get("owner_class") else {}),
        }
    signature = dict(candidate.get("signature") or {})
    snippet = _snippet_text(candidate.get("snippet"))
    function, source_complete = _function_node(snippet)
    args = [row for row in signature.get("args", []) or [] if isinstance(row, dict)]
    args = [row for row in args if str(row.get("name") or "") not in {"self", "cls"}]
    docstring_types = docstring_argument_types(snippet, [str(row.get("name") or "") for row in args])
    argument_names = [str(row.get("name") or "") for row in args]
    constraint_types = {**_argument_default_types(function, argument_names), **_argument_constraint_types(function, argument_names)}
    usage_types = _argument_usage_types(function, [str(row.get("name") or "") for row in args])
    return_annotation = str(signature.get("returns") or "").strip()
    inferred_output, output_basis = _output_shape(function, return_annotation, snippet, source_complete=source_complete)
    typed_args = [row for row in args if concrete_type(row.get("annotation"))]
    return {
        "source_body_available": function is not None,
        "async_callable": isinstance(function, ast.AsyncFunctionDef),
        "source_body_complete": source_complete,
        "docstring_available": bool(ast.get_docstring(function)) if function is not None else _has_docstring_prefix(snippet),
        "docstring_argument_types": docstring_types,
        "argument_constraint_types": constraint_types,
        "argument_usage_types": usage_types,
        "argument_count": len(args),
        "typed_argument_count": len(typed_args),
        "explicit_return_annotation": return_annotation,
        "inferred_output_type": inferred_output,
        "output_inference_basis": output_basis,
        "return_paths": _return_path_count(function),
        "literal_return_only": literal_return_only(function),
        "yield_paths": yield_path_count(function),
        "raises": _raise_names(function),
        "state_mutation": _has_state_mutation(function),
        "dynamic_dispatch": has_receiver_request_dispatch(function) if function is not None else False,
        "file_extension_policy": is_file_extension_policy(function),
        "called_operations": _called_operations(function),
        "accessed_attributes": _accessed_attributes(function),
        "observed_side_effects": observed_side_effects(function, args),
        "decorators": sorted(str(value) for value in candidate.get("decorators", []) if value),
        **({"owner_class": candidate["owner_class"]} if candidate.get("owner_class") else {}),
    }


def structural_quality_adjustment(
    evidence: dict[str, Any],
    *,
    input_contract: dict[str, Any] | None = None,
    output_contract: dict[str, Any] | None = None,
    side_effect_contract: dict[str, Any] | None = None,
) -> tuple[int, list[str]]:
    if not evidence:
        return 0, []
    score = 0
    reasons: list[str] = []
    inputs = dict(input_contract or {})
    outputs = dict(output_contract or {})
    effects = dict(side_effect_contract or {})
    concrete_inputs = [value for value in inputs.values() if concrete_type(value)]
    if inputs and len(concrete_inputs) == len(inputs):
        score += 6
        reasons.append("source-bound input shapes are concrete")
    elif concrete_inputs:
        score += 3
        reasons.append("source-bound input shapes are partially concrete")
    explicit_return = str(evidence.get("explicit_return_annotation") or "").strip()
    inferred_output = str(evidence.get("inferred_output_type") or "").strip()
    if concrete_type(explicit_return) or explicit_return.lower() in {"none", "nonetype"}:
        score += 8
        reasons.append("return behavior is bound to an explicit annotation")
    elif concrete_type(inferred_output) and concrete_output(outputs):
        score += 5
        reasons.append("return shape is inferred from callable body or docstring")
    if evidence.get("source_body_complete"):
        score += 4
        reasons.append("complete callable body is available for structural contract review")
    elif evidence.get("source_body_available"):
        score += 1
        reasons.append("partial callable body provides limited structural evidence")
    if evidence.get("docstring_available"):
        score += 2
        reasons.append("callable docstring corroborates structural evidence")
    if evidence.get("raises") and evidence.get("source_body_complete"):
        score += 4
        reasons.append("explicit failure paths prove a negative contract")
    declared_effects = list(effects.get("declared") or [])
    if declared_effects and effects.get("retry_policy") and effects.get("requires_process_boundary"):
        score += 4
        reasons.append("declared side effects have explicit retry and isolation policy")
    elif "declared" in effects and evidence.get("source_body_complete"):
        score += 2
        reasons.append("complete source analysis found no declared side effects")
    input_types = {str(value) for value in inputs.values()}
    output_types = {str(value) for value in outputs.values()}
    if "RequestLike" in input_types and "ResponseLike" in output_types and evidence.get("source_body_complete"):
        score += 3
        reasons.append("framework request/response boundary is structurally proven")
    void_outputs = {"VoidSideEffect", "VoidPersistenceCommand"}
    mutating_effects = {"memory_state", "database", "filesystem_write", "network"}
    if output_types & void_outputs and set(declared_effects) & mutating_effects and evidence.get("source_body_complete"):
        score += 3
        reasons.append("state transition boundary is structurally proven")
    if (
        not declared_effects
        and not evidence.get("state_mutation")
        and not evidence.get("observed_side_effects")
        and all_contract_shapes_concrete(inputs, outputs)
        and evidence.get("source_body_complete")
    ):
        score += 3
        reasons.append("complete source proves a bounded side-effect-free transform")
    return score, reasons


def _output_shape(function: ast.AST | None, annotation: str, snippet: str, *, source_complete: bool) -> tuple[str, str]:
    if annotation:
        has_value_return = function is not None and any(
            isinstance(node, ast.Return) and node.value is not None for node in callable_scope_walk(function)
        )
        if annotation.lower() in {"none", "nonetype"} and not has_value_return:
            return "VoidSideEffect", "explicit_none_annotation"
        if annotation.lower() not in {"any", "typing.any", "object", "none", "nonetype"}:
            return annotation, "explicit_return_annotation"
    if function is not None:
        argument_names = [
            arg.arg
            for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
            if arg.arg not in {"self", "cls"}
        ]
        nested_callables = {node.name: "Callable" for node in nested_definitions(function) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        usage_shapes = _argument_usage_types(function, argument_names)
        assignments = {
            **usage_shapes,
            **assignment_shapes(function, usage_shapes),
            **local_type_factories(function),
            **nested_callables,
        }
        yielded = [node for node in callable_scope_walk(function) if isinstance(node, (ast.Yield, ast.YieldFrom))]
        if yielded:
            return "IteratorLike", "yield_expression"
        shapes = [expression_shape(node.value, assignments) for node in callable_scope_walk(function) if isinstance(node, ast.Return) and node.value]
        shapes = [shape for shape in shapes if shape]
        if shapes:
            unique = sorted(set(shapes))
            return (unique[0] if len(unique) == 1 else f"Union[{', '.join(unique)}]"), "return_expression"
        if source_complete and not any(isinstance(node, ast.Return) and node.value for node in callable_scope_walk(function)):
            return "VoidSideEffect", "no_value_return"
    lowered = snippet.lower()
    documented = documented_output_shape(snippet)
    if documented:
        return documented, "docstring_return_contract"
    if "convert" in lowered and ("kwargs" in lowered or "mapping" in lowered or "dictionary" in lowered):
        return "MappingLike", "docstring_semantics"
    return "InferredOutput", "insufficient_structural_evidence"


def _function_node(snippet: str) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, bool]:
    if not snippet:
        return None, False
    source = textwrap.dedent(snippet)
    try:
        tree, _ = parse_compatible_source(source, "<candidate-snippet>")
    except SyntaxError:
        return _partial_function_node(source), False
    return next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None), True


def _partial_function_node(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    lines = source.splitlines()
    for end in range(len(lines), 1, -1):
        candidate = "\n".join(lines[:end]).rstrip() + "\n    pass\n"
        try:
            tree = ast.parse(candidate)
        except SyntaxError:
            continue
        return next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    return None


def _return_path_count(function: ast.AST | None) -> int:
    return sum(isinstance(node, ast.Return) for node in callable_scope_walk(function)) if function is not None else 0


def _raise_names(function: ast.AST | None) -> list[str]:
    if function is None:
        return []
    return sorted({_call_name(node.exc.func if isinstance(node.exc, ast.Call) else node.exc) for node in callable_scope_walk(function) if isinstance(node, ast.Raise) and node.exc} - {""})


def _has_state_mutation(function: ast.AST | None) -> bool:
    if function is None:
        return False
    local_names = {
        target.id
        for node in callable_scope_walk(function)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    for node in callable_scope_walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
            if isinstance(node, ast.Delete):
                targets = node.targets
            elif isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
            if any(target_mutates_external_state(target, local_names) for target in targets):
                return True
    return False


def _called_operations(function: ast.AST | None) -> list[str]:
    if function is None:
        return []
    return sorted({_call_name(node.func) for node in callable_scope_walk(function) if isinstance(node, ast.Call)} - {""})


def _accessed_attributes(function: ast.AST | None) -> list[str]:
    if function is None:
        return []
    return sorted({node.attr for node in callable_scope_walk(function) if isinstance(node, ast.Attribute)})


def _snippet_text(value: object) -> str:
    return str(value.get("text") or "") if isinstance(value, dict) else str(value or "")


def _has_docstring_prefix(snippet: str) -> bool:
    return '"""' in snippet or "'''" in snippet
