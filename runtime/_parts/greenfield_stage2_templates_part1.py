from __future__ import annotations

from runtime.greenfield_csv_sort_template import content_for as csv_sort_content_for
from runtime.greenfield_generic_file_converter_template import content_for as generic_file_converter_content_for
from runtime.greenfield_image_contents_template import content_for as image_contents_content_for
from runtime.greenfield_image_table_excel_template import content_for as image_table_excel_content_for
from runtime.greenfield_news_scraper_template import acceptance_for as news_scraper_acceptance_for
from runtime.greenfield_news_scraper_template import content_for as news_scraper_content_for
from runtime.greenfield_news_scraper_template import expected_artifacts as news_scraper_expected_artifacts
from runtime.greenfield_ocr_template import content_for as ocr_content_for
from runtime.greenfield_web_research_summarizer_template import acceptance_for as web_research_acceptance_for
from runtime.greenfield_web_research_summarizer_template import content_for as web_research_content_for
from runtime.greenfield_web_research_summarizer_template import expected_artifacts as web_research_expected_artifacts
from runtime.greenfield_web_research_fastapi_template import acceptance_for as web_research_fastapi_acceptance_for
from runtime.greenfield_web_research_fastapi_template import content_for as web_research_fastapi_content_for
from runtime.greenfield_web_research_fastapi_template import expected_artifacts as web_research_fastapi_expected_artifacts

CSV_CASE = "fastapi_csv_aggregator"
KV_CASE = "fastapi_kv_store"
CSV_SORT_CASE = "csv_sort_cli"
OCR_CASE = "ocr_image_cli"
IMAGE_CONTENTS_CASE = "image_contents_cli"
IMAGE_TABLE_EXCEL_CASE = "image_table_to_excel_cli"
GENERIC_FILE_CONVERTER_CASE = "generic_file_converter_cli"
NEWS_SITE_SCRAPER_CASE = "news_site_scraper_cli"
WEB_RESEARCH_SUMMARIZER_CASE = "web_research_summarizer_cli"
WEB_RESEARCH_SUMMARIZER_FASTAPI_CASE = "web_research_summarizer_fastapi"

def has_case(case_name: str) -> bool:
    return case_name in {
        CSV_CASE,
        KV_CASE,
        CSV_SORT_CASE,
        OCR_CASE,
        IMAGE_CONTENTS_CASE,
        IMAGE_TABLE_EXCEL_CASE,
        GENERIC_FILE_CONVERTER_CASE,
        NEWS_SITE_SCRAPER_CASE,
        WEB_RESEARCH_SUMMARIZER_CASE,
        WEB_RESEARCH_SUMMARIZER_FASTAPI_CASE,
    }

def acceptance_for(case_name: str, verification: dict[str, object]) -> list[str]:
    if verification.get("status") != "passed":
        return []
    if case_name == CSV_SORT_CASE:
        return [
            "CSV fixture is sorted by requested column",
            "CLI writes sorted CSV output",
            "missing sort column is rejected",
            "all tests run from generated project root",
        ]
    if case_name == OCR_CASE:
        return [
            "image fixture is recognized through an injectable OCR backend",
            "CLI writes recognized text output",
            "missing or unsupported images are rejected with controlled errors",
            "real OCR dependencies are optional and no live network is required",
            "all tests run from generated project root",
        ]
    if case_name == IMAGE_CONTENTS_CASE:
        return [
            "image fixture is described through an injectable vision backend",
            "CLI writes JSON contents output",
            "missing or unsupported images are rejected with controlled errors",
            "real vision backend is optional and not required for default tests",
            "all tests run from generated project root",
        ]
    if case_name == IMAGE_TABLE_EXCEL_CASE:
        return [
            "image table fixture is parsed through an injectable OCR backend",
            "recognized OCR text can be supplied through a UTF-8 text file",
            "CLI writes XLSX, CSV, legacy XLS-compatible, HTML, DOC-compatible and RTF outputs",
            "default output path uses the same base image name with the requested suffix",
            "missing images and unavailable OCR backend are rejected with controlled errors",
            "real vision OCR backend is optional and not required for default tests",
            "all tests run from generated project root",
        ]
    if case_name == GENERIC_FILE_CONVERTER_CASE:
        return [
            "conversion recipe captures source and target formats",
            "library binding recipe proposes bounded adapter candidates",
            "adapter implementation plan selects implemented stdlib backend or fallback",
            "CLI writes target output through adapter boundary",
            "missing or unsupported inputs are rejected with controlled errors",
            "default tests run without real conversion dependencies or network",
            "all tests run from generated project root",
        ]
    if case_name == NEWS_SITE_SCRAPER_CASE:
        return news_scraper_acceptance_for(verification)
    if case_name == WEB_RESEARCH_SUMMARIZER_CASE:
        return web_research_acceptance_for(verification)
    if case_name == WEB_RESEARCH_SUMMARIZER_FASTAPI_CASE:
        return web_research_fastapi_acceptance_for(verification)
    if case_name == KV_CASE:
        return [
            "FastAPI app exposes health and item endpoints",
            "items can be created read updated and deleted",
            "missing items return a controlled 404 response",
            "store logic is separated from API endpoint",
            "all tests run from generated project root",
        ]
    if case_name != CSV_CASE:
        return []
    return [
        "FastAPI app exposes health and aggregate endpoints",
        "CSV payload is validated for required columns",
        "aggregates are grouped and written as JSON report",
        "invalid CSV returns a controlled 400 response",
        "all tests run from generated project root",
    ]

def content_for_case(artifact: str, case_name: str, prompt: str) -> str:
    path = artifact.replace("\\", "/")
    if case_name == KV_CASE:
        return _kv_content(path, prompt)
    if case_name == CSV_SORT_CASE:
        return csv_sort_content_for(path, prompt)
    if case_name == OCR_CASE:
        return ocr_content_for(path, prompt)
    if case_name == IMAGE_CONTENTS_CASE:
        return image_contents_content_for(path, prompt)
    if case_name == IMAGE_TABLE_EXCEL_CASE:
        return image_table_excel_content_for(path, prompt)
    if case_name == GENERIC_FILE_CONVERTER_CASE:
        return generic_file_converter_content_for(path, prompt)
    if case_name == NEWS_SITE_SCRAPER_CASE:
        return news_scraper_content_for(path, prompt)
    if case_name == WEB_RESEARCH_SUMMARIZER_CASE:
        return web_research_content_for(path, prompt)
    if case_name == WEB_RESEARCH_SUMMARIZER_FASTAPI_CASE:
        return web_research_fastapi_content_for(path, prompt)
    if path == "pyproject.toml":
        return _pyproject("csv_aggregator_service")
    if path == "README.md":
        return _readme(prompt)
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("app.py"):
        return _app()
    if path.endswith("aggregator.py"):
        return _aggregator()
    if path.endswith("sample.csv"):
        return "category,value\nalpha,10\nalpha,5\nbeta,7\n"
    if path.endswith("test_aggregator.py"):
        return _test_aggregator()
    if path.endswith("test_api.py"):
        return _test_api()
    return "# Generated Stage 2 package placeholder.\n"

def expected_artifacts_for_case(case_name: str, prompt: str) -> list[str]:
    if case_name == NEWS_SITE_SCRAPER_CASE:
        return news_scraper_expected_artifacts()
    if case_name == WEB_RESEARCH_SUMMARIZER_CASE:
        return web_research_expected_artifacts()
    if case_name == WEB_RESEARCH_SUMMARIZER_FASTAPI_CASE:
        return web_research_fastapi_expected_artifacts()
    return []

def _pyproject(package: str) -> str:
    return (
        "[project]\n"
        f'name = "{package}"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = ["fastapi"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )

def _kv_content(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject("kv_store_service")
    if path == "README.md":
        return _kv_readme(prompt)
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("app.py"):
        return _kv_app()
    if path.endswith("store.py"):
        return _kv_store()
    if path.endswith("test_store.py"):
        return _kv_test_store()
    if path.endswith("test_api.py"):
        return _kv_test_api()
    return "# Generated Stage 2 FastAPI KV package placeholder.\n"

def _kv_readme(prompt: str) -> str:
    return (
        "# fastapi_kv_store\n\n"
        f"Prompt: {prompt}\n\n"
        "Local FastAPI service with in-memory key/value CRUD operations and controlled errors.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run app: `uvicorn kv_store_service.app:app --app-dir src`.\n"
    )

def _kv_store() -> str:
    return (
        "from __future__ import annotations\n\n"
        "class KeyValueStore:\n"
        "    def __init__(self) -> None:\n"
        "        self._items: dict[str, str] = {}\n\n"
        "    def put(self, key: str, value: str) -> dict[str, str]:\n"
        "        if not key.strip():\n"
        "            raise ValueError('key must not be empty')\n"
        "        self._items[key] = value\n"
        "        return {'key': key, 'value': value}\n\n"
        "    def get(self, key: str) -> dict[str, str] | None:\n"
        "        value = self._items.get(key)\n"
        "        return None if value is None else {'key': key, 'value': value}\n\n"
        "    def delete(self, key: str) -> bool:\n"
        "        return self._items.pop(key, None) is not None\n\n"
        "    def all(self) -> list[dict[str, str]]:\n"
        "        return [{'key': key, 'value': value} for key, value in sorted(self._items.items())]\n"
    )

def _kv_app() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from fastapi import FastAPI, HTTPException\n"
        "from pydantic import BaseModel\n\n"
        "from kv_store_service.store import KeyValueStore\n\n\n"
        "app = FastAPI(title='Key Value Store Service')\n"
        "store = KeyValueStore()\n\n\n"
        "class ItemPayload(BaseModel):\n"
        "    value: str\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, str]:\n"
        "    return {'status': 'ok'}\n\n\n"
        "@app.get('/items')\n"
        "def list_items() -> list[dict[str, str]]:\n"
        "    return store.all()\n\n\n"
        "@app.put('/items/{key}')\n"
        "def put_item(key: str, payload: ItemPayload) -> dict[str, str]:\n"
        "    try:\n"
        "        return store.put(key, payload.value)\n"
        "    except ValueError as exc:\n"
        "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n\n\n"
        "@app.get('/items/{key}')\n"
        "def get_item(key: str) -> dict[str, str]:\n"
        "    item = store.get(key)\n"
        "    if item is None:\n"
        "        raise HTTPException(status_code=404, detail='item not found')\n"
        "    return item\n\n\n"
        "@app.delete('/items/{key}')\n"
        "def delete_item(key: str) -> dict[str, str]:\n"
        "    if not store.delete(key):\n"
        "        raise HTTPException(status_code=404, detail='item not found')\n"
        "    return {'status': 'deleted', 'key': key}\n"
    )

def _kv_test_store() -> str:
    return (
        "from kv_store_service.store import KeyValueStore\n\n\n"
        "def test_store_put_get_delete():\n"
        "    store = KeyValueStore()\n"
        "    assert store.put('a', '1') == {'key': 'a', 'value': '1'}\n"
        "    assert store.get('a') == {'key': 'a', 'value': '1'}\n"
        "    assert store.delete('a') is True\n"
        "    assert store.get('a') is None\n\n\n"
        "def test_store_rejects_empty_key():\n"
        "    try:\n"
        "        KeyValueStore().put('', 'x')\n"
        "    except ValueError as exc:\n"
        "        assert 'key' in str(exc)\n"
        "    else:\n"
        "        raise AssertionError('empty key must fail')\n"
    )

def _kv_test_api() -> str:
    return (
        "from fastapi.testclient import TestClient\n\n"
        "from kv_store_service.app import app\n\n\n"
        "def test_health_endpoint():\n"
        "    assert TestClient(app).get('/health').json() == {'status': 'ok'}\n\n\n"
        "def test_item_crud_flow():\n"
        "    client = TestClient(app)\n"
        "    assert client.put('/items/sample', json={'value': 'one'}).json() == {'key': 'sample', 'value': 'one'}\n"
        "    assert client.get('/items/sample').json() == {'key': 'sample', 'value': 'one'}\n"
        "    assert client.get('/items').status_code == 200\n"
        "    assert client.delete('/items/sample').json() == {'status': 'deleted', 'key': 'sample'}\n\n\n"
        "def test_missing_item_returns_404():\n"
        "    assert TestClient(app).get('/items/missing').status_code == 404\n"
    )

def _readme(prompt: str) -> str:
    return (
        "# fastapi_csv_aggregator\n\n"
        f"Prompt: {prompt}\n\n"
        "Local FastAPI service that accepts CSV text, validates category/value columns, "
        "computes grouped aggregates, saves a JSON report, and exposes health checks.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run app: `uvicorn csv_aggregator_service.app:app --reload`.\n"
    )
