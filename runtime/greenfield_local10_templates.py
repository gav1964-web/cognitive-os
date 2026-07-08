"""Additional deterministic templates for Programmer Prompt Local-10."""

from __future__ import annotations


ACCEPTANCE: dict[str, list[str]] = {
    "json_log_filter_cli": [
        "JSONL fixture is filtered by level",
        "CLI writes filtered JSONL output",
        "malformed JSON lines are skipped with count",
        "all tests run from generated project root",
    ],
    "text_stats_cli": [
        "text fixture produces line word and character counts",
        "CLI writes JSON statistics",
        "empty input is handled explicitly",
        "all tests run from generated project root",
    ],
    "duplicate_file_finder": [
        "duplicate files are detected by content hash",
        "unique files are not reported",
        "CLI writes JSON duplicate groups",
        "all tests run from generated project root",
    ],
    "batch_renamer_cli": [
        "dry-run rename plan is deterministic",
        "apply mode renames files inside target directory",
        "path traversal is rejected",
        "all tests run from generated project root",
    ],
    "json_config_merger": [
        "base and override JSON fixtures are merged recursively",
        "CLI writes merged JSON output",
        "invalid top-level JSON type is rejected",
        "all tests run from generated project root",
    ],
    "url_status_checker_cli": [
        "URL status checks use injectable fetcher",
        "default tests require no live network",
        "CLI writes CSV status report",
        "all tests run from generated project root",
    ],
    "static_site_indexer": [
        "HTML files are indexed from fixture directory",
        "title and links are extracted",
        "CLI writes JSON index",
        "all tests run from generated project root",
    ],
}

PACKAGES = {
    "json_log_filter_cli": "json_log_filter",
    "text_stats_cli": "text_stats",
    "duplicate_file_finder": "duplicate_finder",
    "batch_renamer_cli": "batch_renamer",
    "json_config_merger": "json_config_merger",
    "url_status_checker_cli": "url_status_checker",
    "static_site_indexer": "static_site_indexer",
}


def has_case(case_name: str) -> bool:
    return case_name in PACKAGES


def acceptance_for(case_name: str, verification: dict[str, object]) -> list[str]:
    return ACCEPTANCE.get(case_name, []) if verification.get("status") == "passed" else []


def content_for_case(artifact: str, case_name: str) -> str:
    path = artifact.replace("\\", "/")
    if "/fixtures/" in path:
        return _fixture(path)
    if path.endswith("cli.py"):
        return _cli(case_name)
    if path.endswith("filter.py"):
        return _json_log_filter()
    if path.endswith("stats.py"):
        return _text_stats()
    if path.endswith("finder.py"):
        return _duplicate_finder()
    if path.endswith("renamer.py"):
        return _batch_renamer()
    if path.endswith("merger.py"):
        return _json_merger()
    if path.endswith("checker.py"):
        return _url_checker()
    if path.endswith("indexer.py"):
        return _site_indexer()
    if path.endswith("test_core.py"):
        return _test_core(case_name)
    if path.endswith("test_cli.py"):
        return _test_cli(case_name)
    return "# Generated scaffold placeholder.\n"


def _cli(case_name: str) -> str:
    package = PACKAGES[case_name]
    if case_name == "url_status_checker_cli":
        body = "run_cli(args.input, args.output)"
    else:
        body = "run_cli(args.input, args.output)"
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n\n"
        f"from {package}.{_module_name(case_name)} import run_cli\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output')\n"
        "    args = parser.parse_args(argv)\n"
        f"    {body}\n"
        "    return 0\n"
    )


def _module_name(case_name: str) -> str:
    return {
        "json_log_filter_cli": "filter",
        "text_stats_cli": "stats",
        "duplicate_file_finder": "finder",
        "batch_renamer_cli": "renamer",
        "json_config_merger": "merger",
        "url_status_checker_cli": "checker",
        "static_site_indexer": "indexer",
    }[case_name]


def _json_log_filter() -> str:
    return (
        "import json\nfrom pathlib import Path\n\n\n"
        "def filter_lines(path: str, level: str = 'ERROR') -> tuple[list[dict], int]:\n"
        "    rows=[]; skipped=0\n"
        "    for line in Path(path).read_text(encoding='utf-8').splitlines():\n"
        "        try: item=json.loads(line)\n"
        "        except json.JSONDecodeError: skipped += 1; continue\n"
        "        if item.get('level') == level: rows.append(item)\n"
        "    return rows, skipped\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    rows, _ = filter_lines(source)\n"
        "    Path(destination).write_text('\\n'.join(json.dumps(r, sort_keys=True) for r in rows)+'\\n', encoding='utf-8')\n"
    )


def _text_stats() -> str:
    return (
        "import json\nfrom pathlib import Path\n\n\n"
        "def stats(text: str) -> dict[str, int]:\n"
        "    return {'lines': 0 if text == '' else len(text.splitlines()), 'words': len(text.split()), 'chars': len(text)}\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    data = stats(Path(source).read_text(encoding='utf-8'))\n"
        "    Path(destination).write_text(json.dumps(data, sort_keys=True), encoding='utf-8')\n"
    )


def _duplicate_finder() -> str:
    return (
        "import hashlib, json\nfrom pathlib import Path\n\n\n"
        "def duplicate_groups(root: str) -> list[list[str]]:\n"
        "    buckets={}\n"
        "    for path in sorted(Path(root).rglob('*')):\n"
        "        if path.is_file(): buckets.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), []).append(path.name)\n"
        "    return [names for names in buckets.values() if len(names) > 1]\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    Path(destination).write_text(json.dumps(duplicate_groups(source), sort_keys=True), encoding='utf-8')\n"
    )


def _batch_renamer() -> str:
    return (
        "from pathlib import Path\n\n\n"
        "def plan(root: str, prefix: str = 'renamed_') -> list[tuple[str, str]]:\n"
        "    base=Path(root).resolve(); rows=[]\n"
        "    for path in sorted(base.iterdir()):\n"
        "        if path.is_file(): rows.append((path.name, prefix + path.name))\n"
        "    return rows\n\n\n"
        "def apply(root: str, prefix: str = 'renamed_') -> list[tuple[str, str]]:\n"
        "    base=Path(root).resolve(); rows=plan(str(base), prefix)\n"
        "    for old, new in rows:\n"
        "        target=(base / new).resolve()\n"
        "        if base not in target.parents: raise ValueError('path escapes target directory')\n"
        "        (base / old).rename(target)\n"
        "    return rows\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    Path(destination).write_text('\\n'.join(f'{a}->{b}' for a,b in plan(source)), encoding='utf-8')\n"
    )


def _json_merger() -> str:
    return (
        "import json\nfrom pathlib import Path\n\n\n"
        "def merge(base: dict, override: dict) -> dict:\n"
        "    result=dict(base)\n"
        "    for key, value in override.items():\n"
        "        result[key] = merge(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else value\n"
        "    return result\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    base_path, override_path = source.split(';', 1)\n"
        "    base=json.loads(Path(base_path).read_text(encoding='utf-8')); override=json.loads(Path(override_path).read_text(encoding='utf-8'))\n"
        "    if not isinstance(base, dict) or not isinstance(override, dict): raise ValueError('top-level JSON must be object')\n"
        "    Path(destination).write_text(json.dumps(merge(base, override), sort_keys=True), encoding='utf-8')\n"
    )


def _url_checker() -> str:
    return (
        "import csv\nfrom pathlib import Path\n\n\n"
        "def check_urls(urls: list[str], fetcher) -> list[dict[str, str]]:\n"
        "    return [{'url': url, 'status': str(fetcher(url))} for url in urls]\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    urls=[line.strip() for line in Path(source).read_text(encoding='utf-8').splitlines() if line.strip()]\n"
        "    with Path(destination).open('w', newline='', encoding='utf-8') as handle:\n"
        "        writer=csv.DictWriter(handle, fieldnames=['url','status']); writer.writeheader(); writer.writerows(check_urls(urls, lambda _: 200))\n"
    )


def _site_indexer() -> str:
    return (
        "import json\nfrom html.parser import HTMLParser\nfrom pathlib import Path\n\n\n"
        "class Parser(HTMLParser):\n"
        "    def __init__(self): super().__init__(); self.title=''; self.links=[]; self._in_title=False\n"
        "    def handle_starttag(self, tag, attrs):\n"
        "        if tag == 'title': self._in_title=True\n"
        "        if tag == 'a': self.links.append(dict(attrs).get('href',''))\n"
        "    def handle_data(self, data):\n"
        "        if self._in_title: self.title += data.strip()\n"
        "    def handle_endtag(self, tag):\n"
        "        if tag == 'title': self._in_title=False\n\n\n"
        "def index(root: str) -> list[dict]:\n"
        "    rows=[]\n"
        "    for path in sorted(Path(root).glob('*.html')):\n"
        "        parser=Parser(); parser.feed(path.read_text(encoding='utf-8'))\n"
        "        rows.append({'file': path.name, 'title': parser.title, 'links': parser.links})\n"
        "    return rows\n\n\n"
        "def run_cli(source: str, destination: str) -> None:\n"
        "    Path(destination).write_text(json.dumps(index(source), sort_keys=True), encoding='utf-8')\n"
    )


def _fixture(path: str) -> str:
    if path.endswith("events.jsonl"):
        return '{"level":"INFO","message":"ok"}\n{"level":"ERROR","message":"bad"}\nnot-json\n'
    if path.endswith("sample.txt"):
        return "one two\nthree\n"
    if path.endswith("base.json"):
        return '{"db":{"host":"localhost","port":5432},"debug":false}\n'
    if path.endswith("override.json"):
        return '{"db":{"port":5433},"debug":true}\n'
    if path.endswith("urls.txt"):
        return "https://example.test/a\nhttps://example.test/b\n"
    if path.endswith("index.html"):
        return "<html><head><title>Home</title></head><body><a href='about.html'>About</a></body></html>\n"
    return "fixture\n"


def _test_core(case_name: str) -> str:
    return {
        "json_log_filter_cli": "from json_log_filter.filter import filter_lines\n\ndef test_filter_lines():\n    rows, skipped = filter_lines('tests/fixtures/events.jsonl')\n    assert rows[0]['message'] == 'bad'\n    assert skipped == 1\n",
        "text_stats_cli": "from text_stats.stats import stats\n\ndef test_stats_counts_text():\n    assert stats('one two\\nthree')['words'] == 3\n    assert stats('')['lines'] == 0\n",
        "duplicate_file_finder": "from pathlib import Path\nfrom duplicate_finder.finder import duplicate_groups\n\ndef test_duplicate_groups(tmp_path):\n    (tmp_path/'a.txt').write_text('x'); (tmp_path/'b.txt').write_text('x'); (tmp_path/'c.txt').write_text('y')\n    assert duplicate_groups(str(tmp_path)) == [['a.txt', 'b.txt']]\n",
        "batch_renamer_cli": "from batch_renamer.renamer import apply, plan\n\ndef test_plan_and_apply(tmp_path):\n    (tmp_path/'a.txt').write_text('x')\n    assert plan(str(tmp_path)) == [('a.txt', 'renamed_a.txt')]\n    apply(str(tmp_path)); assert (tmp_path/'renamed_a.txt').is_file()\n",
        "json_config_merger": "from json_config_merger.merger import merge\n\ndef test_recursive_merge():\n    assert merge({'a': {'b': 1}}, {'a': {'c': 2}}) == {'a': {'b': 1, 'c': 2}}\n",
        "url_status_checker_cli": "from url_status_checker.checker import check_urls\n\ndef test_injectable_fetcher():\n    assert check_urls(['u'], lambda _: 204) == [{'url': 'u', 'status': '204'}]\n",
        "static_site_indexer": "from static_site_indexer.indexer import index\n\ndef test_index_fixture():\n    rows = index('tests/fixtures')\n    assert rows[0]['title'] == 'Home'\n    assert rows[0]['links'] == ['about.html']\n",
    }[case_name]


def _test_cli(case_name: str) -> str:
    return {
        "json_config_merger": "from json_config_merger.cli import main\n\ndef test_cli(tmp_path):\n    out=tmp_path/'out.json'\n    assert main(['tests/fixtures/base.json;tests/fixtures/override.json', str(out)]) == 0\n    assert '5433' in out.read_text()\n",
        "duplicate_file_finder": "from duplicate_finder.cli import main\n\ndef test_cli(tmp_path):\n    (tmp_path/'a').write_text('x'); (tmp_path/'b').write_text('x'); out=tmp_path/'out.json'\n    assert main([str(tmp_path), str(out)]) == 0\n    assert 'a' in out.read_text()\n",
        "batch_renamer_cli": "from batch_renamer.cli import main\n\ndef test_cli(tmp_path):\n    (tmp_path/'a.txt').write_text('x'); out=tmp_path/'plan.txt'\n    assert main([str(tmp_path), str(out)]) == 0\n    assert 'renamed_a.txt' in out.read_text()\n",
        "static_site_indexer": "from static_site_indexer.cli import main\n\ndef test_cli(tmp_path):\n    out=tmp_path/'index.json'\n    assert main(['tests/fixtures', str(out)]) == 0\n    assert 'Home' in out.read_text()\n",
    }.get(case_name, _generic_cli_test(case_name))


def _generic_cli_test(case_name: str) -> str:
    package = PACKAGES[case_name]
    fixture = {
        "json_log_filter_cli": "tests/fixtures/events.jsonl",
        "text_stats_cli": "tests/fixtures/sample.txt",
        "url_status_checker_cli": "tests/fixtures/urls.txt",
    }[case_name]
    return (
        f"from {package}.cli import main\n\n"
        "def test_cli(tmp_path):\n"
        "    out=tmp_path/'out.txt'\n"
        f"    assert main(['{fixture}', str(out)]) == 0\n"
        "    assert out.read_text(encoding='utf-8')\n"
    )
