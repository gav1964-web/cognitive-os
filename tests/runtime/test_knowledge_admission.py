from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.knowledge_admission import (
    build_kb_candidate,
    can_promote_candidate,
    grouped_candidate_report,
    kb_candidate_from_generic_project,
    knowledge_candidate_report,
    load_kb_candidates,
    write_kb_candidate,
)


def test_kb_candidate_needs_multiple_confirmed_cases():
    candidate = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record={"rule_id": "signing_utility"},
        source_cases=[{"project": "itsdangerous", "status": "confirmed"}],
        teacher_reference="Codex analysis notes",
        teacher_approved=True,
        codex_approved=True,
    )

    assert candidate["status"] == "collect_more_cases"
    assert can_promote_candidate(candidate) is False
    assert candidate["evidence_policy"]["automatic_self_promotion_forbidden"] is True


def test_kb_candidate_requires_teacher_and_codex_approval_after_cases():
    cases = [{"project": f"p{i}", "status": "confirmed"} for i in range(3)]

    needs_teacher = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record={"rule_id": "signing_utility"},
        source_cases=cases,
        teacher_reference="External teacher review",
        teacher_approved=False,
        codex_approved=True,
    )
    needs_codex = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record={"rule_id": "signing_utility"},
        source_cases=cases,
        teacher_reference="External teacher review",
        teacher_approved=True,
        codex_approved=False,
    )
    ready = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record={"rule_id": "signing_utility"},
        source_cases=cases,
        teacher_reference="External teacher review",
        teacher_approved=True,
        codex_approved=True,
    )

    assert needs_teacher["status"] == "needs_teacher_approval"
    assert needs_codex["status"] == "needs_codex_approval"
    assert ready["status"] == "ready_for_human_merge"
    assert can_promote_candidate(ready) is True


def test_kb_candidate_store_and_report(tmp_path):
    candidate = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record={"rule_id": "signing_utility"},
        source_cases=[{"project": f"p{i}", "status": "confirmed"} for i in range(3)],
        teacher_reference="External teacher review",
        teacher_approved=True,
        codex_approved=True,
    )

    path = write_kb_candidate(candidate, root=tmp_path)
    loaded = load_kb_candidates(root=tmp_path)
    report = knowledge_candidate_report(loaded)

    assert path.exists()
    assert loaded[0]["candidate_id"] == candidate["candidate_id"]
    assert report["candidate_count"] == 1
    assert report["ready_for_human_merge"] == [candidate["candidate_id"]]
    assert report["policy"]["automatic_merge_forbidden"] is True


def test_grouped_candidate_report_counts_confirmed_cases():
    candidates = [
        build_kb_candidate(
            record_type="project_archetype_rule",
            proposed_record={"rule_id": "schema_validation_library", "label": "schema"},
            source_cases=[{"project": project, "status": "confirmed"}],
            teacher_reference="PyPI metadata",
        )
        for project in ("pydantic", "jsonschema", "marshmallow")
    ]

    report = grouped_candidate_report(candidates)
    group = report["groups"][0]

    assert group["group_key"] == "project_archetype_rule:schema_validation_library"
    assert group["confirmed_case_count"] == 3
    assert group["gate_status"] == "needs_teacher_approval"
    assert report["ready_for_teacher_review"] == ["project_archetype_rule:schema_validation_library"]


def test_kb_candidate_from_generic_project_stays_staged():
    candidate = kb_candidate_from_generic_project(
        project="itsdangerous",
        proposed_rule_id="signing_utility",
        label="signing/token utility",
        candidate_signals=["sign", "serializer", "token"],
        first_slice_hint="sign_verify_contract_slice",
        source_cases=[{"project": "itsdangerous", "status": "confirmed"}],
        teacher_reference="Codex noted generic python_project fallback",
    )

    assert candidate["status"] == "collect_more_cases"
    assert candidate["proposed_record"]["evidence_strength"] == "weak"
    assert candidate["proposed_record"]["candidate_origin"]["project"] == "itsdangerous"


def test_knowledge_candidates_cli_report(tmp_path):
    root = Path(__file__).resolve().parents[2]
    candidate = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record={"rule_id": "signing_utility"},
        source_cases=[{"project": f"p{i}", "status": "confirmed"} for i in range(3)],
        teacher_reference="External teacher review",
        teacher_approved=True,
        codex_approved=True,
    )
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "knowledge_candidates.py"),
            "--root",
            str(tmp_path),
            "write",
            "--candidate",
            str(candidate_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = subprocess.run(
        [sys.executable, str(root / "tools" / "knowledge_candidates.py"), "--root", str(tmp_path), "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(report.stdout)
    assert payload["candidate_count"] == 1
    assert payload["by_status"] == {"ready_for_human_merge": 1}
