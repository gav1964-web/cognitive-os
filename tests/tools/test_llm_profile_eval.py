from __future__ import annotations

import json
from pathlib import Path

from tools.llm_profile_eval import build_llm_profile_eval


def test_llm_profile_eval_reads_configured_profiles_without_live_calls(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "llm_profiles.json").write_text(
        json.dumps(
            {
                "schema_version": "llm_profiles.v1",
                "profiles": {
                    "local_l35": {
                        "base_url": "http://127.0.0.1:8000/v1",
                        "model": "local",
                        "provider_label": "local",
                        "response_format": True,
                        "timeout_seconds": 20,
                    },
                    "external_l45_intent_resolver": {
                        "base_url": "http://127.0.0.1:8000/v1",
                        "model": "deepseek/deepseek-chat",
                        "provider_label": "external_l45_intent_resolver",
                        "response_format": False,
                        "timeout_seconds": 60,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_llm_profile_eval(root=tmp_path, smoke=False, benchmark_l45=False)

    assert report["status"] == "ok"
    assert report["summary"]["profile_count"] == 2
    assert report["profiles"][0]["smoke"]["status"] == "skipped"


def test_llm_profile_eval_reports_missing_profile(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "llm_profiles.json").write_text(
        json.dumps({"schema_version": "llm_profiles.v1", "profiles": {}}),
        encoding="utf-8",
    )

    report = build_llm_profile_eval(root=tmp_path, profile_ids=["missing"], smoke=False)

    assert report["status"] == "failed"
    assert report["profiles"][0]["errors"] == ["profile_missing"]


def test_live_smoke_bootstraps_loopback_gateway(tmp_path: Path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    (config / "llm_profiles.json").write_text(
        json.dumps({
            "schema_version": "llm_profiles.v1",
            "profiles": {
                "external_l45_intent_resolver": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "model": "test",
                    "provider_label": "test",
                }
            },
        }),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        "tools.llm_profile_eval.ensure_llm_gateway_for_url",
        lambda root, base_url: calls.append(base_url) or {"status": "started", "checked": True},
    )
    monkeypatch.setattr(
        "tools.llm_profile_eval.call_json_chat", lambda messages, config=None: {"ok": True}
    )

    report = build_llm_profile_eval(
        root=tmp_path, profile_ids=["external_l45_intent_resolver"], smoke=True
    )

    assert calls == ["http://127.0.0.1:8000/v1"]
    assert report["llm_gateway"]["status"] == "started"
    assert report["profiles"][0]["smoke"]["status"] == "ok"
