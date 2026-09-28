"""OCR CLI template for Stage 2 generated packages."""

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
    if path.endswith("ocr.py"):
        return _core()
    if path.endswith("sample.png"):
        return "fake image fixture used with injectable OCR backend\n"
    if path.endswith("test_core.py"):
        return _test_core()
    if path.endswith("test_cli.py"):
        return _test_cli()
    return "# Generated Stage 2 OCR package placeholder.\n"


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "image_ocr_cli"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = []\n\n'
        "[project.optional-dependencies]\n"
        'ocr = ["pillow", "pytesseract"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )


def _readme(prompt: str) -> str:
    return (
        "# image_ocr_cli\n\n"
        f"Prompt: {prompt}\n\n"
        "Local CLI utility that reads an image path and writes recognized text to stdout or a text file. "
        "Default tests use an injectable OCR backend, so they do not require live network, Pillow, "
        "pytesseract, or a local Tesseract binary. Real OCR can be enabled by installing the optional "
        "`ocr` dependency group and the system Tesseract executable.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run CLI: `python -m image_ocr.cli input.png output.txt`.\n"
        "Run CLI to stdout: `python -m image_ocr.cli input.png`.\n"
    )


def _core() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n"
        "from typing import Callable\n\n\n"
        "SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}\n"
        "OcrEngine = Callable[[Path], str]\n\n\n"
        "def recognize_image(path: str, *, engine: OcrEngine | None = None) -> str:\n"
        "    image_path = _validate_image_path(path)\n"
        "    if engine is not None:\n"
        "        return _clean_text(engine(image_path))\n"
        "    return _clean_text(_recognize_with_optional_backend(image_path))\n\n\n"
        "def save_text(text: str, output_path: str) -> str:\n"
        "    target = Path(output_path)\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    target.write_text(text, encoding='utf-8')\n"
        "    return str(target)\n\n\n"
        "def run_ocr(image_path: str, output_path: str | None = None, *, engine: OcrEngine | None = None) -> str:\n"
        "    text = recognize_image(image_path, engine=engine)\n"
        "    if output_path:\n"
        "        save_text(text, output_path)\n"
        "    return text\n\n\n"
        "def _validate_image_path(path: str) -> Path:\n"
        "    image_path = Path(path)\n"
        "    if not image_path.is_file():\n"
        "        raise ValueError(f'image file not found: {path}')\n"
        "    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:\n"
        "        raise ValueError(f'unsupported image extension: {image_path.suffix}')\n"
        "    return image_path\n\n\n"
        "def _recognize_with_optional_backend(image_path: Path) -> str:\n"
        "    try:\n"
        "        from PIL import Image\n"
        "        import pytesseract\n"
        "    except ImportError as exc:\n"
        "        raise RuntimeError('OCR backend unavailable: install pillow, pytesseract and Tesseract, or inject an engine') from exc\n"
        "    return str(pytesseract.image_to_string(Image.open(image_path)))\n\n\n"
        "def _clean_text(value: str) -> str:\n"
        "    return value.strip()\n"
    )


def _cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n"
        "import sys\n\n"
        "from image_ocr.ocr import run_ocr\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser(description='Recognize text from an image file')\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output', nargs='?')\n"
        "    args = parser.parse_args(argv)\n"
        "    try:\n"
        "        text = run_ocr(args.input, args.output)\n"
        "    except (RuntimeError, ValueError) as exc:\n"
        "        print(str(exc), file=sys.stderr)\n"
        "        return 2\n"
        "    if args.output is None:\n"
        "        print(text)\n"
        "    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _test_core() -> str:
    return (
        "import pytest\n\n"
        "from image_ocr.ocr import recognize_image, run_ocr\n\n\n"
        "def test_recognize_image_with_injected_backend():\n"
        "    text = recognize_image('tests/fixtures/sample.png', engine=lambda path: ' Hello OCR ')\n"
        "    assert text == 'Hello OCR'\n\n\n"
        "def test_run_ocr_writes_text_file(tmp_path):\n"
        "    output = tmp_path / 'out.txt'\n"
        "    text = run_ocr('tests/fixtures/sample.png', str(output), engine=lambda path: 'Detected text')\n"
        "    assert text == 'Detected text'\n"
        "    assert output.read_text(encoding='utf-8') == 'Detected text'\n\n\n"
        "def test_missing_image_is_rejected():\n"
        "    with pytest.raises(ValueError, match='image file not found'):\n"
        "        recognize_image('tests/fixtures/missing.png', engine=lambda path: 'never')\n\n\n"
        "def test_unsupported_image_extension_is_rejected(tmp_path):\n"
        "    path = tmp_path / 'sample.txt'\n"
        "    path.write_text('not image', encoding='utf-8')\n"
        "    with pytest.raises(ValueError, match='unsupported image extension'):\n"
        "        recognize_image(str(path), engine=lambda value: 'never')\n"
    )


def _test_cli() -> str:
    return (
        "from image_ocr import cli\n\n\n"
        "def test_cli_writes_output_file(monkeypatch, tmp_path):\n"
        "    def fake_run_ocr(image_path, output_path=None):\n"
        "        if output_path:\n"
        "            tmp_path.joinpath('out.txt').write_text('CLI text', encoding='utf-8')\n"
        "        return 'CLI text'\n\n"
        "    output = tmp_path / 'out.txt'\n"
        "    monkeypatch.setattr(cli, 'run_ocr', fake_run_ocr)\n"
        "    assert cli.main(['tests/fixtures/sample.png', str(output)]) == 0\n"
        "    assert output.read_text(encoding='utf-8') == 'CLI text'\n\n\n"
        "def test_cli_prints_stdout(monkeypatch, capsys):\n"
        "    monkeypatch.setattr(cli, 'run_ocr', lambda image_path, output_path=None: 'STDOUT text')\n"
        "    assert cli.main(['tests/fixtures/sample.png']) == 0\n"
        "    assert 'STDOUT text' in capsys.readouterr().out\n\n\n"
        "def test_cli_reports_controlled_error(monkeypatch, capsys):\n"
        "    def fail(image_path, output_path=None):\n"
        "        raise ValueError('unsupported image extension')\n\n"
        "    monkeypatch.setattr(cli, 'run_ocr', fail)\n"
        "    assert cli.main(['bad.txt']) == 2\n"
        "    assert 'unsupported image extension' in capsys.readouterr().err\n"
    )
