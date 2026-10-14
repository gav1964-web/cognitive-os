"""Image table to Excel CLI template for Stage 2 generated packages."""

from __future__ import annotations
from pathlib import Path


def content_for(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path == "image_table_to_excel.py":
        return _root_cli()
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("test_core.py"):
        return _test_core()
    if path.endswith("test_cli.py"):
        return _test_cli()
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("table_extractor.py"):
        return _core()
    if path.endswith("sample.webp"):
        return "fake webp fixture used with injectable OCR backend\n"
    return "# Generated Stage 2 image table to Excel package placeholder.\n"



_ASSET_DIR = Path(__file__).with_name("template_assets") / "image_table_excel"

def _asset(name: str) -> str:
    return (_ASSET_DIR / name).read_text(encoding="utf-8")

def _pyproject() -> str:
    return _asset("pyproject.txt")



def _readme(prompt: str) -> str:
    return (
        "# image_table_excel_cli\n\n"
        f"Prompt: {prompt}\n\n"
        "Local CLI utility that reads an image containing a simple price table, extracts rows "
        "through an injectable OCR/text backend, and writes an `.xlsx` workbook with the same "
        "base name as the image by default. Default tests do not require network, OCR engines, "
        "or spreadsheet libraries.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run CLI: `python image_table_to_excel.py input.webp`.\n"
        "Run CLI with explicit output: `python image_table_to_excel.py input.webp output.xlsx`.\n\n"
        "Use `--format xlsx`, `--format csv`, `--format xls`, `--format html`, `--format doc`, "
        "or `--format rtf` when output path is omitted. When output path is provided, `.xlsx`, "
        "`.csv`, `.xls`, `.html`, `.doc`, and `.rtf` suffixes select the writer. The `.xls` and "
        "`.doc` writers produce application-compatible HTML tables; the `.rtf` writer produces a "
        "plain Rich Text Format table without external dependencies.\n\n"
        "For deterministic OCR text, use `--ocr-text-file recognized.txt` or set "
        "`IMAGE_TABLE_OCR_TEXT`. For live image understanding, configure an OpenAI-compatible "
        "vision/OCR backend with `IMAGE_TABLE_VISION_BASE_URL`, `IMAGE_TABLE_VISION_MODEL`, "
        "and optional `IMAGE_TABLE_VISION_API_KEY`. The generated workbook is written with a "
        "minimal stdlib OOXML writer.\n"
    )


def _core() -> str:
    return _asset("core.txt")



def _cli() -> str:
    return _asset("cli.txt")



def _root_cli() -> str:
    return _asset("root_cli.txt")



def _test_core() -> str:
    return _asset("test_core.txt")



def _test_cli() -> str:
    return _asset("test_cli.txt")
