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


def parse_args(parser):
    parser.add_argument("--no-llm", action="store_true", help="Disable Qwen extraction and use rule-based parsing only.")
    parser.add_argument("--llm-url", default=DEFAULT_LLM_URL, help="OpenAI-compatible chat completions URL.")
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL, help="Qwen model name.")
    parser.add_argument("--llm-scope", help="Send only complex candidate lines to Qwen, or all candidate lines.")


def run_batches():
    print(f"  Qwen batch {1}")
