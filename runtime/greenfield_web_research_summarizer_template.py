"""Stage 2 web research summarizer CLI template."""

from __future__ import annotations
from pathlib import Path


CASE = "web_research_summarizer_cli"


def expected_artifacts() -> list[str]:
    return [
        "pyproject.toml",
        "README.md",
        "src/web_research_summarizer/__init__.py",
        "src/web_research_summarizer/cli.py",
        "src/web_research_summarizer/contracts.py",
        "src/web_research_summarizer/search.py",
        "src/web_research_summarizer/fetcher.py",
        "src/web_research_summarizer/extractor.py",
        "src/web_research_summarizer/summarizer.py",
        "src/web_research_summarizer/report.py",
        "tests/fixtures/search_results.json",
        "tests/fixtures/search_page.html",
        "tests/fixtures/article_one.html",
        "tests/fixtures/article_two.html",
        "tests/test_search.py",
        "tests/test_fetcher.py",
        "tests/test_extractor.py",
        "tests/test_summarizer.py",
        "tests/test_core.py",
        "tests/test_report.py",
        "tests/test_cli.py",
    ]


def acceptance_for(verification: dict[str, object]) -> list[str]:
    if verification.get("status") != "passed":
        return []
    return [
        "CLI accepts a search phrase and top-N limit",
        "plain query live search uses default adapter and default tests use fixtures without live network",
        "top-15 result limit is enforced before article fetching",
        "HTML article text extraction is covered by fixture tests",
        "summary report contains links to source articles",
        "empty search results and malformed HTML are handled with controlled output",
        "README documents dependency and live-network policy",
        "all tests run from generated project root",
    ]


def content_for(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path.endswith("search_results.json"):
        return _search_fixture()
    if path.endswith("search_page.html"):
        return _search_page_fixture()
    if path.endswith("article_one.html"):
        return _article_one_fixture()
    if path.endswith("article_two.html"):
        return _article_two_fixture()
    if path.endswith("test_search.py"):
        return _test_search()
    if path.endswith("test_fetcher.py"):
        return _test_fetcher()
    if path.endswith("test_extractor.py"):
        return _test_extractor()
    if path.endswith("test_summarizer.py"):
        return _test_summarizer()
    if path.endswith("test_core.py"):
        return _test_summarizer()
    if path.endswith("test_report.py"):
        return _test_report()
    if path.endswith("test_cli.py"):
        return _test_cli()
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("contracts.py"):
        return _contracts()
    if path.endswith("search.py"):
        return _search()
    if path.endswith("fetcher.py"):
        return _fetcher()
    if path.endswith("extractor.py"):
        return _extractor()
    if path.endswith("summarizer.py"):
        return _summarizer()
    if path.endswith("report.py"):
        return _report()
    return "# Generated Stage 2 web research summarizer placeholder.\n"



_ASSET_DIR = Path(__file__).with_name("template_assets") / "web_research_summarizer"

def _asset(name: str) -> str:
    return (_ASSET_DIR / name).read_text(encoding="utf-8")

def _pyproject() -> str:
    return _asset("pyproject.txt")



def _readme(prompt: str) -> str:
    return (
        "# web_research_summarizer\n\n"
        f"Prompt: {prompt}\n\n"
        "CLI for researching a phrase on the web: it gets up to 15 search results, fetches article pages, "
        "extracts readable text, and writes a Markdown or JSON summary with source links.\n\n"
        "Dependency policy: the generated MVP uses only the Python standard library. Default tests are fixture-only "
        "and never require live network. Live mode accepts a plain human query and uses DuckDuckGo HTML search by default. "
        "For controlled deployments you can pass `--search-endpoint-template`, a JSON URL template containing `{query}`; "
        "fetched pages use timeout and a clear user-agent.\n\n"
        "Install from the project root: `python -m pip install -e .`.\n"
        "Run tests: `python -m pytest tests -q`.\n\n"
        "Fixture example: `web-research-summarizer \"python packaging\" report.md --fixture-search tests/fixtures/search_results.json --fixture-dir tests/fixtures`.\n"
        "JSON output example: `web-research-summarizer \"python packaging\" report.json --fixture-search tests/fixtures/search_results.json --fixture-dir tests/fixtures`.\n"
        "Live example: `web-research-summarizer \"latest Python packaging news\" report.md`.\n"
        "Controlled JSON search example: `web-research-summarizer \"python packaging\" report.md --search-endpoint-template \"https://example.test/search?q={query}\"`.\n\n"
        "Controlled JSON search expects a response containing either a list of objects or an object with `results`; "
        "each item must expose `title` and `url` or `link`.\n"
    )


def _contracts() -> str:
    return _asset("contracts.txt")



def _search() -> str:
    return _asset("search.txt")



def _fetcher() -> str:
    return _asset("fetcher.txt")



def _extractor() -> str:
    return _asset("extractor.txt")



def _summarizer() -> str:
    return _asset("summarizer.txt")



def _report() -> str:
    return _asset("report.txt")



def _cli() -> str:
    return _asset("cli.txt")



def _search_fixture() -> str:
    return _asset("search_fixture.txt")



def _search_page_fixture() -> str:
    return _asset("search_page_fixture.txt")



def _article_one_fixture() -> str:
    return _asset("article_one_fixture.txt")



def _article_two_fixture() -> str:
    return _asset("article_two_fixture.txt")



def _test_search() -> str:
    return _asset("test_search.txt")



def _test_extractor() -> str:
    return _asset("test_extractor.txt")



def _test_fetcher() -> str:
    return _asset("test_fetcher.txt")



def _test_summarizer() -> str:
    return _asset("test_summarizer.txt")



def _test_report() -> str:
    return _asset("test_report.txt")



def _test_cli() -> str:
    return _asset("test_cli.txt")
