from pathlib import Path

from runtime.programmer_patch_synthesizer_core import synthesize_patch_package


def _plan(target: str, operator: str, *, authorized: bool = True) -> dict:
    intent = {
        "operator_id": operator,
        "allowed_operator_ids": [operator],
    }
    if authorized:
        intent["authority"] = "explicit_training_replay"
    return {
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target},
        "expected_files": [target.split(":", 1)[0]],
        "implementation_delta": {"status": "ready", "intent": intent},
    }


def test_training_repair_requires_explicit_authority(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "more.py").write_text(
        "def split_before(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n\n"
        "def split_after(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n",
        encoding="utf-8",
    )
    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "more.py:split_before", "guard_empty_materialized_fast_path", authorized=False
        ),
        test_plan={},
    )
    assert package["status"] == "blocked"
    assert package["reason"] == "training_replay_authority_required"


def test_empty_fast_path_training_patch_is_bounded(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "more.py").write_text(
        "def split_before(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n\n"
        "def split_after(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n",
        encoding="utf-8",
    )
    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "more.py:split_before", "guard_empty_materialized_fast_path"
        ),
        test_plan={},
    )
    patched = Path(package["sandbox_project"]) / "more.py"
    assert package["status"] == "prepared"
    assert patched.read_text(encoding="utf-8").count("buf = list(iterable)") == 2
    assert "yield list(iterable)" in (project / "more.py").read_text(encoding="utf-8")


def test_numeric_range_training_patch_preserves_capture_numbering(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "factor.py").write_text(
        "import re\n\n"
        "def expand_ranges(value: str) -> str:\n"
        "    def expand(match):\n"
        "        return match.group()\n"
        "    return re.sub(\n"
        "        r\"\"\"\n"
        "        (\n"
        "            ( \\d+ ) - ( \\d+ )   # closed range: start-end\n"
        "            |\n"
        "            ( \\d+ ) -           # right-open range: start-\n"
        "            |\n"
        "            (?<= [{,] ) - ( \\d+ )\n"
        "        )\n"
        "        (?: , | \\} )\n"
        "        \"\"\", expand, value, flags=re.VERBOSE)\n",
        encoding="utf-8",
    )
    package = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=_plan(
            "factor.py:expand_ranges", "require_left_token_boundary_for_numeric_range"
        ),
        test_plan={},
    )
    text = (Path(package["sandbox_project"]) / "factor.py").read_text(encoding="utf-8")
    assert package["status"] == "prepared"
    assert "(?<! [\\w.] )" in text
    assert "(?:\n                ( \\d+ )" in text
