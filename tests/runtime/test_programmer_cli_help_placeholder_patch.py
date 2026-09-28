from pathlib import Path

from runtime.patch_synthesis_policy import cli_help_type_placeholder_contract_recipe
from runtime.programmer_cli_help_placeholder_patch import cli_help_placeholder_patch
from runtime.programmer_patch_synthesizer import synthesize_patch_package


SOURCE = '''class ParserContext(object):
    def help_for(self, flag):
        arg = self.flags[flag]
        value = {
            str: 'STRING',
        }.get(arg.kind)
        return value
'''


def test_cli_help_placeholder_patch_adds_exact_integer_mapping():
    patch = cli_help_placeholder_patch(
        SOURCE,
        symbol="ParserContext.help_for",
        recipe=cli_help_type_placeholder_contract_recipe(),
    )

    assert patch is not None
    assert "            int: 'INT',\n" in patch["source"]
    assert patch["source"].count("int: 'INT'") == 1


def test_cli_help_placeholder_patch_rejects_wider_or_shadowed_maps():
    wider = SOURCE.replace("str: 'STRING',", "str: 'STRING',\n            float: 'FLOAT',")
    shadowed = "int = object()\n" + SOURCE
    recipe = cli_help_type_placeholder_contract_recipe()

    assert cli_help_placeholder_patch(
        wider, symbol="ParserContext.help_for", recipe=recipe
    ) is None
    assert cli_help_placeholder_patch(
        shadowed, symbol="ParserContext.help_for", recipe=recipe
    ) is None


def test_cli_help_placeholder_patch_rejects_import_and_argument_shadowing():
    imported = "from custom_types import int\n" + SOURCE
    argument = SOURCE.replace("def help_for(self, flag):", "def help_for(self, flag, *, int=None):")
    recipe = cli_help_type_placeholder_contract_recipe()

    assert cli_help_placeholder_patch(
        imported, symbol="ParserContext.help_for", recipe=recipe
    ) is None
    assert cli_help_placeholder_patch(
        argument, symbol="ParserContext.help_for", recipe=recipe
    ) is None


def test_synthesizer_prepares_cli_help_placeholder_patch(tmp_path: Path):
    project = tmp_path / "project"
    source = project / "invoke" / "parser"
    source.mkdir(parents=True)
    (source / "context.py").write_text(SOURCE, encoding="utf-8")
    target = "invoke/parser/context.py:ParserContext.help_for"

    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "expected_files": ["invoke/parser/context.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "add_cli_int_help_placeholder",
                    "allowed_operator_ids": ["add_cli_int_help_placeholder"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "add_cli_int_help_placeholder"
