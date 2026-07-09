"""Build a sandbox patch package for map direct GigaChat migration."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--target-model", default="GigaChat-2-Pro")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir).resolve()
    report = build_patch(root=root, project_dir=project_dir, target_model=args.target_model)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def build_patch(*, root: Path, project_dir: Path, target_model: str) -> dict[str, object]:
    source = project_dir / "import_indoc.py"
    if not source.is_file():
        raise FileNotFoundError(source)
    out_dir = _out_dir(root)
    package_dir = out_dir / "package"
    tests_dir = package_dir / "tests"
    package_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    original = source.read_text(encoding="utf-8")
    patched = _patch_import_indoc(original, target_model)
    (package_dir / "import_indoc.py").write_text(patched, encoding="utf-8")
    (tests_dir / "test_gigachat_client.py").write_text(_test_content(), encoding="utf-8")
    _write_readme(out_dir, project_dir, target_model)
    verification = _verify(package_dir)
    report = {
        "artifact_type": "SandboxPatchPackage",
        "status": "ok" if verification["status"] == "passed" else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project": project_dir.as_posix(),
        "target_model": target_model,
        "sandbox_dir": out_dir.as_posix(),
        "files": [
            "package/import_indoc.py",
            "package/tests/test_gigachat_client.py",
            "README.md",
        ],
        "source_code_changes": False,
        "registry_changes": False,
        "verification": verification,
        "next_steps": [
            "review package/import_indoc.py against source import_indoc.py",
            "run tests in sandbox",
            "apply to source project only after explicit approval",
        ],
    }
    (out_dir / "patch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _patch_import_indoc(text: str, target_model: str) -> str:
    text = _ensure_imports(text, ["os", "time", "uuid"])
    text = text.replace(
        'DEFAULT_LLM_URL = "http://127.0.0.1:8000/v1/chat/completions"\n'
        'DEFAULT_LLM_MODEL = "qwen/qwen-plus-2025-07-28"\n',
        'DEFAULT_LLM_URL = os.environ.get("GIGACHAT_API_URL", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions")\n'
        f'DEFAULT_LLM_MODEL = os.environ.get("GIGACHAT_MODEL", "{target_model}")\n'
        'DEFAULT_GIGACHAT_OAUTH_URL = os.environ.get("GIGACHAT_OAUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")\n'
        'DEFAULT_GIGACHAT_SCOPE = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")\n',
    )
    text = text.replace("Disable Qwen extraction and use rule-based parsing only.", "Disable GigaChat extraction and use rule-based parsing only.")
    text = text.replace("OpenAI-compatible chat completions URL.", "GigaChat chat completions URL.")
    text = text.replace("Qwen model name.", "GigaChat model name.")
    text = text.replace("Send only complex candidate lines to Qwen, or all candidate lines.", "Send only complex candidate lines to GigaChat, or all candidate lines.")
    start = text.index("class LlmExtractor:")
    end = text.index("\ndef parse_json_response", start)
    return text[:start] + _llm_extractor_class() + text[end:]


def _ensure_imports(text: str, modules: list[str]) -> str:
    insert_after = "import json\n"
    if insert_after not in text:
        return text
    additions = "".join(f"import {module}\n" for module in modules if f"import {module}\n" not in text)
    if not additions:
        return text
    return text.replace(insert_after, insert_after + additions, 1)


def _llm_extractor_class() -> str:
    return '''class LlmExtractor:
    def __init__(
        self,
        url: str,
        model: str,
        timeout: int = 120,
        cache_path: Path = LLM_CACHE_PATH,
        *,
        auth_key: str | None = None,
        access_token: str | None = None,
        oauth_url: str = DEFAULT_GIGACHAT_OAUTH_URL,
        scope: str = DEFAULT_GIGACHAT_SCOPE,
        verify_ssl: bool = True,
    ):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.cache_path = cache_path
        self.auth_key = auth_key or os.environ.get("GIGACHAT_AUTH_KEY", "")
        self.access_token = access_token or os.environ.get("GIGACHAT_ACCESS_TOKEN", "")
        self.oauth_url = oauth_url
        self.scope = scope
        self.verify_ssl = verify_ssl
        self.token_expires_at = 0.0
        self.cache = self.load_cache()
        self.failed_batches = 0
        self.cache_hits = 0

    def load_cache(self) -> dict:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_cache(self) -> None:
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def batch_key(self, report_date: str, rows: list[dict]) -> str:
        value = json.dumps(
            {"provider": "gigachat", "model": self.model, "prompt_version": LLM_PROMPT_VERSION, "date": report_date, "rows": rows},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _headers(self) -> dict[str, str]:
        token = self._access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}

    def _access_token(self) -> str:
        if self.access_token and time.time() < self.token_expires_at - 60:
            return self.access_token
        if self.access_token and not self.auth_key:
            return self.access_token
        if not self.auth_key:
            raise RuntimeError("GIGACHAT_AUTH_KEY or GIGACHAT_ACCESS_TOKEN is required for direct GigaChat API")
        response = requests.post(
            self.oauth_url,
            data={"scope": self.scope},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {self.auth_key}",
            },
            timeout=min(self.timeout, 30),
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        payload = response.json()
        self.access_token = str(payload["access_token"])
        self.token_expires_at = float(payload.get("expires_at", 0)) / 1000 if float(payload.get("expires_at", 0)) > 10_000_000_000 else float(payload.get("expires_at", 0))
        return self.access_token

    def _post_chat(self, payload: dict, timeout: int | None = None):
        return requests.post(self.url, json=payload, headers=self._headers(), timeout=timeout or self.timeout, verify=self.verify_ssl)

    def check_available(self, timeout: int = 5) -> tuple[bool, str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Ответь только JSON: {\\\"ok\\\": true}"}],
            "temperature": 0,
            "max_tokens": 20,
        }
        try:
            response = self._post_chat(payload, timeout=timeout)
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:300]}"
            content = response.json()["choices"][0]["message"]["content"]
            parse_json_response(content)
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def extract_batch(self, report_date: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        cache_key = self.batch_key(report_date, rows)
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        system_prompt = (
            "Ты извлекаешь структурированные события из русских оперативных сводок. "
            "Верни только валидный JSON без markdown. Не придумывай факты. "
            "Если в строке есть несколько населенных пунктов или несколько типов последствий, "
            "верни отдельные записи для каждого населенного пункта. "
            "Фразы вида 'погибших и пострадавших нет' не являются группами dead/wounded. "
            "Допустимые группы: attack_aircraft, attack_fpv, drop, suppressed, damage, wounded, dead, other. "
            "Классификация строгая: если сказано 'БПЛА самолетного типа' или 'самолетного типа', ставь attack_aircraft. "
            "Ставь attack_fpv только если в строке явно есть 'FPV'. "
            "Если в одной строке есть FPV-дрон и БПЛА самолетного типа, верни обе группы только для соответствующего описания. "
            "damage ставь только при реальном повреждении имущества. "
            "dead/wounded ставь только при реальных погибших или пострадавших, не при фразе об их отсутствии."
        )
        user_prompt = {
            "report_date": report_date,
            "schema": {
                "events": [
                    {
                        "line": "number",
                        "time": "HH:MM or empty string",
                        "place": "населенный пункт без префикса н.п./город/село/станция",
                        "district": "район без окончания -ский/-ского, or empty string",
                        "groups": ["attack_fpv"],
                        "summary": "краткое описание события из строки",
                        "confidence": 0.0,
                    }
                ]
            },
            "rows": rows,
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": 4096,
        }
        response = self._post_chat(payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = parse_json_response(content)
        events = data.get("events", [])
        if not isinstance(events, list):
            raise ValueError("LLM response does not contain an events array")
        parsed_events = [event for event in events if isinstance(event, dict)]
        self.cache[cache_key] = parsed_events
        self.save_cache()
        return parsed_events
'''


def _test_content() -> str:
    return '''import time
from unittest.mock import Mock, patch

from import_indoc import LlmExtractor


def _response(status=200, payload=None, text=""):
    response = Mock()
    response.status_code = status
    response.text = text
    response.json.return_value = payload or {}
    response.raise_for_status.return_value = None
    return response


def test_check_available_uses_gigachat_bearer_token(tmp_path):
    oauth = _response(payload={"access_token": "token-1", "expires_at": int((time.time() + 1800) * 1000)})
    chat = _response(payload={"choices": [{"message": {"content": "{\\"ok\\": true}"}}]})
    with patch("import_indoc.requests.post", side_effect=[oauth, chat]) as post:
        client = LlmExtractor("https://gigachat.devices.sberbank.ru/api/v1/chat/completions", "GigaChat-2-Pro", cache_path=tmp_path / "cache.json", auth_key="basic-key")
        assert client.check_available() == (True, "ok")
    assert post.call_args_list[0].kwargs["headers"]["Authorization"] == "Basic basic-key"
    assert post.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer token-1"


def test_extract_batch_preserves_json_contract_and_cache_key(tmp_path):
    chat = _response(payload={"choices": [{"message": {"content": "{\\"events\\": [{\\"line\\": 1, \\"place\\": \\"Курск\\"}]}"}}]})
    with patch("import_indoc.requests.post", return_value=chat):
        client = LlmExtractor("https://gigachat.devices.sberbank.ru/api/v1/chat/completions", "GigaChat-2-Pro", cache_path=tmp_path / "cache.json", access_token="token-1")
        rows = [{"line": 1, "text": "г. Курск"}]
        assert client.extract_batch("2026-06-18", rows)[0]["place"] == "Курск"
        key = client.batch_key("2026-06-18", rows)
    assert key in client.cache
    assert client.batch_key("2026-06-19", rows) != key
'''


def _write_readme(out_dir: Path, project_dir: Path, target_model: str) -> None:
    content = (
        "# GigaChat Sandbox Patch\n\n"
        f"Source project: `{project_dir.as_posix()}`\n\n"
        f"Target model: `{target_model}`\n\n"
        "This package does not modify the source project. Review `package/import_indoc.py` and tests before applying.\n\n"
        "Required runtime secrets are environment variables, not source literals: `GIGACHAT_AUTH_KEY` or `GIGACHAT_ACCESS_TOKEN`.\n"
    )
    (out_dir / "README.md").write_text(content, encoding="utf-8")


def _verify(package_dir: Path) -> dict[str, object]:
    commands = [
        [sys.executable, "-m", "compileall", "-b", "."],
        [sys.executable, "-m", "pytest", "tests", "-q"],
    ]
    results = []
    for command in commands:
        result = subprocess.run(command, cwd=package_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        results.append(
            {
                "command": " ".join(command),
                "returncode": result.returncode,
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout_tail": result.stdout[-1200:],
                "stderr_tail": result.stderr[-1200:],
            }
        )
    return {"status": "passed" if all(row["status"] == "passed" for row in results) else "failed", "commands": results}


def _out_dir(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_dir = root / "artifacts" / "gigachat_sandbox_patches" / f"patch_{stamp}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    return out_dir


if __name__ == "__main__":
    raise SystemExit(main())
