"""Project-driven self-improvement loop for Cognitive OS roles."""

from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .foundation_semantic_quality import evaluate_foundation_semantic_quality
from .knowledge_admission import build_kb_candidate, write_kb_candidate
from .local_inference import LocalInferenceConfig
from .project_evolution_policy import load_project_evolution_policy
from .role_foundation_field_trial import (
    DEFAULT_GOAL,
    _case_status,
    _result_with_loaded_artifacts,
    _role_scores,
    _warnings,
)
from .role_foundation_pipeline import run_role_foundation_pipeline
from .self_improvement_analysis import diagnose_training_failure
from .self_improvement_trials import best_attempt, challenger_sources, trial_conclusion


def train_on_project(
    *,
    root: Path,
    project_dir: Path,
    target_score: float | None = None,
    local_config: LocalInferenceConfig | None = None,
    teacher_config: LocalInferenceConfig | None = None,
    write: bool = True,
) -> dict[str, Any]:
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    target = float(target_score or policy.get("trigger_score_below") or 9.7)
    source_before = _source_fingerprint(project_dir)
    baseline = _evaluate(root, project_dir, write=True)
    if baseline["status"] == "ok" and baseline["project_min_score"] >= target:
        return _report(project_dir, target, baseline, None, None, status="already_at_target")
    local = local_config or LocalInferenceConfig.from_env()
    teacher = teacher_config or LocalInferenceConfig.from_l45_env()
    failure_packet = _failure_packet(baseline, target)
    diagnosis = diagnose_training_failure(failure_packet, local_config=local, teacher_config=teacher)
    diagnosis = _validate_recommended_source(diagnosis, baseline)
    selected = teacher if dict(diagnosis.get("model_trace") or {}).get("tier") == "external_teacher" else local
    sources = challenger_sources(
        diagnosis,
        failure_packet,
        current_source=str(baseline.get("selected_extraction_candidate") or ""),
        limit=int(policy.get("max_challenger_attempts") or 3),
    )
    attempts = _run_training_attempts(root, project_dir, baseline, diagnosis, selected, target, sources)
    trained = best_attempt(baseline, attempts)
    conclusion = trial_conclusion(baseline, attempts)
    source_changed = _source_fingerprint(project_dir) != source_before
    outcome = _outcome(baseline, trained, target, source_changed=source_changed)
    candidate_path = _stage_experience(
        root, project_dir, diagnosis, baseline, trained, outcome, attempts, conclusion
    ) if write else None
    report = _report(project_dir, target, baseline, diagnosis, trained, status=outcome["status"])
    report["outcome"] = outcome
    report["training_attempts"] = attempts
    report["trial_conclusion"] = conclusion
    report["knowledge_candidate_path"] = candidate_path.as_posix() if candidate_path else None
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    return report


def _run_training_attempts(
    root: Path,
    project_dir: Path,
    baseline: dict[str, Any],
    diagnosis: dict[str, Any],
    selected: LocalInferenceConfig,
    target: float,
    sources: list[str],
) -> list[dict[str, Any]]:
    roles = set(diagnosis.get("target_roles") or [])
    trial_sources: list[str | None] = sources or [None]
    attempts: list[dict[str, Any]] = []
    for source in trial_sources:
        trial_diagnosis = {**diagnosis, "recommended_source": source or diagnosis.get("recommended_source")}
        context = _training_context(trial_diagnosis, baseline, target)
        advisory = replace(selected, advisory_context=context)
        result = _evaluate(
            root,
            project_dir,
            write=True,
            architect_config=advisory if source is None and "architect" in roles else None,
            spec_writer_config=advisory if source is not None or "spec_writer" in roles else None,
        )
        attempts.append({
            "parameter_changes": {
                "architect_advisory": bool(source is None and "architect" in roles),
                "spec_writer_advisory": bool(source is not None or "spec_writer" in roles),
                "spec_writer_candidate_preference": source,
                "model_tier": dict(diagnosis.get("model_trace") or {}).get("tier"),
            },
            "result": result,
        })
        if result["status"] == "ok" and result["project_min_score"] >= target:
            break
    return attempts


def _evaluate(
    root: Path,
    project_dir: Path,
    *,
    write: bool,
    architect_config: LocalInferenceConfig | None = None,
    spec_writer_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    result = run_role_foundation_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"{DEFAULT_GOAL} in {project_dir.name}",
        write=write,
        architect_advisory_config=architect_config,
        spec_writer_advisory_config=spec_writer_config,
    )
    loaded = _result_with_loaded_artifacts(result)
    semantic = evaluate_foundation_semantic_quality(loaded)
    result["foundation_semantic_quality"] = semantic
    scores = _role_scores({**result, "artifacts": loaded["artifacts"]})
    available = [float(value) for value in scores.values() if value is not None]
    return {
        "status": _case_status(result),
        "project_min_score": round(min(available), 2) if available else 0.0,
        "role_scores": scores,
        "selected_extraction_candidate": result.get("selected_extraction_candidate"),
        "selected_candidate_quality": result.get("selected_candidate_quality", {}),
        "warnings": _warnings(result),
        "safety": result.get("safety", {}),
        "artifacts": result.get("artifacts", {}),
    }


def _failure_packet(case: dict[str, Any], target: float) -> dict[str, Any]:
    packet = {
        "project_min_score": case["project_min_score"],
        "target_score": target,
        "role_scores": case["role_scores"],
        "status": case["status"],
        "selected_candidate": case.get("selected_extraction_candidate"),
        "candidate_quality": _compact_candidate_quality(case.get("selected_candidate_quality", {})),
        "warnings": case.get("warnings", [])[:12],
        "artifact_paths": {key: dict(value or {}).get("path") for key, value in case.get("artifacts", {}).items()},
        "artifact_evidence": _artifact_evidence(case.get("artifacts", {})),
    }
    encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > 6000:
        packet["artifact_evidence"] = _minimal_artifact_evidence(packet["artifact_evidence"])
    return packet


def _training_context(diagnosis: dict[str, Any], baseline: dict[str, Any], target: float) -> dict[str, Any]:
    return {
        "purpose": "improve a failed prior attempt without changing evaluation policy",
        "target_score": target,
        "prior_scores": baseline["role_scores"],
        "failure_class": diagnosis.get("failure_class"),
        "diagnosis": diagnosis.get("diagnosis"),
        "hypothesis": diagnosis.get("hypothesis"),
        "preferred_source": diagnosis.get("recommended_source"),
        "forbidden": ["invent source targets", "change score thresholds", "weaken safety gates"],
    }


def _outcome(
    before: dict[str, Any], after: dict[str, Any], target: float, *, source_changed: bool = False
) -> dict[str, Any]:
    regressions = [
        role for role, score in before["role_scores"].items()
        if score is not None and after["role_scores"].get(role) is not None and after["role_scores"][role] < score
    ]
    delta = round(after["project_min_score"] - before["project_min_score"], 2)
    reached = after["status"] == "ok" and after["project_min_score"] >= target
    improved = delta > 0 and not regressions and not source_changed
    return {
        "status": "confirmed_improvement" if (reached or improved) and not source_changed else "hypothesis_not_confirmed",
        "score_delta": delta,
        "target_reached": reached,
        "role_regressions": regressions,
        "source_project_changed": source_changed,
    }


def _stage_experience(
    root: Path,
    project_dir: Path,
    diagnosis: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    outcome: dict[str, Any],
    attempts: list[dict[str, Any]],
    conclusion: dict[str, Any],
) -> Path:
    confirmed = outcome["status"] == "confirmed_improvement"
    proposed = dict(diagnosis.get("proposed_knowledge") or {})
    proposed.update({"failure_class": diagnosis.get("failure_class"), "hypothesis": diagnosis.get("hypothesis")})
    proposed["trial_conclusion"] = conclusion
    candidate = build_kb_candidate(
        record_type="role_training_experience",
        proposed_record=proposed,
        source_cases=[{
            "project": project_dir.name,
            "status": "confirmed" if confirmed else "observed",
            "before": before["project_min_score"],
            "after": after["project_min_score"],
        }],
        teacher_reference=f"Cognitive OS self-improvement via {dict(diagnosis.get('model_trace') or {}).get('model')}",
    )
    candidate["training_outcome"] = outcome
    candidate["parameter_trials"] = [dict(row.get("parameter_changes") or {}) for row in attempts]
    return write_kb_candidate(candidate, root=root)


def _report(
    project_dir: Path,
    target: float,
    baseline: dict[str, Any],
    diagnosis: dict[str, Any] | None,
    trained: dict[str, Any] | None,
    *,
    status: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "CognitiveSelfImprovementReport",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "target_score": target,
        "baseline": baseline,
        "diagnosis": diagnosis,
        "trained_attempt": trained,
        "invariants": {
            "evaluation_policy_changed": False,
            "source_project_changes_allowed": False,
            "active_kb_auto_promotion": False,
        },
    }


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_improvement"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_improvement_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _artifact_evidence(artifacts: dict[str, Any]) -> dict[str, Any]:
    evidence = {}
    for key in ("architecture_decision", "technical_spec"):
        path = dict(artifacts.get(key) or {}).get("path")
        if not path:
            continue
        try:
            payload = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if key == "architecture_decision":
            first_slice = dict(payload.get("first_slice_contract") or {})
            evidence[key] = {
                "first_slice": {"goal": first_slice.get("goal"), "targets": list(first_slice.get("targets") or [])[:8]},
                "risks": [_compact_risk(row) for row in list(payload.get("risks") or [])[:4]],
                "advisory": payload.get("architect_advisory"),
            }
        else:
            contract = dict(payload.get("extraction_contract") or {})
            evidence[key] = {
                "status": contract.get("status"),
                "candidate": contract.get("candidate"),
                "semantic_quality": _compact_candidate_quality(contract.get("semantic_quality", {})),
                "ranked_candidates": [_compact_ranked(row) for row in list(contract.get("ranked_candidates") or [])[:5]],
            }
    return evidence


def _source_fingerprint(project_dir: Path) -> str:
    digest = hashlib.sha256()
    try:
        paths = sorted(project_dir.rglob("*.py"))
    except OSError:
        paths = []
    for path in paths:
        try:
            digest.update(path.relative_to(project_dir).as_posix().encode())
            digest.update(path.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()


def _compact_candidate_quality(value: Any) -> dict[str, Any]:
    row = dict(value or {})
    return {
        key: row.get(key)
        for key in ("target", "status", "score", "semantic_profile_ids", "contract_archetype_ids")
        if row.get(key) not in (None, "", [])
    }


def _compact_ranked(value: Any) -> dict[str, Any]:
    row = dict(value or {})
    return {
        "source": row.get("source"),
        "score": row.get("score"),
        "kind": row.get("kind"),
        "side_effects": list(row.get("side_effects") or [])[:5],
        "reasons": [str(item)[:160] for item in list(row.get("reasons") or [])[:4]],
    }


def _compact_risk(value: Any) -> dict[str, Any]:
    row = dict(value or {})
    return {key: row.get(key) for key in ("description", "evidence", "severity") if row.get(key)}


def _minimal_artifact_evidence(value: Any) -> dict[str, Any]:
    evidence = dict(value or {})
    adr = dict(evidence.get("architecture_decision") or {})
    spec = dict(evidence.get("technical_spec") or {})
    return {
        "architecture_decision": {"first_slice": adr.get("first_slice")},
        "technical_spec": {
            "status": spec.get("status"),
            "candidate": spec.get("candidate"),
            "semantic_quality": spec.get("semantic_quality"),
            "ranked_candidates": list(spec.get("ranked_candidates") or [])[:3],
        },
    }


def _validate_recommended_source(diagnosis: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    row = dict(diagnosis)
    recommended = str(row.get("recommended_source") or "")
    packet = _failure_packet(baseline, 9.7)
    spec = dict(dict(packet.get("artifact_evidence") or {}).get("technical_spec") or {})
    allowed = {str(item.get("source") or "") for item in list(spec.get("ranked_candidates") or [])}
    current = str(baseline.get("selected_extraction_candidate") or "")
    if recommended and (recommended not in allowed or recommended == current):
        row["recommended_source"] = ""
        code = "same_as_failed_target" if recommended == current else "recommended_source_outside_bounded_candidates"
        row.setdefault("policy_violations", []).append(code)
    return row
