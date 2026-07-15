"""Small benchmark for the L4.0 <-> L4.5 semantic loop."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cognitive_control_plane import run_prompt_product_control_plane
from .l4_semantic_validation import validate_l45_semantic_proposal
from .l45_model_modes import resolve_model_quality_mode
from .prompt_adequacy import evaluate_prompt_adequacy
from .semantic_evidence_pack import build_semantic_evidence_pack
from .semantic_reasoner import build_semantic_hypothesis_request, build_stage2_template_backlog_item, run_semantic_reasoner
from .semantic_replay import build_semantic_replay_record, write_semantic_replay_record


BENCHMARK_CASES: list[dict[str, Any]] = [
    {
        "case_id": "unknown_csv_normalizer",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, нормализует значения в колонке name, сохраняет CSV-файл, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "known_csv_sort",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, сортирует строки по колонке name, сохраняет CSV-файл, имеет README и тесты.",
        "supported_template": "csv_sort_cli",
        "expected_escalation": False,
        "expected_l4_action": "build_verified_system_package",
    },
    {
        "case_id": "vague_prompt",
        "prompt": "Сделай полезную штуку для файлов.",
        "supported_template": None,
        "expected_escalation": False,
        "expected_l4_action": "ask_clarification",
    },
    {
        "case_id": "unsupported_system_type",
        "prompt": "Создай мобильное приложение с push-уведомлениями, авторизацией и публикацией в store.",
        "supported_template": None,
        "expected_escalation": False,
        "expected_l4_action": "ask_clarification",
    },
]


def run_l45_semantic_benchmark(
    *,
    root: Path,
    cases: list[dict[str, Any]] | None = None,
    write: bool = False,
    use_model: bool = False,
    model_quality_mode: str | None = None,
    config: Any = None,
) -> dict[str, Any]:
    policy = resolve_model_quality_mode(model_quality_mode, use_model_flag=use_model)
    rows = [
        _run_case(root=root, case=case, write=write, policy=policy, config=config)
        for case in (cases or BENCHMARK_CASES)
    ]
    passed = sum(1 for row in rows if row["status"] == "ok")
    report = {
        "artifact_type": "L45SemanticBenchmarkReport",
        "status": "ok" if passed == len(rows) else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_quality_mode": policy["mode"],
        "summary": {
            "case_count": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "escalated": sum(1 for row in rows if row["actual"]["l4_5_required"]),
            "validated": sum(1 for row in rows if row["actual"].get("validation_status") == "accepted"),
        },
        "cases": rows,
    }
    if write:
        out_dir = root / "artifacts" / "l45_semantic_benchmark"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "l45_semantic_benchmark.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _run_case(
    *,
    root: Path,
    case: dict[str, Any],
    write: bool,
    policy: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    gate = evaluate_prompt_adequacy(str(case["prompt"])).to_dict()
    decision = run_prompt_product_control_plane(
        prompt=str(case["prompt"]),
        prompt_adequacy=gate,
        supported_template=case.get("supported_template"),
        llm_invoked=bool(policy["use_model"]),
    )
    evidence_pack = build_semantic_evidence_pack(
        control_plane_decision=decision,
        prompt=str(case["prompt"]),
        prompt_adequacy=gate,
        supported_templates=[case["supported_template"]] if case.get("supported_template") else [],
        known_templates=["json_log_filter_cli", "text_stats_cli", "csv_sort_cli", "fastapi_csv_aggregator", "fastapi_kv_store"],
        context={"benchmark_case_id": case["case_id"]},
    )
    request = build_semantic_hypothesis_request(
        control_plane_decision=decision,
        context={"prompt": case["prompt"], "evidence_pack": evidence_pack},
    )
    proposal = None
    validation = None
    backlog = None
    replay_path = None
    if request is not None and policy["mode"] != "blocked_model_untrusted":
        proposal = run_semantic_reasoner(request=request, config=config, use_model=bool(policy["use_model"]))
        validation = validate_l45_semantic_proposal(request=request, proposal=proposal)
        if validation["accepted_action"] == "record_template_backlog":
            backlog = build_stage2_template_backlog_item(proposal)
        if write:
            replay = build_semantic_replay_record(
                request=request,
                proposal=proposal,
                validation=validation,
                evidence_pack=evidence_pack,
                model_quality_mode=str(policy["mode"]),
                outcome={"stage2_template_backlog_item": backlog},
            )
            replay_path = write_semantic_replay_record(root, replay).as_posix()
    actual_action = _actual_action(decision, validation)
    checks = {
        "escalation_matches": decision["semantic_escalation"]["l4_5_required"] == case.get("expected_escalation"),
        "hypothesis_matches": request is None
        or case.get("expected_hypothesis_type") is None
        or (proposal or {}).get("hypothesis_type") == case.get("expected_hypothesis_type"),
        "action_matches": actual_action == case.get("expected_l4_action"),
    }
    return {
        "case_id": case["case_id"],
        "status": "ok" if all(checks.values()) else "failed",
        "checks": checks,
        "expected": {
            "l4_5_required": case.get("expected_escalation"),
            "hypothesis_type": case.get("expected_hypothesis_type"),
            "l4_action": case.get("expected_l4_action"),
        },
        "actual": {
            "prompt_adequacy_status": gate.get("status"),
            "l4_5_required": decision["semantic_escalation"]["l4_5_required"],
            "role_next_action": decision["role_transition"]["next_action"],
            "hypothesis_type": (proposal or {}).get("hypothesis_type"),
            "validation_status": (validation or {}).get("status"),
            "accepted_action": (validation or {}).get("accepted_action"),
            "l4_action": actual_action,
            "backlog_created": backlog is not None,
            "replay_path": replay_path,
        },
    }


def _actual_action(decision: dict[str, Any], validation: dict[str, Any] | None) -> str:
    if validation is not None:
        return str(validation.get("accepted_action") or "blocked")
    return str(dict(decision.get("role_transition", {})).get("next_action") or "blocked")
