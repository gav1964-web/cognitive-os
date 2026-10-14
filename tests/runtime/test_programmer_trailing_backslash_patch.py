from pathlib import Path

from runtime.patch_synthesis_policy import trailing_backslash_bounds_contract_recipe
from runtime.programmer_patch_synthesizer import synthesize_patch_package
from runtime.programmer_trailing_backslash_patch import trailing_backslash_bounds_patch


SOURCE = '''def file_contents(contents):
    in_lines = contents.splitlines()
    line_count = len(in_lines)
    index = 1
    line = in_lines[0]
    while line.strip().endswith("\\\\"):
        line, new_comment = parse_comments(in_lines[index])
        line = line.lstrip()
        index += 1
    return line
'''


def test_trailing_backslash_patch_adds_the_proven_index_bound():
    patch = trailing_backslash_bounds_patch(
        SOURCE,
        symbol="file_contents",
        recipe=trailing_backslash_bounds_contract_recipe(),
    )

    assert patch is not None
    assert 'while line.strip().endswith("\\\\") and index < line_count:' in patch["source"]


def test_trailing_backslash_patch_rejects_a_different_loop_body():
    assert trailing_backslash_bounds_patch(
        SOURCE.replace("in_lines[index]", "in_lines[index + 1]"),
        symbol="file_contents",
        recipe=trailing_backslash_bounds_contract_recipe(),
    ) is None


def test_synthesizer_prepares_trailing_backslash_bounds_patch(tmp_path: Path):
    project = tmp_path / "project"
    (project / "isort").mkdir(parents=True)
    (project / "isort" / "parse.py").write_text(SOURCE, encoding="utf-8")
    target = "isort/parse.py:file_contents"

    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "expected_files": ["isort/parse.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "guard_trailing_backslash_index",
                    "allowed_operator_ids": ["guard_trailing_backslash_index"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "guard_trailing_backslash_index"
