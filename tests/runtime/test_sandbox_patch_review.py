from pathlib import Path

from tools.gigachat_sandbox_patch import build_patch
from tools.sandbox_patch_review import review_patch_package


SOURCE = '''
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


def _build_package(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "map"
    project_dir.mkdir()
    (project_dir / "import_indoc.py").write_text(SOURCE, encoding="utf-8")
    package = build_patch(root=tmp_path, project_dir=project_dir, target_model="GigaChat-2-Pro")
    return project_dir, Path(str(package["sandbox_dir"]))


def test_sandbox_patch_review_is_review_only_by_default(tmp_path: Path) -> None:
    project_dir, patch_dir = _build_package(tmp_path)

    review = review_patch_package(
        patch_dir=patch_dir,
        expected_source_project=project_dir,
        write_review=True,
        apply_approved=False,
    )

    assert review["status"] == "review_ready"
    assert review["apply"]["status"] == "not_requested"
    assert (patch_dir / "patch_review.json").is_file()
    assert (patch_dir / "patch_review.md").is_file()
    assert "http://127.0.0.1:8000" in (project_dir / "import_indoc.py").read_text(encoding="utf-8")


def test_sandbox_patch_review_applies_only_with_explicit_flag(tmp_path: Path) -> None:
    project_dir, patch_dir = _build_package(tmp_path)

    review = review_patch_package(
        patch_dir=patch_dir,
        expected_source_project=project_dir,
        apply_approved=True,
    )

    assert review["status"] == "applied"
    assert review["apply"]["status"] == "applied"
    patched = (project_dir / "import_indoc.py").read_text(encoding="utf-8")
    assert "GIGACHAT_AUTH_KEY" in patched
    assert "http://127.0.0.1:8000" not in patched
    backups = list(project_dir.glob("import_indoc.py.bak.*"))
    assert len(backups) == 1
    assert "http://127.0.0.1:8000" in backups[0].read_text(encoding="utf-8")
