"""Option selection and outcome contracts for project development."""

from __future__ import annotations

from typing import Any


def build_development_options(diagnosis: dict[str, Any], *, policy: dict[str, Any]) -> dict[str, Any]:
    options = []
    maximum = int(dict(policy["selection"]).get("maximum_options_per_issue") or 3)
    for issue in diagnosis.get("issues", []):
        templates = list(dict(policy["option_templates"]).get(str(issue.get("category"))) or [])[:maximum]
        if issue.get("rule_id") in {"recognition_gap", "classification_contradiction", "damaged_source", "dirty_portfolio"}:
            templates = [row for row in templates if dict(row).get("route") == "research"]
        for template in templates:
            row = dict(template)
            utility = int(row.get("value") or 0) * 3 + int(row.get("reversibility") or 0) - int(row.get("cost") or 0) - int(row.get("risk") or 0)
            options.append({
                "option_id": f"{issue['issue_id']}:{row.get('id')}",
                "issue_id": issue["issue_id"],
                "strategy": row.get("id"),
                "route": row.get("route"),
                "value": row.get("value"),
                "cost": row.get("cost"),
                "risk": row.get("risk"),
                "reversibility": row.get("reversibility"),
                "utility_score": utility,
                "evidence": list(issue.get("evidence") or []),
            })
    return {"artifact_type": "ProjectDevelopmentOptionPortfolio", "status": "ready" if options else "empty", "options": options}


def select_development_option(diagnosis: dict[str, Any], portfolio: dict[str, Any], *, policy: dict[str, Any]) -> dict[str, Any]:
    issues = {str(row.get("issue_id")): row for row in diagnosis.get("issues", [])}
    minimum = float(dict(policy["selection"]).get("minimum_confidence") or 0.7)
    candidates = [row for row in portfolio.get("options", []) if float(dict(issues.get(str(row.get("issue_id"))) or {}).get("confidence") or 0) >= minimum]
    if not candidates:
        return {"artifact_type": "ProjectDevelopmentDecision", "status": "controlled_stop", "reason": "no_option_with_sufficient_evidence", "selected_option": None}
    severity = {value: index for index, value in enumerate(dict(policy["selection"]).get("severity_order") or [])}
    routes = {value: index for index, value in enumerate(dict(policy["selection"]).get("route_order") or [])}
    selected = sorted(candidates, key=lambda row: (
        severity.get(str(issues[row["issue_id"]].get("severity")), 99),
        int(str(row.get("issue_id") or "ISSUE-999").rsplit("-", 1)[-1]),
        routes.get(str(row.get("route")), 99),
        -int(row.get("utility_score") or 0),
        str(row.get("option_id")),
    ))[0]
    issue = issues[str(selected["issue_id"])]
    return {
        "artifact_type": "ProjectDevelopmentDecision",
        "status": "selected",
        "selected_issue": issue,
        "selected_option": selected,
        "rejected_options": [row for row in candidates if row.get("option_id") != selected.get("option_id")],
        "authority": "policy_ranked_evidence",
    }


def build_outcome_contract(decision: dict[str, Any], *, policy: dict[str, Any]) -> dict[str, Any]:
    selected = dict(decision.get("selected_option") or {})
    issue = dict(decision.get("selected_issue") or {})
    return {
        "artifact_type": "ProjectDevelopmentOutcomeContract",
        "status": "defined" if selected else "blocked",
        "issue_id": issue.get("issue_id"),
        "baseline_evidence": list(issue.get("evidence") or []),
        "expected_outcome": f"Resolve or measurably reduce {issue.get('rule_id')} without widening the approved scope" if issue else None,
        "required_checks": list(dict(policy["outcome_policy"]).get("required_checks") or []),
        "forbidden_success_substitutes": list(dict(policy["outcome_policy"]).get("forbidden_success_substitutes") or []),
        "reassessment": "rerun ProjectDevelopmentDiagnosis and compare the selected issue against baseline evidence",
    }
