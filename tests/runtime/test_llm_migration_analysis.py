from __future__ import annotations

import importlib.util
from pathlib import Path


def test_llm_migration_analysis_finds_local_proxy_and_gigachat_plan(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "import_indoc.py").write_text(
        "import requests\n"
        "DEFAULT_LLM_URL = 'http://127.0.0.1:8000/v1/chat/completions'\n"
        "DEFAULT_LLM_MODEL = 'qwen/qwen-plus-2025-07-28'\n"
        "LLM_CACHE_PATH = 'cache.json'\n"
        "def check_available():\n"
        "    return requests.post(DEFAULT_LLM_URL, json={'model': DEFAULT_LLM_MODEL}).status_code == 200\n"
        "def parse_args(parser):\n"
        "    parser.add_argument('--llm-model')\n",
        encoding="utf-8",
    )
    module = _load_tool()

    report = module.analyze_llm_migration(project_dir=project, target_model="GigaChat-2-Pro")

    assert report["artifact_type"] == "LlmMigrationAnalysis"
    assert report["status"] == "needs_migration"
    assert report["blockers"] == []
    assert report["current_state"]["default_urls"]
    assert report["current_state"]["request_calls"]
    assert report["migration_plan"][1]["action"] == "Add GigaChat direct implementation with model `GigaChat-2-Pro`."


def _load_tool():
    path = Path(__file__).resolve().parents[2] / "tools" / "llm_migration_analysis.py"
    spec = importlib.util.spec_from_file_location("llm_migration_analysis_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
