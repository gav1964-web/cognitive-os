from pathlib import Path

from tools.gigachat_sandbox_patch import _patch_import_indoc
from tools.map_llm_migration_trial import run_trial


def test_map_llm_migration_trial_replays_teacher_patch(tmp_path: Path) -> None:
    source_project = tmp_path / "map"
    source_project.mkdir()
    baseline = _baseline_import_indoc()
    teacher = _patch_import_indoc(baseline, "GigaChat-2-Pro")

    (source_project / "import_indoc.py").write_text(teacher, encoding="utf-8")
    (source_project / "import_indoc.py.bak.0").write_text(baseline, encoding="utf-8")

    report = run_trial(root=tmp_path, source_project=source_project, target_model="GigaChat-2-Pro", write=True)

    assert report["status"] == "ok"
    assert report["comparison"]["exact_match"] is True
    assert report["comparison"]["feature_score"] == report["comparison"]["feature_total"]
    assert report["invariants"]["source_project_modified"] is False


def _baseline_import_indoc() -> str:
    return '''import hashlib
import json
from pathlib import Path

import requests

LLM_CACHE_PATH = Path("indoc_llm_cache.json")
LLM_PROMPT_VERSION = "test"
DEFAULT_LLM_URL = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_LLM_MODEL = "qwen/qwen-plus-2025-07-28"


class LlmExtractor:
    pass


def parse_json_response(text: str) -> dict:
    return json.loads(text)


def parse_args(parser):
    parser.add_argument("--no-llm", action="store_true", help="Disable Qwen extraction and use rule-based parsing only.")
    parser.add_argument("--llm-url", default=DEFAULT_LLM_URL, help="OpenAI-compatible chat completions URL.")
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL, help="Qwen model name.")
    parser.add_argument("--llm-scope", help="Send only complex candidate lines to Qwen, or all candidate lines.")


def run_batches():
    print(f"  Qwen batch {1}")
'''
