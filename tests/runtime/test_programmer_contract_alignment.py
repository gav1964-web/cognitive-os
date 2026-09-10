from pathlib import Path

from runtime.programmer_patch_strategy import build_patch_strategy


def test_patch_strategy_preserves_qualified_method_in_source_criterion(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    source = project / "src" / "click"
    source.mkdir(parents=True)
    (source / "core.py").write_text(
        "class Option:\n"
        "    def get_help_extra(self):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    target = "src/click/core.py:Option.get_help_extra"

    proposal = build_patch_strategy(
        project_dir=project,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": target}},
        test_plan={
            "executable_acceptance": {
                "obligations": [{
                    "target": target,
                    "source_criterion": f"The selected extraction_contract `{target}` defines this behavior.",
                }]
            }
        },
        synthesis={"status": "skipped", "reason": "no_supported_patch_pattern"},
    )

    assert proposal["contract_alignment"]["status"] == "aligned"
    assert proposal["contract_alignment"]["source_refs"] == []
