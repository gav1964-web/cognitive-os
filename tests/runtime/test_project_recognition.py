from runtime.project_recognition import attach_project_recognition, recognize_project


def _report(kind: str):
    return {"answers": {"1_scope": {"domain_profile": {"kind": kind}}}}


def test_recognition_routes_known_supported_project_to_full_chain():
    decision = recognize_project(
        project="normalizer",
        project_report=_report("schema_validation_library"),
    )

    assert decision["status"] == "recognized"
    assert decision["classification"]["project_stratum"] == "library_pure_transform"
    assert decision["role_route"]["status"] == "configured_role_chain"
    assert decision["pilot_route"]["status"] == "eligible_for_full_chain"


def test_recognition_routes_unknown_authoritative_archetype_to_researcher():
    decision = recognize_project(
        project="mystery-cli",
        project_report=_report("event_log_projection"),
    )

    assert decision["status"] == "unknown"
    assert decision["role_route"]["status"] == "unknown_project_lifecycle"
    assert decision["pilot_route"]["status"] == "analysis_only_stop"


def test_recognition_keeps_identity_conflict_ambiguous():
    decision = recognize_project(
        project="athina-sdk",
        project_report=_report("docs_site_generator"),
    )

    assert decision["status"] == "ambiguous"
    assert decision["confidence"] <= 0.65
    assert decision["role_route"]["status"] == "recognition_review"


def test_recognition_stops_known_but_prohibited_risk_before_full_chain():
    decision = recognize_project(
        project="jobs",
        project_report=_report("async_worker_queue"),
    )

    assert decision["status"] == "recognized"
    assert decision["pilot_route"]["status"] == "analysis_only_stop"
    assert "risk_profile_allowed" in decision["pilot_route"]["blocking_reasons"]


def test_recognition_admits_repeated_pure_target_inside_stateful_project(tmp_path):
    source = tmp_path / "pkg" / "parse.py"
    source.parent.mkdir()
    source.write_text("def parse(value):\n    return value.strip()\n", encoding="utf-8")
    classification = {
        "project_stratum": "cli_local_tool",
        "project_archetype": "import_sorting_tool",
        "classification_source": "explicit",
        "risk_profiles": ["deterministic", "filesystem", "stateful"],
    }

    decision = recognize_project(
        project="formatter",
        project_report=_report("import_sorting_tool"),
        classification=classification,
        project_dir=tmp_path,
        change_request={
            "authority": "failing_contract_test",
            "repeat_count": 2,
            "target": "pkg/parse.py:parse",
        },
    )

    assert decision["pilot_route"]["status"] == "eligible_for_full_chain"
    assert decision["pilot_route"]["scope"] == "authoritative_failure_target"
    assert decision["pilot_route"]["target_scope_admission"]["waived_project_risks"] == ["stateful"]


def test_recognition_rejects_target_with_direct_write_effect(tmp_path):
    source = tmp_path / "pkg" / "writer.py"
    source.parent.mkdir()
    source.write_text(
        "def save(path, value):\n    path.write_text(value)\n", encoding="utf-8"
    )
    classification = {
        "project_stratum": "cli_local_tool",
        "project_archetype": "import_sorting_tool",
        "classification_source": "explicit",
        "risk_profiles": ["deterministic", "filesystem", "stateful"],
    }

    decision = recognize_project(
        project="formatter",
        project_report=_report("import_sorting_tool"),
        classification=classification,
        project_dir=tmp_path,
        change_request={
            "authority": "failing_contract_test",
            "repeat_count": 2,
            "target": "pkg/writer.py:save",
        },
    )

    assert decision["pilot_route"]["status"] == "analysis_only_stop"
    assert decision["pilot_route"]["target_scope_admission"]["reason"] == "target_has_prohibited_direct_effects"


def test_recognition_allows_literal_read_only_open_in_scoped_target(tmp_path):
    source = tmp_path / "pkg" / "reader.py"
    source.parent.mkdir()
    source.write_text(
        "def load(path):\n    with open(path, 'rb') as stream:\n        return stream.read()\n",
        encoding="utf-8",
    )
    classification = {
        "project_stratum": "framework_plugin_build",
        "project_archetype": "docs_site_generator",
        "classification_source": "explicit",
        "risk_profiles": ["deterministic", "filesystem", "stateful"],
    }

    decision = recognize_project(
        project="docs",
        project_report=_report("docs_site_generator"),
        classification=classification,
        project_dir=tmp_path,
        change_request={
            "authority": "failing_contract_test",
            "repeat_count": 2,
            "target": "pkg/reader.py:load",
        },
    )

    assert decision["pilot_route"]["status"] == "eligible_for_full_chain"
    assert decision["pilot_route"]["target_scope_admission"]["status"] == "admitted"


def test_recognition_rejects_literal_write_open_in_scoped_target(tmp_path):
    source = tmp_path / "pkg" / "writer.py"
    source.parent.mkdir()
    source.write_text("def save(path):\n    return open(path, 'wb')\n", encoding="utf-8")
    classification = {
        "project_stratum": "framework_plugin_build",
        "project_archetype": "docs_site_generator",
        "classification_source": "explicit",
        "risk_profiles": ["deterministic", "filesystem", "stateful"],
    }

    decision = recognize_project(
        project="docs",
        project_report=_report("docs_site_generator"),
        classification=classification,
        project_dir=tmp_path,
        change_request={
            "authority": "failing_contract_test",
            "repeat_count": 2,
            "target": "pkg/writer.py:save",
        },
    )

    assert decision["pilot_route"]["status"] == "analysis_only_stop"
    scoped = decision["pilot_route"]["target_scope_admission"]
    assert scoped["observed_forbidden_calls"] == ["open"]


def test_recognition_rejects_open_without_explicit_read_mode(tmp_path):
    source = tmp_path / "pkg" / "reader.py"
    source.parent.mkdir()
    source.write_text("def load(path):\n    return open(path)\n", encoding="utf-8")
    classification = {
        "project_stratum": "framework_plugin_build",
        "project_archetype": "docs_site_generator",
        "classification_source": "explicit",
        "risk_profiles": ["deterministic", "filesystem", "stateful"],
    }

    decision = recognize_project(
        project="docs",
        project_report=_report("docs_site_generator"),
        classification=classification,
        project_dir=tmp_path,
        change_request={
            "authority": "failing_contract_test",
            "repeat_count": 2,
            "target": "pkg/reader.py:load",
        },
    )

    assert decision["pilot_route"]["status"] == "analysis_only_stop"


def test_recognition_keeps_low_confidence_analyzer_hypothesis_ambiguous():
    report = _report("code_generation_toolkit")
    report["answers"]["1_scope"]["domain_profile"].update({
        "confidence": 0.63,
        "evidence": ["matched text markers: render_"],
    })
    report["answers"]["2_execution"] = {
        "central_flow_nodes": [{"side_effects": ["filesystem"]}],
    }

    decision = recognize_project(project="unrelated-render-helper", project_report=report)

    assert decision["status"] == "ambiguous"
    assert decision["confidence"] == 0.63
    assert decision["ambiguity_reasons"] == ["project_analyzer_confidence_below_threshold"]
    assert decision["evidence"]["project_analyzer_evidence"] == ["matched text markers: render_"]


def test_attached_recognition_is_role_pipeline_context():
    report = _report("schema_validation_library")
    decision = recognize_project(project="normalizer", project_report=report)

    attached = attach_project_recognition(report, decision)

    assert attached["project_recognition"] == decision
    assert attached["project_classification"] == decision["classification"]
