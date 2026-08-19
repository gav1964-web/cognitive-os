from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from runtime.role_source_context import _python_source_paths, build_source_context


def test_python_source_discovery_tolerates_unreadable_tree(tmp_path):
    with patch.object(Path, "rglob", side_effect=FileNotFoundError("vanished path")):
        assert _python_source_paths(tmp_path) == []


def test_source_context_marks_ambiguous_method_symbol(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "core.py").write_text(
        "class Command:\n"
        "    def parse_args(self, ctx, args):\n"
        "        return args\n"
        "\n"
        "class Group:\n"
        "    def parse_args(self, ctx, args):\n"
        "        return args\n",
        encoding="utf-8",
    )

    context = build_source_context(
        project_root=str(project),
        project_report={},
        sources=["core.py:parse_args"],
    )

    snippet = context["core.py:parse_args"]["snippet"]
    assert snippet["target_binding"] == "ambiguous_method_symbol"
    assert {row["class_name"] for row in snippet["symbol_occurrences"]} == {"Command", "Group"}


def test_source_context_resolves_class_qualified_method_symbol(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "core.py").write_text(
        "class Command:\n    def parse_args(self):\n        return 'command'\n\n"
        "class Group:\n    def parse_args(self):\n        return 'group'\n",
        encoding="utf-8",
    )

    context = build_source_context(
        project_root=str(project), project_report={}, sources=["core.py:Group.parse_args"]
    )

    snippet = context["core.py:Group.parse_args"]["snippet"]
    assert snippet["target_binding"] == "method_symbol"
    assert snippet["owner_class"] == "Group"
    assert "return 'group'" in snippet["text"]


def test_source_context_reads_extensionless_python_executable(tmp_path: Path):
    script = tmp_path / "protocol"
    script.write_text(
        "#!/usr/bin/python\nclass Protocol:\n    def parse_spec(self, spec):\n        return spec.split(',')\n",
        encoding="utf-8",
    )

    context = build_source_context(
        project_root=str(tmp_path), project_report={}, sources=["protocol:parse_spec"]
    )

    assert context["protocol:parse_spec"]["snippet"]["owner_class"] == "Protocol"


def test_source_context_marks_unique_method_symbol_owner(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "core.py").write_text(
        "class Parameter:\n"
        "    def handle_parse_result(self, ctx, opts, args):\n"
        "        return None, args\n",
        encoding="utf-8",
    )

    context = build_source_context(project_root=str(project), project_report={}, sources=["core.py:handle_parse_result"])
    snippet = context["core.py:handle_parse_result"]["snippet"]

    assert snippet["target_binding"] == "method_symbol"
    assert snippet["owner_class"] == "Parameter"
    assert snippet["structural_contract"]["inferred_output_type"] == "TupleLike"
    assert snippet["structural_contract"]["source_body_complete"] is True


def test_source_context_infers_contract_from_complete_body_beyond_snippet_prefix(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    padding = "".join(f"    value += 'part-{index}'\n" for index in range(220))
    (project / "builder.py").write_text(
        "def build_text():\n    value = 'start'\n" + padding + "    return value\n",
        encoding="utf-8",
    )

    context = build_source_context(
        project_root=str(project), project_report={}, sources=["builder.py:build_text"]
    )

    snippet = context["builder.py:build_text"]["snippet"]
    assert snippet["text_truncated"] is True
    assert snippet["structural_contract"]["inferred_output_type"] == "str"
    assert snippet["structural_contract"]["source_body_complete"] is True


def test_source_context_marks_nested_function_parent(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "workflow.py").write_text(
        "def outer(limit):\n    def inner(value):\n        return value < limit\n    return inner\n",
        encoding="utf-8",
    )

    context = build_source_context(project_root=str(project), project_report={}, sources=["workflow.py:inner"])
    snippet = context["workflow.py:inner"]["snippet"]

    assert snippet["target_binding"] == "nested_function"
    assert snippet["parent_function"] == "outer"


def test_source_context_finds_function_declared_in_top_level_else(tmp_path: Path):
    source = tmp_path / "conditional.py"
    source.write_text(
        "if False:\n"
        "    VALUE = 1\n"
        "else:\n"
        "    def normalize(value):\n"
        "        return value.strip()\n",
        encoding="utf-8",
    )

    context = build_source_context(
        project_root=str(tmp_path),
        project_report={},
        sources=["conditional.py:normalize"],
        function_scoped_dependencies=True,
    )

    snippet = context["conditional.py:normalize"]["snippet"]
    assert snippet["target_binding"] == "function_symbol"
    assert snippet["structural_contract"]["inferred_output_type"] == "str"


def test_source_context_builds_module_script_context(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "basics.py").write_text(
        "import cv2\n\nimage = cv2.imread('dog.png')\nprint(image.shape)\n",
        encoding="utf-8",
    )

    context = build_source_context(project_root=str(project), project_report={}, sources=["basics.py"])

    row = context["basics.py"]
    assert row["kind"] == "module_script"
    assert row["module_imports"] == ["cv2"]
    assert row["side_effects"] == ["filesystem", "stdout"]
    assert "cv2.imread" in row["snippet"]


def test_source_context_extracts_module_cli_environment_and_output_contract(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "backup.py").write_text(
        "import json\nimport os\nimport sys\nimport github\n"
        "username = sys.argv[1]\noutfile = sys.argv[2]\n"
        "client = github.Github(os.environ['GITHUB_TOKEN'])\n"
        "with open(outfile, 'w') as stream:\n    stream.write(json.dumps({'user': username}))\n",
        encoding="utf-8",
    )

    row = build_source_context(project_root=str(project), project_report={}, sources=["backup.py"])["backup.py"]

    assert row["signature"]["args"] == [
        {"name": "username", "annotation": "str"},
        {"name": "outfile", "annotation": "PathLike"},
        {"name": "github_token", "annotation": "SecretStr"},
    ]
    assert row["structural_contract"]["inferred_output_type"] == "JsonFileArtifact"
    assert row["contract_side_effects"] == ["environment", "filesystem_write", "network"]


def test_source_context_infers_nested_network_and_filesystem_calls(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "transfer.py").write_text(
        "def forward(transport, path):\n"
        "    def callback():\n"
        "        sock = socket.socket()\n"
        "        sock.connect(('localhost', 22))\n"
        "    transport.request_port_forward(handler=callback)\n"
        "    with open(path) as payload:\n"
        "        transport.sftp.put(payload)\n",
        encoding="utf-8",
    )

    context = build_source_context(project_root=str(project), project_report={}, sources=["transfer.py:forward"])

    assert context["transfer.py:forward"]["snippet"]["side_effects"] == ["filesystem_read", "network"]


def test_source_context_tolerates_stale_missing_symbol(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "core.py").write_text("def present():\n    return 1\n", encoding="utf-8")

    context = build_source_context(project_root=str(project), project_report={}, sources=["core.py:missing"])

    assert "core.py:missing" not in context


def test_source_context_preserves_bounded_policy_provenance(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "policy.py").write_text(
        "def can_run(kind: str, allowed: set[str]) -> bool:\n    return kind in allowed\n",
        encoding="utf-8",
    )
    report = {
        "answers": {
            "3_capabilities": {
                "bounded_policy_decisions": [
                    {"path": "policy.py", "name": "can_run", "args": [], "returns": "bool"}
                ]
            },
            "6_runtime_extraction_readiness": {
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [
                        {"capability": "policy.py:can_run", "candidate_level": "bounded_policy", "candidate_score": 90}
                    ]
                }
            },
        }
    }

    row = build_source_context(project_root=str(project), project_report=report, sources=["policy.py:can_run"])[
        "policy.py:can_run"
    ]

    assert row["kind"] == "bounded_policy"
    assert row["candidate_level"] == "bounded_policy"


def test_source_context_marks_unresolved_runtime_name_not_standalone(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "legacy.py").write_text(
        "def render(values):\n    return [xrange(value) for value in values]\n",
        encoding="utf-8",
    )

    row = build_source_context(project_root=str(project), project_report={}, sources=["legacy.py:render"])[
        "legacy.py:render"
    ]

    assert row["snippet"]["unresolved_runtime_names"] == ["xrange"]
    assert row["dependency_readiness"]["status"] == "source_context_required"


def test_source_context_records_unknown_global_without_automatic_block(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "handler.py").write_text(
        "def handle(value):\n    return injected_framework_adapter(value)\n",
        encoding="utf-8",
    )

    row = build_source_context(project_root=str(project), project_report={}, sources=["handler.py:handle"])[
        "handler.py:handle"
    ]

    assert row["snippet"]["unresolved_runtime_names"] == ["injected_framework_adapter"]
    assert row["dependency_readiness"]["status"] == "ready"


def test_source_context_preserves_positional_only_and_keyword_only_annotations(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "factory.py").write_text(
        "def build(value: str, /, *, arity: int = 1):\n    return value * arity\n",
        encoding="utf-8",
    )

    row = build_source_context(
        project_root=str(project), project_report={}, sources=["factory.py:build"]
    )["factory.py:build"]

    assert row["signature"] == {
        "args": [{"name": "value", "annotation": "str"}],
        "kwonlyargs": [{"name": "arity", "annotation": "int"}],
        "returns": "",
    }
