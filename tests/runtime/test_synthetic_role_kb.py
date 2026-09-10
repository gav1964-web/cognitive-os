from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from runtime.synthetic_role_kb import (
    generate_llm_role_qa,
    generate_synthetic_role_qa,
    record_role_qa_feedback,
    search_synthetic_role_qa,
    synthetic_role_qa_audit,
    synthetic_probe_report,
    synthetic_role_qa_summary,
    write_synthetic_role_qa,
)
from runtime.local_inference import LocalInferenceConfig


def test_generate_synthetic_role_qa_uses_all_roles_without_promotion():
    corpus = generate_synthetic_role_qa(records_per_role=3)
    summary = synthetic_role_qa_summary(corpus)

    assert corpus["record_count"] > 21
    assert corpus["topic_record_count"] >= 100
    assert summary["by_role"]["architect"] > 3
    assert summary["by_trust_level"] == {"synthetic_seed": corpus["record_count"]}
    assert summary["by_answer_state"] == {"seeded": corpus["record_count"]}
    assert corpus["records"][0]["record_type"] == "role_qa"
    assert corpus["records"][0]["origin"]["kind"] == "synthetic_seed"
    assert corpus["policy"]["auto_promote"] is False
    assert "ground_truth" in corpus["policy"]["forbidden_uses"]


def test_search_synthetic_role_qa_returns_role_scoped_candidate():
    corpus = generate_synthetic_role_qa(records_per_role=20)

    result = search_synthetic_role_qa("acceptance criteria и contract для ТЗ", role_id="spec_writer", corpus=corpus)

    assert result["match_count"] > 0
    assert result["matches"][0]["role_id"] == "spec_writer"
    assert result["matches"][0]["answer"]["status"] == "candidate"
    assert result["matches"][0]["policy"]["auto_promote"] is False


def test_synthetic_probe_covers_core_roles():
    corpus = generate_synthetic_role_qa(records_per_role=50)
    report = synthetic_probe_report(corpus)

    assert report["covered"] == report["probe_count"]
    assert all(row["top_score"] > 0 for row in report["rows"])


def test_provider_interface_seed_answers_openai_api_question():
    corpus = generate_synthetic_role_qa(records_per_role=3)

    result = search_synthetic_role_qa(
        "для работы с какими LLM не используется интерфейс OpenAI API",
        role_id="project_analyzer",
        corpus=corpus,
        limit=3,
    )

    assert result["matches"]
    top = result["matches"][0]
    assert top["source_template"] == "provider_interface_mapping"
    assert top["answer"]["answer_type"] == "provider_interface_mapping_advisory"
    assert "native_direct" in top["answer"]["expected_output_shape"]
    assert "llm" in result["query_tokens"]
    assert "match_details" in top


def test_token_aware_search_expands_tz_to_technical_spec_contracts():
    corpus = generate_synthetic_role_qa(records_per_role=20)

    result = search_synthetic_role_qa("ТЗ acceptance contract", role_id="spec_writer", corpus=corpus, limit=5)

    assert result["matches"]
    assert result["matches"][0]["role_id"] == "spec_writer"
    assert "technicalspec" in result["query_tokens"]
    assert result["matches"][0]["match_details"]["matched_tokens"]


def test_synthetic_role_qa_audit_reports_policy_and_probe_health():
    corpus = generate_synthetic_role_qa(records_per_role=20)

    audit = synthetic_role_qa_audit(corpus)

    assert audit["artifact_type"] == "SyntheticRoleQAAudit"
    assert audit["record_count"] == corpus["record_count"]
    assert audit["duplicate_qa_id_count"] == 0
    assert audit["invalid_policy_count"] == 0
    assert audit["probe_report"]["covered"] == audit["probe_report"]["probe_count"]


def test_positive_feedback_updates_record_state(tmp_path):
    path = tmp_path / "synthetic_role_qa.json"
    write_synthetic_role_qa(output=path, records_per_role=1)
    corpus = json.loads(path.read_text(encoding="utf-8"))
    qa_id = corpus["records"][0]["qa_id"]

    first = record_role_qa_feedback(qa_id=qa_id, outcome="positive", case={"case_id": "case1"}, path=path)
    second = record_role_qa_feedback(qa_id=qa_id, outcome="positive", case={"case_id": "case2"}, path=path)
    third = record_role_qa_feedback(qa_id=qa_id, outcome="positive", case={"case_id": "case3"}, path=path)

    assert first["answer_state"] == "observed_positive"
    assert second["feedback"]["positive_count"] == 2
    assert third["answer_state"] == "confirmed_candidate"
    assert third["trust_level"] == "confirmed_candidate"
    assert third["feedback"]["promotion_ready"] is True


def test_generate_llm_role_qa_keeps_records_low_trust():
    model_payload = {
        "records": [
            {
                "question": "Как роли отвечать на новый вопрос без фактов?",
                "answer": {
                    "status": "verified",
                    "answer_type": "unsafe_claim",
                    "short_answer": "Можно ответить только как гипотеза и запросить evidence.",
                    "recommended_steps": ["find evidence", "emit gap"],
                    "required_evidence": ["project files"],
                    "stop_conditions": ["no evidence"],
                    "confidence": "high",
                    "limitations": [],
                },
                "tags": ["semantic_gap"],
            }
        ]
    }
    config = LocalInferenceConfig(base_url="http://test/v1", model="mock-llm")

    with patch("runtime.synthetic_role_kb.call_json_chat", return_value=model_payload):
        corpus = generate_llm_role_qa(records_per_role=1, config=config)

    assert corpus["llm_record_count"] == corpus["role_count"]
    first = corpus["records"][0]
    assert first["origin"]["kind"] == "llm_synthetic_seed"
    assert first["origin"]["model"] == "mock-llm"
    assert first["trust_level"] == "synthetic_seed"
    assert first["answer_state"] == "seeded"
    assert first["answer"]["status"] == "candidate"
    assert first["answer"]["confidence"] == "low"
    assert "ground_truth" in first["policy"]["forbidden_uses"]


def test_synthetic_role_kb_cli_generate_and_search(tmp_path):
    root = Path(__file__).resolve().parents[2]
    corpus_path = tmp_path / "synthetic_role_qa.json"

    generate = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "synthetic_role_kb.py"),
            "--root",
            str(root),
            "generate",
            "--records-per-role",
            "20",
            "--output",
            str(corpus_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    search = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "synthetic_role_kb.py"),
            "search",
            "--corpus",
            str(corpus_path),
            "--role-id",
            "reviewer",
            "--query",
            "review findings risk",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert json.loads(generate.stdout)["record_count"] > 140
    assert json.loads(search.stdout)["match_count"] > 0
