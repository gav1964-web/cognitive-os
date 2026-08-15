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
    assert row["side_effects"] == ["filesystem"]
    assert "cv2.imread" in row["snippet"]


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
