from __future__ import annotations

from tests.runtime.no_safe_candidate_recovery_helpers import *

def test_json_parse_recovery_closes_role_chain_on_holdout(tmp_path: Path) -> None:
    project = tmp_path / "json_reader"
    project.mkdir()
    source = (
        "import json\nfrom pathlib import Path\n\n"
        "def load_json(path):\n"
        "    payload = json.loads(Path(path).read_text(encoding='utf-8'))\n"
        "    return payload\n"
    )
    (project / "reader.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="json_reader",
        technical_spec=_blocked_spec(target="reader.py:load_json"),
        control_plane=_escalated_control(),
    )

    assert recovery["research_hypothesis"]["proposed_target"] == "reader.py:parse_json"
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )
    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_json_loads_helper"
    patched = (Path(package["sandbox_project"]) / "reader.py").read_text(encoding="utf-8")
    assert "def parse_json(text):" in patched
    assert "parse_json(Path(path).read_text(encoding='utf-8'))" in patched
    assert (project / "reader.py").read_text(encoding="utf-8") == source

    verification = verify_recovery_patch_package(
        project_dir=project,
        patch_package=package,
        verification_dir=tmp_path / "verification",
    )
    assert verification["status"] == "passed"
    assert verification["summary"] == {"case_count": 2, "passed": 2, "failed": 0}
    recovered = run_role_pipeline(
        root=Path(__file__).resolve().parents[2],
        project_dir=Path(package["sandbox_project"]),
        goal="Admit extracted JSON parser through the normal role chain",
        write=False,
    )
    assert recovered["role_quality"]["selected_extraction_candidate"] == "reader.py:parse_json"
    assert recovered["role_quality"]["implementation_target"] == "reader.py:parse_json"
    assert recovered["no_safe_candidate_recovery"]["status"] == "not_applicable"


def test_json_parse_recovery_rejects_multiple_read_boundaries(tmp_path: Path) -> None:
    project = tmp_path / "ambiguous_reader"
    project.mkdir()
    source = (
        "import json\nfrom pathlib import Path\n\n"
        "def load_json(first, second):\n"
        "    return [json.loads(Path(first).read_text()), json.loads(Path(second).read_text())]\n"
    )
    (project / "reader.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="ambiguous_reader",
        technical_spec=_blocked_spec(target="reader.py:load_json"),
        control_plane=_escalated_control(),
    )
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "json_loads_helper_pattern_not_proven"
    assert (project / "reader.py").read_text(encoding="utf-8") == source


def test_json_parse_recipe_transfers_across_independent_plugin_projects(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    cases = (
        (
            root / "plugins" / "project_fact_questions",
            "src/code_fact_analyzers.py:load_code_fact_analyzers",
        ),
        (
            root / "plugins" / "project_map_report",
            "src/language_scope.py:load_language_scope_policy",
        ),
    )
    for index, (project, target) in enumerate(cases):
        recovery = run_no_safe_candidate_recovery(
            project_root=project,
            project=project.name,
            technical_spec=_blocked_spec(target=target),
            control_plane=_escalated_control(),
        )
        package = synthesize_recovery_patch_package(
            execution_dir=tmp_path / f"transfer_{index}",
            project_dir=project,
            recovery_route=recovery,
        )
        assert recovery["research_hypothesis"]["proposed_target"].endswith(":parse_json")
        assert package["status"] == "prepared"
        assert package["patches"][0]["kind"] == "extract_json_loads_helper"


def test_splitlines_recovery_closes_role_chain_on_holdout(tmp_path: Path) -> None:
    project = tmp_path / "line_reader"
    project.mkdir()
    source = (
        "from pathlib import Path\n\n"
        "def load_lines(path):\n"
        "    return Path(path).read_text(encoding='utf-8').splitlines()\n"
    )
    (project / "reader.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="line_reader",
        technical_spec=_blocked_spec(target="reader.py:load_lines"),
        control_plane=_escalated_control(),
    )

    assert recovery["research_hypothesis"]["proposed_target"] == "reader.py:split_lines"
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )
    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_splitlines_helper"
    patched = (Path(package["sandbox_project"]) / "reader.py").read_text(encoding="utf-8")
    assert "def split_lines(text):" in patched
    assert "split_lines(Path(path).read_text(encoding='utf-8'))" in patched
    assert (project / "reader.py").read_text(encoding="utf-8") == source

    verification = verify_recovery_patch_package(
        project_dir=project,
        patch_package=package,
        verification_dir=tmp_path / "verification",
    )
    assert verification["status"] == "passed"
    recovered = run_role_pipeline(
        root=Path(__file__).resolve().parents[2],
        project_dir=Path(package["sandbox_project"]),
        goal="Admit extracted line splitter through the normal role chain",
        write=False,
    )
    assert recovered["role_quality"]["selected_extraction_candidate"] == "reader.py:split_lines"
    assert recovered["role_quality"]["implementation_target"] == "reader.py:split_lines"
    assert recovered["no_safe_candidate_recovery"]["status"] == "not_applicable"


def test_splitlines_recovery_rejects_multiple_boundaries(tmp_path: Path) -> None:
    project = tmp_path / "ambiguous_lines"
    project.mkdir()
    source = (
        "from pathlib import Path\n\n"
        "def load_lines(path):\n"
        "    text = Path(path).read_text()\n"
        "    return text.splitlines(), text.splitlines()\n"
    )
    (project / "reader.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="ambiguous_lines",
        technical_spec=_blocked_spec(target="reader.py:load_lines"),
        control_plane=_escalated_control(),
    )
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "splitlines_helper_pattern_not_proven"


def test_splitlines_recipe_transfers_to_tree_scanner(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    project = root / "packages" / "cognitive-inspect"
    target = "src/cognitive_inspect/tree.py:_line_count"
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project=project.name,
        technical_spec=_blocked_spec(target=target),
        control_plane=_escalated_control(),
    )
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "transfer",
        project_dir=project,
        recovery_route=recovery,
    )

    assert recovery["research_hypothesis"]["proposed_target"] == "src/cognitive_inspect/tree.py:split_lines"
    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_splitlines_helper"


def test_digest_bound_human_apply_and_rollback(tmp_path: Path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    source_project = root / "benchmarks" / "project_analyzer" / "projects" / "legacy_script_dump"
    project = tmp_path / "legacy_apply"
    shutil.copytree(source_project, project)
    original = (project / "legacy.py").read_text(encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="legacy_apply",
        technical_spec=_blocked_spec(target="legacy.py:legacy_process_all"),
        control_plane=_escalated_control(),
    )
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )
    differential = verify_recovery_patch_package(
        project_dir=project,
        patch_package=package,
        verification_dir=tmp_path / "verification",
    )
    package["differential_verification"] = differential
    recovered = run_role_pipeline(
        root=root,
        project_dir=Path(package["sandbox_project"]),
        goal="Admit recovered legacy target",
        write=False,
    )
    admission = build_recovery_patch_admission(
        patch_package=package,
        architect_result=recovered,
    )

    blocked = apply_recovery_patch(
        project_dir=project,
        patch_package=package,
        admission=admission,
        approval=None,
    )
    assert admission["status"] == "ready_for_human_approval"
    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "explicit_human_approval_required"
    assert (project / "legacy.py").read_text(encoding="utf-8") == original

    wrong_digest = apply_recovery_patch(
        project_dir=project,
        patch_package=package,
        admission=admission,
        approval={
            "approved": True,
            "decision": "approve_apply",
            "approver": "test-human",
            "patch_digest": "wrong-digest",
        },
    )
    assert wrong_digest["status"] == "blocked"
    assert wrong_digest["reason"] == "approval_patch_digest_mismatch"

    dry_run = run_recovery_patch_session(
        root=root,
        project_dir=project,
        patch_package=package,
        admission=admission,
    )
    assert dry_run["status"] == "ready_to_apply"
    assert dry_run["apply_requested"] is False

    session = run_recovery_patch_session(
        root=root,
        project_dir=project,
        patch_package=package,
        admission=admission,
        apply=True,
        approval={
            "approved": True,
            "decision": "approve_apply",
            "approver": "test-human",
            "patch_digest": package["patch_digest"],
        },
    )
    receipt = session["apply_receipt"]
    assert session["status"] == "applied_verified"
    assert session["post_apply_verification"]["status"] == "passed"
    assert receipt["status"] == "applied"
    assert receipt["rollback_available"] is True
    assert "def normalize_record(row):" in (project / "legacy.py").read_text(encoding="utf-8")

    rollback = rollback_recovery_patch(project_dir=project, receipt=receipt)
    assert rollback["status"] == "rolled_back"
    assert rollback["matches_precondition"] is True
    assert (project / "legacy.py").read_text(encoding="utf-8") == original

    monkeypatch.setattr("runtime.recovery_patch_session.run_role_pipeline", lambda **_kwargs: {})
    failed_session = run_recovery_patch_session(
        root=root,
        project_dir=project,
        patch_package=package,
        admission=admission,
        apply=True,
        approval={
            "approved": True,
            "decision": "approve_apply",
            "approver": "test-human",
            "patch_digest": package["patch_digest"],
        },
    )
    assert failed_session["status"] == "rolled_back_after_failed_verification"
    assert failed_session["rollback_receipt"]["status"] == "rolled_back"
    assert (project / "legacy.py").read_text(encoding="utf-8") == original

    (project / "legacy.py").write_text(original + "\n# concurrent edit\n", encoding="utf-8")
    drifted = apply_recovery_patch(
        project_dir=project,
        patch_package=package,
        admission=admission,
        approval={
            "approved": True,
            "decision": "approve_apply",
            "approver": "test-human",
            "patch_digest": package["patch_digest"],
        },
    )
    assert drifted["status"] == "blocked"
    assert drifted["reason"] == "source_precondition_mismatch"
    registry = ContractRegistry({})
    registry.validate_artifact(differential)
    registry.validate_artifact(admission)
    registry.validate_artifact(receipt)
    registry.validate_artifact(rollback)
    registry.validate_artifact(dry_run)
    registry.validate_artifact(session)
    registry.validate_artifact(failed_session)
