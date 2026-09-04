from pathlib import Path

import pytest

from runtime.programmer_framework_contract_patch import framework_contract_patch


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("project", "source_path", "symbol", "operation", "marker"),
    [
        (
            "pluggy_call_extra_order", "src/pluggy/_hooks.py", "HookCaller.call_extra",
            "order_extra_hooks_after_wrappers", "or hookimpls[i].tryfirst",
        ),
        (
            "build_wheel_dist_info", "src/build/_builder.py", "ProjectBuilder.metadata_path",
            "derive_dist_info_from_wheel_contents", "metadata_names = [",
        ),
        (
            "mkdocs_empty_theme_config", "mkdocs/theme.py", "Theme._load_theme_config",
            "guard_empty_theme_config", "if theme_config is None:",
        ),
    ],
)
def test_framework_reducer_matches_historical_parent(
    project, source_path, symbol, operation, marker
):
    source = (
        ROOT / "benchmarks" / "github_historical_prefixed_20260830" / project / source_path
    ).read_text(encoding="utf-8")
    recipe = {"required_symbol": symbol}

    patch = framework_contract_patch(
        source, symbol=symbol, operation_kind=operation, recipe=recipe
    )

    assert patch is not None
    assert marker in patch["source"]
    compile(patch["source"], source_path, "exec")
    assert framework_contract_patch(
        patch["source"], symbol=symbol, operation_kind=operation, recipe=recipe
    ) is None
