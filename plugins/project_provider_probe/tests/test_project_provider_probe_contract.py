from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from plugins.project_provider_probe.src.main import run


def test_project_provider_probe_runs_project_ping_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "project"
    (project / "tools").mkdir(parents=True)
    (project / "tools" / "ping_llms.py").write_text("print('probe')\n", encoding="utf-8")
    (project / "reports" / "health_checks").mkdir(parents=True)
    (project / "reports" / "health_checks" / "cognitive_os_provider_probe.md").write_text("ok", encoding="utf-8")
    completed = Mock(returncode=0, stdout="OK", stderr="")

    with patch("plugins.project_provider_probe.src.main.subprocess.run", return_value=completed) as call:
        result = run({"root": str(project), "base_url": "http://127.0.0.1:9000", "max_providers": 1})

    assert result["status"] == "ok"
    assert result["exit_code"] == 0
    assert result["report_path"].endswith("reports/health_checks/cognitive_os_provider_probe.md")
    assert "--start-server" in call.call_args.args[0]
