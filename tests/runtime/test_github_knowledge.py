from unittest.mock import patch

from runtime.knowledge import github_repository_knowledge, official_docs_knowledge
from runtime.knowledge_source_policy import github_source_policy, official_docs_source_policy


def test_github_source_policy_forbids_copying_code():
    policy = github_source_policy()

    assert "copy code verbatim" in policy.forbidden_uses
    assert policy.confidence_cap <= 0.65


def test_github_repository_knowledge_wraps_search_as_evidence():
    fake = {
        "query": "python xlsx csv conversion",
        "source": "github_repository_search",
        "repositories": [{"full_name": "owner/repo", "html_url": "https://github.com/owner/repo"}],
        "total_count": 1,
        "incomplete_results": False,
    }
    with patch("runtime.knowledge.github_repository_search", return_value=fake):
        result = github_repository_knowledge("python xlsx csv conversion", needed_for="spreadsheet design", limit=1)

    artifact = result["knowledge_artifacts"][0]
    assert result["status"] == "ok"
    assert artifact["source"] == "github_repository_search"
    assert artifact["confidence"] <= 0.65
    assert "not ground truth" in artifact["limitations"][0]


def test_official_docs_knowledge_wraps_fetch_as_evidence():
    fake = {
        "source": "official_docs_fetch",
        "url": "https://docs.python.org/3/library/csv.html",
        "domain": "docs.python.org",
        "title": "csv docs",
        "text_excerpt": "csv module details",
        "content_hash": "sha256:abc",
        "fetched_chars": 18,
    }
    with patch("runtime.knowledge.official_docs_fetch", return_value=fake):
        result = official_docs_knowledge(
            "https://docs.python.org/3/library/csv.html",
            question="How does Python csv behave?",
            needed_for="csv conversion design",
        )

    policy = official_docs_source_policy()
    artifact = result["knowledge_artifacts"][0]
    assert result["status"] == "ok"
    assert artifact["source"] == "official_docs_fetch"
    assert artifact["confidence"] <= policy.confidence_cap
    assert "local contract tests" in artifact["limitations"][1]
