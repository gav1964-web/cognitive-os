"""Evidence-backed diagnosis for project development."""

from __future__ import annotations

from typing import Any

from .project_development_policy import load_project_development_policy


def build_development_diagnosis(
    *,
    project: str,
    project_report: dict[str, Any],
    recognition: dict[str, Any],
    chain_case: dict[str, Any] | None = None,
    source_incompleteness: dict[str, Any] | None = None,
    classification_consistency: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_project_development_policy()
    issues: list[dict[str, Any]] = []
    status = str(recognition.get("status") or "unknown")
    if status != "recognized":
        issues.append(_issue("recognition_gap", [f"recognition.status:{status}", *recognition.get("ambiguity_reasons", [])], policy))
    consistency = dict(classification_consistency or {})
    if consistency.get("status") == "classification_contradiction":
        contradictions = list(consistency.get("contradictions") or [])
        evidence = [
            f"{row.get('contract_id')}:{','.join(row.get('mismatched_fields') or [])}"
            for row in contradictions if isinstance(row, dict)
        ]
        affected = [
            str(item.get("path") or "")
            for row in contradictions if isinstance(row, dict)
            for item in row.get("evidence") or [] if isinstance(item, dict)
        ]
        issues.append(_issue(
            "classification_contradiction", evidence, policy,
            subject="owned_contract_vs_project_identity", affected=affected,
        ))
    health = dict(project_report.get("source_health") or {})
    if health.get("status") == "damaged":
        issues.append(_issue("damaged_source", ["source_health.status:damaged", str(health.get("recommendation") or "")], policy))
    if health.get("project_shape") == "dirty_portfolio":
        issues.append(_issue("dirty_portfolio", ["source_health.project_shape:dirty_portfolio"], policy))
    high_risk_observations = []
    medium_risk_observations = []
    for risk in project_report.get("risks", []):
        if not isinstance(risk, dict) or risk.get("severity") not in {"high", "medium"}:
            continue
        severity = str(risk.get("severity"))
        allowed_key = (
            "actionable_high_risk_authorities"
            if severity == "high"
            else "actionable_medium_risk_authorities"
        )
        if not _corroborated_finding(
            risk,
            allowed_key=allowed_key,
            policy=policy,
        ):
            observations = high_risk_observations if severity == "high" else medium_risk_observations
            observations.append(dict(risk))
            continue
        rule = "high_project_risk" if severity == "high" else "medium_project_risk"
        issues.append(_issue(rule, [f"risk:{risk.get('code')}", str(risk.get("detail") or "")], policy, subject=str(risk.get("code") or "risk")))
    answers = dict(project_report.get("answers") or {})
    contracts = dict(answers.get("4_contracts_data") or {})
    weak = [str(value) for value in contracts.get("weak_contract_zones") or [] if value]
    actionable_contracts = _actionable_contract_failures(
        contracts=contracts,
        chain_case=chain_case,
        policy=policy,
    )
    source_incompleteness = dict(source_incompleteness or {})
    for row in source_incompleteness.get("actionable_findings") or []:
        candidate = {
            "target": str(row.get("target") or ""),
            "authority": str(row.get("authority") or ""),
            "detail": str(row.get("detail") or ""),
        }
        if candidate["target"] and candidate not in actionable_contracts:
            actionable_contracts.append(candidate)
    if actionable_contracts:
        targets = [str(row["target"]) for row in actionable_contracts]
        evidence = [
            f"{row['authority']}:{row['target']}"
            for row in actionable_contracts
        ]
        failure_kinds = sorted({str(row.get("failure_kind") or "") for row in actionable_contracts if row.get("failure_kind")})
        allowed_operators = sorted({
            str(operator)
            for failure_kind in failure_kinds
            for operator in dict(policy.get("verified_failure_reducers") or {}).get(failure_kind, [])
        })
        issue = _issue("weak_contracts", evidence[:8], policy, affected=targets[:8])
        issue["failure_kinds"] = failure_kinds
        issue["allowed_operator_ids"] = allowed_operators
        issue["failure_specific_reducer_required"] = True
        issue["failure_evidence"] = actionable_contracts[:8]
        issues.append(issue)
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    mixed = [dict(value) for value in readiness.get("mixed_responsibility_functions") or [] if isinstance(value, dict)]
    actionable_mixed = [
        row for row in mixed
        if _corroborated_finding(
            row,
            allowed_key="actionable_architecture_failure_authorities",
            policy=policy,
        )
    ]
    if actionable_mixed:
        refs = [_source_ref(row) for row in actionable_mixed]
        issues.append(_issue("mixed_responsibility", [value for value in refs if value][:8], policy, affected=refs[:8]))
    if chain_case and str(chain_case.get("binding_status") or "") == "blocked_no_safe_candidate":
        evidence = [str(value) for value in dict(chain_case.get("target_chain") or {}).get("adr_targets") or []]
        issues.append(_issue("no_safe_candidate", evidence[:8] or ["binding_status:blocked_no_safe_candidate"], policy))
    issues = _rank_issues(issues, policy)
    maximum = int(dict(policy["selection"]).get("maximum_active_issues") or 8)
    issues = [{**row, "issue_id": f"ISSUE-{index:03d}"} for index, row in enumerate(issues[:maximum], start=1)]
    return {
        "artifact_type": "ProjectDevelopmentDiagnosis",
        "status": "issues_found" if issues else "no_actionable_issue",
        "project": project,
        "issues": issues,
        "issue_count": len(issues),
        "evidence_authority": "ProjectMapReport + ProjectRecognitionDecision + optional full-chain case",
        "observations": {
            "weak_contract_zones": weak[:8],
            "actionable_contract_failures": actionable_contracts[:8],
            "mixed_responsibility_functions": mixed[:8],
            "actionable_mixed_responsibility": actionable_mixed[:8],
            "high_project_risks": high_risk_observations[:8],
            "medium_project_risks": medium_risk_observations[:8],
            "source_incompleteness": source_incompleteness,
            "classification_consistency": consistency,
        },
    }


def _actionable_contract_failures(
    *,
    contracts: dict[str, Any],
    chain_case: dict[str, Any] | None,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    diagnosis_policy = dict(policy.get("diagnosis_policy") or {})
    allowed = {
        str(value)
        for value in diagnosis_policy.get("actionable_contract_failure_authorities") or []
    }
    candidates = list(contracts.get("actionable_contract_failures") or [])
    if chain_case:
        candidates.extend(list(chain_case.get("contract_failure_evidence") or []))
    result = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        target = str(candidate.get("target") or "")
        authority = str(candidate.get("authority") or "")
        if not target or authority not in allowed or (target, authority) in seen:
            continue
        seen.add((target, authority))
        result.append({
            "target": target,
            "authority": authority,
            "detail": str(candidate.get("detail") or ""),
            "failure_kind": str(candidate.get("failure_kind") or "") or None,
            "failing_nodeids": [str(value) for value in candidate.get("failing_nodeids") or [] if value],
            "failure_signature": str(candidate.get("failure_signature") or "") or None,
        })
    return result


def _corroborated_finding(
    finding: dict[str, Any], *, allowed_key: str, policy: dict[str, Any]
) -> bool:
    authority = str(finding.get("authority") or "")
    allowed = {
        str(value)
        for value in dict(policy.get("diagnosis_policy") or {}).get(allowed_key) or []
    }
    return bool(authority and authority in allowed)


def _issue(rule_id: str, evidence: list[str], policy: dict[str, Any], *, subject: str | None = None, affected: list[str] | None = None) -> dict[str, Any]:
    rule = dict(dict(policy["issue_rules"]).get(rule_id) or {})
    return {
        "rule_id": rule_id,
        "subject": subject or rule_id,
        "category": rule.get("category"),
        "severity": rule.get("severity"),
        "confidence": rule.get("confidence"),
        "evidence": [value for value in evidence if value],
        "affected_targets": affected or [],
        "impact": f"Project evolution remains exposed to {subject or rule_id}",
    }


def _rank_issues(issues: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    order = {value: index for index, value in enumerate(dict(policy["selection"]).get("severity_order") or [])}
    return sorted(issues, key=lambda row: (order.get(str(row.get("severity")), 99), -float(row.get("confidence") or 0), str(row.get("rule_id")), str(row.get("subject"))))


def _source_ref(row: dict[str, Any]) -> str:
    direct = str(row.get("source") or row.get("target") or "")
    if direct:
        return direct
    path = str(row.get("path") or "")
    name = str(row.get("name") or "")
    return f"{path}:{name}" if path and name else name or path
