"""Backfill and evaluate shadow self-development dossiers on proven changes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .self_development_change import (
    build_self_development_change_proposal,
    build_shadow_change_dossier,
    interpret_self_development_change,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_shadow_trial.json"


class SelfDevelopmentShadowTrialError(ValueError):
    """Raised when the shadow corpus or policy is not trustworthy."""


@lru_cache(maxsize=1)
def load_self_development_shadow_trial_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_shadow_trial.v1":
        raise SelfDevelopmentShadowTrialError("shadow trial policy schema mismatch")
    if payload.get("status") != "active":
        raise SelfDevelopmentShadowTrialError("shadow trial policy must be active")
    if int(payload.get("minimum_cases") or 0) < 1:
        raise SelfDevelopmentShadowTrialError("shadow trial minimum_cases must be positive")
    score = float(payload.get("minimum_case_score") or 0.0)
    if not 0.0 < score <= 1.0:
        raise SelfDevelopmentShadowTrialError("shadow trial score must be in (0, 1]")
    sources = payload.get("sources")
    if not isinstance(sources, list) or len(sources) < int(payload["minimum_cases"]):
        raise SelfDevelopmentShadowTrialError("shadow trial requires enough sources")
    for row in sources:
        if not isinstance(row, dict) or not all(row.get(key) for key in (
            "path", "expected_change_class", "expected_project_type"
        )):
            raise SelfDevelopmentShadowTrialError("shadow trial source is incomplete")
    invariants = dict(payload.get("invariants") or {})
    if not all(invariants.get(key) is True for key in (
        "backfill_is_read_only", "historical_promotion_is_evidence_not_authority"
    )) or invariants.get("source_apply") is not False or invariants.get("promotion_applied") is not False:
        raise SelfDevelopmentShadowTrialError("shadow trial invariants are unsafe")
    return payload


def run_self_development_shadow_trial(
    *,
    root: Path,
    policy: dict[str, Any] | None = None,
    write: bool = False,
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_self_development_shadow_trial_policy(
        str(base / "config" / "self_development_shadow_trial.json")
    )
    matrix_path = _resolve(base, str(rules["maturity_matrix"]))
    matrix = _read_json(matrix_path)
    mature = _mature_project_types(matrix)
    cases = []
    for source_rule in rules["sources"]:
        source_path = _resolve(base, str(source_rule["path"]))
        before = _sha256(source_path)
        transaction = _read_json(source_path)
        dossier = build_promotion_shadow_dossier(
            root=base,
            transaction=transaction,
            source_path=source_path,
            matrix_path=matrix_path,
        )
        case = evaluate_shadow_dossier(
            dossier=dossier,
            expected_change_class=str(source_rule["expected_change_class"]),
            expected_project_type=str(source_rule["expected_project_type"]),
            mature_project_types=mature,
            minimum_score=float(rules["minimum_case_score"]),
        )
        case["source"] = _relative(base, source_path)
        case["source_sha256"] = before
        case["source_unchanged"] = _sha256(source_path) == before
        cases.append(case)
    catalog_paths = sorted({
        str(dict(case["dossier"]["proposal"]).get("change", {}).get("target") or "")
        for case in cases
    })
    catalog_digests = {
        path: _sha256(_resolve(base, path))
        for path in catalog_paths if path and _resolve(base, path).is_file()
    }
    accepted = [case for case in cases if case["status"] == "validated_shadow"]
    checks = {
        "minimum_cases": len(cases) >= int(rules["minimum_cases"]),
        "all_cases_validated": len(accepted) == len(cases),
        "all_sources_unchanged": all(case["source_unchanged"] for case in cases),
        "mature_project_types_only": all(case["checks"]["mature_project_type"] for case in cases),
        "catalogs_unchanged": all(
            _sha256(_resolve(base, path)) == digest for path, digest in catalog_digests.items()
        ),
        "no_apply_authority": all(
            case["dossier"]["constraints"]["apply_source"] is False for case in cases
        ),
        "no_promotion_applied": all(
            case["dossier"]["constraints"]["promotion_applied"] is False for case in cases
        ),
    }
    report = {
        "artifact_type": "SelfDevelopmentShadowTrialReport",
        "schema_version": "self_development_shadow_trial_report.v1",
        "status": "validated_shadow" if all(checks.values()) else "needs_work",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "maturity_matrix": _relative(base, matrix_path),
        "maturity_matrix_sha256": _sha256(matrix_path),
        "mature_project_types": sorted(mature),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "summary": {
            "case_count": len(cases),
            "validated_case_count": len(accepted),
            "minimum_score": min((case["score"] for case in cases), default=0.0),
            "change_classes": sorted({case["actual_change_class"] for case in cases}),
            "project_types": sorted({case["actual_project_type"] for case in cases}),
        },
        "cases": cases,
        "catalog_digests": catalog_digests,
        "safety": {
            "mode": "historical_backfill_shadow_only",
            "source_apply": False,
            "promotion_applied": False,
            "historical_promotion_is_evidence_not_authority": True,
        },
    }
    if write:
        report["report_path"] = _write_report(base, report).as_posix()
    return report


def build_promotion_shadow_dossier(
    *,
    root: Path,
    transaction: dict[str, Any],
    source_path: Path,
    matrix_path: Path,
) -> dict[str, Any]:
    if transaction.get("artifact_type") != "ProjectNativeRepairPromotionTransaction":
        raise SelfDevelopmentShadowTrialError("unsupported shadow source artifact")
    evidence = dict(transaction.get("evidence") or {})
    development_rows = [dict(row) for row in list(evidence.get("development_reports") or [])]
    if not development_rows:
        raise SelfDevelopmentShadowTrialError("promotion transaction has no development evidence")
    project_types = _development_project_types(root, development_rows)
    if len(project_types) != 1:
        raise SelfDevelopmentShadowTrialError("promotion evidence must resolve to one project type")
    project_type = next(iter(project_types))
    checks = dict(transaction.get("checks") or {})
    matrix_digest = _sha256(matrix_path)
    proposal = build_self_development_change_proposal(
        problem={
            "summary": "Repeated verified project failures require reusable repair knowledge",
            "failure_signature": "+".join(sorted(str(item) for item in evidence.get("failure_kinds") or [])),
        },
        hypothesis={
            "summary": "A bounded repair-pattern catalog transfers across independent lineages",
            "expected_effect": "retain verified repairs without widening source-apply authority",
        },
        change={
            "target": str(transaction.get("catalog_path") or ""),
            "target_kind": "staged_pattern",
            "operation": "backfill_historical_repair_pattern_promotion",
            "patch_digest": str(transaction.get("after_digest") or ""),
        },
        evidence=[{
            "artifact_type": "HistoricalPromotionEvidence",
            "source": _relative(root, source_path),
            "source_sha256": _sha256(source_path),
            "projects": list(evidence.get("projects") or []),
            "development_reports": development_rows,
            "before_digest": transaction.get("before_digest"),
            "after_digest": transaction.get("after_digest"),
        }],
        impact_map={
            "components": ["knowledge_admission", "project_native_repair"],
            "roles": list(evidence.get("matrix_roles") or []),
            "project_types": [project_type],
            "contracts": sorted(str(item) for item in evidence.get("failure_kinds") or []),
            "changes_evaluator_architecture": False,
            "changes_admission_or_promotion": False,
            "changes_success_measure": False,
        },
        verification={
            "regression_passed": checks.get("regression_tests") is True,
            "independent_holdout_passed": checks.get("minimum_independent_lineages") is True,
            "independent_evaluator": True,
            "evaluator_fingerprint": matrix_digest,
            "historical_explicit_approval": checks.get("explicit_approval") is True,
        },
        rollback_plan={
            "strategy": "restore catalog snapshot bound to before_digest",
            "before_digest": transaction.get("before_digest"),
            "target": transaction.get("catalog_path"),
        },
    )
    return build_shadow_change_dossier(proposal)


def evaluate_shadow_dossier(
    *,
    dossier: dict[str, Any],
    expected_change_class: str,
    expected_project_type: str,
    mature_project_types: set[str],
    minimum_score: float,
) -> dict[str, Any]:
    proposal = dict(dossier.get("proposal") or {})
    classification = dict(proposal.get("classification") or {})
    impact = dict(proposal.get("impact_map") or {})
    evidence = list(proposal.get("evidence") or [])
    delta = dict(dossier.get("architectural_delta") or {})
    project_types = list(impact.get("project_types") or [])
    actual_project_type = project_types[0] if len(project_types) == 1 else None
    propose = interpret_self_development_change(proposal, action="propose")
    apply_admission = interpret_self_development_change(proposal, action="apply")
    checks = {
        "classification_matches_expected": classification.get("class") == expected_change_class,
        "classification_is_known": classification.get("known_target_kind") is True,
        "typed_evidence_present": bool(evidence) and all(row.get("artifact_type") for row in evidence),
        "impact_project_type_matches": actual_project_type == expected_project_type,
        "mature_project_type": actual_project_type in mature_project_types,
        "impact_roles_present": bool(impact.get("roles")),
        "impact_components_present": bool(impact.get("components")),
        "architectural_delta_complete": all(delta.get(key) for key in (
            "change_class", "target", "components", "roles", "project_types", "contracts"
        )),
        "proposal_integrity_passed": propose.get("status") == "allowed",
        "apply_requires_separate_authority": apply_admission.get("status") != "allowed",
        "shadow_constraints_hold": (
            dict(dossier.get("constraints") or {}).get("apply_source") is False
            and dict(dossier.get("constraints") or {}).get("promotion_applied") is False
        ),
    }
    score = round(sum(checks.values()) / len(checks), 4)
    return {
        "artifact_type": "SelfDevelopmentShadowTrialCase",
        "status": "validated_shadow" if score >= minimum_score and all(checks.values()) else "needs_work",
        "score": score,
        "expected_change_class": expected_change_class,
        "actual_change_class": classification.get("class"),
        "expected_project_type": expected_project_type,
        "actual_project_type": actual_project_type,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "dossier": dossier,
    }


def _development_project_types(root: Path, rows: list[dict[str, Any]]) -> set[str]:
    result = set()
    for row in rows:
        path = _resolve(root, str(row.get("path") or ""))
        report = _read_json(path)
        classification = dict(dict(report.get("recognition") or {}).get("classification") or {})
        project_type = str(classification.get("project_stratum") or "")
        if not project_type:
            raise SelfDevelopmentShadowTrialError(f"development report lacks project type: {path}")
        result.add(project_type)
    return result


def _mature_project_types(matrix: dict[str, Any]) -> set[str]:
    return {
        str(row.get("project_stratum"))
        for row in list(matrix.get("cells") or [])
        if row.get("applicable") is True and row.get("maturity") == "mature"
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SelfDevelopmentShadowTrialError(f"shadow source is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SelfDevelopmentShadowTrialError("shadow source escapes workspace") from exc
    return resolved


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_development_shadow_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
