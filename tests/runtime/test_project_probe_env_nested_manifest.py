from runtime.project_probe_env import declared_package_satisfies_module, declared_project_packages


def test_nested_pyproject_dependencies_are_declared(tmp_path):
    package = tmp_path / "mcp"
    package.mkdir()
    (package / "pyproject.toml").write_text(
        '[project]\ndependencies = [\n  "mcp[cli]>=1.9",\n  "httpx>=0.27",\n'
        '  "djangorestframework>=3",\n]\n',
        encoding="utf-8",
    )

    declared = declared_project_packages(tmp_path)

    assert {"mcp", "httpx", "djangorestframework"} <= declared
    assert declared_package_satisfies_module("rest_framework", declared)


def test_distribution_module_alias_is_source_proven_by_policy(tmp_path):
    (tmp_path / "requirements.txt").write_text("python-status>=1.0\n", encoding="utf-8")

    declared = declared_project_packages(tmp_path)

    assert declared_package_satisfies_module("status", declared)
