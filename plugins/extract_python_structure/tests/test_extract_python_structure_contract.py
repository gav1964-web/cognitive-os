from pathlib import Path

from plugins.extract_python_structure.src.main import run


def test_extract_python_structure_accepts_utf8_bom(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/app.py").write_text("\ufeffdef ready():\n    return True\n", encoding="utf-8")

    result = run({"root": "project"})

    assert result["files"][0]["functions"][0]["name"] == "ready"
    assert result["skipped"] == []


def test_extract_python_structure_separates_newer_parser_syntax(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/app.py").write_text("class Cache[T]:\n    pass\n", encoding="utf-8")

    result = run({"root": "project"})

    assert result["skipped"] == [
        {"path": "app.py", "reason": "ParserVersionIncompatible", "line": 1}
    ]


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


def test_extract_python_structure_ignores_dummyserver_routes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "dummyserver").mkdir(parents=True)
    (project / "dummyserver" / "app.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.route('/fixture')\n"
        "def fixture():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    result = run({"root": "."})

    assert result["routes"] == []


def test_extract_python_structure_treats_wasm_preview_runner_as_context(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "pydantic-core" / "wasm-preview").mkdir(parents=True)
    (project / "pydantic-core" / "wasm-preview" / "run_tests.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/fixture')\n"
        "def fixture():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    result = run({"root": "."})

    assert result["routes"] == []


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


def test_extract_python_structure_defers_build_metadata_behind_named_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/product/apis").mkdir(parents=True)
    Path("project/setup.py").write_text("def parse_requirements():\n    return []\n", encoding="utf-8")
    Path("project/product/__init__.py").write_text("", encoding="utf-8")
    Path("project/product/apis/inference.py").write_text(
        "def run_inference(model: str, inputs: list) -> list:\n    return list(inputs)\n", encoding="utf-8"
    )

    result = run({"root": "project", "max_files": 2})

    assert [row["path"] for row in result["files"]] == ["product/__init__.py", "product/apis/inference.py"]


def test_extract_python_structure_prioritizes_owned_package_over_config_modules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/configs/base").mkdir(parents=True)
    Path("project/sdk/apis").mkdir(parents=True)
    for index in range(4):
        Path(f"project/configs/base/backend_{index}.py").write_text("backend = 'demo'\n", encoding="utf-8")
    Path("project/sdk/__init__.py").write_text("", encoding="utf-8")
    Path("project/sdk/apis/inference.py").write_text("def infer(values):\n    return list(values)\n", encoding="utf-8")

    result = run({"root": "project", "max_files": 2})

    assert [row["path"] for row in result["files"]] == ["sdk/__init__.py", "sdk/apis/inference.py"]


def test_extract_python_structure_prioritizes_package_code_over_docs_src(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/typer").mkdir(parents=True)
    Path("project/docs_src/tutorial").mkdir(parents=True)
    Path("project/docs_src/__init__.py").write_text("", encoding="utf-8")
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


def test_extract_python_structure_defers_end_to_end_generated_clients(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/end_to_end_tests/generated_client").mkdir(parents=True)
    Path("project/openapi_client").mkdir(parents=True)
    Path("project/end_to_end_tests/__init__.py").write_text("", encoding="utf-8")
    Path("project/end_to_end_tests/generated_client/api.py").write_text("def regen():\n    return None\n", encoding="utf-8")
    Path("project/openapi_client/__init__.py").write_text("", encoding="utf-8")
    Path("project/openapi_client/parser.py").write_text("def parse_schema(data: dict) -> dict:\n    return data\n", encoding="utf-8")

    result = run({"root": "project", "max_files": 2})

    assert [row["path"] for row in result["files"]] == ["openapi_client/__init__.py", "openapi_client/parser.py"]


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


def test_extract_python_structure_prioritizes_root_src_over_nested_packages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/packages/noisy/tests").mkdir(parents=True)
    Path("project/src/zarr").mkdir(parents=True)
    for index in range(20):
        Path(f"project/packages/noisy/module_{index}.py").write_text(f"def helper_{index}():\n    pass\n", encoding="utf-8")
        Path(f"project/packages/noisy/tests/test_{index}.py").write_text("def test_noise():\n    pass\n", encoding="utf-8")
    Path("project/src/zarr/__init__.py").write_text(
        "def open_array(store: str, path: str | None = None) -> dict:\n"
        "    return {'store': store, 'path': path}\n",
        encoding="utf-8",
    )

    result = run({"root": "project", "max_files": 2})

    assert result["files"][0]["path"] == "src/zarr/__init__.py"
    assert result["contracts"]["typed_functions"][0]["name"] == "open_array"


def test_extract_python_structure_defers_profiling_and_integration_noise(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/profiling").mkdir(parents=True)
    Path("project/integration_embedded").mkdir()
    Path("project/clientlib").mkdir()
    Path("project/profiling/benchmark.py").write_text("def run_profile():\n    pass\n", encoding="utf-8")
    Path("project/integration_embedded/conftest.py").write_text("def fixture():\n    pass\n", encoding="utf-8")
    Path("project/clientlib/query.py").write_text(
        "def build_query(filters: dict) -> dict:\n    return {'where': filters}\n",
        encoding="utf-8",
    )

    result = run({"root": "project", "max_files": 1})

    assert result["files"][0]["path"] == "clientlib/query.py"
    assert result["contracts"]["typed_functions"][0]["name"] == "build_query"


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


def test_extract_python_structure_finds_reproducible_boolean_policy(tmp_path, monkeypatch):
    (tmp_path / "policy.py").write_text(
        "def can_comment(media_type: str, allowed: set[str]) -> bool:\n"
        "    return media_type in allowed\n\n"
        "def can_like(state, percentage: int) -> bool:\n"
        "    return randint(1, 100) <= percentage\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = run({"root": "."})

    assert [row["name"] for row in result["bounded_policy_candidates"]] == ["can_comment"]


def test_pure_transform_candidates_exclude_void_async_wrappers(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text(
        "def capture_exit(function):\n"
        "    return function\n\n"
        "@capture_exit\n"
        "async def api_server(host='0.0.0.0'):\n"
        "    await app.run_api_server(host)\n\n"
        "def normalize(value):\n"
        "    return value.strip().lower()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = run({"root": "."})

    names = [row["name"] for row in result["pure_transform_candidates"]]
    assert "normalize" in names
    assert "api_server" not in names


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


def test_extract_python_structure_indexes_oversized_single_file_cli_with_explicit_budget(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = "# product CLI\n" + ("# retained behavior\n" * 15000) + "def deploy(config: str) -> bool:\n    return bool(config)\n"
    Path("product.py").write_text(source, encoding="utf-8")

    result = run({"root": ".", "max_files": 10, "max_bytes_per_file": 1_000_000})

    assert result["files"][0]["path"] == "product.py"
    assert result["contracts"]["typed_functions"][0]["name"] == "deploy"
