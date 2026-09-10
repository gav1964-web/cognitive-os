"""Image contents CLI template for Stage 2 generated packages."""

from __future__ import annotations


def content_for(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("analyzer.py"):
        return _core()
    if path.endswith("sample.webp"):
        return "fake webp fixture used with injectable vision backend\n"
    if path.endswith("test_core.py"):
        return _test_core()
    if path.endswith("test_cli.py"):
        return _test_cli()
    return "# Generated Stage 2 image contents package placeholder.\n"


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "image_contents_cli"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = []\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )


def _readme(prompt: str) -> str:
    return (
        "# image_contents_cli\n\n"
        f"Prompt: {prompt}\n\n"
        "Local CLI utility that reads an image path and prints a JSON list of visible contents. "
        "Default tests use an injectable analyzer, so they do not require live network or a vision model. "
        "For real image understanding, configure an OpenAI-compatible vision backend with "
        "`VISION_BASE_URL`, `VISION_MODEL`, and optional `VISION_API_KEY`.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run CLI: `python -m image_contents.cli input.webp output.json`.\n"
        "Run CLI to stdout: `python -m image_contents.cli input.webp`.\n"
    )


def _core() -> str:
    return r'''from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, TypedDict


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


class ImageContents(TypedDict):
    items: list[str]
    summary: str
    limitations: list[str]


VisionAnalyzer = Callable[[Path], ImageContents]


def list_image_contents(path: str, *, analyzer: VisionAnalyzer | None = None) -> ImageContents:
    image_path = _validate_image_path(path)
    result = analyzer(image_path) if analyzer is not None else _analyze_with_openai_compatible_vision(image_path)
    return _normalize_result(result)


def save_contents(result: ImageContents, output_path: str) -> str:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(target)


def run_image_contents(
    image_path: str,
    output_path: str | None = None,
    *,
    analyzer: VisionAnalyzer | None = None,
) -> ImageContents:
    result = list_image_contents(image_path, analyzer=analyzer)
    if output_path:
        save_contents(result, output_path)
    return result


def _validate_image_path(path: str) -> Path:
    image_path = Path(path)
    if not image_path.is_file():
        raise ValueError(f"image file not found: {path}")
    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported image extension: {image_path.suffix}")
    return image_path


def _analyze_with_openai_compatible_vision(image_path: Path) -> ImageContents:
    base_url = os.getenv("VISION_BASE_URL")
    model = os.getenv("VISION_MODEL")
    if not base_url or not model:
        raise RuntimeError("vision backend unavailable: set VISION_BASE_URL and VISION_MODEL or inject an analyzer")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "List the visible contents of the image. Return compact JSON with keys "
                            "items, summary and limitations. Do not invent hidden objects."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
                ],
            }
        ],
        "temperature": 0,
    }
    request = urllib.request.Request(
        _chat_url(base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"vision backend call failed: {exc}") from exc
    content = str(body["choices"][0]["message"]["content"])
    return _parse_model_content(content)


def _parse_model_content(content: str) -> ImageContents:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[-1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"items": [], "summary": cleaned, "limitations": ["model returned non-json content"]}
    return _normalize_result(parsed)


def _normalize_result(value: object) -> ImageContents:
    data = value if isinstance(value, dict) else {}
    items = data.get("items") if isinstance(data, dict) else []
    limitations = data.get("limitations") if isinstance(data, dict) else []
    summary = data.get("summary") if isinstance(data, dict) else ""
    return {
        "items": [str(item).strip() for item in items if str(item).strip()] if isinstance(items, list) else [],
        "summary": str(summary).strip(),
        "limitations": [str(item).strip() for item in limitations if str(item).strip()] if isinstance(limitations, list) else [],
    }


def _data_url(image_path: Path) -> str:
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _chat_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("VISION_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
'''


def _cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n"
        "import json\n"
        "import sys\n\n"
        "from image_contents.analyzer import run_image_contents\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser(description='List visible contents of an image file')\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output', nargs='?')\n"
        "    args = parser.parse_args(argv)\n"
        "    try:\n"
        "        result = run_image_contents(args.input, args.output)\n"
        "    except (RuntimeError, ValueError) as exc:\n"
        "        print(str(exc), file=sys.stderr)\n"
        "        return 2\n"
        "    if args.output is None:\n"
        "        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))\n"
        "    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _test_core() -> str:
    return (
        "import pytest\n\n"
        "from image_contents.analyzer import list_image_contents, run_image_contents\n\n\n"
        "def test_list_image_contents_with_injected_backend():\n"
        "    result = list_image_contents(\n"
        "        'tests/fixtures/sample.webp',\n"
        "        analyzer=lambda path: {'items': ['window', 'grass'], 'summary': 'Window near grass', 'limitations': []},\n"
        "    )\n"
        "    assert result['items'] == ['window', 'grass']\n"
        "    assert result['summary'] == 'Window near grass'\n\n\n"
        "def test_run_image_contents_writes_json_file(tmp_path):\n"
        "    output = tmp_path / 'contents.json'\n"
        "    result = run_image_contents(\n"
        "        'tests/fixtures/sample.webp',\n"
        "        str(output),\n"
        "        analyzer=lambda path: {'items': ['frame'], 'summary': 'Frame visible', 'limitations': ['fixture']},\n"
        "    )\n"
        "    assert result['items'] == ['frame']\n"
        "    assert 'Frame visible' in output.read_text(encoding='utf-8')\n\n\n"
        "def test_missing_image_is_rejected():\n"
        "    with pytest.raises(ValueError, match='image file not found'):\n"
        "        list_image_contents('tests/fixtures/missing.webp', analyzer=lambda path: {})\n\n\n"
        "def test_unsupported_image_extension_is_rejected(tmp_path):\n"
        "    path = tmp_path / 'sample.txt'\n"
        "    path.write_text('not image', encoding='utf-8')\n"
        "    with pytest.raises(ValueError, match='unsupported image extension'):\n"
        "        list_image_contents(str(path), analyzer=lambda value: {})\n\n\n"
        "def test_missing_backend_is_controlled(monkeypatch):\n"
        "    monkeypatch.delenv('VISION_BASE_URL', raising=False)\n"
        "    monkeypatch.delenv('VISION_MODEL', raising=False)\n"
        "    with pytest.raises(RuntimeError, match='vision backend unavailable'):\n"
        "        list_image_contents('tests/fixtures/sample.webp')\n"
    )


def _test_cli() -> str:
    return (
        "from image_contents import cli\n\n\n"
        "def test_cli_writes_output_file(monkeypatch, tmp_path):\n"
        "    def fake_run(image_path, output_path=None):\n"
        "        result = {'items': ['window'], 'summary': 'One window', 'limitations': []}\n"
        "        if output_path:\n"
        "            tmp_path.joinpath('out.json').write_text('{\"items\": [\"window\"]}', encoding='utf-8')\n"
        "        return result\n\n"
        "    output = tmp_path / 'out.json'\n"
        "    monkeypatch.setattr(cli, 'run_image_contents', fake_run)\n"
        "    assert cli.main(['tests/fixtures/sample.webp', str(output)]) == 0\n"
        "    assert 'window' in output.read_text(encoding='utf-8')\n\n\n"
        "def test_cli_prints_stdout(monkeypatch, capsys):\n"
        "    monkeypatch.setattr(cli, 'run_image_contents', lambda image_path, output_path=None: {'items': ['grass'], 'summary': 'Grass', 'limitations': []})\n"
        "    assert cli.main(['tests/fixtures/sample.webp']) == 0\n"
        "    assert 'grass' in capsys.readouterr().out\n\n\n"
        "def test_cli_reports_controlled_error(monkeypatch, capsys):\n"
        "    def fail(image_path, output_path=None):\n"
        "        raise RuntimeError('vision backend unavailable')\n\n"
        "    monkeypatch.setattr(cli, 'run_image_contents', fail)\n"
        "    assert cli.main(['tests/fixtures/sample.webp']) == 2\n"
        "    assert 'vision backend unavailable' in capsys.readouterr().err\n"
    )
