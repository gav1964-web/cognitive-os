from __future__ import annotations


CASE = "web_research_summarizer_fastapi"

def expected_artifacts() -> list[str]:
    return [
        "pyproject.toml",
        "README.md",
        "src/web_research_service/__init__.py",
        "src/web_research_service/app.py",
        "src/web_research_service/contracts.py",
        "src/web_research_service/search.py",
        "src/web_research_service/fetcher.py",
        "src/web_research_service/extractor.py",
        "src/web_research_service/llm_client.py",
        "src/web_research_service/service.py",
        "tests/fixtures/search_results.json",
        "tests/fixtures/article_one.html", "tests/fixtures/article_two.html",
        "tests/test_search.py", "tests/test_service.py",
        "tests/test_llm_client.py", "tests/test_api.py",
    ]

def acceptance_for(verification: dict[str, object]) -> list[str]:
    if verification.get("status") != "passed":
        return []
    return [
        "FastAPI app exposes health and research endpoints",
        "API accepts a plain search phrase and top-N limit",
        "top-20 result limit is enforced before article fetching",
        "article fetching, extraction and LLM summarization are separated by adapters",
        "LLM gateway defaults to http://127.0.0.1:8000/v1 and model GigaChat",
        "search, fetch and LLM failures are returned as controlled API errors or warnings",
        "default tests use fixtures and mocks without live network or real LLM calls",
        "README documents run command, environment variables and live-network policy",
        "all tests run from generated project root",
    ]

def content_for(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("test_search.py"):
        return _test_search()
    if path.endswith("test_service.py"):
        return _test_service()
    if path.endswith("test_llm_client.py"):
        return _test_llm_client()
    if path.endswith("test_api.py"):
        return _test_api()
    if path.endswith("contracts.py"):
        return _contracts()
    if path.endswith("search.py"):
        return _search()
    if path.endswith("fetcher.py"):
        return _fetcher()
    if path.endswith("extractor.py"):
        return _extractor()
    if path.endswith("llm_client.py"):
        return _llm_client()
    if path.endswith("service.py"):
        return _service()
    if path.endswith("app.py"):
        return _app()
    if path.endswith("search_results.json"):
        return _search_fixture()
    if path.endswith("article_one.html"):
        return "<html><article><h1>One</h1><p>Alpha article text about reliable search.</p></article></html>\n"
    if path.endswith("article_two.html"):
        return "<html><main><h1>Two</h1><p>Beta article text about grounded summaries.</p></main></html>\n"
    return "# Generated FastAPI web research service placeholder.\n"

def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "web_research_service"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = ["fastapi"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )

def _readme(prompt: str) -> str:
    return (
        "# web_research_service\n\n"
        f"Prompt: {prompt}\n\n"
        "FastAPI service for web research by phrase. The `/research` endpoint searches the web, keeps up to 20 "
        "result pages, extracts readable text, sends grounded excerpts to an OpenAI-compatible LLM gateway, and "
        "returns one final summary plus source links and warnings.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run app: `uvicorn web_research_service.app:app --app-dir src --reload`.\n\n"
        "Environment:\n"
        "- `LLM_BASE_URL`, default `http://127.0.0.1:8000/v1`.\n"
        "- `LLM_MODEL`, default `GigaChat`.\n"
        "- `WEB_SEARCH_ENDPOINT_TEMPLATE`, optional JSON search endpoint containing `{query}`.\n"
        "- `REQUEST_TIMEOUT_SECONDS`, default `15`.\n\n"
        "Default tests are fixture-only and do not call the live network or a real LLM. Live search uses "
        "DuckDuckGo HTML when no JSON search endpoint is configured.\n"
    )

def _contracts() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class SearchResult:\n"
        "    title: str\n"
        "    url: str\n"
        "    snippet: str = ''\n\n\n"
        "@dataclass(frozen=True)\n"
        "class Article:\n"
        "    title: str\n"
        "    url: str\n"
        "    text: str\n"
        "    snippet: str = ''\n\n\n"
        "@dataclass(frozen=True)\n"
        "class ResearchReport:\n"
        "    query: str\n"
        "    summary: str\n"
        "    sources: list[dict[str, str]]\n"
        "    warnings: list[str]\n"
    )

def _search() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from html.parser import HTMLParser\n"
        "import json\n"
        "from pathlib import Path\n"
        "from urllib.parse import parse_qs, quote_plus, unquote, urlparse\n"
        "from urllib.request import Request, urlopen\n\n"
        "from web_research_service.contracts import SearchResult\n\n\n"
        "DEFAULT_USER_AGENT = 'Mozilla/5.0 (compatible; cognitive-os-web-research-service/0.1)'\n\n\n"
        "def load_fixture_results(path: str, *, limit: int = 20) -> list[SearchResult]:\n"
        "    return _coerce_results(json.loads(Path(path).read_text(encoding='utf-8')))[:limit]\n\n\n"
        "def search_web(query: str, *, endpoint_template: str | None = None, limit: int = 20, timeout: float = 15.0) -> list[SearchResult]:\n"
        "    limit = min(limit, 20)\n"
        "    if endpoint_template is None:\n"
        "        return search_duckduckgo_html(query, limit=limit, timeout=timeout)\n"
        "    if '{query}' not in endpoint_template:\n"
        "        raise ValueError('search endpoint template must contain {query}')\n"
        "    request = Request(endpoint_template.replace('{query}', quote_plus(query)), headers={'User-Agent': DEFAULT_USER_AGENT})\n"
        "    with urlopen(request, timeout=timeout) as response:\n"
        "        payload = json.loads(response.read().decode(response.headers.get_content_charset() or 'utf-8', errors='replace'))\n"
        "    return _coerce_results(payload)[:limit]\n\n\n"
        "def search_duckduckgo_html(query: str, *, limit: int = 20, timeout: float = 15.0) -> list[SearchResult]:\n"
        "    url = 'https://duckduckgo.com/html/?q=' + quote_plus(query)\n"
        "    request = Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})\n"
        "    with urlopen(request, timeout=timeout) as response:\n"
        "        html = response.read().decode(response.headers.get_content_charset() or 'utf-8', errors='replace')\n"
        "    return parse_duckduckgo_html(html, limit=limit)\n\n\n"
        "def parse_duckduckgo_html(html: str, *, limit: int = 20) -> list[SearchResult]:\n"
        "    parser = _DuckDuckGoParser()\n"
        "    parser.feed(html)\n"
        "    return parser.results[:min(limit, 20)]\n\n\n"
        "class _DuckDuckGoParser(HTMLParser):\n"
        "    def __init__(self) -> None:\n"
        "        super().__init__()\n"
        "        self.results: list[SearchResult] = []\n"
        "        self._capture = False\n"
        "        self._href = ''\n"
        "        self._parts: list[str] = []\n\n"
        "    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:\n"
        "        attrs_dict = {name: value or '' for name, value in attrs}\n"
        "        if tag == 'a' and ('result__a' in attrs_dict.get('class', '') or 'result-link' in attrs_dict.get('class', '')):\n"
        "            self._capture = True\n"
        "            self._href = attrs_dict.get('href', '')\n"
        "            self._parts = []\n\n"
        "    def handle_data(self, data: str) -> None:\n"
        "        if self._capture and data.strip():\n"
        "            self._parts.append(' '.join(data.split()))\n\n"
        "    def handle_endtag(self, tag: str) -> None:\n"
        "        if tag != 'a' or not self._capture:\n"
        "            return\n"
        "        self._capture = False\n"
        "        title = ' '.join(self._parts).strip()\n"
        "        url = _normalize_duckduckgo_url(self._href)\n"
        "        if title and url and not any(item.url == url for item in self.results):\n"
        "            self.results.append(SearchResult(title=title, url=url))\n\n\n"
        "def _normalize_duckduckgo_url(href: str) -> str:\n"
        "    if href.startswith('//'):\n"
        "        href = 'https:' + href\n"
        "    parsed = urlparse(href)\n"
        "    if 'duckduckgo.com' in parsed.netloc and parsed.path.startswith('/l/'):\n"
        "        return unquote(parse_qs(parsed.query).get('uddg', [''])[0])\n"
        "    return href if href.startswith(('http://', 'https://')) else ''\n\n\n"
        "def _coerce_results(payload: object) -> list[SearchResult]:\n"
        "    rows = payload.get('results', payload) if isinstance(payload, dict) else payload\n"
        "    results: list[SearchResult] = []\n"
        "    if not isinstance(rows, list):\n"
        "        return results\n"
        "    for row in rows:\n"
        "        if isinstance(row, dict):\n"
        "            title = str(row.get('title') or '').strip()\n"
        "            url = str(row.get('url') or row.get('link') or '').strip()\n"
        "            snippet = str(row.get('snippet') or '').strip()\n"
        "            if title and url.startswith(('http://', 'https://')):\n"
        "                results.append(SearchResult(title=title, url=url, snippet=snippet))\n"
        "    return results\n"
    )

def _fetcher() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from urllib.request import Request, urlopen\n\n\n"
        "def fetch_html(url: str, *, timeout: float = 15.0) -> str:\n"
        "    request = Request(url, headers={'User-Agent': 'cognitive-os-web-research-service/0.1'})\n"
        "    with urlopen(request, timeout=timeout) as response:\n"
        "        return response.read().decode(response.headers.get_content_charset() or 'utf-8', errors='replace')\n"
    )

def _extractor() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from html.parser import HTMLParser\n\n\n"
        "def extract_text(html: str, *, max_chars: int = 4000) -> str:\n"
        "    parser = _TextParser()\n"
        "    parser.feed(html)\n"
        "    return ' '.join(' '.join(parser.parts).split())[:max_chars]\n\n\n"
        "class _TextParser(HTMLParser):\n"
        "    def __init__(self) -> None:\n"
        "        super().__init__()\n"
        "        self.parts: list[str] = []\n"
        "        self._skip = 0\n\n"
        "    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:\n"
        "        if tag in {'script', 'style', 'nav', 'footer'}:\n"
        "            self._skip += 1\n\n"
        "    def handle_endtag(self, tag: str) -> None:\n"
        "        if tag in {'script', 'style', 'nav', 'footer'} and self._skip:\n"
        "            self._skip -= 1\n\n"
        "    def handle_data(self, data: str) -> None:\n"
        "        text = ' '.join(data.split())\n"
        "        if not self._skip and len(text) > 2:\n"
        "            self.parts.append(text)\n"
    )

def _llm_client() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import json\n"
        "import os\n"
        "from urllib.request import Request, urlopen\n\n\n"
        "DEFAULT_BASE_URL = 'http://127.0.0.1:8000/v1'\n"
        "DEFAULT_MODEL = 'GigaChat'\n\n\n"
        "def summarize_with_llm(query: str, articles: list[dict[str, str]], *, base_url: str | None = None, model: str | None = None, timeout: float = 30.0) -> str:\n"
        "    base = (base_url or os.environ.get('LLM_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')\n"
        "    selected_model = model or os.environ.get('LLM_MODEL') or DEFAULT_MODEL\n"
        "    excerpts = '\\n\\n'.join(f\"[{i+1}] {a['title']}\\nURL: {a['url']}\\nTEXT: {a['text'][:1200]}\" for i, a in enumerate(articles))\n"
        "    payload = {\n"
        "        'model': selected_model,\n"
        "        'messages': [\n"
        "            {'role': 'system', 'content': 'You write one concise Russian summary grounded only in provided source excerpts.'},\n"
        "            {'role': 'user', 'content': f'Query: {query}\\nTop pages:\\n{excerpts}\\nReturn one final summary and mention uncertainty if evidence is weak.'},\n"
        "        ],\n"
        "        'temperature': 0.2,\n"
        "    }\n"
        "    request = Request(base + '/chat/completions', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})\n"
        "    with urlopen(request, timeout=timeout) as response:\n"
        "        data = json.loads(response.read().decode('utf-8', errors='replace'))\n"
        "    return str(data['choices'][0]['message']['content']).strip()\n"
    )

def _service() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import os\n"
        "from typing import Callable\n\n"
        "from web_research_service.contracts import Article, ResearchReport, SearchResult\n"
        "from web_research_service.extractor import extract_text\n"
        "from web_research_service.fetcher import fetch_html\n"
        "from web_research_service.llm_client import summarize_with_llm\n"
        "from web_research_service.search import search_web\n\n\n"
        "SearchFn = Callable[..., list[SearchResult]]\n"
        "FetchFn = Callable[[str], str]\n"
        "SummaryFn = Callable[[str, list[dict[str, str]]], str]\n\n\n"
        "def research(query: str, *, top: int = 20, search_fn: SearchFn | None = None, fetch_fn: FetchFn | None = None, summary_fn: SummaryFn | None = None, timeout: float | None = None) -> ResearchReport:\n"
        "    query = query.strip()\n"
        "    if not query:\n"
        "        raise ValueError('query must not be empty')\n"
        "    limit = min(max(top, 1), 20)\n"
        "    request_timeout = timeout if timeout is not None else float(os.environ.get('REQUEST_TIMEOUT_SECONDS', '15'))\n"
        "    finder = search_fn or search_web\n"
        "    loader = fetch_fn or (lambda url: fetch_html(url, timeout=request_timeout))\n"
        "    summarizer = summary_fn or summarize_with_llm\n"
        "    results = finder(query, endpoint_template=os.environ.get('WEB_SEARCH_ENDPOINT_TEMPLATE'), limit=limit, timeout=request_timeout)\n"
        "    warnings: list[str] = []\n"
        "    articles: list[Article] = []\n"
        "    for item in results[:limit]:\n"
        "        try:\n"
        "            text = extract_text(loader(item.url))\n"
        "        except Exception as exc:\n"
        "            warnings.append(f'fetch failed for {item.url}: {exc}')\n"
        "            continue\n"
        "        if text:\n"
        "            articles.append(Article(title=item.title, url=item.url, text=text, snippet=item.snippet))\n"
        "    if not articles:\n"
        "        raise RuntimeError('no readable pages fetched')\n"
        "    payload = [{'title': a.title, 'url': a.url, 'text': a.text, 'snippet': a.snippet} for a in articles]\n"
        "    return ResearchReport(query=query, summary=summarizer(query, payload), sources=[{'title': a.title, 'url': a.url} for a in articles], warnings=warnings)\n"
    )
