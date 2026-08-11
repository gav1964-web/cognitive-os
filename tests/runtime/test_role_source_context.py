from __future__ import annotations

from pathlib import Path

from runtime.role_source_context import build_source_context


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

    assert context["transfer.py:forward"]["snippet"]["side_effects"] == ["filesystem", "network"]
