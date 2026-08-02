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
