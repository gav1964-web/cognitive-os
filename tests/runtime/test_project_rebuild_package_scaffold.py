from __future__ import annotations

from runtime.project_rebuild_package_scaffold import build_package_entrypoint_files


def test_package_entrypoint_files_preserve_public_entrypoint_shape():
    files = build_package_entrypoint_files(
        {
            "main_task": "Provide async queue helpers.",
            "entrypoints": ["src/pkg/__init__.py", "src/pkg/core.py"],
            "core_capabilities": ["pkg.core:run"],
        }
    )

    assert "src/pkg/__init__.py" in files
    assert "src/pkg/core.py" in files
    assert "src/__init__.py" not in files
    assert "Provide async queue helpers." in files["src/pkg/core.py"]
    assert "pkg.core:run" in files["src/pkg/core.py"]


def test_package_entrypoint_files_skip_unsafe_paths():
    files = build_package_entrypoint_files(
        {"entrypoints": ["../secret.py", "/abs/path.py", "pkg/data.txt", "app.py"]}
    )

    assert files == {}


def test_package_entrypoint_files_skip_monorepo_distribution_package_markers():
    files = build_package_entrypoint_files(
        {
            "main_task": "Collect telemetry.",
            "entrypoints": [
                "exporter/opentelemetry-exporter-otlp-json-common/src/opentelemetry/exporter/otlp/json/common/__init__.py"
            ],
        }
    )

    assert "exporter/__init__.py" not in files
    assert "exporter/opentelemetry-exporter-otlp-json-common/__init__.py" not in files
    assert "exporter/opentelemetry-exporter-otlp-json-common/src/__init__.py" not in files
    assert (
        "exporter/opentelemetry-exporter-otlp-json-common/src/opentelemetry/exporter/otlp/json/common/__init__.py"
        in files
    )
    assert "exporter/opentelemetry-exporter-otlp-json-common/src/opentelemetry/__init__.py" not in files
    assert "exporter/opentelemetry-exporter-otlp-json-common/src/opentelemetry/exporter/__init__.py" not in files


def test_package_entrypoint_file_is_not_overwritten_by_child_parent_marker():
    files = build_package_entrypoint_files(
        {
            "main_task": "Expose framework API.",
            "entrypoints": ["src/flask/__init__.py", "src/flask/app.py"],
            "behavior_blueprints": [
                {
                    "kind": "module_import",
                    "path": "src/flask/__init__.py",
                    "shape": {"public_names": ["Flask", "Blueprint"]},
                }
            ],
        }
    )

    assert "__all__ = ['Flask', 'Blueprint']" in files["src/flask/__init__.py"]
    assert "class Flask:" in files["src/flask/__init__.py"]
    assert "Rebuilt package marker" not in files["src/flask/__init__.py"]


def test_package_entrypoint_file_defines_public_function_exports():
    files = build_package_entrypoint_files(
        {
            "main_task": "Expose parser helpers.",
            "entrypoints": ["pkg/__init__.py"],
            "behavior_blueprints": [
                {
                    "kind": "module_import",
                    "path": "pkg/__init__.py",
                    "shape": {"public_names": ["parse"], "attr_kinds": {"parse": "function"}},
                }
            ],
        }
    )

    assert "__all__ = ['parse']" in files["pkg/__init__.py"]
    assert "def parse(*args, **kwargs):" in files["pkg/__init__.py"]
