import os
from pathlib import Path

from tools.map_gigachat_tester import run_map_gigachat_tester


def test_map_gigachat_tester_dry_run_approves_with_risk(tmp_path: Path) -> None:
    project = _project(tmp_path)

    report = run_map_gigachat_tester(root=tmp_path, project_dir=project, live=False, write=True)

    assert report["artifact_type"] == "TesterProjectReview"
    assert report["role"] == "tester"
    assert report["recommendation"] == "approve_with_risks"
    assert report["checks"]["compile_passed"] is True
    assert report["checks"]["rule_based_import_passed"] is True
    assert report["checks"]["live_smoke_passed"] is True
    assert report["secret_policy"]["secrets_written_to_artifacts"] is False
    assert Path(report["report_path"]).is_file()


def test_map_gigachat_tester_live_smoke_with_mocked_provider(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setenv("GIGACHAT_CLIENT_SECRET", "redacted-test-secret")
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL", "0")

    report = run_map_gigachat_tester(root=tmp_path, project_dir=project, live=True, write=False)

    assert report["recommendation"] == "approve"
    assert report["checks"]["live_smoke_passed"] is True
    assert report["evidence"]["live_smoke"]["payload"]["event_count"] == 1
    assert "redacted-test-secret" not in str(report)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "map"
    project.mkdir()
    (project / "import_indoc.py").write_text(
        '''
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

LLM_CACHE_PATH = Path("cache.json")
LLM_PROMPT_VERSION = "test"
DEFAULT_LLM_URL = os.environ.get("GIGACHAT_API_URL", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions")
DEFAULT_LLM_MODEL = os.environ.get("GIGACHAT_MODEL", "GigaChat-2-Pro")
DEFAULT_GIGACHAT_VERIFY_SSL = os.environ.get("GIGACHAT_VERIFY_SSL", "1").lower() not in {"0", "false", "no", "off"}
SCHEMA_HINT = "населенный пункт без префикса н.п./город/село/станция"


class LlmExtractor:
    def __init__(self, url, model, timeout=60, cache_path=LLM_CACHE_PATH):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.cache_path = cache_path
        self.auth_key = os.environ.get("GIGACHAT_AUTH_KEY", "") or os.environ.get("GIGACHAT_CLIENT_SECRET", "")

    def check_available(self, timeout=30):
        return bool(self.auth_key), "ok" if self.auth_key else "missing"

    def extract_batch(self, report_date, rows):
        return [{
            "line": 1,
            "time": "12:30",
            "place": "Курск",
            "district": "",
            "groups": ["suppressed", "attack_aircraft"],
            "summary": "Подавлен БПЛА самолетного типа",
            "confidence": 0.0,
        }]

    def batch_key(self, report_date, rows):
        return hashlib.sha256(json.dumps({"provider": "gigachat", "model": self.model, "prompt_version": LLM_PROMPT_VERSION, "date": report_date, "rows": rows}, sort_keys=True).encode()).hexdigest()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Disable GigaChat extraction and use rule-based parsing only.")
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL, help="GigaChat model name.")
    parser.add_argument("--llm-url", default=DEFAULT_LLM_URL, help="GigaChat chat completions URL.")
    parser.add_argument("--llm-scope", help="Send only complex candidate lines to GigaChat, or all candidate lines.")
    return parser.parse_args()


def main():
    args = parse_args()
    print("  GigaChat batch 1/1")
    print(SCHEMA_HINT)
    print("Wrote incidents.json")
    print(json.dumps({"total_events": 1, "rules_events": 1, "llm_events": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )
    return project
