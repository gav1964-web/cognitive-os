from pathlib import Path
import sys
from cognitive_inspect import extract_python_structure as run


def test_generic_class_matches_host_parser_capability(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/app.py").write_text("class Cache[T]:\n    pass\n", encoding="utf-8")
    result = run({"root": "project"})
    if sys.version_info >= (3, 12):
        assert result["skipped"] == []
        assert result["files"][0]["classes"][0]["name"] == "Cache"
    else:
        assert result["skipped"] == [{"path": "app.py", "reason": "ParserVersionIncompatible", "line": 1}]


def test_python2_conversion_or_explicit_skip_on_host_without_lib2to3(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/app.py").write_text("#!/usr/bin/env python2\ndef run(value):\n    print value\n", encoding="utf-8")
    result = run({"root": "project"})
    if sys.version_info >= (3, 13):
        assert result["files"] == []
        assert result["skipped"] == [{"path": "app.py", "reason": "SyntaxError", "line": 3}]
    else:
        assert result["files"][0]["functions"][0]["name"] == "run"
        assert result["files"][0]["parser_compatibility"] == "python2_compatibility_ast"
        assert result["skipped"] == []
