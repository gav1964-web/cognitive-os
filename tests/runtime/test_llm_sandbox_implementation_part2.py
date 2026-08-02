from __future__ import annotations
from pathlib import Path
import pytest
import runtime.llm_sandbox_implementation as sandbox_impl
from runtime.llm_sandbox_implementation import run_llm_sandbox_implementation
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.verified_system_package import build_verified_system_package
ROOT = Path(__file__).resolve().parents[2]

def test_llm_sandbox_implementation_uses_l45_operation_recipe_fallback(monkeypatch):
    calls = {"count": 0}

    def fake_call_json_chat(messages):
        calls["count"] += 1
        if calls["count"] == 1:
            assert "available_operations" in messages[1]["content"]
            return {"operation_id": None, "confidence": 0.0, "reason": "no listed operation fits"}
        assert "OperationRecipe" in messages[0]["content"]
        return {
            "interface_contract": "stdin_to_stdout_text_transform",
            "transform": "uppercase",
            "expression": None,
            "input_shape": "utf8_text",
            "output_shape": "utf8_text",
            "evidence": ["semantic:stdin uppercase"],
        }

    monkeypatch.setattr(sandbox_impl, "call_json_chat", fake_call_json_chat)

    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: стандартный поток семантически нормализуй и покажи результат",
        write=True,
        use_model=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["route_resolution"]["strategy"] == "l45_operation_recipe_parser"
    assert report["implementation_plan"]["operation_recipe"]["interface_contract"] == "stdin_to_stdout_text_transform"
    assert report["implementation_plan"]["operation"]["profile"] == "stdin_text_expression"
    assert report["verification"]["tests"]["status"] == "passed"
    assert calls["count"] == 2


def test_llm_sandbox_implementation_uses_l45_operation_recipe_file_output_fallback(monkeypatch):
    calls = {"count": 0}

    def fake_call_json_chat(messages):
        calls["count"] += 1
        if calls["count"] == 1:
            return {"operation_id": None, "confidence": 0.0, "reason": "no listed operation fits"}
        return {
            "interface_contract": "stdin_to_file_text_transform",
            "transform": "lowercase",
            "expression": None,
            "input_shape": "utf8_text",
            "output_shape": "output_path",
            "evidence": ["semantic:stdin lowercase file"],
        }

    monkeypatch.setattr(sandbox_impl, "call_json_chat", fake_call_json_chat)

    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: поток сделай тихим и сохрани",
        write=True,
        use_model=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["route_resolution"]["strategy"] == "l45_operation_recipe_parser"
    assert report["implementation_plan"]["operation"]["profile"] == "stdin_file_text_expression"
    assert report["implementation_plan"]["interface_contract"]["id"] == "stdin_to_file_text_transform"
    assert report["verification"]["tests"]["status"] == "passed"
    assert calls["count"] == 2


def test_llm_sandbox_implementation_rejects_invalid_l45_operation_recipe(monkeypatch):
    monkeypatch.setattr(
        sandbox_impl,
        "call_json_chat",
        lambda messages: {
            "interface_contract": "stdin_to_stdout_text_transform",
            "transform": "run_shell",
            "expression": None,
            "input_shape": "utf8_text",
            "output_shape": "utf8_text",
            "evidence": ["bad"],
        },
    )

    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: стандартный поток обработай как-нибудь",
        write=False,
        use_model=True,
    )

    assert report["status"] == "blocked"
    assert report["route_resolution"]["status"] == "blocked_invalid_operation_recipe"
    assert "unsupported_transform" in report["route_resolution"]["errors"]


def test_llm_sandbox_implementation_loads_composition_from_registry(tmp_path: Path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "sandbox_programmer_operations.json").write_text(
        """{
  "schema_version": "sandbox_programmer_operations.v1",
  "operations": [
    {
      "id": "trim",
      "package": "trim_text_cli",
      "description": "trim",
      "match": ["trim"],
      "profile": "text_expression",
      "expression": "text.strip() + '\\\\n'",
      "sample": "  One  ",
      "expected": "One\\n"
    },
    {
      "id": "upper",
      "package": "upper_text_cli",
      "description": "upper",
      "match": ["upper"],
      "profile": "text_expression",
      "expression": "text.upper()",
      "sample": "one",
      "expected": "ONE"
    }
  ]
}
""",
        encoding="utf-8",
    )
    (registry / "sandbox_programmer_compositions.json").write_text(
        """{
  "schema_version": "sandbox_programmer_compositions.v1",
  "compositions": [
    {
      "id": "custom_trim_then_upper",
      "package": "custom_trim_then_upper_cli",
      "description": "trim then upper",
      "match_any_groups": [["spaces"], ["uppercase"]],
      "sample": "  One two  \\n",
      "expected": "ONE TWO\\n",
      "steps": [{"operation": "trim"}, {"operation": "upper"}]
    }
  ]
}
""",
        encoding="utf-8",
    )

    report = run_llm_sandbox_implementation(
        root=tmp_path,
        prompt="Write CLI that removes spaces and then uppercase text.",
        write=False,
    )

    assert report["status"] == "planned"
    assert report["route_resolution"]["strategy"] == "deterministic_operation_composition"
    assert report["implementation_plan"]["operation"]["operation"] == "custom_trim_then_upper"


def test_llm_sandbox_implementation_rejects_composition_with_unknown_step(tmp_path: Path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "sandbox_programmer_operations.json").write_text(
        """{
  "schema_version": "sandbox_programmer_operations.v1",
  "operations": [
    {
      "id": "trim",
      "package": "trim_text_cli",
      "description": "trim",
      "match": ["trim"],
      "profile": "text_expression",
      "expression": "text.strip() + '\\\\n'",
      "sample": "  One  ",
      "expected": "One\\n"
    }
  ]
}
""",
        encoding="utf-8",
    )
    (registry / "sandbox_programmer_compositions.json").write_text(
        """{
  "schema_version": "sandbox_programmer_compositions.v1",
  "compositions": [
    {
      "id": "bad_composition",
      "package": "bad_composition_cli",
      "description": "bad",
      "match_any_groups": [["bad"], ["composition"]],
      "sample": "x",
      "expected": "x",
      "steps": [{"operation": "trim"}, {"operation": "missing"}]
    }
  ]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown operation"):
        run_llm_sandbox_implementation(root=tmp_path, prompt="CLI bad composition", write=False)


@pytest.mark.parametrize(
    ("prompt", "profile"),
    [
        ("CLI посчитать строки csv", "csv_row_count"),
        ("Напиши CLI .py, которая извлекает html таблицу в csv.", "html_table_to_csv"),
    ],
)
def test_llm_sandbox_implementation_builds_file_table_profiles(prompt: str, profile: str):
    report = run_llm_sandbox_implementation(root=ROOT, prompt=prompt, write=True)

    assert report["status"] == "sandbox_verified"
    assert report["implementation_plan"]["operation"]["profile"] == profile
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_rejects_unsafe_registry_expression(tmp_path: Path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "sandbox_programmer_operations.json").write_text(
        """{
  "schema_version": "sandbox_programmer_operations.v1",
  "operations": [
    {
      "id": "bad",
      "package": "bad_cli",
      "description": "bad",
      "match": ["опасн"],
      "profile": "text_expression",
      "expression": "__import__('os').system('echo bad')",
      "sample": "x",
      "expected": "x"
    }
  ]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        run_llm_sandbox_implementation(root=tmp_path, prompt="Напиши CLI .py опасн", write=False)


def test_llm_sandbox_implementation_rejects_expression_on_profile(tmp_path: Path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "sandbox_programmer_operations.json").write_text(
        """{
  "schema_version": "sandbox_programmer_operations.v1",
  "operations": [
    {
      "id": "bad_profile",
      "package": "bad_profile_cli",
      "description": "bad",
      "match": ["csv bad"],
      "profile": "csv_row_count",
      "expression": "text.upper()",
      "sample": "a\\n",
      "expected": "1\\n"
    }
  ]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        run_llm_sandbox_implementation(root=tmp_path, prompt="Напиши CLI .py csv bad", write=False)


def test_prompt_adequacy_accepts_simple_cli_transform_prompt():
    gate = evaluate_prompt_adequacy("Напиши CLI .py, которая считает количество слов.").to_dict()

    assert gate["status"] == "ready"
    assert gate["checks"]["inputs_defined"] is True
    assert gate["checks"]["outputs_defined"] is True
    assert gate["checks"]["success_criteria_verifiable"] is True
