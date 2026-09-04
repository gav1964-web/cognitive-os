from pathlib import Path

from runtime.patch_synthesis_policy import duplicate_cli_short_option_contract_recipe
from runtime.programmer_duplicate_cli_option_patch import duplicate_cli_option_patch
from runtime.programmer_patch_synthesizer import synthesize_patch_package


SOURCE = '''import click

@click.command()
@click.option("--json", "-j", is_flag=True)
@click.option("--emoji", "-j", is_flag=True)
def main(json, emoji):
    return json, emoji
'''


def test_duplicate_cli_option_patch_changes_only_the_proven_option_token():
    patch = duplicate_cli_option_patch(
        SOURCE,
        symbol="main",
        recipe=duplicate_cli_short_option_contract_recipe(),
    )

    assert patch is not None
    assert '@click.option("--json", "-j", is_flag=True)' in patch["source"]
    assert "@click.option(\"--emoji\", '-J', is_flag=True)" in patch["source"]


def test_duplicate_cli_option_patch_rejects_an_occupied_replacement_flag():
    source = SOURCE.replace(
        "@click.command()",
        '@click.command()\n@click.option("--joined", "-J", is_flag=True)',
    )

    assert duplicate_cli_option_patch(
        source,
        symbol="main",
        recipe=duplicate_cli_short_option_contract_recipe(),
    ) is None


def test_synthesizer_prepares_duplicate_cli_option_patch(tmp_path: Path):
    project = tmp_path / "project"
    source = project / "src" / "rich_cli"
    source.mkdir(parents=True)
    (source / "__main__.py").write_text(SOURCE, encoding="utf-8")
    target = "src/rich_cli/__main__.py:main"
    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "expected_files": ["src/rich_cli/__main__.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "replace_duplicate_cli_short_option",
                    "allowed_operator_ids": ["replace_duplicate_cli_short_option"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "replace_duplicate_cli_short_option"
