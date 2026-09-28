from __future__ import annotations

from pathlib import Path

from runtime.generated_product_quality import evaluate_generated_product


def test_generated_product_quality_scores_web_research_package(tmp_path: Path) -> None:
    project = tmp_path / "pkg"
    (project / "src" / "web_research_summarizer").mkdir(parents=True)
    (project / "tests" / "fixtures").mkdir(parents=True)
    (project / "README.md").write_text(
        "Run tests: `python -m pytest tests -q`.\n"
        "Install: `python -m pip install -e .`.\n"
        "Use --search-endpoint-template for live network search.\n",
        encoding="utf-8",
    )
    (project / "src" / "web_research_summarizer" / "cli.py").write_text(
        "import argparse\n"
        "from urllib.request import urlopen\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('query')\n"
        "    parser.add_argument('output')\n"
        "    parser.add_argument('--fixture-search')\n"
        "    parser.add_argument('--search-endpoint-template')\n"
        "    args = parser.parse_args()\n"
        "    search_endpoint_template = args.search_endpoint_template\n"
        "    search_duckduckgo_html = parse_duckduckgo_html = object()\n"
        "    limit = min(args.top, 15) if hasattr(args, 'top') else 15\n"
        "    raise SystemExit('requires search source')\n",
        encoding="utf-8",
    )
    (project / "src" / "web_research_summarizer" / "report.py").write_text(
        "target.suffix.lower() == '.json'\n# Web Research Summary\n## Summary\n## Sources\n_combined_summary(report)\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_cli.py").write_text(
        "def test_malformed_empty_missing_reject():\n    assert True\n",
        encoding="utf-8",
    )
    (project / "tests" / "fixtures" / "search_results.json").write_text("[]", encoding="utf-8")
    report = {
        "project_dir": project.as_posix(),
        "source_code": {
            "files": [
                "README.md",
                "src/web_research_summarizer/cli.py",
                "src/web_research_summarizer/report.py",
                "tests/test_cli.py",
                "tests/fixtures/search_results.json",
            ]
        },
        "tester_review": {
            "review_target": {"case": "web_research_summarizer_cli"},
            "checks": {"cli_accepts_input_output": True},
        },
        "verification_report": {"status": "passed", "project_scoped": True},
        "release_decision": {"decision": "release_ready_with_risks"},
    }

    quality = evaluate_generated_product(report)

    assert quality["artifact_type"] == "GeneratedProductQuality"
    assert quality["status"] == "passed"
    assert quality["score"] == 1.0


def test_generated_product_quality_blocks_runtime_cache_files(tmp_path: Path) -> None:
    project = tmp_path / "pkg"
    (project / "src" / "demo" / "__pycache__").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "README.md").write_text("pytest\npython -m demo.cli\n", encoding="utf-8")
    (project / "src" / "demo" / "cli.py").write_text(
        "import argparse\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output')\n"
        "    raise SystemExit('missing')\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_cli.py").write_text("def test_missing(): assert True\n", encoding="utf-8")
    report = {
        "project_dir": project.as_posix(),
        "source_code": {"files": ["README.md", "src/demo/cli.py", "tests/test_cli.py"]},
        "tester_review": {"review_target": {"case": "demo"}, "checks": {"cli_accepts_input_output": True}},
        "verification_report": {"status": "passed", "project_scoped": True},
        "release_decision": {"decision": "release_ready"},
    }

    quality = evaluate_generated_product(report)

    assert quality["status"] == "needs_rework"
    assert "no_generated_runtime_cache_files" in quality["failed_checks"]
