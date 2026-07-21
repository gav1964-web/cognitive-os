"""Generic file converter CLI template driven by ConversionRecipe."""

from __future__ import annotations

from .adapter_implementation_plan import adapter_implementation_plan_json
from .generic_file_conversion_recipe import build_conversion_recipe, recipe_json
from .library_binding_recipe import library_binding_json


def content_for(path: str, prompt: str) -> str:
    recipe = build_conversion_recipe(prompt)
    if recipe is None:
        raise ValueError("generic file converter template requires a source and target extension")
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt, recipe.source_ext, recipe.target_ext)
    if path == "conversion_recipe.json":
        return recipe_json(prompt)
    if path == "library_binding_recipe.json":
        return library_binding_json(prompt)
    if path == "adapter_implementation_plan.json":
        return adapter_implementation_plan_json(prompt)
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("test_core.py"):
        return _test_core(recipe.source_ext, recipe.target_ext)
    if path.endswith("test_cli.py"):
        return _test_cli(recipe.source_ext, recipe.target_ext)
    if path.endswith("test_adapter_backend.py"):
        return _test_adapter_backend(recipe.source_ext, recipe.target_ext)
    if path.endswith("adapters.py"):
        return _adapters()
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("converter.py"):
        return _converter()
    if path.endswith(f"sample{recipe.source_ext}") and recipe.source_ext == ".py":
        return "print('fixture payload for generic conversion recipe')\n"
    if path.endswith(f"sample{recipe.source_ext}"):
        return "fixture payload for generic conversion recipe\n"
    return "# Generated generic file converter placeholder.\n"


def expected_artifacts(prompt: str) -> list[str]:
    recipe = build_conversion_recipe(prompt)
    if recipe is None:
        raise ValueError("generic file converter requires a two-format prompt")
    return [
        "pyproject.toml",
        "README.md",
        "conversion_recipe.json",
        "library_binding_recipe.json",
        "adapter_implementation_plan.json",
        "src/file_converter_cli/__init__.py",
        "src/file_converter_cli/adapters.py",
        "src/file_converter_cli/cli.py",
        "src/file_converter_cli/converter.py",
        f"tests/fixtures/sample{recipe.source_ext}",
        "tests/test_adapter_backend.py",
        "tests/test_core.py",
        "tests/test_cli.py",
    ]


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "file_converter_cli"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = []\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
        'pythonpath = ["src"]\n'
    )


def _readme(prompt: str, source_ext: str, target_ext: str) -> str:
    return (
        "# file_converter_cli\n\n"
        f"Prompt: {prompt}\n\n"
        f"Generic file conversion CLI for `{source_ext}` -> `{target_ext}` tasks. "
        "The package is generated from `conversion_recipe.json`, `library_binding_recipe.json` and "
        "`adapter_implementation_plan.json`: "
        "the core code validates input/output contracts, uses an adapter boundary for real libraries, "
        "and keeps default tests dependency-free. "
        "The bundled adapter creates a deterministic fixture artifact; production fidelity should be added "
        "by supplying a backend behind the same adapter contract. Candidate libraries are advisory only: "
        "they do not grant permission to install dependencies or bypass tests.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run CLI: `python -m file_converter_cli.cli input"
        f"{source_ext} output{target_ext}`.\n"
    )


def _converter() -> str:
    return r'''from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Callable

from file_converter_cli.adapters import stdlib_adapter_for


Adapter = Callable[[bytes, str, str], bytes]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def convert_file(
    input_path: str,
    output_path: str | None = None,
    *,
    source_ext: str,
    target_ext: str,
    adapter: Adapter | None = None,
) -> dict[str, object]:
    source = Path(input_path)
    if not source.is_file():
        raise FileNotFoundError(f"input file not found: {source}")
    if source.suffix.lower() != source_ext:
        raise ValueError(f"unsupported input extension: {source.suffix or '<none>'}")
    output = Path(output_path) if output_path else source.with_suffix(target_ext)
    if output.suffix.lower() != target_ext:
        raise ValueError(f"unsupported output extension: {output.suffix or '<none>'}")
    payload = source.read_bytes()
    renderer = adapter or stdlib_adapter_for(source_ext, target_ext) or fixture_adapter
    result = renderer(payload, source_ext, target_ext)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    return {
        "input_path": source.as_posix(),
        "output_path": output.as_posix(),
        "source_ext": source_ext,
        "target_ext": target_ext,
        "bytes_written": len(result),
    }


def fixture_adapter(payload: bytes, source_ext: str, target_ext: str) -> bytes:
    if not payload:
        raise ValueError("input file is empty")
    if target_ext == ".png":
        return _tiny_png()
    if target_ext in {".txt", ".md", ".rtf", ".csv", ".html", ".json", ".xml"}:
        return (
            f"Converted fixture from {source_ext} to {target_ext}\n"
            f"source_bytes={len(payload)}\n"
        ).encode("utf-8")
    return b"Converted fixture from " + source_ext.encode("ascii") + b" to " + target_ext.encode("ascii") + b"\n"


def _tiny_png() -> bytes:
    width = 2
    height = 2
    rows = [
        b"\x00\x2d\x7f\xc4\x2d\x7f\xc4",
        b"\x00\x2d\x7f\xc4\x2d\x7f\xc4",
    ]
    raw = b"".join(rows)
    return PNG_SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
'''


def _adapters() -> str:
    return r'''from __future__ import annotations

import base64
import html
import re
from typing import Callable


Adapter = Callable[[bytes, str, str], bytes]


def stdlib_adapter_for(source_ext: str, target_ext: str) -> Adapter | None:
    if (source_ext, target_ext) == (".txt", ".html"):
        return text_to_html
    if (source_ext, target_ext) == (".md", ".rtf"):
        return markdown_subset_to_rtf
    if source_ext in {".jpg", ".jpeg", ".png"} and target_ext == ".doc":
        return image_to_doc_html
    return None


def text_to_html(payload: bytes, source_ext: str, target_ext: str) -> bytes:
    text = payload.decode("utf-8")
    escaped = html.escape(text)
    body = "<br>\n".join(escaped.splitlines())
    return (
        "<!doctype html>\n"
        "<html><head><meta charset=\"utf-8\"><title>Converted text</title></head>"
        f"<body><pre>{body}</pre></body></html>\n"
    ).encode("utf-8")


def markdown_subset_to_rtf(payload: bytes, source_ext: str, target_ext: str) -> bytes:
    text = payload.decode("utf-8")
    lines = [_markdown_line_to_plain(line) for line in text.splitlines()]
    body = "\\par\n".join(_rtf_escape(line) for line in lines)
    return ("{\\rtf1\\ansi\n" + body + "\n}\n").encode("utf-8")


def image_to_doc_html(payload: bytes, source_ext: str, target_ext: str) -> bytes:
    mime = "image/png" if source_ext == ".png" else "image/jpeg"
    encoded = base64.b64encode(payload).decode("ascii")
    return (
        "<!doctype html>\n"
        "<html><head><meta charset=\"utf-8\"><title>Converted image</title></head>"
        "<body><p>Converted image</p>"
        f"<img alt=\"converted image\" src=\"data:{mime};base64,{encoded}\">"
        "</body></html>\n"
    ).encode("utf-8")


def _markdown_line_to_plain(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    if stripped.startswith(("- ", "* ")):
        return "* " + stripped[2:].strip()
    return re.sub(r"[*_`]+", "", line)


def _rtf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
'''


def _cli() -> str:
    return r'''from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from file_converter_cli.converter import convert_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a recipe-driven file conversion")
    parser.add_argument('input')
    parser.add_argument('output', nargs='?')
    parser.add_argument('--recipe', default='conversion_recipe.json')
    args = parser.parse_args(argv)
    try:
        recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
        result = convert_file(
            args.input,
            args.output,
            source_ext=str(recipe["source_ext"]),
            target_ext=str(recipe["target_ext"]),
        )
    except (KeyError, RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(result["output_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _test_core(source_ext: str, target_ext: str) -> str:
    return (
        "from pathlib import Path\n\n"
        "import pytest\n\n"
        "from file_converter_cli.converter import PNG_SIGNATURE, convert_file\n\n\n"
        "def test_convert_file_writes_target(tmp_path):\n"
        f"    source = tmp_path / 'sample{source_ext}'\n"
        f"    output = tmp_path / 'sample{target_ext}'\n"
        "    source.write_bytes(b'fixture')\n"
        f"    result = convert_file(str(source), str(output), source_ext='{source_ext}', target_ext='{target_ext}')\n"
        "    assert Path(result['output_path']).is_file()\n"
        + ("    assert output.read_bytes().startswith(PNG_SIGNATURE)\n" if target_ext == ".png" else "    assert output.read_bytes()\n")
        + "\n\n"
        "def test_missing_input_is_controlled(tmp_path):\n"
        "    with pytest.raises(FileNotFoundError):\n"
        f"        convert_file(str(tmp_path / 'missing{source_ext}'), source_ext='{source_ext}', target_ext='{target_ext}')\n\n\n"
        "def test_unsupported_input_extension_is_rejected(tmp_path):\n"
        "    source = tmp_path / 'sample.bad'\n"
        "    source.write_bytes(b'fixture')\n"
        "    with pytest.raises(ValueError, match='unsupported input extension'):\n"
        f"        convert_file(str(source), source_ext='{source_ext}', target_ext='{target_ext}')\n\n\n"
        "def test_unsupported_output_extension_is_rejected(tmp_path):\n"
        f"    source = tmp_path / 'sample{source_ext}'\n"
        "    source.write_bytes(b'fixture')\n"
        "    with pytest.raises(ValueError, match='unsupported output extension'):\n"
        f"        convert_file(str(source), str(tmp_path / 'bad.out'), source_ext='{source_ext}', target_ext='{target_ext}')\n"
    )


def _test_adapter_backend(source_ext: str, target_ext: str) -> str:
    if (source_ext, target_ext) == (".txt", ".html"):
        return (
            "from file_converter_cli.converter import convert_file\n\n\n"
            "def test_stdlib_text_to_html_backend_writes_semantic_html(tmp_path):\n"
            "    source = tmp_path / 'sample.txt'\n"
            "    output = tmp_path / 'sample.html'\n"
            "    source.write_text('Hello <world>\\nsecond line', encoding='utf-8')\n"
            "    convert_file(str(source), str(output), source_ext='.txt', target_ext='.html')\n"
            "    html = output.read_text(encoding='utf-8')\n"
            "    assert '<!doctype html>' in html\n"
            "    assert 'Hello &lt;world&gt;' in html\n"
            "    assert 'second line' in html\n"
        )
    if (source_ext, target_ext) == (".md", ".rtf"):
        return (
            "from file_converter_cli.converter import convert_file\n\n\n"
            "def test_stdlib_markdown_subset_to_rtf_backend_writes_rtf(tmp_path):\n"
            "    source = tmp_path / 'sample.md'\n"
            "    output = tmp_path / 'sample.rtf'\n"
            "    source.write_text('# Title\\n\\n- item', encoding='utf-8')\n"
            "    convert_file(str(source), str(output), source_ext='.md', target_ext='.rtf')\n"
            "    rtf = output.read_text(encoding='utf-8')\n"
            "    assert rtf.startswith('{\\\\rtf1')\n"
            "    assert 'Title' in rtf\n"
            "    assert '* item' in rtf\n"
        )
    if source_ext in {".jpg", ".jpeg", ".png"} and target_ext == ".doc":
        return (
            "from file_converter_cli.converter import convert_file\n\n\n"
            "def test_stdlib_image_to_doc_backend_embeds_image(tmp_path):\n"
            f"    source = tmp_path / 'sample{source_ext}'\n"
            "    output = tmp_path / 'sample.doc'\n"
            "    source.write_bytes(b'fake-image-bytes')\n"
            f"    convert_file(str(source), str(output), source_ext='{source_ext}', target_ext='.doc')\n"
            "    doc = output.read_text(encoding='utf-8')\n"
            "    assert '<!doctype html>' in doc\n"
            "    assert 'data:image/' in doc\n"
            "    assert 'ZmFrZS1pbWFnZS1ieXRlcw==' in doc\n"
        )
    return (
        "from file_converter_cli.adapters import stdlib_adapter_for\n\n\n"
        f"def test_no_stdlib_backend_for_{source_ext.lstrip('.')}_to_{target_ext.lstrip('.')}():\n"
        f"    assert stdlib_adapter_for('{source_ext}', '{target_ext}') is None\n"
    )


def _test_cli(source_ext: str, target_ext: str) -> str:
    return (
        "import json\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "from file_converter_cli.cli import main\n"
        "from file_converter_cli.converter import PNG_SIGNATURE\n\n\n"
        "def _write_recipe(path):\n"
        f"    path.write_text(json.dumps({{'source_ext': '{source_ext}', 'target_ext': '{target_ext}'}}), encoding='utf-8')\n\n\n"
        "def test_cli_main_writes_output(tmp_path):\n"
        f"    source = tmp_path / 'sample{source_ext}'\n"
        f"    output = tmp_path / 'sample{target_ext}'\n"
        "    recipe = tmp_path / 'conversion_recipe.json'\n"
        "    source.write_bytes(b'fixture')\n"
        "    _write_recipe(recipe)\n"
        "    assert main([str(source), str(output), '--recipe', str(recipe)]) == 0\n"
        "    assert output.exists()\n\n\n"
        "def test_module_cli_writes_output(tmp_path):\n"
        f"    source = tmp_path / 'sample{source_ext}'\n"
        f"    output = tmp_path / 'sample{target_ext}'\n"
        "    recipe = tmp_path / 'conversion_recipe.json'\n"
        "    source.write_bytes(b'fixture')\n"
        "    _write_recipe(recipe)\n"
        "    env = dict(os.environ)\n"
        "    env['PYTHONPATH'] = str(Path.cwd() / 'src')\n"
        "    result = subprocess.run(\n"
        "        [sys.executable, '-m', 'file_converter_cli.cli', str(source), str(output), '--recipe', str(recipe)],\n"
        "        capture_output=True,\n"
        "        text=True,\n"
        "        check=False,\n"
        "        env=env,\n"
        "    )\n"
        "    assert result.returncode == 0\n"
        + ("    assert output.read_bytes().startswith(PNG_SIGNATURE)\n" if target_ext == ".png" else "    assert output.read_bytes()\n")
        + "\n\n"
        "def test_cli_reports_controlled_error(tmp_path, capsys):\n"
        "    recipe = tmp_path / 'conversion_recipe.json'\n"
        "    _write_recipe(recipe)\n"
        f"    assert main([str(tmp_path / 'missing{source_ext}'), '--recipe', str(recipe)]) == 2\n"
        "    assert 'input file not found' in capsys.readouterr().err\n"
    )
