"""Stage 2 deterministic package templates."""

from __future__ import annotations


CASE = "fastapi_csv_aggregator"
PACKAGE = "csv_aggregator_service"


def has_case(case_name: str) -> bool:
    return case_name == CASE


def acceptance_for(case_name: str, verification: dict[str, object]) -> list[str]:
    if case_name != CASE or verification.get("status") != "passed":
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
    if path == "pyproject.toml":
        return _pyproject()
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


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "csv_aggregator_service"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = ["fastapi"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
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
