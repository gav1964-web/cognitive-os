"""Stage 2 deterministic package templates."""

from __future__ import annotations

from .greenfield_csv_sort_template import content_for as csv_sort_content_for
from .greenfield_image_contents_template import content_for as image_contents_content_for
from .greenfield_ocr_template import content_for as ocr_content_for


CSV_CASE = "fastapi_csv_aggregator"
KV_CASE = "fastapi_kv_store"
CSV_SORT_CASE = "csv_sort_cli"
OCR_CASE = "ocr_image_cli"
IMAGE_CONTENTS_CASE = "image_contents_cli"


def has_case(case_name: str) -> bool:
    return case_name in {CSV_CASE, KV_CASE, CSV_SORT_CASE, OCR_CASE, IMAGE_CONTENTS_CASE}


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


def _aggregator() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import csv\n"
        "import json\n"
        "from io import StringIO\n"
        "from pathlib import Path\n\n\n"
        "REQUIRED_COLUMNS = {'category', 'value'}\n\n\n"
        "def aggregate_csv(csv_text: str) -> dict[str, object]:\n"
        "    reader = csv.DictReader(StringIO(csv_text))\n"
        "    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):\n"
        "        raise ValueError('CSV must contain category and value columns')\n"
        "    groups: dict[str, list[float]] = {}\n"
        "    for row in reader:\n"
        "        category = (row.get('category') or '').strip()\n"
        "        if not category:\n"
        "            raise ValueError('category must not be empty')\n"
        "        try:\n"
        "            value = float(row.get('value') or '')\n"
        "        except ValueError as exc:\n"
        "            raise ValueError('value must be numeric') from exc\n"
        "        groups.setdefault(category, []).append(value)\n"
        "    return {'groups': {name: _stats(values) for name, values in sorted(groups.items())}}\n\n\n"
        "def save_report(report: dict[str, object], output_path: str) -> str:\n"
        "    target = Path(output_path)\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')\n"
        "    return str(target)\n\n\n"
        "def _stats(values: list[float]) -> dict[str, float]:\n"
        "    total = sum(values)\n"
        "    return {'count': len(values), 'sum': total, 'average': total / len(values)}\n"
    )


def _app() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from fastapi import FastAPI, HTTPException\n"
        "from pydantic import BaseModel\n\n"
        "from csv_aggregator_service.aggregator import aggregate_csv, save_report\n\n\n"
        "app = FastAPI(title='CSV Aggregator Service')\n\n\n"
        "class CsvPayload(BaseModel):\n"
        "    csv_text: str\n"
        "    output_path: str = 'reports/report.json'\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, str]:\n"
        "    return {'status': 'ok'}\n\n\n"
        "@app.post('/aggregate')\n"
        "def aggregate(payload: CsvPayload) -> dict[str, object]:\n"
        "    try:\n"
        "        report = aggregate_csv(payload.csv_text)\n"
        "    except ValueError as exc:\n"
        "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n"
        "    path = save_report(report, payload.output_path)\n"
        "    return {'report': report, 'output_path': path}\n"
    )


def _test_aggregator() -> str:
    return (
        "from pathlib import Path\n\n"
        "import pytest\n\n"
        "from csv_aggregator_service.aggregator import aggregate_csv, save_report\n\n\n"
        "def test_aggregate_csv_fixture(tmp_path):\n"
        "    csv_text = Path('tests/fixtures/sample.csv').read_text(encoding='utf-8')\n"
        "    report = aggregate_csv(csv_text)\n"
        "    assert report['groups']['alpha']['sum'] == 15.0\n"
        "    assert report['groups']['beta']['count'] == 1\n"
        "    path = save_report(report, str(tmp_path / 'report.json'))\n"
        "    assert Path(path).is_file()\n\n\n"
        "def test_invalid_csv_missing_columns():\n"
        "    with pytest.raises(ValueError):\n"
        "        aggregate_csv('name,total\\na,1\\n')\n"
    )


def _test_api() -> str:
    return (
        "from pathlib import Path\n\n"
        "from fastapi.testclient import TestClient\n\n"
        "from csv_aggregator_service.app import app\n\n\n"
        "def test_health_endpoint():\n"
        "    assert TestClient(app).get('/health').json() == {'status': 'ok'}\n\n\n"
        "def test_aggregate_endpoint_writes_report(tmp_path):\n"
        "    csv_text = Path('tests/fixtures/sample.csv').read_text(encoding='utf-8')\n"
        "    response = TestClient(app).post('/aggregate', json={'csv_text': csv_text, 'output_path': str(tmp_path / 'r.json')})\n"
        "    assert response.status_code == 200\n"
        "    body = response.json()\n"
        "    assert body['report']['groups']['alpha']['average'] == 7.5\n"
        "    assert Path(body['output_path']).is_file()\n\n\n"
        "def test_invalid_csv_returns_400():\n"
        "    response = TestClient(app).post('/aggregate', json={'csv_text': 'bad,data\\n1,2\\n'})\n"
        "    assert response.status_code == 400\n"
    )
