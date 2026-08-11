"""Infer bounded callable contract facts from source evidence."""

from __future__ import annotations

import ast
import re
import textwrap
from typing import Any


_WEAK_TYPES = {"", "any", "typing.any", "object", "inferredinput", "inferredoutput"}


def infer_source_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    precomputed = candidate.get("structural_contract")
    if isinstance(precomputed, dict) and precomputed:
        return dict(precomputed)
    signature = dict(candidate.get("signature") or {})
    snippet = _snippet_text(candidate.get("snippet"))
    function, source_complete = _function_node(snippet)
    args = [row for row in signature.get("args", []) or [] if isinstance(row, dict)]
    args = [row for row in args if str(row.get("name") or "") not in {"self", "cls"}]
    docstring_types = _docstring_argument_types(snippet, [str(row.get("name") or "") for row in args])
    constraint_types = _argument_constraint_types(function, [str(row.get("name") or "") for row in args])
    return_annotation = str(signature.get("returns") or "").strip()
    inferred_output, output_basis = _output_shape(function, return_annotation, snippet, source_complete=source_complete)
    typed_args = [row for row in args if _concrete_type(row.get("annotation"))]
    return {
        "source_body_available": function is not None,
        "source_body_complete": source_complete,
        "docstring_available": bool(ast.get_docstring(function)) if function is not None else _has_docstring_prefix(snippet),
        "docstring_argument_types": docstring_types,
        "argument_constraint_types": constraint_types,
        "argument_count": len(args),
        "typed_argument_count": len(typed_args),
        "explicit_return_annotation": return_annotation,
        "inferred_output_type": inferred_output,
        "output_inference_basis": output_basis,
        "return_paths": _return_path_count(function),
        "raises": _raise_names(function),
        "state_mutation": _has_state_mutation(function),
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
    concrete_inputs = [value for value in inputs.values() if _concrete_type(value)]
    if inputs and len(concrete_inputs) == len(inputs):
        score += 6
        reasons.append("source-bound input shapes are concrete")
    elif concrete_inputs:
        score += 3
        reasons.append("source-bound input shapes are partially concrete")
    explicit_return = str(evidence.get("explicit_return_annotation") or "").strip()
    inferred_output = str(evidence.get("inferred_output_type") or "").strip()
    if _concrete_type(explicit_return) or explicit_return.lower() in {"none", "nonetype"}:
        score += 8
        reasons.append("return behavior is bound to an explicit annotation")
    elif _concrete_type(inferred_output) and _concrete_output(outputs):
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
    if "VoidSideEffect" in output_types and "memory_state" in declared_effects and evidence.get("source_body_complete"):
        score += 3
        reasons.append("state transition boundary is structurally proven")
    if not declared_effects and _all_contract_shapes_concrete(inputs, outputs) and evidence.get("source_body_complete"):
        score += 3
        reasons.append("complete source proves a bounded side-effect-free transform")
    return score, reasons


def _output_shape(function: ast.AST | None, annotation: str, snippet: str, *, source_complete: bool) -> tuple[str, str]:
    if annotation:
        if annotation.lower() in {"none", "nonetype"}:
            return "VoidSideEffect", "explicit_none_annotation"
        if annotation.lower() not in {"any", "typing.any", "object"}:
            return annotation, "explicit_return_annotation"
    if function is not None:
        assignments = _assignment_shapes(function)
        shapes = [_expression_shape(node.value, assignments) for node in ast.walk(function) if isinstance(node, ast.Return) and node.value]
        shapes = [shape for shape in shapes if shape]
        if shapes and len(set(shapes)) == 1:
            return shapes[0], "return_expression"
        if source_complete and not any(isinstance(node, ast.Return) and node.value for node in ast.walk(function)):
            return "VoidSideEffect", "no_value_return"
    lowered = snippet.lower()
    documented = _documented_output_shape(snippet)
    if documented:
        return documented, "docstring_return_contract"
    if "convert" in lowered and ("kwargs" in lowered or "mapping" in lowered or "dictionary" in lowered):
        return "MappingLike", "docstring_semantics"
    return "InferredOutput", "insufficient_structural_evidence"


def _assignment_shapes(function: ast.AST) -> dict[str, str]:
    shapes: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            shape = _expression_shape(value, shapes) if value is not None else ""
            for target in targets:
                if isinstance(target, ast.Name) and shape:
                    shapes[target.id] = shape
    return shapes


def _expression_shape(node: ast.AST, assignments: dict[str, str]) -> str:
    if isinstance(node, ast.Dict):
        return "MappingLike"
    if isinstance(node, (ast.List, ast.ListComp)):
        return "SequenceLike"
    if isinstance(node, ast.Tuple):
        return "TupleLike"
    if isinstance(node, ast.Set):
        return "SetLike"
    if isinstance(node, ast.Name):
        return assignments.get(node.id, "")
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Call):
        name = _call_name(node.func).lower()
        if any(token in name for token in ("render", "response", "redirect")):
            return "ResponseLike"
        if name.endswith(("dict", "to_dict", "kwargs")):
            return "MappingLike"
        if name.endswith(("list", "all")):
            return "SequenceLike"
    return ""


def _function_node(snippet: str) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, bool]:
    if not snippet:
        return None, False
    source = textwrap.dedent(snippet)
    try:
        tree = ast.parse(source)
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
    return sum(isinstance(node, ast.Return) for node in ast.walk(function)) if function is not None else 0


def _raise_names(function: ast.AST | None) -> list[str]:
    if function is None:
        return []
    return sorted({_call_name(node.exc.func if isinstance(node.exc, ast.Call) else node.exc) for node in ast.walk(function) if isinstance(node, ast.Raise) and node.exc} - {""})


def _has_state_mutation(function: ast.AST | None) -> bool:
    if function is None:
        return False
    local_names = {
        target.id
        for node in ast.walk(function)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_target_mutates_external_state(target, local_names) for target in targets):
                return True
    return False


def _target_mutates_external_state(target: ast.AST, local_names: set[str]) -> bool:
    if isinstance(target, ast.Attribute):
        return True
    if isinstance(target, ast.Subscript):
        return not isinstance(target.value, ast.Name) or target.value.id not in local_names
    return False


def _call_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _snippet_text(value: object) -> str:
    return str(value.get("text") or "") if isinstance(value, dict) else str(value or "")


def _has_docstring_prefix(snippet: str) -> bool:
    return '"""' in snippet or "'''" in snippet


def _docstring_argument_types(snippet: str, names: list[str]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for name in names:
        if not name:
            continue
        patterns = (
            rf"(?m)^\s*{re.escape(name)}\s*:\s*([^\n]+)$",
            rf"(?m)^\s*{re.escape(name)}\s*\(([^)]+)\)\s*:",
        )
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                hints[name] = match.group(1).strip()
                break
    return hints


def _documented_output_shape(snippet: str) -> str:
    match = re.search(r"(?is)\breturns?\s*\n\s*-*\s*\n?\s*([A-Za-z_][A-Za-z0-9_.\[\], ]*)", snippet)
    if not match:
        return ""
    documented = match.group(1).strip()
    lowered = documented.lower()
    if "tuple" in lowered:
        return "TupleLike"
    if "dict" in lowered or "mapping" in lowered:
        return "MappingLike"
    if "list" in lowered or "sequence" in lowered:
        return "SequenceLike"
    return documented


def _argument_constraint_types(function: ast.AST | None, names: list[str]) -> dict[str, str]:
    if function is None:
        return {}
    values: dict[str, set[object]] = {name: set() for name in names}
    optional: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name) or node.left.id not in values:
            continue
        name = node.left.id
        for comparator in node.comparators:
            constants = _constraint_constants(comparator)
            optional.update([name] if None in constants else [])
            values[name].update(value for value in constants if value is not None)
    result = {}
    for name, constants in values.items():
        if not constants:
            continue
        literal = "Literal[" + ", ".join(repr(value) for value in sorted(constants, key=str)) + "]"
        result[name] = f"Optional[{literal}]" if name in optional else literal
    return result


def _constraint_constants(node: ast.AST) -> set[object]:
    if isinstance(node, ast.Constant):
        return {node.value}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {item.value for item in node.elts if isinstance(item, ast.Constant)}
    return set()


def _concrete_output(contract: dict[str, Any]) -> bool:
    return bool(contract) and all(_concrete_type(value) for value in contract.values())


def _all_contract_shapes_concrete(inputs: dict[str, Any], outputs: dict[str, Any]) -> bool:
    return bool(inputs and outputs) and all(_concrete_type(value) for value in [*inputs.values(), *outputs.values()])


def _concrete_type(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text not in _WEAK_TYPES and not text.startswith("inferred")
