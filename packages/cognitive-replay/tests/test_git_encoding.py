import subprocess
import locale

import pytest

from cognitive_replay.git import _git, HistoricalDefectMiningError


def test_git_history_and_patch_ignore_controller_locale(tmp_path, monkeypatch):
    _git(tmp_path, ["init", "-q"])
    _git(tmp_path, ["config", "user.name", "Test"])
    _git(tmp_path, ["config", "user.email", "test@example.test"])
    path = tmp_path / "sample.py"
    path.write_text("label = 'начало'\n", encoding="utf-8")
    _git(tmp_path, ["add", "."])
    _git(tmp_path, ["commit", "-qm", "fix кодировка 🚀"])
    path.write_text("label = 'исправлено 🚀'\n", encoding="utf-8")
    # Force the locale that caused the real Windows mining reader thread to fail.
    monkeypatch.setattr(locale, "getpreferredencoding", lambda *args: "cp1251")
    if hasattr(subprocess, "_text_encoding"):
        monkeypatch.setattr(subprocess, "_text_encoding", lambda: "cp1251")
    assert "fix кодировка 🚀" in _git(tmp_path, ["log", "-1", "--format=%s"])
    assert "+label = 'исправлено 🚀'" in _git(tmp_path, ["diff"])


def test_non_utf8_patch_fails_without_replacing_evidence_bytes(tmp_path):
    _git(tmp_path, ["init", "-q"])
    _git(tmp_path, ["config", "user.name", "Test"])
    _git(tmp_path, ["config", "user.email", "test@example.test"])
    path = tmp_path / "sample.py"
    path.write_bytes(b"label = 'old'\n")
    _git(tmp_path, ["add", "."])
    _git(tmp_path, ["commit", "-qm", "baseline"])
    path.write_bytes(b"label = '\xff'\n")
    with pytest.raises(HistoricalDefectMiningError, match="not UTF-8"):
        _git(tmp_path, ["diff"])
