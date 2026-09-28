"""General Stage 2 news-site scraper CLI template."""

from __future__ import annotations

from pathlib import Path


CASE = "news_site_scraper_cli"
_ASSET_DIR = Path(__file__).with_name("template_assets") / "news_site_scraper"


def expected_artifacts() -> list[str]:
    return [
        "Dockerfile",
        "pyproject.toml",
        "README.md",
        "run_news_scraper.bat",
        "src/news_site_scraper/__init__.py",
        "src/news_site_scraper/article_summary.py",
        "src/news_site_scraper/browser_fetcher.py",
        "src/news_site_scraper/cli.py",
        "src/news_site_scraper/collection_plan.py",
        "src/news_site_scraper/news_site_profiles.json",
        "src/news_site_scraper/feed.py",
        "src/news_site_scraper/fetcher.py",
        "src/news_site_scraper/failure_report.py",
        "src/news_site_scraper/llm_extractor.py",
        "src/news_site_scraper/parser.py",
        "src/news_site_scraper/popular_news_sites.json",
        "src/news_site_scraper/profile_promotion.py",
        "src/news_site_scraper/profile_proposal.py",
        "src/news_site_scraper/report_writer.py",
        "src/news_site_scraper/run_report.py",
        "src/news_site_scraper/sitemap.py",
        "src/news_site_scraper/source_discovery.py",
        "src/news_site_scraper/source_methods.py",
        "src/news_site_scraper/site_profile.py",
        "src/news_site_scraper/strategy_registry.py",
        "tests/fixtures/news_page.html",
        "tests/test_parser.py",
        "tests/test_report_writer.py",
        "tests/test_cli.py",
    ]


def acceptance_for(verification: dict[str, object]) -> list[str]:
    if verification.get("status") != "passed":
        return []
    return [
        "parser works from fixture without network",
        "CLI writes CSV, Markdown or JSON by output suffix",
        "top news limit is enforced",
        "live page must satisfy requested top count or fail explicitly",
        "live summaries are enriched from article pages when card summaries are absent",
        "fixture output is explicitly labeled as non-live parser smoke",
        "live URL with no parsed news returns controlled failure instead of fake output",
        "site URL is handled through a profile instead of hardcoded one-site logic",
        "network call has timeout and identifiable user-agent",
        "live access is optional and not required for default tests",
        "Dockerfile runs the CLI entrypoint without extra host setup",
        "Windows batch launcher runs the CLI with PYTHONPATH configured",
        "popular-sites mode discovers source sites from the topic and uses the seed list only as fallback",
        "topic searches write a single Markdown report with one combined summary",
        "all tests run from generated project root",
    ]


def content_for(path: str, prompt: str) -> str:
    if path == "Dockerfile":
        return _dockerfile()
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path == "run_news_scraper.bat":
        return _run_bat()
    if path.endswith("news_page.html"):
        return _fixture()
    if path.endswith("test_parser.py"):
        return _test_parser()
    if path.endswith("test_report_writer.py"):
        return _test_report_writer()
    if path.endswith("test_cli.py"):
        return _test_cli()
    if path.endswith("article_summary.py"):
        return _article_summary()
    if path.endswith("browser_fetcher.py"):
        return _browser_fetcher()
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("collection_plan.py"):
        return _collection_plan()
    if path.endswith("feed.py"):
        return _feed()
    if path.endswith("fetcher.py"):
        return _fetcher()
    if path.endswith("failure_report.py"):
        return _failure_report()
    if path.endswith("llm_extractor.py"):
        return _llm_extractor()
    if path.endswith("parser.py"):
        return _parser()
    if path.endswith("profile_promotion.py"):
        return _profile_promotion()
    if path.endswith("profile_proposal.py"):
        return _profile_proposal()
    if path.endswith("report_writer.py"):
        return _report_writer()
    if path.endswith("run_report.py"):
        return _run_report()
    if path.endswith("sitemap.py"):
        return _sitemap()
    if path.endswith("source_discovery.py"):
        return _source_discovery()
    if path.endswith("source_methods.py"):
        return _source_methods()
    if path.endswith("site_profile.py"):
        return _site_profile()
    if path.endswith("strategy_registry.py"):
        return _strategy_registry()
    if path.endswith("news_site_profiles.json"):
        return _news_site_profiles_json()
    if path.endswith("popular_news_sites.json"):
        return _popular_news_sites_json()
    if path.endswith("__init__.py"):
        return "__all__ = []\n"
    raise KeyError(path)


def _asset(name: str) -> str:
    return (_ASSET_DIR / name).read_text(encoding="utf-8")


def _readme(prompt: str) -> str:
    return f"""# news_site_scraper

Prompt: {prompt}

Fixture-first CLI for scraping news links from a site front page into UTF-8 CSV, Markdown or JSON.
The site URL is converted into a small profile so ixbt.com, cnews.ru, 3dnews.ru and similar news pages use the same parser contract instead of one hardcoded scraper.

Fixtures are parser smoke evidence only; they are not live ixbt.com news and must not be presented as current site output.
For a real URL, the CLI returns a controlled non-zero exit if the page cannot be fetched or no news items are parsed.

Run tests: `python -m pytest tests -q`.

Example: `python -m news_site_scraper.cli tests/fixtures/news_page.html out.md --base-url https://3dnews.ru/ --top 10`.
Popular-sites example: `python -m news_site_scraper.cli popular out.md --use-popular-sites --topic "Trump" --source-discovery search --total-top 20 --summary-mode llm`.
Windows launcher: `run_news_scraper.bat` creates `trump-news.md` with default popular-sites settings; pass CLI arguments to override them.
Docker example: `docker build -t news-site-scraper .` then `docker run --rm -v %cd%:/work news-site-scraper popular /work/trump-news.md --use-popular-sites --topic "Trump" --source-discovery search --total-top 20 --summary-mode llm`.
In popular-sites mode the program first discovers candidate news sources from the topic through a search-result page; `popular_news_sites.json` is only a fallback seed when discovery is unavailable.
Live URLs are optional and should be used as a separate smoke with rate limits.
Browser-rendered pages are opt-in: install `.[browser]`, run `python -m playwright install chromium`, then use `--browser always` or let `--browser auto` react to a `browser_required` LLM diagnosis.
"""


def _pyproject() -> str:
    return _asset("pyproject.txt")

def _dockerfile() -> str:
    return _asset("dockerfile.txt")

def _run_bat() -> str:
    return _asset("run_bat.txt")

def _cli() -> str:
    return _asset("cli.txt")

def _fetcher() -> str:
    return _asset("fetcher.txt")

def _collection_plan() -> str:
    return _asset("collection_plan.txt")

def _run_report() -> str:
    return _asset("run_report.txt")

def _news_site_profiles_json() -> str:
    return _asset("news_site_profiles_json.txt")

def _popular_news_sites_json() -> str:
    return _asset("popular_news_sites_json.txt")

def _source_discovery() -> str:
    return _asset("source_discovery.txt")

def _source_methods() -> str:
    return _asset("source_methods.txt")

def _browser_fetcher() -> str:
    return _asset("browser_fetcher.txt")

def _failure_report() -> str:
    return _asset("failure_report.txt")

def _feed() -> str:
    return _asset("feed.txt")

def _sitemap() -> str:
    return _asset("sitemap.txt")

def _strategy_registry() -> str:
    return _asset("strategy_registry.txt")

def _llm_extractor() -> str:
    return _asset("llm_extractor.txt")

def _article_summary() -> str:
    return _asset("article_summary.txt")

def _site_profile() -> str:
    return _asset("site_profile.txt")

def _parser() -> str:
    return _asset("parser.txt")

def _profile_proposal() -> str:
    return _asset("profile_proposal.txt")

def _profile_promotion() -> str:
    return _asset("profile_promotion.txt")

def _report_writer() -> str:
    return _asset("report_writer.txt")

def _fixture() -> str:
    return _asset("fixture.txt")

def _test_parser() -> str:
    return _asset("test_parser.txt")

def _test_report_writer() -> str:
    return _asset("test_report_writer.txt")

def _test_cli() -> str:
    return _asset("test_cli.txt")
