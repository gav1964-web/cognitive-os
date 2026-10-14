from __future__ import annotations

from tests.runtime.no_safe_candidate_recovery_helpers import *

def test_exhausted_mixed_effect_candidate_routes_through_researcher_and_architect(tmp_path: Path) -> None:
    (tmp_path / "legacy.py").write_text(
        "from pathlib import Path\nimport subprocess\n\n"
        "def process_all():\n"
        "    raw = Path('in').read_text()\n"
        "    rows = [x.split(',') for x in raw.splitlines()]\n"
        "    subprocess.run(['echo', rows[0][0]])\n"
        "    Path('out').write_text(str(rows))\n"
        "    return [{'name': row[0].strip()} for row in rows]\n",
        encoding="utf-8",
    )

    result = run_no_safe_candidate_recovery(
        project_root=tmp_path,
        project="legacy",
        technical_spec=_blocked_spec(),
        control_plane=_escalated_control(),
    )

    assert result["status"] == "bounded_rework_ready"
    assert result["route"] == ["reviewer", "researcher", "architect", "developer", "architect"]
    assert result["research_hypothesis"]["proposed_target"] == "legacy.py:normalize_record"
    assert result["architect_reentry_gate"]["status"] == "accepted_for_bounded_rework"
    assert result["architect_reentry_gate"]["can_replace_controlled_stop"] is False
    assert result["provisional_candidate"]["source_backed"] is False
    assert result["provisional_candidate"]["selection_eligible"] is False
    assert result["fallback"]["status"] == "blocked_no_safe_candidate"
    assert result["source_changes"] is False
    assert result["kb_changes"] is False

    registry = ContractRegistry({})
    for key in (
        "failure_packet",
        "research_hypothesis",
        "architect_reentry_gate",
        "provisional_candidate",
        "developer_request",
    ):
        registry.validate_artifact(result[key])
    registry.validate_artifact(result)


def test_missing_source_keeps_controlled_stop(tmp_path: Path) -> None:
    result = run_no_safe_candidate_recovery(
        project_root=tmp_path,
        project="missing",
        technical_spec=_blocked_spec(),
        control_plane=_escalated_control(),
    )

    assert result["status"] == "controlled_stop"
    assert result["research_hypothesis"]["status"] == "knowledge_gap"
    assert result["architect_reentry_gate"]["status"] == "rejected"
    assert result["developer_request"] is None
    assert result["fallback"]["status"] == "blocked_no_safe_candidate"


def test_unrelated_pipeline_does_not_enter_recovery(tmp_path: Path) -> None:
    result = run_no_safe_candidate_recovery(
        project_root=tmp_path,
        project="mature",
        technical_spec={},
        control_plane={"semantic_escalation": {"l4_5_required": False}},
    )

    assert result["status"] == "not_applicable"
    assert result["source_changes"] is False
    assert result["kb_changes"] is False


def test_developer_output_reenters_normal_architect_gate(tmp_path: Path) -> None:
    project = tmp_path / "legacy_recovered"
    project.mkdir()
    (project / "legacy.py").write_text(
        "import json\nimport subprocess\nfrom pathlib import Path\n\n"
        "def normalize_record(row):\n"
        "    return {'name': row[0].strip(), 'value': row[-1].strip()}\n\n"
        "def legacy_process_all():\n"
        "    raw = Path('input.txt').read_text(encoding='utf-8')\n"
        "    rows = [line.split(',') for line in raw.splitlines()]\n"
        "    cleaned = []\n"
        "    for row in rows:\n"
        "        if not row:\n"
        "            continue\n"
        "        subprocess.run(['echo', row[0]], check=False)\n"
        "        cleaned.append(normalize_record(row))\n"
        "    Path('out.json').write_text(json.dumps(cleaned), encoding='utf-8')\n"
        "    return cleaned\n",
        encoding="utf-8",
    )

    result = run_role_pipeline(
        root=Path(__file__).resolve().parents[2],
        project_dir=project,
        goal="Assess recovered legacy project",
        write=False,
    )

    assert result["role_quality"]["selected_extraction_candidate"] == "legacy.py:normalize_record"
    assert result["role_quality"]["implementation_target"] == "legacy.py:normalize_record"
    assert result["role_quality"]["implementation_blocked_no_safe_candidate"] is False
    assert result["recommendation"] in {"approve", "approve_with_risks"}
    assert result["no_safe_candidate_recovery"]["status"] == "not_applicable"


def test_recovery_patch_package_closes_loop_without_editing_corpus(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    project = root / "benchmarks" / "project_analyzer" / "projects" / "legacy_script_dump"
    original = (project / "legacy.py").read_text(encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="legacy_script_dump",
        technical_spec=_blocked_spec(target="legacy.py:legacy_process_all"),
        control_plane=_escalated_control(),
    )

    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )

    assert package["artifact_type"] == "RecoveryPatchPackage"
    assert package["status"] == "prepared"
    assert package["source_code_changes"] is False
    assert package["policy"]["apply_source_enabled"] is False
    assert (project / "legacy.py").read_text(encoding="utf-8") == original
    sandbox = Path(package["sandbox_project"])
    patched = (sandbox / "legacy.py").read_text(encoding="utf-8")
    assert "def normalize_record(row):" in patched
    assert "cleaned.append(normalize_record(row))" in patched

    result = run_role_pipeline(
        root=root,
        project_dir=sandbox,
        goal="Verify recovery patch through the normal role pipeline",
        write=False,
    )

    assert result["role_quality"]["selected_extraction_candidate"] == "legacy.py:normalize_record"
    assert result["role_quality"]["implementation_target"] == "legacy.py:normalize_record"
    assert result["no_safe_candidate_recovery"]["status"] == "not_applicable"
    ContractRegistry({}).validate_artifact(package)


def test_role_pipeline_executor_prepares_recovery_patch_without_applying_source() -> None:
    root = Path(__file__).resolve().parents[2]
    project = root / "benchmarks" / "project_analyzer" / "projects" / "legacy_script_dump"
    original = (project / "legacy.py").read_text(encoding="utf-8")

    result = run_role_pipeline(
        root=root,
        project_dir=project,
        goal="Prepare bounded legacy recovery",
        write=False,
        run_executor=True,
    )

    execution = result["no_safe_candidate_recovery"]["developer_execution"]
    assert execution["artifact_type"] == "RecoveryPatchPackage"
    assert execution["status"] == "prepared"
    assert execution["source_code_changes"] is False
    assert execution["policy"]["apply_source_enabled"] is False
    assert execution["differential_verification"]["status"] == "passed"
    assert execution["differential_verification"]["summary"] == {
        "case_count": 3,
        "passed": 3,
        "failed": 0,
    }
    assert (project / "legacy.py").read_text(encoding="utf-8") == original


def test_recovery_synthesizer_rejects_ambiguous_mapping_boundaries(tmp_path: Path) -> None:
    project = tmp_path / "ambiguous"
    project.mkdir()
    source = (
        "def process_all(rows):\n"
        "    cleaned = []\n"
        "    for row in rows:\n"
        "        cleaned.append({'name': row[0].strip()})\n"
        "        cleaned.append({'value': row[-1].strip()})\n"
        "    return cleaned\n"
    )
    (project / "legacy.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="ambiguous",
        technical_spec=_blocked_spec(),
        control_plane=_escalated_control(),
    )

    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "append_mapping_helper_pattern_not_proven"
    assert package["patches"] == []
    assert (project / "legacy.py").read_text(encoding="utf-8") == source


def test_json_serialization_recovery_synthesizes_and_verifies_holdout(tmp_path: Path) -> None:
    project = tmp_path / "writer"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def write_json(path, value):\n"
        "    Path(path).write_text(json.dumps({'text': value}), encoding='utf-8')\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="writer",
        technical_spec=_blocked_spec(target="writer.py:write_json"),
        control_plane=_escalated_control(),
    )

    assert recovery["research_hypothesis"]["proposed_target"] == "writer.py:serialize_json"
    assert recovery["developer_request"]["patch_recipe"]["id"] == "extract_json_dumps_helper"
    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )

    assert package["status"] == "prepared"
    assert package["patches"][0]["kind"] == "extract_json_dumps_helper"
    assert (project / "writer.py").read_text(encoding="utf-8") == source
    patched = (Path(package["sandbox_project"]) / "writer.py").read_text(encoding="utf-8")
    assert "def serialize_json(value):" in patched
    assert "write_text(serialize_json(value), encoding='utf-8')" in patched

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
        goal="Admit extracted JSON serializer through the normal role chain",
        write=False,
    )
    assert recovered["role_quality"]["selected_extraction_candidate"] == "writer.py:serialize_json"
    assert recovered["role_quality"]["implementation_target"] == "writer.py:serialize_json"
    assert recovered["no_safe_candidate_recovery"]["status"] == "not_applicable"


def test_json_serialization_recovery_rejects_multiple_boundaries(tmp_path: Path) -> None:
    project = tmp_path / "ambiguous_writer"
    project.mkdir()
    source = (
        "import json\n"
        "from pathlib import Path\n\n"
        "def write_json(path, value):\n"
        "    Path(path).write_text(json.dumps(value), encoding='utf-8')\n"
        "    Path(str(path) + '.copy').write_text(json.dumps(value), encoding='utf-8')\n"
    )
    (project / "writer.py").write_text(source, encoding="utf-8")
    recovery = run_no_safe_candidate_recovery(
        project_root=project,
        project="ambiguous_writer",
        technical_spec=_blocked_spec(target="writer.py:write_json"),
        control_plane=_escalated_control(),
    )

    package = synthesize_recovery_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        recovery_route=recovery,
    )

    assert package["status"] == "skipped"
    assert package["reason"] == "json_dumps_helper_pattern_not_proven"
    assert (project / "writer.py").read_text(encoding="utf-8") == source


def test_json_serialization_recipe_transfers_across_real_corpus_shapes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    corpus = root / "benchmarks" / "project_analyzer" / "projects"
    cases = (
        ("data_pipeline_csv_json", "pipeline.py:write_json"),
        ("flask_api_with_mixed_logic", "app.py:write_audit"),
        ("simple_cli_tool", "main.py:write_json"),
    )

    for project_name, target in cases:
        project = corpus / project_name
        relative = target.split(":", 1)[0]
        original = (project / relative).read_bytes()
        recovery = run_no_safe_candidate_recovery(
            project_root=project,
            project=project_name,
            technical_spec=_blocked_spec(target=target),
            control_plane=_escalated_control(),
        )
        package = synthesize_recovery_patch_package(
            execution_dir=tmp_path / project_name,
            project_dir=project,
            recovery_route=recovery,
        )

        assert recovery["research_hypothesis"]["proposed_target"].endswith(":serialize_json")
        assert package["status"] == "prepared"
        assert package["patches"][0]["kind"] == "extract_json_dumps_helper"
        assert (project / relative).read_bytes() == original
        compile(
            (Path(package["sandbox_project"]) / relative).read_text(encoding="utf-8"),
            relative,
            "exec",
        )
