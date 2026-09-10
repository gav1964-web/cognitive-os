from tools.pilot_supervised_run import _artifact_path


def test_pilot_run_artifact_paths_include_stable_run_identity(tmp_path):
    first = _artifact_path(tmp_path, "pilot_run", "pilot_first")
    second = _artifact_path(tmp_path, "pilot_run", "pilot_second")

    assert first != second
    assert first.name.endswith("_pilot_first.json")
    assert second.name.endswith("_pilot_second.json")
