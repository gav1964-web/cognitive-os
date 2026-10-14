"""Evaluate fresh post-cutoff project-development evidence as one blind batch."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_fresh_blind_trial.json"


class FreshBlindTrialError(ValueError):
    """Raised when fresh blind evidence is incomplete or unsafe."""


@lru_cache(maxsize=1)
def load_fresh_blind_trial_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_fresh_blind_trial.v1":
        raise FreshBlindTrialError("fresh blind trial policy schema mismatch")
    if payload.get("status") != "active":
        raise FreshBlindTrialError("fresh blind trial policy must be active")
    if int(payload.get("minimum_projects_per_type") or 0) < 3:
        raise FreshBlindTrialError("fresh blind trial requires three projects per type")
    targets = set(str(item) for item in payload.get("target_project_types") or [])
    if len(targets) != 3 or not payload.get("sources"):
        raise FreshBlindTrialError("fresh blind trial scope is incomplete")
    invariants = dict(payload.get("invariants") or {})
    if invariants.get("candidate_must_not_be_fabricated") is not True:
        raise FreshBlindTrialError("fresh blind trial must forbid fabricated candidates")
    if any(invariants.get(key) is not False for key in (
        "chain_hint_used", "sandbox_execution_used", "source_apply", "promotion_applied"
    )):
        raise FreshBlindTrialError("fresh blind trial execution boundary is unsafe")
    return payload


def run_fresh_blind_trial(
    *, root: Path, policy: dict[str, Any] | None = None, write: bool = False
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_fresh_blind_trial_policy(
        str(base / "config" / "self_development_fresh_blind_trial.json")
    )
    cutoff = _parse_time(str(rules["evidence_cutoff"]))
    checkpoint = _read_json(_resolve(base, str(rules["collector_checkpoint"])))
    processed = dict(checkpoint.get("processed") or {})
    prospective = _read_json(_resolve(base, str(rules["prospective_report"])))
    target_types = [str(item) for item in rules["target_project_types"]]
    coverage = {project_type: 0 for project_type in target_types}
    cases = []
    for source_rule in rules["sources"]:
        path = _resolve(base, str(source_rule["path"]))
        payload = _read_json(path)
        relative = path.relative_to(base).as_posix()
        digest = _sha256(path)
        classification = dict(dict(payload.get("recognition") or {}).get("classification") or {})
        actual = str(classification.get("project_stratum") or "")
        expected = str(source_rule["expected_project_type"])
        generated = _parse_time(str(payload.get("generated_at") or ""))
        recognition_status = str(dict(payload.get("recognition") or {}).get("status") or "")
        collector_row = dict(processed.get(relative) or {})
        checks = {
            "post_cutoff": generated > cutoff,
            "collector_digest_matches": collector_row.get("sha256") == digest,
            "source_safety": (
                dict(payload.get("safety") or {}).get("source_changes") is False
                and dict(payload.get("safety") or {}).get("automatic_kb_promotion") is False
            ),
            "expected_type_matches": actual == expected,
        }
        contrast = source_rule.get("contrast") is True
        if actual == expected and expected in coverage and not contrast:
            coverage[expected] += 1
        cases.append({
            "artifact_type": "SelfDevelopmentFreshBlindCase",
            "project": payload.get("project"),
            "source": relative,
            "source_sha256": digest,
            "expected_project_type": expected,
            "actual_project_type": actual,
            "recognition_status": recognition_status,
            "contrast": contrast,
            "issue_rules": sorted({
                str(row.get("rule_id"))
                for row in list(dict(payload.get("diagnosis") or {}).get("issues") or [])
                if isinstance(row, dict) and row.get("rule_id")
            }),
            "checks": checks,
            "status": "matched" if all(checks.values()) else "contrast_observed" if contrast else "needs_work",
        })
    minimum = int(rules["minimum_projects_per_type"])
    checks = {
        "all_sources_post_cutoff": all(case["checks"]["post_cutoff"] for case in cases),
        "all_sources_collected": all(case["checks"]["collector_digest_matches"] for case in cases),
        "all_sources_safe": all(case["checks"]["source_safety"] for case in cases),
        "target_type_coverage": all(count >= minimum for count in coverage.values()),
        "prospective_report_is_current": (
            prospective.get("audit", {}).get("post_cutoff_files") == len(cases)
        ),
        "candidate_not_fabricated": (
            prospective.get("status") == "waiting_for_evidence"
            and int(prospective.get("candidate_count") or 0) == 0
        ),
    }
    status = "evidence_exhausted" if all(checks.values()) else "needs_work"
    report = {
        "artifact_type": "SelfDevelopmentFreshBlindTrialReport",
        "schema_version": "self_development_fresh_blind_trial_report.v1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_cutoff": cutoff.isoformat(),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "coverage": coverage,
        "summary": {
            "case_count": len(cases),
            "matched_count": sum(case["status"] == "matched" for case in cases),
            "contrast_count": sum(case["contrast"] for case in cases),
            "recognized_count": sum(case["recognition_status"] == "recognized" for case in cases),
            "systematic_issue_count": sum(bool(case["issue_rules"]) for case in cases),
            "candidate_count": int(prospective.get("candidate_count") or 0),
        },
        "cases": cases,
        "prospective_report": str(rules["prospective_report"]),
        "safety": {
            "chain_hint_used": False,
            "sandbox_execution_used": False,
            "source_apply": False,
            "promotion_applied": False,
        },
    }
    if write:
        report["report_path"] = _write_report(base, report).as_posix()
    return report


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FreshBlindTrialError(f"invalid fresh evidence time: {value}") from exc
    if parsed.tzinfo is None:
        raise FreshBlindTrialError("fresh evidence time must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FreshBlindTrialError("fresh blind source escapes workspace") from exc
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FreshBlindTrialError(f"fresh blind source is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_development_fresh_blind_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
