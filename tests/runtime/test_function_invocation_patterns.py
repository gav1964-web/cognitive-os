from pathlib import Path

from runtime.function_invocation_miner import mine_function_invocations
from runtime.function_invocation_patterns import load_function_invocation_patterns, match_invocation_pattern


def test_invocation_kb_is_anonymized_and_selects_declared_model():
    catalog = load_function_invocation_patterns()

    assert catalog["admission_policy"]["store_project_names"] is False
    match = match_invocation_pattern({"request": "CreateUserRequest"}, {"result": "User"}, catalog)
    assert match["id"] == "declared_local_model_contract"
    assert match["construction"] == "signature_annotation_keyword_constructor"


def test_miner_promotes_only_repeated_anonymized_shapes(tmp_path: Path):
    roots = []
    for index in range(3):
        root = tmp_path / f"private-project-{index}"
        tests = root / "tests"
        tests.mkdir(parents=True)
        calls = 2 if index < 2 else 1
        source = "\n".join(f"def test_{n}():\n    assert normalize(value=' X ') == 'x'" for n in range(calls))
        (tests / "test_api.py").write_text(source + "\n", encoding="utf-8")
        roots.append(root)

    report = mine_function_invocations(roots)

    row = next(item for item in report["patterns"] if item["call_shape"] == "keyword:literal")
    assert row == {
        "call_shape": "keyword:literal",
        "oracle": "equality",
        "observations": 5,
        "distinct_projects": 3,
        "promotion_eligible": True,
    }
    assert "private-project" not in str(report)
    assert report["privacy"] == {"project_names_stored": False, "source_code_stored": False}


def test_miner_never_promotes_calls_without_an_observed_oracle(tmp_path: Path):
    roots = []
    for index in range(3):
        root = tmp_path / f"project-{index}"
        root.mkdir()
        (root / "test_flow.py").write_text(
            "def test_flow():\n    execute('x')\n    execute('y')\n", encoding="utf-8"
        )
        roots.append(root)

    report = mine_function_invocations(roots)

    row = next(item for item in report["patterns"] if item["oracle"] == "execution_only")
    assert row["observations"] == 6
    assert row["promotion_eligible"] is False
