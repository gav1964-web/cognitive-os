from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from runtime.knowledge_import import infer_archetype_from_pypi, official_docs_fact_candidate, pypi_candidate_from_metadata


def test_infer_archetype_from_pypi_detects_schema_validation():
    metadata = {
        "package": "pydantic",
        "summary": "Data validation using Python type hints",
        "classifiers": ["Topic :: Software Development"],
        "keywords": "schema validation",
    }

    result = infer_archetype_from_pypi(metadata)

    assert result["rule_id"] == "schema_validation_library"
    assert "validation" in result["matched_signals"]


def test_pypi_candidate_is_staged_and_weak():
    candidate = pypi_candidate_from_metadata(
        {
            "package": "itsdangerous",
            "summary": "Safely pass trusted data to untrusted environments and back.",
            "keywords": "serializer signer token",
            "classifiers": [],
            "project_urls": {},
        }
    )

    assert candidate is not None
    assert candidate["status"] == "collect_more_cases"
    assert candidate["proposed_record"]["rule_id"] == "signing_token_utility"
    assert candidate["proposed_record"]["evidence_strength"] == "weak"
    assert candidate["proposed_record"]["match"]["required_contains_any"] == ["itsdangerous"]


def test_official_docs_fact_candidate_wraps_evidence():
    fake = {
        "status": "ok",
        "knowledge_artifacts": [
            {
                "extracted_fact": "Official documentation fetched from docs.python.org: csv docs (100 chars excerpt)",
                "confidence": 0.85,
                "evidence": {"url": "https://docs.python.org/3/library/csv.html", "content_hash": "sha256:abc"},
                "limitations": ["external evidence"],
            }
        ],
    }
    with patch("runtime.knowledge_import.official_docs_knowledge", return_value=fake):
        candidate = official_docs_fact_candidate(
            url="https://docs.python.org/3/library/csv.html",
            question="How does csv work?",
            needed_for="csv converter",
        )

    assert candidate["record_type"] == "official_docs_fact"
    assert candidate["status"] == "collect_more_cases"
    assert candidate["proposed_record"]["source"] == "official_docs_fetch"


def test_import_knowledge_sources_cli_with_mocked_pypi(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = (
        "from unittest.mock import patch\n"
        "from tools.import_knowledge_sources import main\n"
        "fake = {'source':'pypi_json','package':'pydantic','name':'pydantic','summary':'Data validation',"
        "'classifiers':[],'project_urls':{},'requires_dist':[],'keywords':'schema validation'}\n"
        "with patch('tools.import_knowledge_sources.fetch_pypi_metadata', return_value=fake):\n"
        f" import sys; sys.argv=['tool','--root',r'{tmp_path}','--pypi','pydantic']; raise SystemExit(main())\n"
    )

    result = subprocess.run([sys.executable, "-c", script], cwd=root, check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["written"][0]["package"] == "pydantic"
    assert payload["candidate_report"]["candidate_count"] == 1
