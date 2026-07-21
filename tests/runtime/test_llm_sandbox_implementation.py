from __future__ import annotations

from pathlib import Path
import pytest

import runtime.llm_sandbox_implementation as sandbox_impl
from runtime.llm_sandbox_implementation import run_llm_sandbox_implementation
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.verified_system_package import build_verified_system_package


ROOT = Path(__file__).resolve().parents[2]


def test_llm_sandbox_implementation_verifies_allowlisted_cli(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=tmp_path,
        prompt="Напиши CLI .py, которая переводит текстовый файл в верхний регистр.",
        write=True,
    )

    assert report["artifact_type"] == "LLMSandboxImplementationResult"
    assert report["status"] == "sandbox_verified"
    assert report["verification"]["status"] == "passed"
    assert report["promotion_allowed"] is False
    assert report["llm_policy"]["llm_output_executed_directly"] is False
    assert (Path(report["project_dir"]) / "src" / "uppercase_text_cli" / "cli.py").is_file()


def test_llm_sandbox_implementation_blocks_unbounded_prompt(tmp_path: Path):
    report = run_llm_sandbox_implementation(root=tmp_path, prompt="Сделай полезное приложение.", write=True)

    assert report["status"] == "blocked"
    assert report["promotion_allowed"] is False


def test_verified_system_package_includes_bounded_sandbox_for_unknown_cli(tmp_path: Path):
    report = build_verified_system_package(
        root=tmp_path,
        prompt="Напиши CLI .py, которая переводит текстовый файл в верхний регистр.",
        curriculum_dir=ROOT / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["llm_sandbox_implementation"]["status"] == "sandbox_verified"
    assert report["llm_sandbox_implementation"]["promotion_allowed"] is False
    assert report["sandbox_programmer_admission"]["status"] == "passed"
    assert report["programmer_sandbox_gate"]["status"] == "passed"
    assert report["generated_package_evaluation"]["artifact_type"] == "GeneratedPackageEvaluation"
    assert report["generated_package_evaluation"]["status"] == "passed"
    assert report["generated_package_evaluation"]["score"] == 1.0
    assert report["release_decision"]["decision"] == "release_ready_with_risks"
    assert report["sandbox_successful_resolution_candidate"]["status"] == "collect_more_cases"
    assert Path(report["sandbox_successful_resolution_candidate"]["candidate_path"]).is_file()


def test_llm_sandbox_implementation_loads_operations_from_registry(tmp_path: Path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "sandbox_programmer_operations.json").write_text(
        """{
  "schema_version": "sandbox_programmer_operations.v1",
  "operations": [
    {
      "id": "word_count",
      "package": "word_count_cli",
      "description": "count words",
      "match": ["количество слов"],
      "profile": "text_expression",
      "expression": "str(len(text.split())) + '\\\\n'",
      "sample": "one two three",
      "expected": "3\\n"
    }
  ]
}
""",
        encoding="utf-8",
    )

    report = run_llm_sandbox_implementation(
        root=tmp_path,
        prompt="Напиши CLI .py, которая считает количество слов.",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["implementation_plan"]["operation"]["operation"] == "word_count"


def test_llm_sandbox_implementation_accepts_russian_console_tool_prefilter():
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Сделай консольную штуку, которая уберет пробелы по краям текста.",
        write=False,
    )

    assert report["status"] == "planned"
    assert report["implementation_plan"]["operation"]["operation"] == "trim"


def test_llm_sandbox_implementation_builds_csv_profile_from_registry(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Напиши CLI .py, которая сортирует CSV по первой колонке.",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["implementation_plan"]["operation"]["profile"] == "csv_sort_first_column"
    graph = report["implementation_plan"]["operation_graph"]
    assert graph["artifact_type"] == "SandboxOperationGraph"
    assert [edge[0] for edge in graph["edges"]][:2] == ["read_input", "parse_input"]
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_uses_l45_only_as_operation_normalizer(monkeypatch, tmp_path: Path):
    def fake_call_json_chat(messages):
        assert "available_operations" in messages[1]["content"]
        return {"operation_id": "csv_row_count", "confidence": 0.9, "reason": "CSV row counting request"}

    monkeypatch.setattr(sandbox_impl, "call_json_chat", fake_call_json_chat)

    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Напиши CLI .py, которая считает строки CSV файла.",
        write=True,
        use_model=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["route_resolution"]["strategy"] == "l45_registry_operation_normalization"
    assert report["route_resolution"]["model_invoked"] is True
    assert report["implementation_plan"]["operation"]["operation"] == "csv_row_count"
    assert report["implementation_plan"]["operation"]["evidence"] == ["l45:csv_row_count"]
    assert report["llm_policy"]["llm_output_executed_directly"] is False


def test_llm_sandbox_implementation_rejects_l45_operation_outside_registry(monkeypatch):
    monkeypatch.setattr(
        sandbox_impl,
        "call_json_chat",
        lambda messages: {"operation_id": "install_random_package", "confidence": 0.99, "reason": "bad"},
    )

    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Напиши CLI .py, которая считает строки CSV файла.",
        write=False,
        use_model=True,
    )

    assert report["status"] == "blocked"
    assert report["route_resolution"]["status"] == "blocked_invalid_model_operation"
    assert report["promotion_allowed"] is False


def test_llm_sandbox_implementation_rejects_low_confidence_l45_match(monkeypatch):
    monkeypatch.setattr(
        sandbox_impl,
        "call_json_chat",
        lambda messages: {"operation_id": "csv_row_count", "confidence": 0.2, "reason": "maybe"},
    )

    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Напиши CLI .py, которая считает строки CSV файла.",
        write=False,
        use_model=True,
    )

    assert report["status"] == "blocked"
    assert report["route_resolution"]["status"] == "blocked_low_model_confidence"
    assert report["source_code_changes"] is False


def test_llm_sandbox_implementation_does_not_match_upper_for_json_top_level():
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="CLI должен перечислить ключи верхнего уровня JSON объекта.",
        write=False,
        use_model=False,
    )

    assert report["status"] == "planned"
    assert report["implementation_plan"]["operation"]["operation"] == "json_keys"


def test_llm_sandbox_implementation_builds_csv_operation_composition():
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Напиши CLI .py: из CSV убрать строки с пустой первой колонкой, оставить первые две колонки и вывести JSON.",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["operation"] == "csv_filter_select_to_json_records"
    assert [step["operation"] for step in operation["steps"]] == [
        "csv_filter_first_column_nonempty",
        "csv_select_first_two_columns",
        "csv_to_json_records",
    ]
    graph = report["implementation_plan"]["operation_graph"]
    assert [node["id"] for node in graph["nodes"] if node["kind"] == "transform"] == [
        "transform_1",
        "transform_2",
        "transform_3",
    ]
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_builds_text_operation_composition():
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="Сделай CLI .py: убери пробелы по краям текста и переведи в большие буквы.",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["implementation_plan"]["operation"]["operation"] == "trim_then_upper"
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_builds_numeric_args_stdout_cli(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="программе как параметры передаются два числа и она должна в терминале вывести их сумму",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    assert report["implementation_plan"]["operation"]["operation"] == "sum_two_numbers_args"
    assert report["implementation_plan"]["operation"]["profile"] == "numeric_args_sum"
    assert report["verification"]["tests"]["status"] == "passed"
    assert (Path(report["project_dir"]) / "src" / "sum_two_numbers_cli" / "cli.py").is_file()


def test_llm_sandbox_implementation_builds_numeric_args_expression_cli(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt=(
            "напиши программу CLI которая принимает три аргумента, первые два перемножает, "
            "результат складывает с третьим и выводит результат, например 22*6+3"
        ),
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["operation"].startswith("numeric_args_expression_")
    assert operation["profile"] == "numeric_args_expression"
    assert operation["expression"] == "a*b+c"
    assert report["route_resolution"]["strategy"] == "deterministic_numeric_expression_extraction"
    assert report["implementation_plan"]["operation_recipe"]["artifact_type"] == "OperationRecipe"
    assert report["implementation_plan"]["operation_recipe"]["transform"] == "numeric_expression"
    assert report["implementation_plan"]["interface_contract"]["id"] == "argv_stdout_numeric_expression"
    assert report["implementation_plan"]["operation_graph"]["nodes"][1]["contract"]["output"] == "numeric_args"
    assert report["verification"]["tests"]["status"] == "passed"
    assert (Path(report["project_dir"]) / "tests" / "test_cli.py").is_file()


def test_llm_sandbox_implementation_builds_generic_symbolic_numeric_expression_cli(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши программу CLI: принимает три аргумента a b c, считает (a+b)/c и выводит результат",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["profile"] == "numeric_args_expression"
    assert operation["expression"] == "(a+b)/c"
    assert operation["expected"] == "1.25\n"
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_blocks_unsafe_numeric_expression():
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши программу CLI: принимает аргументы и считает __import__('os').system('dir')",
        write=False,
    )

    assert report["status"] == "blocked"


def test_llm_sandbox_implementation_builds_stdin_stdout_cli(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: читает stdin, переводит текст в верхний регистр и выводит stdout",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["operation"] == "stdin_upper_stdout"
    assert operation["profile"] == "stdin_text_expression"
    assert report["implementation_plan"]["interface_contract"]["id"] == "stdin_to_stdout_text_transform"
    assert report["implementation_plan"]["operation_graph"]["nodes"][0]["id"] == "read_stdin"
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_builds_file_stdout_cli(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: читает файл считает слова и выводит количество слов в stdout",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["operation"] == "file_word_count_stdout"
    assert operation["profile"] == "file_stdout_text_expression"
    assert report["implementation_plan"]["interface_contract"]["id"] == "file_to_stdout_text_transform"
    assert report["implementation_plan"]["operation_graph"]["nodes"][0]["id"] == "read_input"
    assert report["implementation_plan"]["operation_graph"]["nodes"][4]["id"] == "write_stdout"
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_builds_stdin_file_cli_from_recipe(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: читает stdin, переводит текст в верхний регистр и сохраняет результат в файл",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["profile"] == "stdin_file_text_expression"
    assert report["route_resolution"]["strategy"] == "deterministic_operation_recipe_parser"
    assert report["implementation_plan"]["interface_contract"]["id"] == "stdin_to_file_text_transform"
    assert report["implementation_plan"]["operation_graph"]["nodes"][0]["id"] == "read_stdin"
    assert report["implementation_plan"]["operation_graph"]["nodes"][4]["id"] == "write_output"
    assert report["verification"]["tests"]["status"] == "passed"


def test_llm_sandbox_implementation_builds_numeric_args_file_cli_from_recipe(tmp_path: Path):
    report = run_llm_sandbox_implementation(
        root=ROOT,
        prompt="напиши CLI: принимает аргументы a b c, считает a*b+c и записывает результат в файл",
        write=True,
    )

    assert report["status"] == "sandbox_verified"
    operation = report["implementation_plan"]["operation"]
    assert operation["profile"] == "numeric_args_file_expression"
    assert operation["expression"] == "a*b+c"
    assert report["route_resolution"]["strategy"] == "deterministic_operation_recipe_parser"
    assert report["implementation_plan"]["interface_contract"]["id"] == "argv_to_file_numeric_expression"
    assert report["implementation_plan"]["operation_graph"]["nodes"][4]["id"] == "write_output"
    assert report["verification"]["tests"]["status"] == "passed"


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
        ("Напиши CLI .py: выбрать первые две колонки CSV.", "csv_select_first_two_columns"),
        ("Напиши CLI .py: отфильтровать CSV по непустая первая колонка.", "csv_filter_first_column_nonempty"),
        ("Напиши CLI .py: HTML таблицу в CSV.", "html_table_to_csv"),
        ("Напиши CLI .py: извлечь JSON по первый ключ JSON.", "json_extract_first_key"),
        ("Напиши CLI .py: форматировать JSON красиво.", "json_pretty"),
        ("Напиши CLI .py: отсортировать строки.", "line_sort"),
        ("Напиши CLI .py: убрать дубли строк.", "line_unique"),
        ("Напиши CLI .py: сумма второй колонки CSV.", "csv_sum_second_column"),
        ("Напиши CLI .py: CSV в JSON.", "csv_to_json_records"),
        ("Напиши CLI .py: перечислить ключи JSON.", "json_keys"),
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
