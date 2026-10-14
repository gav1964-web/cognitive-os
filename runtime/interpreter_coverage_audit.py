"""Measure whether runtime transition producers emit interpreter authority traces."""

from __future__ import annotations

import ast
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "interpreter_coverage_audit.json"


@lru_cache(maxsize=1)
def load_interpreter_coverage_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "interpreter_coverage_audit.v1":
        raise ValueError("interpreter coverage policy schema mismatch")
    if payload.get("status") != "active" or not payload.get("required_modules"):
        raise ValueError("interpreter coverage policy scope is incomplete")
    if float(payload.get("minimum_coverage") or 0.0) != 1.0:
        raise ValueError("interpreter coverage must target complete authority")
    invariants = dict(payload.get("invariants") or {})
    if invariants.get("report_only") is not True or any(
        invariants.get(name) is not False for name in ("source_apply", "promotion_applied")
    ):
        raise ValueError("interpreter coverage policy boundary is unsafe")
    return payload


def run_interpreter_coverage_audit(*, root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    required_calls_by_module = dict(policy.get("required_authority_calls") or {})
    authority_calls = set(policy.get("authority_calls") or []) | {
        str(call)
        for calls in required_calls_by_module.values()
        for call in calls
    }
    transition_markers = set(policy.get("transition_markers") or [])
    modules = []
    for relative in policy.get("required_modules") or []:
        path = (root / str(relative)).resolve()
        path.relative_to(root.resolve())
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = _names(tree)
        strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        observed_transitions = sorted(marker for marker in transition_markers if marker in names or marker in strings or marker in source)
        observed_authority = sorted(authority_calls.intersection(names))
        required_authority = sorted(
            str(call) for call in required_calls_by_module.get(str(relative).replace("\\", "/"), [])
        )
        requires_trace = bool(observed_transitions)
        covered = (
            set(required_authority).issubset(observed_authority)
            if required_authority
            else bool(observed_authority)
        ) if requires_trace else True
        modules.append({
            "module": str(relative).replace("\\", "/"),
            "requires_interpreter_trace": requires_trace,
            "transition_markers": observed_transitions,
            "required_authority_calls": required_authority,
            "authority_calls": observed_authority,
            "status": "covered" if covered else "bypass_gap",
            "source_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    required = [row for row in modules if row["requires_interpreter_trace"]]
    covered_count = sum(row["status"] == "covered" for row in required)
    coverage = covered_count / len(required) if required else 1.0
    checks = {
        "all_required_modules_read": len(modules) == len(policy.get("required_modules") or []),
        "transition_producers_identified": bool(required),
        "authority_requirements_bound": all(
            row["required_authority_calls"] or row["authority_calls"] for row in required
        ),
        "minimum_coverage_met": coverage >= float(policy.get("minimum_coverage") or 1.0),
        "report_only": dict(policy.get("invariants") or {}).get("report_only") is True,
        "no_source_apply": True,
        "no_promotion_applied": True,
    }
    body = {
        "artifact_type": "InterpreterCoverageAudit",
        "schema_version": "interpreter_coverage_audit_report.v1",
        "status": "passed" if all(checks.values()) else "coverage_gap",
        "summary": {
            "module_count": len(modules), "transition_producer_count": len(required),
            "covered_count": covered_count, "bypass_gap_count": len(required) - covered_count,
            "coverage": round(coverage, 6),
        },
        "modules": modules,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "next_action": "enforce_interpreter_trace_at_orchestrator_boundaries" if coverage < 1.0 else "retain_trace_regression_gate",
        "safety": {"source_apply": False, "promotion_applied": False},
    }
    return {**body, "audit_digest": _digest(body)}


def _names(tree: ast.AST) -> set[str]:
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            result.add(node.id)
        elif isinstance(node, ast.Attribute):
            result.add(node.attr)
        elif isinstance(node, ast.alias):
            result.add(node.asname or node.name.rsplit(".", 1)[-1])
    return result


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
