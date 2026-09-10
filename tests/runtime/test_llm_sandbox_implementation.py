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
