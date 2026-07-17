"""CSV sort CLI template for Stage 2 generated packages."""

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
    if path.endswith("sorter.py"):
        return _sorter()
    if path.endswith("sample.csv"):
        return "name,value\nbeta,2\nalpha,1\ngamma,3\n"
    if path.endswith("test_core.py"):
        return _test_core()
    if path.endswith("test_cli.py"):
        return _test_cli()
    return "# Generated Stage 2 CSV sort package placeholder.\n"


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "csv_sort_cli"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )


def _readme(prompt: str) -> str:
    return (
        "# csv_sort_cli\n\n"
        f"Prompt: {prompt}\n\n"
        "Local CLI utility without external dependencies. It reads a CSV file, "
        "sorts rows by a named column, and writes a sorted CSV file.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run CLI: `python -m csv_sort.cli input.csv output.csv --column name`.\n"
    )


def _sorter() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import csv\n"
        "from pathlib import Path\n\n\n"
        "def sort_csv(source: str, destination: str, *, column: str = 'name') -> list[dict[str, str]]:\n"
        "    rows = read_csv(source)\n"
        "    sorted_rows = sort_rows(rows, column=column)\n"
        "    write_csv(destination, sorted_rows, fieldnames=list(rows[0].keys()) if rows else [column])\n"
        "    return sorted_rows\n\n\n"
        "def read_csv(source: str) -> list[dict[str, str]]:\n"
        "    with Path(source).open(newline='', encoding='utf-8') as handle:\n"
        "        reader = csv.DictReader(handle)\n"
        "        if not reader.fieldnames:\n"
        "            raise ValueError('CSV header is required')\n"
        "        return [dict(row) for row in reader]\n\n\n"
        "def sort_rows(rows: list[dict[str, str]], *, column: str) -> list[dict[str, str]]:\n"
        "    if not column.strip():\n"
        "        raise ValueError('sort column is required')\n"
        "    if rows and column not in rows[0]:\n"
        "        raise ValueError(f'missing sort column: {column}')\n"
        "    return sorted(rows, key=lambda row: row.get(column, ''))\n\n\n"
        "def write_csv(destination: str, rows: list[dict[str, str]], *, fieldnames: list[str]) -> None:\n"
        "    target = Path(destination)\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with target.open('w', newline='', encoding='utf-8') as handle:\n"
        "        writer = csv.DictWriter(handle, fieldnames=fieldnames)\n"
        "        writer.writeheader()\n"
        "        writer.writerows(rows)\n"
    )


def _cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n\n"
        "from csv_sort.sorter import sort_csv\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output')\n"
        "    parser.add_argument('--column', default='name')\n"
        "    args = parser.parse_args(argv)\n"
        "    sort_csv(args.input, args.output, column=args.column)\n"
        "    return 0\n"
    )


def _test_core() -> str:
    return (
        "import pytest\n\n"
        "from csv_sort.sorter import sort_rows\n\n\n"
        "def test_sort_rows_by_name():\n"
        "    rows = [{'name': 'beta'}, {'name': 'alpha'}]\n"
        "    assert sort_rows(rows, column='name') == [{'name': 'alpha'}, {'name': 'beta'}]\n\n\n"
        "def test_missing_sort_column_is_rejected():\n"
        "    with pytest.raises(ValueError, match='missing sort column'):\n"
        "        sort_rows([{'name': 'alpha'}], column='missing')\n"
    )


def _test_cli() -> str:
    return (
        "from csv_sort.cli import main\n\n\n"
        "def test_cli_writes_sorted_csv(tmp_path):\n"
        "    out = tmp_path / 'sorted.csv'\n"
        "    assert main(['tests/fixtures/sample.csv', str(out), '--column', 'name']) == 0\n"
        "    text = out.read_text(encoding='utf-8')\n"
        "    assert text.splitlines()[1].startswith('alpha,')\n"
    )
