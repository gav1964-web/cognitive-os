from pathlib import Path

from plugins.project_map_report.src.domain_profile import infer_domain_profile
from runtime._parts.role_foundation_field_trial_scope import _primary_language_scope
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.project_architecture_knowledge import load_architecture_knowledge, match_architecture_rule


def _domain_profile(*, root: Path, text: str) -> dict:
    return infer_domain_profile(
        {"root": root.as_posix(), "frameworks": [], "entrypoints": ["main.py"], "routes": 0},
        {"files": [{"path": "main.py", "text": text}]},
        {"files": [{"path": "main.py", "functions": []}]},
        [],
        {"cv2"},
    )


def test_foreign_language_monorepo_with_incidental_python_is_out_of_scope(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    for index in range(500):
        (source / f"proof_{index}.v").write_text("Definition x := 1.\n", encoding="utf-8")
    (tmp_path / "display_lemma.py").write_text("print('helper')\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_explicit_deployment_template_without_product_manifest_is_out_of_scope(tmp_path: Path):
    package = tmp_path / "django_project" / "sample"
    package.mkdir(parents=True)
    for name in ("models.py", "views.py", "urls.py"):
        (package / name).write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "manage.py").write_text("print('manage')\n", encoding="utf-8")
    (tmp_path / "captain-definition").write_text("{}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "This project template is a baseline extracted from production deployment experience.\n",
        encoding="utf-8",
    )

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_computer_vision_tracking_profile_has_rich_contract_summaries(tmp_path: Path):
    profile = _domain_profile(
        root=tmp_path / "traffic-counter",
        text="cv2.VideoCapture source; cv2.findContours(mask); tracker.updateCoords(cx, cy)",
    )

    assert profile["kind"] == "computer_vision_tracking_application"
    assert len(profile["scenario_summary"]) >= 3
    assert profile["input_summary"]
    assert profile["output_summary"]


def test_binary_codec_kb_rule_produces_specific_first_slice():
    facts = {
        "root": "/work/polyglot-codec",
        "frameworks": [],
        "task": "Binary structured data format encoder and decoder",
        "inputs": ["binary stream"],
        "domain_profile": {"kind": "binary_structured_data_codec", "confidence": 0.8, "evidence": ["codec"]},
        "central": ["python/codec.py:encode", "python/codec.py:decode"],
        "capabilities": ["python/codec.py:encode", "python/codec.py:decode"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "binary_structured_data_codec"
    assert match["rule"]["first_slice"]["name"] == "binary_codec_round_trip_slice"


def test_hamiltonian_trajectory_contract_is_profiled():
    contract = contract_archetype_for_target("hmc/integrator.py:solve_trajectory")

    assert contract["contract_family"] == "hamiltonian_trajectory_integration"
    assert "integration_policy" in contract["input_contract"]
