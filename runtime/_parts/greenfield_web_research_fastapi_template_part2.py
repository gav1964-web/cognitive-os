from __future__ import annotations


CASE = "web_research_summarizer_fastapi"

def _app() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from fastapi import FastAPI, HTTPException\n"
        "from pydantic import BaseModel, Field\n\n"
        "from web_research_service.service import research\n\n\n"
        "app = FastAPI(title='Web Research Summary Service')\n\n\n"
        "class ResearchRequest(BaseModel):\n"
        "    query: str = Field(min_length=1)\n"
        "    top: int = Field(default=20, ge=1, le=20)\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, str]:\n"
        "    return {'status': 'ok'}\n\n\n"
        "@app.post('/research')\n"
        "def research_endpoint(payload: ResearchRequest) -> dict[str, object]:\n"
        "    try:\n"
        "        report = research(payload.query, top=payload.top)\n"
        "    except ValueError as exc:\n"
        "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n"
        "    except Exception as exc:\n"
        "        raise HTTPException(status_code=502, detail=str(exc)) from exc\n"
        "    return {'query': report.query, 'summary': report.summary, 'sources': report.sources, 'warnings': report.warnings}\n"
    )

def _search_fixture() -> str:
    return (
        '{"results": ['
        '{"title": "One", "url": "https://example.test/one", "snippet": "alpha"},'
        '{"title": "Two", "url": "https://example.test/two", "snippet": "beta"}'
        ']}\n'
    )

def _test_search() -> str:
    return (
        "from web_research_service.search import load_fixture_results, parse_duckduckgo_html\n\n\n"
        "def test_load_fixture_results_limits_top_20():\n"
        "    rows = load_fixture_results('tests/fixtures/search_results.json', limit=50)\n"
        "    assert len(rows) == 2\n"
        "    assert rows[0].url == 'https://example.test/one'\n\n\n"
        "def test_parse_duckduckgo_html_result_link():\n"
        "    html = '<a class=\"result__a\" href=\"https://example.test/a\">Example A</a>'\n"
        "    assert parse_duckduckgo_html(html)[0].title == 'Example A'\n"
    )

def _test_service() -> str:
    return (
        "from web_research_service.contracts import SearchResult\n"
        "from web_research_service.service import research\n\n\n"
        "def test_research_builds_single_grounded_summary():\n"
        "    def fake_search(query, **kwargs):\n"
        "        assert kwargs['limit'] == 20\n"
        "        return [SearchResult('One', 'https://example.test/one'), SearchResult('Two', 'https://example.test/two')]\n\n"
        "    def fake_fetch(url):\n"
        "        return '<main><p>content for ' + url + '</p></main>'\n\n"
        "    def fake_summary(query, articles):\n"
        "        assert query == 'test query'\n"
        "        assert len(articles) == 2\n"
        "        return 'single summary'\n\n"
        "    report = research('test query', top=99, search_fn=fake_search, fetch_fn=fake_fetch, summary_fn=fake_summary)\n"
        "    assert report.summary == 'single summary'\n"
        "    assert len(report.sources) == 2\n\n\n"
        "def test_empty_query_is_rejected():\n"
        "    try:\n"
        "        research('   ')\n"
        "    except ValueError as exc:\n"
        "        assert 'query' in str(exc)\n"
        "    else:\n"
        "        raise AssertionError('empty query must fail')\n"
    )

def _test_llm_client() -> str:
    return (
        "import json\n\n"
        "from web_research_service import llm_client\n\n\n"
        "class FakeResponse:\n"
        "    headers = {}\n"
        "    def __enter__(self): return self\n"
        "    def __exit__(self, *args): return None\n"
        "    def read(self):\n"
        "        return json.dumps({'choices': [{'message': {'content': 'Итоговое суммари'}}]}).encode('utf-8')\n\n\n"
        "def test_llm_client_uses_gigachat_gateway_defaults(monkeypatch):\n"
        "    captured = {}\n"
        "    def fake_urlopen(request, timeout):\n"
        "        captured['url'] = request.full_url\n"
        "        captured['body'] = json.loads(request.data.decode('utf-8'))\n"
        "        return FakeResponse()\n"
        "    monkeypatch.setattr(llm_client, 'urlopen', fake_urlopen)\n"
        "    text = llm_client.summarize_with_llm('q', [{'title': 't', 'url': 'https://e.test', 'text': 'body'}])\n"
        "    assert text == 'Итоговое суммари'\n"
        "    assert captured['url'] == 'http://127.0.0.1:8000/v1/chat/completions'\n"
        "    assert captured['body']['model'] == 'GigaChat'\n"
    )

def _test_api() -> str:
    return (
        "from fastapi.testclient import TestClient\n\n"
        "from web_research_service import app as app_module\n\n\n"
        "def test_health_endpoint():\n"
        "    assert TestClient(app_module.app).get('/health').json() == {'status': 'ok'}\n\n\n"
        "def test_research_endpoint_returns_summary(monkeypatch):\n"
        "    def fake_research(query, *, top=20):\n"
        "        assert query == 'python news'\n"
        "        assert top == 3\n"
        "        return type('Report', (), {'query': query, 'summary': 'one summary', 'sources': [{'title': 'A', 'url': 'https://a.test'}], 'warnings': []})()\n"
        "    monkeypatch.setattr(app_module, 'research', fake_research)\n"
        "    response = TestClient(app_module.app).post('/research', json={'query': 'python news', 'top': 3})\n"
        "    assert response.status_code == 200\n"
        "    assert response.json()['summary'] == 'one summary'\n\n\n"
        "def test_research_endpoint_returns_controlled_error(monkeypatch):\n"
        "    monkeypatch.setattr(app_module, 'research', lambda query, *, top=20: (_ for _ in ()).throw(RuntimeError('search failed')))\n"
        "    response = TestClient(app_module.app).post('/research', json={'query': 'python news'})\n"
        "    assert response.status_code == 502\n"
    )
