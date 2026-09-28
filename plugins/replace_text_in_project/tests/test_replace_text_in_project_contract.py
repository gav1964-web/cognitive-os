from pathlib import Path

from plugins.replace_text_in_project.src.main import run


def test_replace_text_in_project_changes_scoped_candidate_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    (root / "server.py").write_text("port=8000\nother=8000\n", encoding="utf-8")
    (root / "notes.md").write_text("port 8000\n", encoding="utf-8")

    result = run(
        {
            "root": str(root),
            "old_value": "8000",
            "new_value": "9000",
            "paths": ["server.py"],
            "max_replacements": 10,
        }
    )

    assert result["replacement_count"] == 2
    assert result["changed_files"] == [{"path": "server.py", "replacements": 2}]
    assert (root / "server.py").read_text(encoding="utf-8") == "port=9000\nother=9000\n"
    assert (root / "notes.md").read_text(encoding="utf-8") == "port 8000\n"
