from runtime.dependency_boundary_profile import build_dependency_boundary_profile
from runtime.isolated_dependency_profile import build_isolated_dependency_profile


def test_declared_low_risk_dependency_is_ready_for_isolated_probe(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["attrs>=24"]\n',
        encoding="utf-8",
    )

    profile = build_isolated_dependency_profile(
        project_root=tmp_path,
        target="pkg/core.py:normalize",
        missing_modules=["attr"],
    )

    assert profile["status"] == "ready_for_probe"
    assert profile["install_plan"]["allowed_packages"] == ["attrs"]
    assert profile["environment"]["automatic_install_allowed"] is False
    assert profile["environment"]["outside_source_project"] is True
    assert profile["environment"]["install_timeout_seconds"] == 240
    assert profile["environment"]["prefer_binary"] is True
    assert len(profile["profile_fingerprint"]) == 64
    assert profile["approval_request"]["requested_packages"] == ["attrs"]
    assert profile["approval_request"]["risk_status"] == "ready_for_probe"


def test_declared_unknown_dependency_requires_risk_review(tmp_path):
    (tmp_path / "setup.cfg").write_text(
        "[options]\ninstall_requires =\n    scientific-sdk>=2\n",
        encoding="utf-8",
    )

    profile = build_isolated_dependency_profile(
        project_root=tmp_path,
        target="pkg/adapter.py:convert",
        missing_modules=["scientific_sdk"],
    )

    assert profile["status"] == "review_required"
    assert profile["install_plan"]["review_packages"] == ["scientific-sdk"]
    assert profile["package_candidates"][0]["declared"] is True
    assert profile["approval_request"]["requested_packages"] == ["scientific-sdk"]


def test_undeclared_dependency_is_blocked(tmp_path):
    profile = build_isolated_dependency_profile(
        project_root=tmp_path,
        target="pkg/adapter.py:convert",
        missing_modules=["unknown_sdk"],
    )

    assert profile["status"] == "blocked_undeclared"
    assert profile["install_plan"]["blocked_packages"] == ["unknown-sdk"]
    assert "install_undeclared_package" in profile["forbidden_actions"]


def test_approved_distribution_metadata_can_declare_transitive_dependency(tmp_path):
    profile = build_isolated_dependency_profile(
        project_root=tmp_path,
        target="pkg/adapter.py:convert",
        missing_modules=["numpy"],
        transitive_evidence={"ase": ["numpy>=1.21.6", "scipy>=1.7.0"]},
    )

    assert profile["status"] == "ready_for_probe"
    assert profile["install_plan"]["wheel_packages"] == ["numpy"]
    evidence = profile["manifest_evidence"]["approved_distribution_requirements"]
    assert evidence["ase"][0].startswith("numpy")


def test_dependency_boundary_embeds_manifest_backed_isolated_profile(tmp_path):
    (tmp_path / "requirements.txt").write_text("attrs>=24\n", encoding="utf-8")
    profile = build_dependency_boundary_profile(
        {
            "candidate": "pkg/core.py:normalize",
            "dependency_readiness": {"missing_external_modules": ["attr"]},
        },
        project_root=tmp_path.as_posix(),
    )

    isolated = profile["isolated_environment_profile"]
    assert isolated["artifact_type"] == "IsolatedDependencyProfile"
    assert isolated["status"] == "ready_for_probe"
    assert isolated["manifest_evidence"]["dependency_files"]
