from __future__ import annotations

from pathlib import Path

import runtime.llm_sandbox_implementation as sandbox_impl
from runtime.sandbox_prompt_field_trial import run_sandbox_prompt_field_trial


ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_prompt_field_trial_summarizes_model_normalization(monkeypatch):
    def fake_call_json_chat(messages):
        content = messages[1]["content"]
        if "строки CSV файла" in content:
            return {"operation_id": "csv_row_count", "confidence": 0.9, "reason": "row count"}
        return {"operation_id": None, "confidence": 0.0, "reason": "unsupported"}

    monkeypatch.setattr(sandbox_impl, "call_json_chat", fake_call_json_chat)

    report = run_sandbox_prompt_field_trial(
        root=ROOT,
        prompts=[
            "Напиши CLI .py, которая считает строки CSV файла.",
            "Напиши CLI, который скачает сайт и сделает PDF.",
        ],
        use_model=True,
        write=False,
    )

    assert report["artifact_type"] == "SandboxPromptFieldTrialReport"
    assert report["summary"]["planned"] == 1
    assert report["summary"]["blocked"] == 1
    assert report["summary"]["model_invoked"] == 2
    assert report["summary"]["operation_counts"]["csv_row_count"] == 1
    assert report["cases"][0]["strategy"] == "l45_registry_operation_normalization"


def test_sandbox_prompt_field_trial_deterministic_case_without_model():
    report = run_sandbox_prompt_field_trial(
        root=ROOT,
        prompts=["Напиши CLI .py, которая переводит текстовый файл в верхний регистр."],
        use_model=False,
        write=False,
    )

    assert report["summary"]["planned"] == 1
    assert report["summary"]["model_invoked"] == 0
    assert report["cases"][0]["operation_id"] == "upper"
