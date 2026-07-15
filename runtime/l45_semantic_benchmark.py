"""Small benchmark for the L4.0 <-> L4.5 semantic loop."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cognitive_control_plane import run_prompt_product_control_plane
from .l45_semantic_corpus import generate_l45_semantic_cases
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
    {
        "case_id": "known_text_stats",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": "text_stats_cli",
        "expected_escalation": False,
        "expected_l4_action": "build_verified_system_package",
    },
    {
        "case_id": "known_json_log_filter",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает JSONL-файл логов, фильтрует записи уровня ERROR, пропускает malformed строки, сохраняет новый JSONL-файл, имеет README и тесты.",
        "supported_template": "json_log_filter_cli",
        "expected_escalation": False,
        "expected_l4_action": "build_verified_system_package",
    },
    {
        "case_id": "known_fastapi_kv",
        "prompt": "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, хранит данные в памяти, возвращает JSON, имеет controlled 404, README, тесты и команду запуска.",
        "supported_template": "fastapi_kv_store",
        "expected_escalation": False,
        "expected_l4_action": "build_verified_system_package",
    },
    {
        "case_id": "unknown_url_status_cli",
        "prompt": "Напиши CLI-утилиту с зависимостью requests, которая читает список URL из файла, проверяет HTTP status, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "unknown_csv_deduplicate",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, удаляет дубликаты по колонке email, сохраняет CSV-файл, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "unknown_json_validator",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает JSON-файл, валидирует обязательные поля id/name, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "unknown_markdown_link_report",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает markdown-файл, извлекает ссылки, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "unknown_fastapi_image_metadata",
        "prompt": "Сделай локальную FastAPI-службу с зависимостью fastapi, которая принимает JSON с именем изображения, возвращает JSON metadata report, имеет README, тесты и команду запуска.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "too_broad_anything",
        "prompt": "Сделай любую систему для обработки всего что нужно.",
        "supported_template": None,
        "expected_escalation": False,
        "expected_l4_action": "ask_clarification",
    },
    {
        "case_id": "unclear_missing_outputs",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "desktop_gui_boundary",
        "prompt": "Напиши desktop GUI приложение без внешних зависимостей, которое читает CSV файл, показывает таблицу, сохраняет JSON отчет, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "ask_clarification",
    },
    {
        "case_id": "source_edit_boundary",
        "prompt": "Измени исходники проекта: напиши CLI-утилиту без внешних зависимостей, которая читает JSON-файл, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog_requires_human_review",
    },
    {
        "case_id": "secret_boundary",
        "prompt": "Напиши CLI-утилиту с api key, которая читает URL из файла, вызывает внешний API, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": False,
        "expected_l4_action": "ask_clarification",
    },
    {
        "case_id": "network_scraper_boundary",
        "prompt": "Напиши CLI-скрапер с зависимостью requests, который читает URL, скачивает HTML, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog_requires_human_review",
    },
    {
        "case_id": "small_local_service_unknown",
        "prompt": "Сделай локальный сервис без внешней сети, который принимает JSON-файл, считает checksum, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "xlsx_to_json_unknown",
        "prompt": "Напиши CLI-утилиту с зависимостью openpyxl, которая читает XLSX-файл, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "html_title_knownish_unknown",
        "prompt": "Напиши CLI-утилиту без внешних зависимостей, которая читает HTML-файл, извлекает title, сохраняет JSON-отчёт, имеет README и тесты.",
        "supported_template": None,
        "expected_escalation": True,
        "expected_hypothesis_type": "new_template_candidate",
        "expected_l4_action": "record_template_backlog",
    },
    {
        "case_id": "unsupported_blockchain_boundary",
        "prompt": "Напиши blockchain smart contract, который принимает JSON input, возвращает transaction receipt JSON, имеет README и тесты, без внешних зависимостей.",
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
    generated_corpus_size: int | None = None,
    seed: int = 45,
    corpus_profile: str = "balanced",
) -> dict[str, Any]:
    policy = resolve_model_quality_mode(model_quality_mode, use_model_flag=use_model)
    selected_cases = cases
    corpus_kind = "curated"
    if selected_cases is None and generated_corpus_size is not None:
        selected_cases = generate_l45_semantic_cases(size=generated_corpus_size, seed=seed, profile=corpus_profile)
        corpus_kind = "generated"
    rows = [
        _run_case(root=root, case=case, write=write, policy=policy, config=config)
        for case in (selected_cases or BENCHMARK_CASES)
    ]
    passed = sum(1 for row in rows if row["status"] == "ok")
    report = {
        "artifact_type": "L45SemanticBenchmarkReport",
        "status": "ok" if passed == len(rows) else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_quality_mode": policy["mode"],
        "corpus": {
            "kind": corpus_kind,
            "seed": seed if corpus_kind == "generated" else None,
            "requested_size": generated_corpus_size if corpus_kind == "generated" else None,
            "profile": corpus_profile if corpus_kind == "generated" else None,
        },
        "summary": {
            "case_count": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "escalated": sum(1 for row in rows if row["actual"]["l4_5_required"]),
            "validated": sum(1 for row in rows if row["actual"].get("validation_status") == "accepted"),
            "model_used": sum(1 for row in rows if row["actual"].get("raw_model_output_used")),
            "model_fallbacks": sum(1 for row in rows if row["actual"].get("model_error")),
            "forbidden_actions_stripped": sum(1 for row in rows if row["actual"].get("forbidden_actions_stripped")),
            "proposal_payload_synthesized": sum(1 for row in rows if row["actual"].get("proposal_payload_synthesized")),
        },
        "cases": rows,
    }
    if write:
        out_dir = root / "artifacts" / "l45_semantic_benchmark"
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = (
            f"{policy['mode']}_generated_{corpus_profile}"
            if corpus_kind == "generated"
            else str(policy["mode"])
        )
        path = out_dir / f"l45_semantic_benchmark_{suffix}.json"
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
            "prompt_boundary": dict(gate.get("boundary_classification", {})).get("boundary"),
            "l4_5_required": decision["semantic_escalation"]["l4_5_required"],
            "role_next_action": decision["role_transition"]["next_action"],
            "hypothesis_type": (proposal or {}).get("hypothesis_type"),
            "validation_status": (validation or {}).get("status"),
            "validation_quality_score": dict((validation or {}).get("quality", {})).get("score"),
            "validation_failed_codes": dict((validation or {}).get("quality", {})).get("failed_codes"),
            "accepted_action": (validation or {}).get("accepted_action"),
            "policy_review": (validation or {}).get("policy_review"),
            "l4_action": actual_action,
            "backlog_created": backlog is not None,
            "replay_path": replay_path,
            "raw_model_output_used": dict((proposal or {}).get("hardening", {})).get("raw_model_output_used"),
            "forbidden_actions_stripped": dict((proposal or {}).get("hardening", {})).get("forbidden_actions_stripped"),
            "proposal_payload_synthesized": dict((proposal or {}).get("hardening", {})).get("proposal_payload_synthesized"),
            "model_error": dict((proposal or {}).get("hardening", {})).get("model_error"),
        },
    }


def _actual_action(decision: dict[str, Any], validation: dict[str, Any] | None) -> str:
    if validation is not None:
        return str(validation.get("accepted_action") or "blocked")
    return str(dict(decision.get("role_transition", {})).get("next_action") or "blocked")
