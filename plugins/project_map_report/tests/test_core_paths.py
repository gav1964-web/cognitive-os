from __future__ import annotations

from plugins.project_map_report.src.core_paths import classify_source_path, is_core_path


def test_core_paths_treat_support_files_as_context_only():
    for path in [
        "runtests.py",
        "hatch_build.py",
        "install_dev_repos.py",
        "client/python/gradio_client/documentation.py",
        "external-deps/python-lsp-server/pylsp/plugins/symbols.py",
        "bootloader/waflib/Scripting.py",
        "src/integrations/prefect-aws/infra/worker/service_stack.py",
    ]:
        result = classify_source_path(path)

        assert result["kind"] == "context_only"
        assert not is_core_path(path)


def test_core_paths_keep_real_package_source_active():
    assert is_core_path("src/prefect/task_engine.py")
    assert is_core_path("airflow-core/src/airflow/api/common/trigger_dag.py")
