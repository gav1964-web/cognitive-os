from __future__ import annotations

from pathlib import Path

import pytest

from runtime.project_fact_rules import (
    ProjectFactRulesError,
    answer_key_for_question,
    load_project_fact_rules,
    matches_line,
)


ROOT = Path(__file__).resolve().parents[2]


def test_project_fact_rules_load_question_routes():
    rules = load_project_fact_rules(str(ROOT / "config" / "project_fact_rules.json"))

    assert matches_line("cache_key = LLMCache.build_key(provider_id, model, messages)", any_markers=["LLMCache.build_key"])
    assert answer_key_for_question("существует ли кэш обращений к LLM", rules=rules) == "llm_cache_exists"
    assert answer_key_for_question("для разных LLM используется один и тот же кэш?", rules=rules) == "llm_cache_sharing"


def test_project_fact_rules_reject_bad_route(tmp_path: Path):
    path = tmp_path / "project_fact_rules.json"
    path.write_text(
        """{
  "schema_version": "project_fact_rules.v1",
  "status": "active",
  "question_answer_routes": [{"answer_key": "x"}]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ProjectFactRulesError, match="answer_key and markers"):
        load_project_fact_rules(str(path))
