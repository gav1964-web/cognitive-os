from pathlib import Path

from runtime.patch_synthesis_policy import falsy_primitive_empty_contract_recipe
from runtime.programmer_falsy_empty_patch import falsy_primitive_empty_patch
from runtime.programmer_patch_synthesizer import synthesize_patch_package


SOURCE = '''class Strategies:
    @staticmethod
    def strategy_override_if_not_empty(config, path, base, nxt):
        """Override unless the new value is empty."""
        return nxt if nxt else base
'''


def test_falsy_empty_patch_preserves_only_null_and_sized_empty_values():
    patch = falsy_primitive_empty_patch(
        SOURCE,
        symbol="Strategies.strategy_override_if_not_empty",
        recipe=falsy_primitive_empty_contract_recipe(),
    )

    assert patch is not None
    namespace: dict[str, object] = {}
    exec(patch["source"], namespace)
    strategy = namespace["Strategies"].strategy_override_if_not_empty
    for value in (0, False, 0.0, 0j):
        result = strategy({}, [], "base", value)
        assert result == value
        assert type(result) is type(value)
    for value in (None, "", [], {}, set(), ()):
        assert strategy({}, [], "base", value) == "base"


def test_falsy_empty_patch_rejects_unproven_shape():
    assert falsy_primitive_empty_patch(
        SOURCE.replace("return nxt if nxt else base", "return nxt or base"),
        symbol="Strategies.strategy_override_if_not_empty",
        recipe=falsy_primitive_empty_contract_recipe(),
    ) is None


def test_synthesizer_prepares_falsy_empty_patch_in_sandbox(tmp_path: Path):
    project = tmp_path / "project"
    source = project / "strategy.py"
    source.parent.mkdir()
    source.write_text(SOURCE, encoding="utf-8")
    target = "strategy.py:Strategies.strategy_override_if_not_empty"
    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "expected_files": ["strategy.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "preserve_falsy_primitive_override",
                    "allowed_operator_ids": ["preserve_falsy_primitive_override"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "preserve_falsy_primitive_override"
    assert Path(result["sandbox_project"]) != project
