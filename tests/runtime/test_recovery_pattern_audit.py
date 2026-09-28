from pathlib import Path

from runtime.recovery_pattern_audit import run_recovery_pattern_audit


def test_audit_separates_resolved_and_unresolved_io_parsing(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "unresolved.py").write_text(
        "from pathlib import Path\n\n"
        "def load():\n"
        "    return Path('x').read_text().splitlines()\n",
        encoding="utf-8",
    )
    (corpus / "resolved.py").write_text(
        "from pathlib import Path\n\n"
        "def parse(text):\n"
        "    return text.splitlines()\n\n"
        "def load():\n"
        "    return parse(Path('x').read_text())\n",
        encoding="utf-8",
    )

    report = run_recovery_pattern_audit(tmp_path, corpus_roots=[corpus])

    cluster = next(row for row in report["clusters"] if row["cluster"] == "parse_text_inside_io_boundary")
    assert cluster["count"] == 2
    assert cluster["unresolved_count"] == 1
    assert cluster["resolved_count"] == 1
    assert cluster["independent_project_count"] == 1
    assert cluster["recipe_status"] == "implemented"
    assert report["scope"]["parse_failures"] == 0
    assert report["recommendation"]["next_cluster"] is None


def test_audit_skips_implemented_serialization_recipe(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    for project_name in ("one", "two"):
        project = corpus / project_name
        project.mkdir(parents=True)
        expression = "value" if project_name == "one" else "{'payload': value}"
        (project / "writer.py").write_text(
            "import json\nfrom pathlib import Path\n\n"
            "def write(path, value):\n"
            f"    Path(path).write_text(json.dumps({expression}))\n",
            encoding="utf-8",
        )

    report = run_recovery_pattern_audit(tmp_path, corpus_roots=[corpus])

    cluster = next(row for row in report["clusters"] if row["cluster"] == "serialize_json_inside_filesystem_boundary")
    assert cluster["recipe_priority"] == "high"
    assert cluster["recipe_status"] == "implemented"
    assert report["recommendation"]["next_cluster"] is None


def test_audit_does_not_conflate_text_parsing_with_lazy_csv_stream(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "loaders.py").write_text(
        "import csv\nfrom pathlib import Path\n\n"
        "def load_text():\n"
        "    return Path('x').read_text().splitlines()\n\n"
        "def load_csv(path):\n"
        "    with open(path) as handle:\n"
        "        return list(csv.DictReader(handle))\n",
        encoding="utf-8",
    )

    report = run_recovery_pattern_audit(tmp_path, corpus_roots=[corpus])
    clusters = {row["cluster"]: row for row in report["clusters"]}

    assert clusters["parse_text_inside_io_boundary"]["count"] == 1
    assert clusters["parse_structured_stream_inside_io_boundary"]["count"] == 1


def test_repeated_stream_boundary_routes_to_researcher_not_recipe(tmp_path: Path) -> None:
    corpus = tmp_path / "plugins"
    sources = {
        "one": (
            "import csv\n\n"
            "def load(path):\n"
            "    with open(path) as handle:\n"
            "        return list(csv.DictReader(handle))\n"
        ),
        "two": (
            "import csv\nfrom pathlib import Path\n\n"
            "def load(path):\n"
            "    with Path(path).open() as handle:\n"
            "        return [row for row in csv.reader(handle)]\n"
        ),
    }
    for project_name, source in sources.items():
        project = corpus / project_name
        project.mkdir(parents=True)
        (project / "loader.py").write_text(source, encoding="utf-8")

    report = run_recovery_pattern_audit(tmp_path, corpus_roots=[corpus])
    cluster = next(
        row for row in report["clusters"]
        if row["cluster"] == "parse_structured_stream_inside_io_boundary"
    )

    assert cluster["recipe_priority"] == "high"
    assert cluster["automatic_recipe_eligible"] is False
    assert cluster["project_type_counts"] == {"plugin": 2}
    assert report["recommendation"]["next_role"] == "researcher"
    assert report["recommendation"]["automatic_recipe_eligible"] is False
    assert report["research_backlog"][0]["handoff_role"] == "architect"
    assert report["execution_lanes"]["research"]["cluster"] == "parse_structured_stream_inside_io_boundary"


def test_audit_resolves_imported_urlopen_as_network_effect(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "client.py").write_text(
        "from urllib.request import urlopen\n\n"
        "def load(url):\n"
        "    with urlopen(url) as response:\n"
        "        return {'body': response.read()}\n",
        encoding="utf-8",
    )

    report = run_recovery_pattern_audit(tmp_path, corpus_roots=[corpus])
    finding = next(
        row for row in report["findings"]
        if row["cluster"] == "response_mapping_inside_network_boundary"
    )
    assert finding["effects"] == ["network"]
