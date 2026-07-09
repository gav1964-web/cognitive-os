"""Acceptance probe for sandbox patch review-only gate."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from gigachat_sandbox_patch import build_patch
from sandbox_patch_review import review_patch_package


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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = root / "artifacts" / "sandbox_patch_review_probe" / "map_fixture"
    if project_dir.parent.exists():
        shutil.rmtree(project_dir.parent)
    project_dir.mkdir(parents=True)
    source = project_dir / "import_indoc.py"
    source.write_text(SOURCE, encoding="utf-8")

    package = build_patch(root=root, project_dir=project_dir, target_model="GigaChat-2-Pro")
    review = review_patch_package(
        patch_dir=Path(str(package["sandbox_dir"])),
        expected_source_project=project_dir,
        write_review=args.write,
        apply_approved=False,
    )
    source_text = source.read_text(encoding="utf-8")
    result = {
        "artifact_type": "SandboxPatchReviewProbe",
        "status": "ok" if review["status"] == "review_ready" and "http://127.0.0.1:8000" in source_text else "failed",
        "package_status": package["status"],
        "review_status": review["status"],
        "apply_status": review["apply"]["status"],
        "source_unchanged": "http://127.0.0.1:8000" in source_text and "GIGACHAT_AUTH_KEY" not in source_text,
        "review_path": review.get("review_json"),
        "patch_dir": package["sandbox_dir"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
