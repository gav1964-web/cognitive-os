from __future__ import annotations

from runtime.patch_synthesis_policy import missing_registry_env_fallback_recipe
from runtime.programmer_patch_synthesizer import synthesize_patch_package
from runtime.programmer_registry_fallback_patch import registry_env_fallback_patch


SOURCE = '''def get_win_folder_from_env_vars(csidl_name: str) -> str:
    return "fallback:" + csidl_name


def get_win_folder_from_registry(csidl_name: str) -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Shell Folders") as key:
        directory, _ = winreg.QueryValueEx(key, csidl_name)
    return str(directory)
'''


def test_registry_fallback_patch_wraps_only_registry_lookup():
    patch = registry_env_fallback_patch(
        SOURCE,
        symbol="get_win_folder_from_registry",
        recipe=missing_registry_env_fallback_recipe(),
    )

    assert patch is not None
    assert "except FileNotFoundError:" in patch["source"]
    assert "return get_win_folder_from_env_vars(csidl_name)" in patch["source"]
    compile(patch["source"], "windows.py", "exec")


def test_registry_fallback_patch_rejects_unrelated_function():
    patch = registry_env_fallback_patch(
        "def read(value):\n    return value\n",
        symbol="read",
        recipe=missing_registry_env_fallback_recipe(),
    )

    assert patch is None


def test_synthesizer_prepares_registry_fallback_in_sandbox(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "windows.py").write_text(SOURCE, encoding="utf-8")

    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": "windows.py:get_win_folder_from_registry"},
            "expected_files": ["windows.py"],
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "operator_id": "fallback_missing_registry_to_env",
                    "allowed_operator_ids": ["fallback_missing_registry_to_env"],
                },
            },
        },
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "fallback_missing_registry_to_env"
    assert result["sandbox_project"] != project.as_posix()
