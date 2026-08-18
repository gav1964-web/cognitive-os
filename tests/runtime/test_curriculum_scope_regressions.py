from pathlib import Path

from runtime.role_foundation_field_trial import _primary_language_scope


def test_nested_curriculum_exercises_are_not_a_python_product_boundary(tmp_path: Path):
    project = tmp_path / "course"
    for chapter in ("CV_01", "CV_02"):
        exercises = project / chapter / "exercices"
        exercises.mkdir(parents=True)
        (exercises / "train.py").write_text("def train(): return True\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["reason_code"] == "no_python_owned_product_boundary"
