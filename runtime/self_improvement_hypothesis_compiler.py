"""Compile repeated project failures into bounded, verifiable improvement hypotheses."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .hypothesis_compiler_contract import build_candidate, validate_candidate
from .hypothesis_compiler_evidence import (
    build_evidence_cluster,
    compact_report,
    load_compiler_reports,
)
from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .project_evolution_policy import load_project_evolution_policy


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "hypothesis_compiler.json"
Synthesizer = Callable[[dict[str, Any]], dict[str, Any]]


@lru_cache(maxsize=1)
def load_hypothesis_compiler_config(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_CONFIG
    payload = json.loads(source.read_text(encoding="utf-8"))
    _validate_config(payload)
    return payload


def compile_hypothesis(
    *, root: Path, report: dict[str, Any], write: bool = True,
    model_config: LocalInferenceConfig | None = None,
    synthesizer: Synthesizer | None = None, use_model: bool | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    config = load_hypothesis_compiler_config()
    if not config.get("enabled"):
        return _result("disabled", reason="hypothesis_compiler_disabled")
    normalization = dict(
        dict(load_project_evolution_policy().get("self_improvement") or {})
        .get("hypothesis_holdout", {}).get("signature_normalization") or {}
    )
    reports = history if history is not None else load_compiler_reports(
        root, limit=int(config["maximum_history_reports"]),
    )
    cluster = build_evidence_cluster(
        report, reports, normalization=normalization,
        maximum_cases=int(config["maximum_evidence_cases"]),
        maximum_counterexamples=int(config["maximum_counterexamples"]),
    )
    minimum = int(config["minimum_cluster_projects"])
    if int(cluster["observed_project_count"]) < minimum:
        return _write(root, _result(
            "collecting_evidence", cluster=cluster,
            reason="minimum_cluster_projects_not_reached",
            minimum_cluster_projects=minimum, candidates=[],
        ), write)
    candidate_type = _candidate_type(cluster)
    capability = str(dict(config["capability_routes"])[candidate_type])
    positive_refs = [str(row["project"]) for row in cluster["positive_cases"]]
    counter_refs = [str(row["project"]) for row in cluster["counterexamples"]]
    model_enabled = bool(config.get("model_enabled_in_training")) if use_model is None else use_model
    cached = _cached_model_abstraction(root, cluster) if write and model_enabled else None
    if cached:
        model_abstraction, model_trace = cached
    else:
        model_abstraction, model_trace = _model_abstraction(
            cluster, config, model_config, synthesizer, enabled=model_enabled,
        )
    candidate = build_candidate(
        candidate_type=candidate_type,
        failure_class=str(cluster["failure_class"]),
        portable_signature=str(cluster["portable_signature"]),
        semantic_context=list(cluster["semantic_context"]),
        evidence_refs=positive_refs, counterexample_refs=counter_refs,
        invariant=_invariant(cluster), desired_effect=_desired_effect(candidate_type),
        capability=capability, gates=list(config["validation_gates"]),
        confidence=_confidence(cluster, model_abstraction),
        model_abstraction=model_abstraction,
    )
    candidate, errors = validate_candidate(
        candidate,
        allowed_types={str(value) for value in config["allowed_candidate_types"]},
        allowed_capabilities={str(value) for value in dict(config["capability_routes"]).values()},
        forbidden_fields={str(value) for value in config["forbidden_output_fields"]},
        evidence_refs=set(positive_refs), counterexample_refs=set(counter_refs),
    )
    status = "compiled" if candidate else "rejected"
    return _write(root, _result(
        status, cluster=cluster, candidates=[candidate] if candidate else [],
        validation_errors=errors, model_trace=model_trace,
    ), write)


def enrich_diagnosis(
    diagnosis: dict[str, Any], compilation: dict[str, Any]
) -> dict[str, Any]:
    candidates = [dict(row) for row in compilation.get("candidates") or [] if row]
    if not candidates:
        return diagnosis
    return {
        **diagnosis,
        "compiled_hypotheses": candidates,
        "hypothesis_compiler_status": compilation.get("status"),
    }


def compile_existing_evidence(
    *, root: Path, limit: int = 2500, write: bool = True,
    use_model: bool = False, model_limit: int = 0,
    model_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    history = load_compiler_reports(root, limit=limit)
    config = load_hypothesis_compiler_config()
    normalization = dict(
        dict(load_project_evolution_policy().get("self_improvement") or {})
        .get("hypothesis_holdout", {}).get("signature_normalization") or {}
    )
    representatives: dict[str, dict[str, Any]] = {}
    cluster_projects: dict[str, set[str]] = {}
    for report in history:
        compact = compact_report(report, normalization)
        key = "|".join([
            str(compact["portable_signature"]),
            ",".join(compact["semantic_context"]) or "context_free",
        ])
        representatives.setdefault(key, report)
        if compact.get("project"):
            cluster_projects.setdefault(key, set()).add(str(compact["project"]))
    ordered = sorted(
        ((report, len(cluster_projects.get(key, set()))) for key, report in representatives.items()),
        key=lambda row: -row[1],
    )
    compilations = []
    eligible = [row for row in ordered if row[1] >= int(config["minimum_cluster_projects"])]
    for index, (report, _support) in enumerate(eligible):
        model_for_cluster = use_model and (model_limit <= 0 or index < model_limit)
        compilation = compile_hypothesis(
            root=root, report=report, write=write, use_model=model_for_cluster,
            model_config=model_config, history=history,
        )
        if compilation.get("status") == "compiled":
            compilations.append(compilation)
    result = {
        "artifact_type": "HypothesisCorpusCompilationReport",
        "status": "compiled" if compilations else "no_eligible_clusters",
        "source_report_count": len(history),
        "cluster_count": len(representatives),
        "compiled_hypothesis_count": sum(len(row.get("candidates") or []) for row in compilations),
        "model_compilation_count": sum(
            dict(row.get("model_trace") or {}).get("status") == "ok" for row in compilations
        ),
        "hypotheses": [candidate for row in compilations for candidate in row.get("candidates") or []],
    }
    if write:
        path = root / "artifacts" / "hypothesis_compiler" / "corpus_compilation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["report_path"] = path.as_posix()
    return result


def _model_abstraction(
    cluster: dict[str, Any], config: dict[str, Any], model_config: LocalInferenceConfig | None,
    synthesizer: Synthesizer | None, *, enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    support = int(cluster["observed_project_count"])
    milestones = {int(value) for value in config.get("model_support_milestones") or []}
    if not enabled or support not in milestones:
        return {}, {"status": "not_requested", "reason": "support_milestone_not_reached"}
    request = _synthesis_request(cluster)
    try:
        response = synthesizer(request) if synthesizer else call_json_chat(
            _messages(request), config=model_config or LocalInferenceConfig.from_env(),
        )
    except (LocalInferenceError, OSError, ValueError) as exc:
        return {}, {"status": "failed", "error": str(exc)[:500]}
    nested = response.get("abstraction")
    abstraction = dict(nested) if isinstance(nested, dict) else {
        str(key).removeprefix("abstraction."): value for key, value in response.items()
    }
    clean = {
        key: str(abstraction[key])[:800]
        for key in ("problem_pattern", "applicability", "counterexample_risk")
        if str(abstraction.get(key) or "").strip()
    }
    if not clean:
        return {}, {
            "status": "invalid", "reason": "model_abstraction_fields_missing",
            "response_fields": sorted(str(key) for key in response)[:12],
        }
    return clean, {
        "status": "ok", "authority": "hypothesis_only",
        "abstraction_fields": sorted(clean),
    }


def _cached_model_abstraction(
    root: Path, cluster: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    directory = root / "artifacts" / "hypothesis_compiler"
    support = int(cluster["observed_project_count"])
    for path in directory.glob(f"hc_*_support_{support}.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if dict(payload.get("cluster") or {}).get("cluster_key") != cluster["cluster_key"]:
            continue
        if dict(payload.get("model_trace") or {}).get("status") not in {"ok", "cached"}:
            continue
        candidates = list(payload.get("candidates") or [])
        if not candidates:
            continue
        abstraction = dict(dict(candidates[0]).get("abstraction") or {})
        model_fields = {
            key: str(abstraction[key]) for key in
            ("problem_pattern", "applicability", "counterexample_risk")
            if abstraction.get(key)
        }
        if model_fields:
            return model_fields, {
                "status": "cached", "authority": "hypothesis_only",
                "source": path.as_posix(),
            }
    return None


def _synthesis_request(cluster: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "project", "before_score", "after_score", "score_delta", "outcome_status",
        "executable_failure_family",
    )
    compact = lambda row: {key: row.get(key) for key in fields if row.get(key) not in {None, ""}}
    return {
        "artifact_type": "HypothesisAbstractionRequest",
        "failure_class": cluster["failure_class"],
        "portable_signature": cluster["portable_signature"],
        "semantic_context": cluster["semantic_context"],
        "positive_cases": [compact(row) for row in cluster["positive_cases"]],
        "counterexamples": [compact(row) for row in cluster["counterexamples"]],
        "allowed_output": {
            "abstraction": ["problem_pattern", "applicability", "counterexample_risk"],
        },
    }


def _messages(request: dict[str, Any]) -> list[dict[str, str]]:
    return [{
        "role": "system",
        "content": (
            "Abstract repeated Cognitive OS failures into one portable engineering hypothesis. "
            "Return JSON with only abstraction.problem_pattern, abstraction.applicability, and "
            "abstraction.counterexample_risk. Use supplied evidence only. Do not output code, diffs, "
            "paths, scoring changes, config mutations, or project-specific rules."
        ),
    }, {"role": "user", "content": json.dumps(request, ensure_ascii=False, separators=(",", ":"))}]


def _candidate_type(cluster: dict[str, Any]) -> str:
    positives = list(cluster["positive_cases"])
    reselections = [
        row for row in positives
        if row.get("selected_candidate") and row.get("successful_candidate")
        and row["selected_candidate"] != row["successful_candidate"]
        and float(row.get("score_delta") or 0) > 0
    ]
    if len(reselections) >= 2:
        return "candidate_selection_rule"
    failure_class = str(cluster["failure_class"])
    families = {str(row.get("executable_failure_family") or "") for row in positives}
    if failure_class == "dependency_boundary":
        return "executable_adapter"
    if failure_class == "executable_sample_contract" and families - {""}:
        return "fixture_strategy"
    if any(row.get("semantic_context") for row in positives):
        return "semantic_contract_profile"
    plugin_confirmations = sum(
        any(outcome.get("status") in {"trial_passed", "promoted"}
            for outcome in row.get("plugin_outcomes") or [])
        for row in positives
    )
    minimum = int(dict(load_hypothesis_compiler_config().get("evidence_planner") or {}).get(
        "minimum_consistent_action_cases") or 2)
    if plugin_confirmations < minimum:
        return "evidence_collection_plan"
    return "improvement_plugin_contract"


def _invariant(cluster: dict[str, Any]) -> str:
    context = ", ".join(cluster["semantic_context"]) or "context-free"
    return (
        f"Repeated {cluster['failure_class']} failures share structural signature "
        f"{cluster['portable_signature']} in {context} cases."
    )


def _desired_effect(candidate_type: str) -> str:
    return {
        "candidate_selection_rule": "Select a portable executable first-slice target without role regression.",
        "fixture_strategy": "Materialize bounded inputs that satisfy the measured callable contract.",
        "executable_adapter": "Represent the dependency boundary inside the acceptance sandbox only.",
        "semantic_contract_profile": "Recognize the recurring contract family from source evidence.",
        "evidence_collection_plan": "Acquire the missing independent evidence before implementing a plugin.",
        "improvement_plugin_contract": "Produce a bounded shadow-trial candidate for the recurring failure class.",
    }[candidate_type]


def _confidence(cluster: dict[str, Any], abstraction: dict[str, Any]) -> float:
    support = int(cluster["observed_project_count"])
    controls = len(cluster["counterexamples"])
    return min(0.95, 0.55 + min(support, 8) * 0.04 + min(controls, 3) * 0.03 + (0.05 if abstraction else 0))


def _result(status: str, **values: Any) -> dict[str, Any]:
    return {
        "artifact_type": "HypothesisCompilationReport", "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(), **values,
    }


def _write(root: Path, result: dict[str, Any], enabled: bool) -> dict[str, Any]:
    if not enabled:
        return result
    candidates = list(result.get("candidates") or [])
    identity = (
        str(dict(candidates[0]).get("hypothesis_id")) if candidates
        else hashlib.sha256(
            str(dict(result.get("cluster") or {}).get("cluster_key") or "empty").encode()
        ).hexdigest()[:12]
    )
    support = int(dict(result.get("cluster") or {}).get("observed_project_count") or 0)
    path = root / "artifacts" / "hypothesis_compiler" / f"{identity}_support_{support}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**result, "report_path": path.as_posix()}


def _validate_config(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "hypothesis_compiler.v1":
        raise ValueError("hypothesis compiler schema mismatch")
    if int(payload.get("minimum_cluster_projects") or 0) < 2:
        raise ValueError("hypothesis compiler requires at least two projects")
    types = {str(value) for value in payload.get("allowed_candidate_types") or []}
    routes = {str(key) for key in dict(payload.get("capability_routes") or {})}
    if not types or types != routes:
        raise ValueError("hypothesis compiler candidate types and routes must match")
    trial = dict(payload.get("trial_policy") or {})
    retries = int(trial.get("maximum_timeout_retries") or 0)
    multipliers = [float(value) for value in trial.get("timeout_retry_multipliers") or []]
    if retries < 0 or retries > len(multipliers) or any(value <= 1.0 for value in multipliers):
        raise ValueError("hypothesis compiler timeout retry policy is invalid")
    evidence = dict(payload.get("evidence_planner") or {})
    if int(evidence.get("minimum_consistent_action_cases") or 0) < 2:
        raise ValueError("hypothesis compiler evidence planner threshold is invalid")
    repository_gate = dict(trial.get("repository_regression_gate") or {})
    command = repository_gate.get("command") or []
    if repository_gate.get("enabled") and (
        not isinstance(command, list) or not command
        or any(not str(value).strip() for value in command)
        or float(repository_gate.get("timeout_seconds") or 0) <= 0
    ):
        raise ValueError("hypothesis compiler repository regression gate is invalid")
