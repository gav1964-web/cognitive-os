"""Detect new systematic Cognitive OS errors without historical leakage."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .self_development_change import (
    build_self_development_change_proposal,
    build_shadow_change_dossier,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_prospective_detection.json"


class ProspectiveDetectionError(ValueError):
    """Raised when prospective evidence or policy violates its boundary."""


@lru_cache(maxsize=1)
def load_prospective_detection_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_prospective_detection.v1":
        raise ProspectiveDetectionError("prospective detection policy schema mismatch")
    if payload.get("status") != "active":
        raise ProspectiveDetectionError("prospective detection policy must be active")
    _parse_time(str(payload.get("evidence_cutoff") or ""))
    if int(payload.get("minimum_independent_projects") or 0) < 2:
        raise ProspectiveDetectionError("prospective detection requires independent projects")
    if not payload.get("allowed_project_types") or not payload.get("systematic_rule_ids"):
        raise ProspectiveDetectionError("prospective detection scope must be non-empty")
    systematic = set(str(item) for item in payload["systematic_rule_ids"])
    for signal_value in list(payload.get("derived_signals") or []):
        signal = dict(signal_value or {})
        if signal.get("rule_id") not in systematic or not signal.get("when"):
            raise ProspectiveDetectionError("derived signal must use an allowlisted rule")
        for predicate_value in signal["when"]:
            predicate = dict(predicate_value or {})
            operators = {"equals", "not_equals"}.intersection(predicate)
            if not predicate.get("path") or len(operators) != 1:
                raise ProspectiveDetectionError("derived signal predicate is invalid")
    if not str(payload.get("target") or "").startswith("knowledge/role_knowledge/"):
        raise ProspectiveDetectionError("prospective lesson target must stay in role knowledge")
    invariants = dict(payload.get("invariants") or {})
    required_true = (
        "pre_cutoff_evidence_forbidden",
        "cross_project_independence_required",
        "candidate_requires_future_holdout",
    )
    if not all(invariants.get(key) is True for key in required_true):
        raise ProspectiveDetectionError("prospective detection invariants are incomplete")
    if invariants.get("source_apply") is not False or invariants.get("promotion_applied") is not False:
        raise ProspectiveDetectionError("prospective detection cannot apply changes")
    return payload


def run_prospective_detection(
    *, root: Path, policy: dict[str, Any] | None = None, write: bool = False
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_prospective_detection_policy(
        str(base / "config" / "self_development_prospective_detection.json")
    )
    cutoff = _parse_time(str(rules["evidence_cutoff"]))
    source_dir = _resolve(base, str(rules["source_directory"]))
    matrix_path = _resolve(base, str(rules["maturity_matrix"]))
    mature = _mature_project_types(_read_json(matrix_path))
    allowed_types = set(str(item) for item in rules["allowed_project_types"])
    eligible_types = mature.intersection(allowed_types)
    systematic_rules = set(str(item) for item in rules["systematic_rule_ids"])
    observations: dict[tuple[str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    audit = {
        "files_seen": 0,
        "post_cutoff_files": 0,
        "pre_cutoff_excluded": 0,
        "out_of_scope_project_type": 0,
        "eligible_project_reports": 0,
        "eligible_reports_without_systematic_issue": 0,
        "non_systematic_issue": 0,
        "eligible_observations": 0,
    }
    source_digests: dict[str, str] = {}
    for path in sorted(source_dir.glob(str(rules["source_glob"]))):
        audit["files_seen"] += 1
        report = _read_json(path)
        generated_at = _parse_time(str(report.get("generated_at") or ""))
        if generated_at <= cutoff:
            audit["pre_cutoff_excluded"] += 1
            continue
        audit["post_cutoff_files"] += 1
        project = str(report.get("project") or "")
        project_type = str(
            dict(dict(report.get("recognition") or {}).get("classification") or {}).get("project_stratum") or ""
        )
        if not project or project_type not in eligible_types:
            audit["out_of_scope_project_type"] += 1
            continue
        audit["eligible_project_reports"] += 1
        source = _relative(base, path)
        source_digests[source] = _sha256(path)
        eligible_issue_count = 0
        for issue_value in _systematic_issues(report, rules):
            issue = dict(issue_value or {})
            rule_id = str(issue.get("rule_id") or "")
            if rule_id not in systematic_rules:
                audit["non_systematic_issue"] += 1
                continue
            eligible_issue_count += 1
            category = str(issue.get("category") or "unspecified")
            subject = str(issue.get("subject") or rule_id)
            signature = (rule_id, category, subject, project_type)
            observations[signature][project] = {
                "artifact_type": "ProspectiveSystematicErrorEvidence",
                "project": project,
                "project_type": project_type,
                "source": source,
                "source_sha256": source_digests[source],
                "generated_at": generated_at.isoformat(),
                "rule_id": rule_id,
                "category": category,
                "subject": subject,
                "status": report.get("status"),
            }
            audit["eligible_observations"] += 1
        if eligible_issue_count == 0:
            audit["eligible_reports_without_systematic_issue"] += 1
    candidates = []
    watchlist = []
    minimum = int(rules["minimum_independent_projects"])
    for signature, by_project in sorted(observations.items()):
        if len(by_project) < minimum:
            evidence = [by_project[name] for name in sorted(by_project)]
            watchlist.append({
                "signature": ":".join(signature),
                "status": "below_independence_threshold",
                "independent_project_count": len(by_project),
                "minimum_independent_projects": minimum,
                "additional_independent_projects_required": minimum - len(by_project),
                "projects": sorted(by_project),
                "evidence": evidence,
            })
            continue
        rule_id, category, subject, project_type = signature
        evidence = [by_project[name] for name in sorted(by_project)]
        proposal = build_self_development_change_proposal(
            problem={
                "summary": f"Systematic {rule_id} recurs across independent projects",
                "failure_signature": ":".join(signature),
            },
            hypothesis={
                "summary": f"A scoped lesson can reduce recurrence of {subject}",
                "expected_effect": "reduce the same systematic error on an unseen project",
            },
            change={
                "target": str(rules["target"]),
                "target_kind": "lesson",
                "operation": "append_prospective_systematic_error_lesson",
                "patch_digest": None,
            },
            evidence=evidence,
            impact_map={
                "components": ["self_improvement_diagnosis", "knowledge_admission"],
                "roles": list(dict(rules.get("role_scope_by_rule") or {}).get(rule_id) or []),
                "project_types": [project_type],
                "contracts": [f"{category}:{subject}"],
                "changes_evaluator_architecture": False,
                "changes_admission_or_promotion": False,
                "changes_success_measure": False,
            },
            verification={
                "regression_passed": False,
                "independent_holdout_passed": False,
                "independent_evaluator": False,
                "evaluator_fingerprint": _sha256(matrix_path),
            },
            rollback_plan={"strategy": "discard staged lesson candidate"},
        )
        candidates.append({
            "signature": ":".join(signature),
            "independent_project_count": len(by_project),
            "dossier": build_shadow_change_dossier(proposal),
            "next_required_evidence": [
                "unseen_project_holdout", "no_role_regression", "independent_evaluator_review"
            ],
        })
    checks = {
        "temporal_boundary_enforced": audit["pre_cutoff_excluded"] + audit["post_cutoff_files"] == audit["files_seen"],
        "mature_scope_configured": bool(eligible_types),
        "source_digests_captured": len(source_digests) == audit["post_cutoff_files"] - audit["out_of_scope_project_type"],
        "no_source_apply": True,
        "no_promotion_applied": True,
    }
    status = "candidate_detected" if candidates else "waiting_for_evidence"
    report = {
        "artifact_type": "SelfDevelopmentProspectiveDetectionReport",
        "schema_version": "self_development_prospective_detection_report.v1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_cutoff": cutoff.isoformat(),
        "eligible_project_types": sorted(eligible_types),
        "minimum_independent_projects": minimum,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "audit": audit,
        "watchlist_count": len(watchlist),
        "watchlist": watchlist,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "source_digests": source_digests,
        "safety": {
            "mode": "prospective_shadow_detection",
            "source_apply": False,
            "promotion_applied": False,
            "pre_cutoff_evidence_used": False,
        },
    }
    if write:
        report["report_path"] = _write_report(base, report).as_posix()
    return report


def _mature_project_types(matrix: dict[str, Any]) -> set[str]:
    return {
        str(row.get("project_stratum"))
        for row in list(matrix.get("cells") or [])
        if row.get("applicable") is True and row.get("maturity") == "mature"
    }


def _systematic_issues(report: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    issues = [
        dict(row)
        for row in list(dict(report.get("diagnosis") or {}).get("issues") or [])
        if isinstance(row, dict)
    ]
    for signal_value in list(policy.get("derived_signals") or []):
        signal = dict(signal_value or {})
        predicates = [dict(row or {}) for row in list(signal.get("when") or [])]
        if predicates and all(_predicate_matches(report, row) for row in predicates):
            issues.append({
                "rule_id": signal.get("rule_id"),
                "category": signal.get("category"),
                "subject": signal.get("subject"),
                "evidence": [
                    f"{row.get('path')}={_nested_value(report, str(row.get('path') or ''))}"
                    for row in predicates
                ],
            })
    return issues


def _predicate_matches(report: dict[str, Any], predicate: dict[str, Any]) -> bool:
    value = _nested_value(report, str(predicate.get("path") or ""))
    if "equals" in predicate:
        return value == predicate["equals"]
    if "not_equals" in predicate:
        return value != predicate["not_equals"]
    return False


def _nested_value(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProspectiveDetectionError(f"invalid prospective evidence time: {value}") from exc
    if parsed.tzinfo is None:
        raise ProspectiveDetectionError("prospective evidence time must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProspectiveDetectionError(f"prospective source is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ProspectiveDetectionError("prospective source escapes workspace") from exc
    return resolved


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_development_prospective_detection_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
