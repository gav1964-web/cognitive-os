from pathlib import Path

from tools.gigachat_sandbox_patch import _patch_import_indoc, build_patch


def test_gigachat_sandbox_patch_builds_verified_package(tmp_path: Path) -> None:
    project_dir = tmp_path / "map"
    project_dir.mkdir()
    (project_dir / "import_indoc.py").write_text(
        '''
import hashlib
import json
from pathlib import Path

import requests

LLM_CACHE_PATH = Path("indoc_llm_cache.json")
LLM_PROMPT_VERSION = "test"
DEFAULT_LLM_URL = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_LLM_MODEL = "qwen/qwen-plus-2025-07-28"


class LlmExtractor:
    def __init__(self):
        raise NotImplementedError


def parse_json_response(text: str) -> dict:
    return json.loads(text)
''',
        encoding="utf-8",
    )

    report = build_patch(root=tmp_path, project_dir=project_dir, target_model="GigaChat-2-Pro")

    assert report["status"] == "ok"
    assert report["source_code_changes"] is False
    assert report["registry_changes"] is False
    assert report["verification"]["status"] == "passed"

    sandbox_dir = Path(str(report["sandbox_dir"]))
    patched = (sandbox_dir / "package" / "import_indoc.py").read_text(encoding="utf-8")
    assert "GIGACHAT_AUTH_KEY" in patched
    assert "GigaChat-2-Pro" in patched
    assert "http://127.0.0.1:8000" not in patched
    assert "населенный пункт без префикса" in patched
    assert "Qwen" not in patched


def test_gigachat_patch_is_idempotent_for_imports(tmp_path: Path) -> None:
    source = SOURCE_WITH_LOCAL_PROXY()
    once = _patch_import_indoc(source, "GigaChat-2-Pro")
    twice = _patch_import_indoc(once, "GigaChat-2-Pro")

    assert twice.count("import os\n") == 1
    assert twice.count("import time\n") == 1
    assert twice.count("import uuid\n") == 1


def SOURCE_WITH_LOCAL_PROXY() -> str:
    return '''
import hashlib
import json
from pathlib import Path

import requests

LLM_CACHE_PATH = Path("indoc_llm_cache.json")
LLM_PROMPT_VERSION = "test"
DEFAULT_LLM_URL = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_LLM_MODEL = "qwen/qwen-plus-2025-07-28"


class LlmExtractor:
    def __init__(self):
        raise NotImplementedError


def parse_json_response(text: str) -> dict:
    return json.loads(text)
'''
