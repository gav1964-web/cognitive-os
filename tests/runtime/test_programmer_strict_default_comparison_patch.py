from pathlib import Path

from runtime.patch_synthesis_policy import strict_default_string_comparison_contract_recipe
from runtime.programmer_patch_synthesizer import synthesize_patch_package
from runtime.programmer_strict_default_comparison_patch import strict_default_comparison_patch


SOURCE = '''class Option:
    def get_help_extra(self, default_value):
        if default_value is None:
            return None
        elif default_value == "":
            return 'empty'
        return str(default_value)
'''


def test_strict_default_patch_guards_the_empty_string_comparison():
    patch = strict_default_comparison_patch(
        SOURCE,
        symbol="Option.get_help_extra",
        recipe=strict_default_string_comparison_contract_recipe(),
    )

    assert patch is not None
    namespace: dict[str, object] = {}
    exec(patch["source"], namespace)

    class Strict:
        def __eq__(self, other):
            raise ValueError("cannot compare")

        def __str__(self):
            return "strict"

    assert namespace["Option"]().get_help_extra(Strict()) == "strict"


def test_strict_default_patch_rejects_shadowed_isinstance():
    source = SOURCE.replace(
        "if default_value is None:",
        "isinstance = lambda *args: True\n        if default_value is None:",
    )
    assert strict_default_comparison_patch(
        source,
        symbol="Option.get_help_extra",
        recipe=strict_default_string_comparison_contract_recipe(),
    ) is None


def test_synthesizer_prepares_strict_default_patch(tmp_path: Path):
    project = tmp_path / "project"
    source = project / "src" / "click"
    source.mkdir(parents=True)
    (source / "core.py").write_text(SOURCE, encoding="utf-8")
    target = "src/click/core.py:Option.get_help_extra"
    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "expected_files": ["src/click/core.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "guard_empty_string_comparison_type",
                    "allowed_operator_ids": ["guard_empty_string_comparison_type"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "guard_empty_string_comparison_type"
