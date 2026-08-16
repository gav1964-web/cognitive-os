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
