from pathlib import Path

from runtime.patch_synthesis_policy import incomplete_import_token_contract_recipe
from runtime.programmer_incomplete_import_patch import incomplete_import_token_patch
from runtime.programmer_patch_synthesizer import synthesize_patch_package


SOURCE = '''def extract_package_name(line: str):
    if line.lstrip().startswith(("import", "from")):
        word = line.split()[1]
    else:
        return None
    return word.split(".")[0]
'''


def test_incomplete_import_patch_guards_the_proven_token_index():
    patch = incomplete_import_token_patch(
        SOURCE,
        symbol="extract_package_name",
        recipe=incomplete_import_token_contract_recipe(),
    )

    assert patch is not None
    namespace: dict[str, object] = {}
    exec(patch["source"], namespace)
    extract = namespace["extract_package_name"]
    assert extract("import") is None
    assert extract("from") is None
    assert extract("import os.path") == "os"


def test_incomplete_import_patch_rejects_an_unproven_index_shape():
    assert incomplete_import_token_patch(
        SOURCE.replace("line.split()[1]", "line.split(maxsplit=1)[1]"),
        symbol="extract_package_name",
        recipe=incomplete_import_token_contract_recipe(),
    ) is None


def test_synthesizer_prepares_incomplete_import_patch(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "autoflake.py").write_text(SOURCE, encoding="utf-8")
    target = "autoflake.py:extract_package_name"
    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "expected_files": ["autoflake.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "guard_incomplete_import_tokens",
                    "allowed_operator_ids": ["guard_incomplete_import_tokens"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "guard_incomplete_import_tokens"
