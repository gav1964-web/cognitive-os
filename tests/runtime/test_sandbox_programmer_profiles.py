from __future__ import annotations

from pathlib import Path

import pytest

from runtime.sandbox_programmer_profiles import (
    SandboxProgrammerProfilesError,
    admission_shape,
    allowed_profiles,
    expression_policy,
    graph_family,
    load_sandbox_programmer_profiles,
)


ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_programmer_profiles_load_policy():
    profiles = load_sandbox_programmer_profiles(str(ROOT / "config" / "sandbox_programmer_profiles.json"))

    assert "csv_sort_first_column" in allowed_profiles(profiles=profiles)
    assert expression_policy("text_expression", profiles=profiles) == "text_expression_required"
    assert expression_policy("csv_row_count", profiles=profiles) == "no_expression"
    assert graph_family("stdin_file_text_expression", profiles=profiles) == "stdin_file_text"
    assert admission_shape("numeric_args_file_expression", profiles=profiles) == "numeric_args_file"


def test_sandbox_programmer_profiles_reject_missing_profile_field(tmp_path: Path):
    path = tmp_path / "profiles.json"
    path.write_text(
        """{
  "schema_version": "sandbox_programmer_profiles.v1",
  "status": "active",
  "profiles": {"demo": {"expression_policy": "no_expression"}},
  "text_expression_policy": {},
  "numeric_expression_policy": {}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(SandboxProgrammerProfilesError, match="graph_family"):
        load_sandbox_programmer_profiles(str(path))
