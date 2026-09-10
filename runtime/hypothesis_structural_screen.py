"""Rank cloned projects by cheap structural evidence for a portable signature."""

from __future__ import annotations
import ast
import builtins
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.python_parser_compatibility import parse_compatible_source
from runtime.python_source_files import iter_python_source_files
from runtime.first_slice_viability import runtime_call_scope_for
from runtime.source_contract_semantics import infer_source_contract
from runtime.source_contract_types import concrete_type


def screen_projects(
    projects: list[Path], portable_signature: str, policy: dict[str, Any]
) -> dict[str, Any]:
    """Return a bounded shortlist; this is retrieval evidence, never admission evidence."""
    target_effects, target_output = _signature_parts(portable_signature)
    target_context = [str(value) for value in policy.get("semantic_context") or []]
    static_context = [value for value in target_context if not value.startswith("executable_failure:")]
    screen_policy = {**policy, "semantic_context": static_context}
    rows = [_screen_project(Path(project), target_effects, target_output, screen_policy)
            for project in projects]
    ranked = sorted(rows, key=_rank_key)
    maximum = max(1, int(policy.get("maximum_shortlist_projects") or len(rows) or 1))
    minimum = min(maximum, max(0, int(policy.get("minimum_shortlist_projects") or 0)))
    recovery_required = bool(screen_policy.get("recovery_contract"))
    context_required = bool(static_context)
    matches = [row for row in ranked if row["structural_match_count"]
               and (not recovery_required or row["recovery_match_count"])
               and (not context_required or row["semantic_context_structural_match_count"])]
    selected = matches[:maximum]
    if len(selected) < minimum and not recovery_required and not context_required:
        selected_names = {row["project"] for row in selected}
        fallback = [row for row in ranked if row["project"] not in selected_names]
        selected.extend(fallback[: minimum - len(selected)])
    selected_names = {row["project"] for row in selected}
    for row in rows:
        row["selected_for_full_probe"] = row["project"] in selected_names
    return {
        "artifact_type": "HypothesisStructuralScreenReport",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "portable_signature": portable_signature,
        "target_effects": sorted(target_effects),
        "target_output_basis": target_output,
        "target_semantic_context": target_context,
        "static_semantic_context": static_context,
        "runtime_only_semantic_context": sorted(set(target_context) - set(static_context)),
        "candidate_project_count": len(rows),
        "structural_match_project_count": len(matches),
        "selected_project_count": len(selected),
        "selected_projects": [row["project"] for row in selected],
        "projects": sorted(rows, key=lambda row: row["project"].lower()),
    }


def _screen_project(
    project: Path, target_effects: set[str], target_output: str, policy: dict[str, Any]
) -> dict[str, Any]:
    maximum_files = max(1, int(policy.get("maximum_python_files") or 120))
    maximum_functions = max(1, int(policy.get("maximum_functions") or 3000))
    maximum_bytes = max(1024, int(policy.get("maximum_file_bytes") or 500_000))
    excluded = {str(value).lower() for value in policy.get("excluded_directories") or []}
    excluded_files = {str(value).lower() for value in policy.get("excluded_file_names") or []}
    excluded_prefixes = tuple(str(value).lower() for value in policy.get("excluded_file_prefixes") or [])
    excluded_callables = {str(value) for value in policy.get("excluded_callable_names") or []}
    files_scanned = functions_scanned = parse_failures = oversized_files = 0
    samples: list[dict[str, Any]] = []
    structural_matches = 0
    recovery_matches = 0
    best_score = 0
    recovery_samples: list[dict[str, Any]] = []
    context_hits: set[str] = set()
    contextual_structural_matches = 0
    contextual_samples: list[dict[str, Any]] = []
    context_tokens = dict(policy.get("semantic_context_tokens") or {})
    context_callable_tokens = dict(policy.get("semantic_context_callable_tokens") or {})
    required_context = {str(value) for value in policy.get("semantic_context") or []}
    for path in iter_python_source_files(project):
        relative = path.relative_to(project)
        if any(part.lower() in excluded for part in relative.parts[:-1]):
            continue
        if path.name.lower() in excluded_files or path.name.lower().startswith(excluded_prefixes):
            continue
        if files_scanned >= maximum_files or functions_scanned >= maximum_functions:
            break
        try:
            if path.stat().st_size > maximum_bytes:
                oversized_files += 1
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            searchable = f"{relative.as_posix()}\n{source}".lower()
            context_hits.update(
                context for context in required_context
                if any(str(token).lower() in searchable for token in context_tokens.get(context) or [])
            )
            tree, parser_mode = parse_compatible_source(source, relative.as_posix())
        except (OSError, SyntaxError):
            parse_failures += 1
            continue
        files_scanned += 1
        source_lines = source.splitlines(keepends=True)
        owners = _method_owners(tree)
        for node in _callable_nodes(tree):
            if node.name in excluded_callables:
                continue
            functions_scanned += 1
            signature = _signature(node)
            snippet = _node_text(source_lines, node)
            node_searchable = f"{relative.as_posix()}\n{snippet}".lower()
            node_context_hits = sorted(
                context for context in required_context
                if any(str(token).lower() in node_searchable for token in context_tokens.get(context) or [])
                and (
                    not context_callable_tokens.get(context)
                    or any(str(token).lower() in node.name.lower()
                           for token in context_callable_tokens.get(context) or [])
                )
            )
            evidence = infer_source_contract({
                "signature": signature,
                "snippet": snippet,
            })
            evidence["runtime_call_scope"] = runtime_call_scope_for(snippet)
            evidence.update(_recovery_fixture_facts(node))
            evidence["receiver_required"] = bool(
                id(node) in owners and node.args.args
                and node.args.args[0].arg in {"self", "cls"}
            )
            evidence["materializable_argument_count"] = _materializable_argument_count(
                signature, evidence
            )
            effects = {str(value) for value in evidence.get("observed_side_effects") or []}
            output = str(evidence.get("output_inference_basis") or "")
            normalized_output = _normalized_output_basis(output, policy)
            score, matched = _function_score(
                node.name, effects, normalized_output, target_effects, target_output, policy
            )
            best_score = max(best_score, score)
            if matched:
                structural_matches += 1
                if node_context_hits:
                    contextual_structural_matches += 1
            recovery_matched = _matches_recovery(evidence, policy)
            if recovery_matched:
                recovery_matches += 1
            if matched and len(samples) < int(policy.get("maximum_evidence_samples") or 8):
                sample = {
                    "source": f"{relative.as_posix()}:{_qualified_name(node, owners)}",
                    "line": int(getattr(node, "lineno", 0) or 0),
                    "observed_side_effects": sorted(effects),
                    "output_inference_basis": output,
                    "score": score,
                    **({"parser_mode": parser_mode} if parser_mode else {}),
                }
                samples.append(sample)
                if node_context_hits:
                    contextual_samples.append({
                        **sample, "semantic_context_matches": node_context_hits,
                    })
            if recovery_matched:
                recovery_samples.append({
                    "source": f"{relative.as_posix()}:{_qualified_name(node, owners)}",
                    "line": int(getattr(node, "lineno", 0) or 0),
                    "observed_side_effects": sorted(effects),
                    "output_inference_basis": output,
                    "argument_count": int(evidence.get("argument_count") or 0),
                    "typed_argument_count": int(evidence.get("typed_argument_count") or 0),
                    "materializable_argument_count": int(
                        evidence.get("materializable_argument_count") or 0
                    ),
                    "explicit_return_annotation": str(evidence.get("explicit_return_annotation") or ""),
                    "return_paths": int(evidence.get("return_paths") or 0),
                    "runtime_call_scope": str(evidence.get("runtime_call_scope") or ""),
                    "external_symbol_dependencies": list(
                        evidence.get("external_symbol_dependencies") or []
                    ),
                    "receiver_required": bool(evidence.get("receiver_required")),
                })
            if functions_scanned >= maximum_functions:
                break
    density = structural_matches / functions_scanned if functions_scanned else 0.0
    recovery_samples.sort(key=_recovery_rank)
    recovery_samples = recovery_samples[:int(policy.get("maximum_evidence_samples") or 8)]
    return {
        "project": project.name,
        "project_dir": project.as_posix(),
        "files_scanned": files_scanned,
        "functions_scanned": functions_scanned,
        "parse_failures": parse_failures,
        "oversized_files": oversized_files,
        "structural_score": best_score,
        "structural_match_count": structural_matches,
        "recovery_match_count": recovery_matches,
        "semantic_context_matches": sorted(context_hits),
        "semantic_context_match_count": len(context_hits),
        "semantic_context_structural_match_count": contextual_structural_matches,
        "contextual_evidence_samples": contextual_samples,
        "structural_match_density": round(density, 6),
        "evidence_samples": samples,
        "recovery_evidence_samples": recovery_samples,
    }


def _matches_recovery(evidence: dict[str, Any], policy: dict[str, Any]) -> bool:
    required = dict(policy.get("recovery_contract") or {})
    if not required:
        return False
    effects = list(evidence.get("observed_side_effects") or [])
    if required.get("no_observed_side_effects") and effects:
        return False
    if bool(evidence.get("state_mutation")) != bool(required.get("state_mutation")):
        return False
    if evidence.get("runtime_call_scope") == "external_global":
        return False
    usage_types = {str(value) for value in dict(evidence.get("argument_usage_types") or {}).values()}
    if "ProtocolLike" in usage_types:
        return False
    if evidence.get("external_symbol_dependencies"):
        return False
    if evidence.get("receiver_context_manager"):
        return False
    if int(evidence.get("materializable_argument_count") or 0) < int(
        evidence.get("argument_count") or 0
    ):
        return False
    if int(evidence.get("return_paths") or 0) < int(required.get("min_return_paths") or 0):
        return False
    forbidden = {str(value) for value in required.get("forbidden_output_inference_basis") or []}
    if str(evidence.get("output_inference_basis") or "") in forbidden:
        return False
    output = _normalized_output_basis(str(evidence.get("output_inference_basis") or ""), policy)
    expected = _normalized_output_basis(str(required.get("output_inference_basis") or ""), policy)
    return not expected or output == expected


def _materializable_argument_count(
    signature: dict[str, Any], evidence: dict[str, Any]
) -> int:
    covered = {
        str(row.get("name") or "")
        for row in signature.get("args") or []
        if isinstance(row, dict) and concrete_type(row.get("annotation"))
    }
    for field in (
        "docstring_argument_types", "argument_constraint_types", "argument_usage_types",
    ):
        covered.update(str(name) for name in dict(evidence.get(field) or {}))
    return len(covered - {""})


def _recovery_fixture_facts(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    parameters = {
        arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    }
    local_names = {
        child.id for statement in node.body for child in ast.walk(statement)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
    }
    allowed = parameters | local_names | set(dir(builtins))
    external = {
        child.id for statement in node.body for child in ast.walk(statement)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
        and child.id not in allowed and not child.id.isupper()
    }
    receiver_context = any(
        isinstance(child, (ast.With, ast.AsyncWith))
        and any(_receiver_root(item.context_expr) for item in child.items)
        for statement in node.body for child in ast.walk(statement)
    )
    return {
        "external_symbol_dependencies": sorted(external),
        "receiver_context_manager": receiver_context,
    }


def _receiver_root(node: ast.AST) -> bool:
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return isinstance(node, ast.Name) and node.id in {"self", "cls"}


def _recovery_rank(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    argument_count = int(row.get("argument_count") or 0)
    typed_count = int(row.get("typed_argument_count") or 0)
    explicit_return = str(row.get("explicit_return_annotation") or "").lower()
    return (
        max(0, argument_count - typed_count),
        int(bool(row.get("receiver_required"))),
        int(explicit_return in {"", "any", "typing.any", "object", "none", "nonetype"}),
        -int(row.get("return_paths") or 0),
        str(row.get("source") or ""),
    )


def _node_text(source_lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if not isinstance(start, int) or not isinstance(end, int):
        return ""
    return "".join(source_lines[max(0, start - 1) : end])


def _function_score(
    name: str, effects: set[str], output: str, target_effects: set[str], target_output: str,
    policy: dict[str, Any],
) -> tuple[int, bool]:
    weights = dict(policy.get("weights") or {})
    effect_exact = effects == target_effects
    effect_compatible = effect_exact or (bool(target_effects) and target_effects.issubset(effects))
    output_match = output == target_output
    score = 0
    if effect_exact:
        score += int(weights.get("exact_effects") or 60)
    elif effect_compatible:
        score += int(weights.get("compatible_effects") or 40)
    elif effects & target_effects:
        score += int(weights.get("overlapping_effects") or 15)
    if output_match:
        score += int(weights.get("output_basis") or 40)
    name_tokens = {
        str(value).lower()
        for value in dict(policy.get("callable_name_tokens") or {}).get(target_output, [])
    }
    name_parts = {value.lower() for value in re.findall(r"[A-Z]+(?=[A-Z]|$)|[A-Z]?[a-z]+|\d+", name)}
    if name_tokens & name_parts:
        score += int(weights.get("callable_name_signal") or 20)
    return score, effect_compatible and output_match


def _signature_parts(signature: str) -> tuple[set[str], str]:
    parts = str(signature).split("|", 2)
    effects = {value for value in (parts[1].split(",") if len(parts) > 1 else []) if value != "pure"}
    return effects, parts[2] if len(parts) > 2 else "unknown"


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    return {
        "args": [
            {"name": arg.arg, "annotation": _unparse(arg.annotation)}
            for arg in arguments if arg.arg not in {"self", "cls"}
        ],
        "returns": _unparse(node.returns),
    }


def _method_owners(tree: ast.AST) -> dict[int, str]:
    owners = {}
    for owner in ast.walk(tree):
        if not isinstance(owner, ast.ClassDef):
            continue
        for member in owner.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owners[id(member)] = owner.name
    return owners


def _callable_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    callables = [
        node for node in getattr(tree, "body", [])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    callables.extend(
        member for owner in ast.walk(tree) if isinstance(owner, ast.ClassDef)
        for member in owner.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return callables


def _qualified_name(
    node: ast.FunctionDef | ast.AsyncFunctionDef, owners: dict[int, str]
) -> str:
    owner = owners.get(id(node))
    return f"{owner}.{node.name}" if owner else node.name


def _unparse(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def _normalized_output_basis(output: str, policy: dict[str, Any]) -> str:
    for family, values in dict(policy.get("output_basis_families") or {}).items():
        if output in {str(value) for value in values or []}:
            return str(family)
    return output


def _rank_key(row: dict[str, Any]) -> tuple[int, int, float, int, str]:
    matches = int(row["structural_match_count"])
    return (
        -int(bool(matches)), -int(row["structural_score"]),
        -float(row["structural_match_density"]), -min(matches, 10),
        str(row["project"]).lower(),
    )
