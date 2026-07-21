from pathlib import Path

from plugins.extract_python_structure.src.main import run


def test_extract_python_structure_detects_imports_functions_and_routes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/app.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.route('/items', methods=['GET', 'POST'])\n"
        "def items():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    result = run({"root": "project"})

    assert result["imports"] == ["flask"]
    assert result["files"][0]["functions"][0]["name"] == "items"
    assert result["routes"][0]["route"] == "/items"
    assert result["routes"][0]["methods"] == ["GET", "POST"]
    assert result["contracts"]["typed_functions"] == []
    assert result["central_nodes"][0]["name"] == "items"


def test_extract_python_structure_detects_fastapi_method_routes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/api.py").write_text(
        "from fastapi import APIRouter, FastAPI\n"
        "app = FastAPI()\n"
        "router = APIRouter()\n"
        "@app.get('/health')\n"
        "async def health():\n"
        "    return {'ok': True}\n"
        "@router.post('/items')\n"
        "def create_item():\n"
        "    return {'id': 1}\n",
        encoding="utf-8",
    )

    result = run({"root": "project"})

    assert result["imports"] == ["fastapi"]
    assert [(route["route"], route["methods"]) for route in result["routes"]] == [
        ("/health", ["GET"]),
        ("/items", ["POST"]),
    ]


def test_extract_python_structure_prioritizes_app_code_over_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/app/api").mkdir(parents=True)
    Path("project/tools").mkdir()
    for index in range(5):
        Path(f"project/tools/tool_{index}.py").write_text(f"def tool_{index}():\n    pass\n", encoding="utf-8")
    Path("project/app/api/server.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )

    result = run({"root": "project", "max_files": 1})

    assert result["files"][0]["path"] == "app/api/server.py"
    assert result["routes"][0]["route"] == "/health"


def test_extract_python_structure_prioritizes_package_code_over_docs_src(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/typer").mkdir(parents=True)
    Path("project/docs_src/tutorial").mkdir(parents=True)
    Path("project/docs_src/tutorial/main.py").write_text(
        "def main():\n"
        "    print('demo')\n",
        encoding="utf-8",
    )
    Path("project/typer/core.py").write_text(
        "def invoke():\n"
        "    parse_args()\n"
        "    build_context()\n"
        "    execute_callback()\n"
        "    render_result()\n"
        "    return True\n"
        "def parse_args():\n"
        "    return []\n"
        "def build_context():\n"
        "    return {}\n"
        "def execute_callback():\n"
        "    return None\n"
        "def render_result():\n"
        "    return ''\n",
        encoding="utf-8",
    )

    result = run({"root": "project", "max_files": 2})

    assert result["files"][0]["path"] == "typer/core.py"
    assert result["central_nodes"][0]["path"] == "typer/core.py"
    assert result["central_nodes"][0]["name"] == "invoke"


def test_extract_python_structure_prioritizes_domain_package_roots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/scripts").mkdir(parents=True)
    Path("project/prefect/task_engine").mkdir(parents=True)
    for index in range(5):
        Path(f"project/scripts/helper_{index}.py").write_text(f"def helper_{index}():\n    pass\n", encoding="utf-8")
    Path("project/prefect/task_engine/runtime.py").write_text(
        "def run_task_engine(flow, task, scheduler):\n"
        "    state = build_task_state(task)\n"
        "    scheduler.submit(flow, state)\n"
        "    return state\n"
        "def build_task_state(task):\n"
        "    return {'task': task}\n",
        encoding="utf-8",
    )

    result = run({"root": "project", "max_files": 1})

    assert result["files"][0]["path"] == "prefect/task_engine/runtime.py"
    assert result["domain_flow_anchors"][0]["name"] == "run_task_engine"


def test_extract_python_structure_does_not_treat_json_dumps_as_file_io(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    (app / "cache.py").write_text(
        """
import hashlib
import json

def build_key(provider_id: str, messages: list) -> str:
    payload = {"provider": provider_id, "messages": messages}
    text = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = run({"root": ".", "max_files": 10})

    functions = result["files"][0]["functions"]
    build_key = next(item for item in functions if item["name"] == "build_key")
    assert "filesystem" not in build_key["side_effects"]
    assert result["pure_transform_candidates"][0]["name"] == "build_key"


def test_extract_python_structure_reports_errors_schema_fields_and_tests(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/app").mkdir(parents=True)
    Path("project/tests").mkdir()
    Path("project/app/models.py").write_text(
        "from pydantic import BaseModel\n"
        "class ItemRequest(BaseModel):\n"
        "    name: str\n"
        "    count: int = 1\n",
        encoding="utf-8",
    )
    Path("project/app/service.py").write_text(
        "from app.models import ItemRequest\n"
        "def handle(item: ItemRequest) -> dict:\n"
        "    try:\n"
        "        if not item.name:\n"
        "            raise ValueError('empty')\n"
        "        return {'name': item.name}\n"
        "    except ValueError:\n"
        "        raise\n",
        encoding="utf-8",
    )
    Path("project/tests/test_service.py").write_text(
        "def test_handle():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    result = run({"root": "project", "max_files": 10})

    insights = result["project_insights"]
    assert insights["schema_fields"][0]["class"] == "ItemRequest"
    assert insights["schema_fields"][0]["fields"][0] == {"name": "name", "annotation": "str"}
    assert "ValueError" in insights["error_handling"]["raises"]
    assert insights["test_surface"]["test_functions"] == 1
    assert insights["test_surface"]["test_files_seen"] == 1
    assert result["contracts"]["typed_functions"][0]["name"] == "handle"
