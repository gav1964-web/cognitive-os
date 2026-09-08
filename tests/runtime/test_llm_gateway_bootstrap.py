import json
from pathlib import Path
from unittest.mock import Mock

from runtime import llm_gateway_bootstrap as bootstrap


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "os"
    gateway = tmp_path / "5"
    (root / "config").mkdir(parents=True)
    (gateway / ".venv" / "Scripts").mkdir(parents=True)
    (gateway / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    policy = {
        "schema_version": "llm_gateway_bootstrap.v1",
        "enabled": True,
        "base_url": "http://127.0.0.1:8000",
        "health_path": "/health",
        "request_timeout_seconds": 0.1,
        "startup_timeout_seconds": 1.0,
        "poll_interval_seconds": 0.01,
        "project_dir": "../5",
        "python_executable": ".venv/Scripts/python.exe",
        "command": ["-m", "uvicorn", "app.api_server:app"],
        "log_path": "artifacts/gateway.log",
    }
    (root / "config" / "llm_gateway_bootstrap.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    return root


def test_reports_running_gateway_without_launch(tmp_path, monkeypatch):
    root = _root(tmp_path)
    launch = Mock()
    monkeypatch.setattr(bootstrap, "_health_ready", lambda *_: True)
    monkeypatch.setattr(bootstrap, "_launch_gateway", launch)

    result = bootstrap.ensure_llm_gateway(root)

    assert result["status"] == "already_running"
    launch.assert_not_called()


def test_starts_gateway_and_waits_for_health(tmp_path, monkeypatch):
    root = _root(tmp_path)
    health = Mock(side_effect=[False, True])
    process = Mock(pid=321)
    process.poll.return_value = None
    monkeypatch.setattr(bootstrap, "_health_ready", health)
    monkeypatch.setattr(bootstrap, "_launch_gateway", lambda _: process)

    result = bootstrap.ensure_llm_gateway(root)

    assert result["status"] == "started"
    assert result["pid"] == 321


def test_reports_early_gateway_exit(tmp_path, monkeypatch):
    root = _root(tmp_path)
    process = Mock(pid=654)
    process.poll.return_value = 3
    monkeypatch.setattr(bootstrap, "_health_ready", lambda *_: False)
    monkeypatch.setattr(bootstrap, "_launch_gateway", lambda _: process)

    result = bootstrap.ensure_llm_gateway(root)

    assert result["status"] == "failed"
    assert "code 3" in result["error"]


def test_loopback_url_uses_managed_gateway(tmp_path, monkeypatch):
    expected = {"status": "started"}
    monkeypatch.setattr(bootstrap, "ensure_llm_gateway", lambda root: expected)

    assert bootstrap.ensure_llm_gateway_for_url(
        tmp_path, "http://127.0.0.1:8000/v1"
    ) is expected


def test_remote_url_does_not_start_managed_gateway(tmp_path, monkeypatch):
    launch = Mock()
    monkeypatch.setattr(bootstrap, "ensure_llm_gateway", launch)

    result = bootstrap.ensure_llm_gateway_for_url(
        tmp_path, "https://provider.example/v1"
    )

    assert result["status"] == "not_required"
    assert result["checked"] is False
    launch.assert_not_called()


def test_other_loopback_port_does_not_start_managed_gateway(tmp_path, monkeypatch):
    root = _root(tmp_path)
    launch = Mock()
    monkeypatch.setattr(bootstrap, "ensure_llm_gateway", launch)

    result = bootstrap.ensure_llm_gateway_for_url(root, "http://127.0.0.1:9000/v1")

    assert result["status"] == "not_required"
    launch.assert_not_called()
