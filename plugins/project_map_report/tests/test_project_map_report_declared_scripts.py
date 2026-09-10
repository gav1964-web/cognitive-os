from plugins.project_map_report.src.main import run


def test_declared_project_script_is_preserved_as_entrypoint_evidence():
    result = run({
        "tree": {"root": "tool", "counts": {"files": 2, "directories": 1, "truncated": False}},
        "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": []},
        "files": {"files": [{
            "path": "pyproject.toml",
            "text": "[project]\nname='tool'\n[project.scripts]\nrun-tool='tool.cli:main'\n",
        }]},
        "python_structure": {"imports": [], "routes": [], "files": [], "project_insights": {}},
        "runtime_commands": {"commands": []},
    })

    assert result["source_health"]["declared_script_entrypoint_count"] == 1
    assert result["summary"]["declared_script_entrypoints"] == [
        "pyproject.toml:[project.scripts]:run-tool=tool.cli:main"
    ]
    assert result["summary"]["declared_script_entrypoints"][0] in result["summary"]["entrypoints"]


def test_declared_plugin_entrypoint_is_preserved_as_identity_evidence():
    result = run({
        "tree": {"root": "plugin", "counts": {"files": 2, "directories": 1}},
        "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": []},
        "files": {"files": [{
            "path": "pyproject.toml",
            "text": "[project]\nname='plugin'\n"
            "[project.entry-points.pytest11]\nplugin='plugin:hook'\n",
        }]},
        "python_structure": {"imports": [], "routes": [], "files": [], "project_insights": {}},
        "runtime_commands": {"commands": []},
    })

    assert result["source_health"]["declared_plugin_entrypoint_count"] == 1
    assert result["summary"]["declared_plugin_entrypoints"] == [
        "pyproject.toml:[plugin:pytest11]:plugin=plugin:hook"
    ]
