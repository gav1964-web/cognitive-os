"""Independently compare structural source contracts with project classification."""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "classification_consistency.json"


class ClassificationConsistencyError(ValueError):
    """Raised when consistency policy or evidence is invalid."""


@lru_cache(maxsize=1)
def load_classification_consistency_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "classification_consistency.v1":
        raise ClassificationConsistencyError("classification consistency policy schema mismatch")
    if payload.get("status") != "active" or not payload.get("contract_profiles"):
        raise ClassificationConsistencyError("classification consistency policy must be active and non-empty")
    if int(payload.get("maximum_python_files") or 0) < 1:
        raise ClassificationConsistencyError("classification consistency scan budget must be positive")
    for value in payload["contract_profiles"]:
        profile = dict(value or {})
        required = (
            "id", "source_path_markers",
            "expected_project_stratum", "expected_project_archetype",
        )
        if any(not profile.get(key) for key in required):
            raise ClassificationConsistencyError("classification consistency profile is incomplete")
        code_signals = (
            profile.get("required_function_names")
            or profile.get("required_function_prefixes_any")
            or profile.get("required_decorator_contains_any")
        )
        if not code_signals:
            raise ClassificationConsistencyError("classification consistency profile has no code signals")
    invariants = dict(payload.get("invariants") or {})
    if not all(invariants.get(key) is True for key in (
        "independent_from_matcher_result", "recognized_only_contradiction"
    )):
        raise ClassificationConsistencyError("classification consistency invariants are incomplete")
    if invariants.get("source_apply") is not False or invariants.get("promotion_applied") is not False:
        raise ClassificationConsistencyError("classification consistency cannot mutate source or promote")
    return payload


def evaluate_classification_consistency(
    *, project_dir: Path, recognition: dict[str, Any], policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    rules = policy or load_classification_consistency_policy()
    contracts, scan = _extract_contracts(project_dir.resolve(), rules)
    classification = dict(recognition.get("classification") or {})
    observed = {
        "recognition_status": str(recognition.get("status") or "unknown"),
        "project_stratum": str(classification.get("project_stratum") or ""),
        "project_archetype": str(classification.get("project_archetype") or ""),
    }
    contradictions = []
    for contract in contracts:
        expected = dict(contract["expected_classification"])
        mismatch = [
            field for field in ("project_stratum", "project_archetype")
            if observed[field] != expected[field]
        ]
        if observed["recognition_status"] == "recognized" and mismatch:
            contradictions.append({
                "contract_id": contract["contract_id"],
                "mismatched_fields": mismatch,
                "expected_classification": expected,
                "observed_classification": observed,
                "evidence": contract["evidence"],
            })
    if contradictions:
        status = "classification_contradiction"
    elif contracts:
        status = "consistent" if observed["recognition_status"] == "recognized" else "deferred_recognition_not_final"
    else:
        status = "no_independent_contract"
    return {
        "artifact_type": "ClassificationConsistencyEvidence",
        "schema_version": "classification_consistency_evidence.v1",
        "status": status,
        "authority": "independent_ast_contract_evaluator",
        "observed_classification": observed,
        "contracts": contracts,
        "contradictions": contradictions,
        "scan": scan,
        "safety": {"source_apply": False, "promotion_applied": False},
    }


def _extract_contracts(root: Path, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    excluded = {str(value).lower() for value in policy.get("excluded_path_parts") or []}
    maximum = int(policy["maximum_python_files"])
    scanned = 0
    parse_failures = 0
    modules: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part.lower() in excluded for part in relative.parts):
            continue
        if scanned >= maximum:
            break
        scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            parse_failures += 1
            continue
        functions = sorted({
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        })
        decorators = sorted({
            _decorator_name(decorator)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for decorator in node.decorator_list
            if _decorator_name(decorator)
        })
        if functions:
            modules.append({
                "path": relative.as_posix(),
                "functions": functions,
                "decorators": decorators,
            })
    contracts = []
    for value in policy["contract_profiles"]:
        profile = dict(value)
        required = {str(item) for item in profile["required_function_names"]}
        supporting = {str(item) for item in profile.get("supporting_function_names") or []}
        prefixes = tuple(str(item) for item in profile.get("required_function_prefixes_any") or [])
        decorator_markers = tuple(str(item) for item in profile.get("required_decorator_contains_any") or [])
        path_markers = [str(item).lower() for item in profile["source_path_markers"]]
        manifest_matches = _manifest_matches(root, profile, excluded)
        if profile.get("required_manifest_contains_all") and not manifest_matches:
            continue
        matches = []
        for module in modules:
            names = set(module["functions"])
            path_text = str(module["path"]).lower()
            if not required.issubset(names) or not any(marker in path_text for marker in path_markers):
                continue
            prefix_hits = sorted(name for name in names if prefixes and name.startswith(prefixes))
            decorator_hits = sorted(
                name for name in module["decorators"]
                if any(marker in name for marker in decorator_markers)
            )
            if len(prefix_hits) + len(decorator_hits) < int(profile.get("minimum_code_signals") or 0):
                continue
            supporting_hits = sorted(names.intersection(supporting))
            if len(supporting_hits) < int(profile.get("minimum_supporting_functions") or 0):
                continue
            matches.append({
                "path": module["path"],
                "required_functions": sorted(required),
                "supporting_functions": supporting_hits,
                "function_prefix_hits": prefix_hits,
                "decorator_hits": decorator_hits,
                "manifest_evidence": manifest_matches,
            })
        if matches:
            contracts.append({
                "contract_id": profile["id"],
                "expected_classification": {
                    "project_stratum": profile["expected_project_stratum"],
                    "project_archetype": profile["expected_project_archetype"],
                },
                "evidence": matches,
            })
    return contracts, {
        "python_files_scanned": scanned,
        "parse_failures": parse_failures,
        "scan_truncated": scanned >= maximum,
        "maximum_python_files": maximum,
    }


def _manifest_matches(root: Path, profile: dict[str, Any], excluded: set[str]) -> list[dict[str, Any]]:
    required = [str(item).lower() for item in profile.get("required_manifest_contains_all") or []]
    if not required:
        return []
    path_markers = {str(item).lower() for item in profile.get("manifest_path_markers") or []}
    matches = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.lower() not in path_markers:
            continue
        relative = path.relative_to(root)
        if any(part.lower() in excluded for part in relative.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            continue
        if all(marker in text for marker in required):
            matches.append({"path": relative.as_posix(), "markers": required})
    return matches


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""
