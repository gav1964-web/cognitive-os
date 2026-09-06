from __future__ import annotations

from tests.runtime.project_native_failure_intake_helpers import *

def test_native_intake_policy_disables_external_pytest_plugin_autoload():
    from runtime.project_development import load_project_development_policy

    intake = load_project_development_policy()["native_failure_intake"]

    assert intake["disable_external_pytest_plugin_autoload"] is True


def test_bounded_process_terminates_at_timeout(tmp_path):
    started = time.monotonic()

    try:
        _run_bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            env=dict(os.environ),
            timeout=1,
        )
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError("process did not time out")

    assert time.monotonic() - started < 8


def test_native_pytest_targets_selects_legacy_root_suite_when_it_is_only_suite(tmp_path):
    (tmp_path / "tests.py").write_text("pass\n", encoding="utf-8")

    assert _native_pytest_targets(tmp_path, None) == ["tests.py"]
    assert _native_pytest_targets(tmp_path, ["tests.py::Case::test_one"]) == [
        "tests.py::Case::test_one"
    ]


def test_native_pytest_targets_keeps_default_discovery_when_standard_tests_exist(tmp_path):
    (tmp_path / "tests.py").write_text("pass\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_module.py").write_text("pass\n", encoding="utf-8")

    assert _native_pytest_targets(tmp_path, None) == []


def test_intake_work_root_uses_short_workspace_local_path(tmp_path):
    work_root = _intake_work_root(
        tmp_path, "20260829T040858754654Z", {"work_directory": ".nfi"}
    )

    assert work_root.parent == tmp_path / ".nfi"
    assert len(str(work_root.relative_to(tmp_path))) < 32


def test_probe_path_bootstrap_prepends_project_source_and_overlay(tmp_path):
    environment = tmp_path / "probe_env"
    project = tmp_path / "project"
    overlay = tmp_path / "overlay"
    (project / "src").mkdir(parents=True)
    overlay.mkdir()

    bootstrap = _write_probe_path_bootstrap(
        environment,
        project,
        {"probe_path_bootstrap": True, "dependency_overlay_path": str(overlay)},
    )

    assert bootstrap is not None
    content = bootstrap.read_text(encoding="utf-8")
    assert content.startswith("import sys; sys.path[:0]")
    paths = ast.literal_eval(content.split("=", 1)[1].strip())
    assert paths == [
        str((project / "src").resolve()),
        str(project.resolve()),
        str(overlay.resolve()),
    ]


def test_project_version_hint_uses_static_pyproject_version(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\nversion = '2.4.1'\n", encoding="utf-8"
    )

    assert _project_version_hint(tmp_path) == "2.4.1"


def test_project_version_hint_prefers_exact_git_tag(tmp_path, monkeypatch):
    class Completed:
        returncode = 0
        stdout = "v3.1.0\n"

    monkeypatch.setattr(
        "runtime.project_native_failure_process.subprocess.run",
        lambda *args, **kwargs: Completed(),
    )

    assert _project_version_hint(tmp_path) == "3.1.0"


def test_project_version_hint_uses_hermetic_fallback_for_vcs_backend(tmp_path, monkeypatch):
    class Completed:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(
        "runtime.project_native_failure_process.subprocess.run",
        lambda *args, **kwargs: Completed(),
    )
    (tmp_path / "pyproject.toml").write_text(
        "[build-system]\nrequires = ['hatch-vcs']\n[project]\ndynamic = ['version']\n",
        encoding="utf-8",
    )

    assert _project_version_hint(tmp_path) == "0.0.0"


def test_git_build_metadata_is_copied_only_for_declared_version_backend(tmp_path):
    project = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    (project / ".git" / "objects").mkdir(parents=True)
    sandbox.mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (project / ".git" / "objects" / "pack").write_bytes(b"git-data")
    (project / "pyproject.toml").write_text(
        "[tool.setuptools-git-versioning]\nenabled = true\n", encoding="utf-8"
    )

    copied = _copy_git_build_metadata(project, sandbox, {})

    assert copied is True
    assert (sandbox / ".git" / "HEAD").is_file()


def test_git_build_metadata_copy_fails_closed_on_size_limit(tmp_path):
    project = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    (project / ".git").mkdir(parents=True)
    sandbox.mkdir()
    (project / ".git" / "HEAD").write_bytes(b"too-large")
    (project / "pyproject.toml").write_text(
        "[tool.setuptools_scm]\n", encoding="utf-8"
    )

    copied = _copy_git_build_metadata(
        project, sandbox, {"maximum_git_metadata_bytes": 2}
    )

    assert copied is False
    assert not (sandbox / ".git").exists()


def test_git_build_metadata_resolves_linked_worktree_pointer(tmp_path):
    repository = tmp_path / "repository"
    common = repository / ".git"
    linked = common / "worktrees" / "source"
    project = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    (common / "objects").mkdir(parents=True)
    linked.mkdir(parents=True)
    project.mkdir()
    sandbox.mkdir()
    (common / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (common / "objects" / "pack").write_bytes(b"git-data")
    (linked / "HEAD").write_text("0123456789abcdef\n", encoding="utf-8")
    (linked / "commondir").write_text("../..\n", encoding="utf-8")
    (project / ".git").write_text(f"gitdir: {linked.as_posix()}\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[tool.hatch.version]\nsource = 'vcs'\n", encoding="utf-8"
    )

    copied = _copy_git_build_metadata(project, sandbox, {})

    assert copied is True
    assert (sandbox / ".git" / "HEAD").read_text(encoding="utf-8") == "0123456789abcdef\n"
    assert (sandbox / ".git" / "objects" / "pack").read_bytes() == b"git-data"


def test_git_build_metadata_rejects_malformed_worktree_pointer(tmp_path):
    project = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    project.mkdir()
    sandbox.mkdir()
    (project / ".git").write_text("not-a-gitdir\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[tool.setuptools_scm]\n", encoding="utf-8")

    copied = _copy_git_build_metadata(project, sandbox, {})

    assert copied is False
    assert not (sandbox / ".git").exists()


def test_test_file_shards_are_balanced_deterministic_and_lossless(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    for index, size in enumerate((10, 20, 30, 40, 50)):
        (tests / f"test_{index}.py").write_text("x" * size, encoding="utf-8")

    first = _test_file_shards(tmp_path, {"maximum_shards": 3})
    second = _test_file_shards(tmp_path, {"maximum_shards": 3})

    assert first == second
    assert sorted(path for shard in first for path in shard) == [
        f"tests/test_{index}.py" for index in range(5)
    ]
    assert len(first) == 3


def test_test_file_shards_fail_closed_above_file_limit(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    for index in range(3):
        (tests / f"test_{index}.py").write_text("pass\n", encoding="utf-8")

    assert _test_file_shards(tmp_path, {"maximum_shard_test_files": 2}) == []


def test_collected_nodeids_are_normalized_deduplicated_and_bounded():
    output = (
        "tests\\test_cli.py::test_one\n"
        "tests/test_cli.py::test_two[value]\n"
        "tests\\test_cli.py::test_one\n"
        "2 tests collected\n"
    )

    assert _collected_nodeids(output, {}) == [
        "tests/test_cli.py::test_one",
        "tests/test_cli.py::test_two[value]",
    ]
    assert _collected_nodeids(output, {"maximum_collected_nodeids": 1}) == []
    assert _collected_nodeids(output, {"maximum_collected_nodeid_chars": 10}) == []
    assert _collected_nodeids(
        "tests/test_cli.py::test_case[" + ("x" * 3000) + "]\n", {}
    ) == []


def test_nodeid_normalization_preserves_escaped_parameter_payload():
    nodeid = r"tests\test_cli.py::test_case[value\nnext]"

    assert _normalize_nodeid(nodeid) == r"tests/test_cli.py::test_case[value\nnext]"


def test_shard_cache_is_content_addressed_and_invalidates_on_source_change(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    overlay = tmp_path / "overlay"
    cache = tmp_path / "cache"
    for project in (first, second):
        project.mkdir()
        (project / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    overlay.mkdir()
    (overlay / "dependency.py").write_text("VERSION = 1\n", encoding="utf-8")
    intake = {
        "shard_cache_enabled": True,
        "shard_cache_path": str(cache),
        "dependency_overlay_path": str(overlay),
        "pytest_arguments": ["-q"],
    }
    nodeids = ["tests/test_module.py"]

    first_key = _shard_cache_key(first, nodeids, intake, mode="coarse")
    second_key = _shard_cache_key(second, nodeids, intake, mode="coarse")
    assert first_key == second_key
    assert first_key is not None
    _store_cached_shard_pass(first_key, intake, nodeids, mode="coarse")
    assert _load_cached_shard_pass(second_key, intake) is True

    (second / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
    intake["_shard_project_digests"].pop(str(second.resolve()))
    changed_key = _shard_cache_key(second, nodeids, intake, mode="coarse")
    assert changed_key != first_key
    assert _load_cached_shard_pass(changed_key, intake) is False


def test_shard_cache_rejects_corrupt_record(tmp_path):
    intake = {"shard_cache_path": str(tmp_path)}
    (tmp_path / "broken.json").write_text("not-json", encoding="utf-8")

    assert _load_cached_shard_pass("broken", intake) is False


def test_project_digest_ignores_native_runtime_directories(tmp_path):
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = _project_digest(tmp_path)
    runtime = tmp_path / ".pytest-native-intake"
    runtime.mkdir()
    (runtime / "state.txt").write_text("generated", encoding="utf-8")

    assert _project_digest(tmp_path) == before


def test_hermetic_user_environment_stays_next_to_sandbox_project(tmp_path):
    project = tmp_path / "run_01" / "project"
    project.mkdir(parents=True)

    env = _hermetic_user_environment(project, {"hermetic_user_environment": True})

    home = project.parent / ".native-user"
    assert env["HOME"] == str(home)
    assert env["USERPROFILE"] == str(home)
    assert env["APPDATA"] == str(home / "AppData" / "Roaming")
    assert env["LOCALAPPDATA"] == str(home / "AppData" / "Local")
    assert env["GIT_CEILING_DIRECTORIES"] == str(project.parent.resolve())
    assert not str(home).startswith(str(project) + "\\")


def test_missing_platform_stdlib_capability_is_environment_blocker(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/test_tz.py::test_tzset\nAttributeError: module 'time' has no attribute 'tzset'",
        {"maximum_output_chars": 12000},
    )

    assert result["status"] == "environment_blocked"


def test_parameterized_failure_nodeid_preserves_spaces(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/test_merge.py::test_case[zero int] - AssertionError: mismatch\n"
        "1 failed in 0.1s",
        {},
    )

    assert result["failing_nodeids"] == ["tests/test_merge.py::test_case[zero int]"]


def test_falsy_empty_failure_kind_requires_semantic_target_and_test_evidence():
    target = "deepmerge/strategy/type_conflict.py:TypeConflictStrategies.strategy_override_if_not_empty"

    assert _failure_kind(
        target,
        "AssertionError: assert 'base' == 0",
        ["tests/test_type_conflict.py::test_merge_if_not_empty_falsy[zero int]"],
    ) == "falsy_primitive_empty_contract"
    assert _failure_kind(target, "AssertionError: assert 'base' == 0", []) is None


def test_incomplete_import_failure_kind_requires_traceback_target_and_test_evidence():
    target = "autoflake.py:extract_package_name"

    assert _failure_kind(
        target,
        "IndexError: list index out of range",
        ["test_autoflake.py::UnitTests::test_extract_package_name_with_incomplete_import"],
    ) == "incomplete_import_token_contract"
    assert _failure_kind(target, "IndexError: list index out of range", []) is None


def test_duplicate_cli_option_failure_kind_requires_target_and_test_evidence():
    target = "src/rich_cli/__main__.py:main"
    summary = (
        "test_main.DuplicateOptionsError: Duplicate option added to command. "
        "The following option appears more than once:"
    )

    assert _failure_kind(
        target,
        summary,
        ["tests/test_main.py::test_duplicate_option_flags_raises_exception"],
    ) == "duplicate_cli_short_option_contract"
    assert _failure_kind(target, summary, []) is None
