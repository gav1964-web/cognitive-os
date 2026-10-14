"""A declared CLI can expose a library without erasing its execution risks."""
from runtime.project_recognition import recognize_project
from runtime.role_project_type_classification import classify_project_case


def report(kind, *, plugin=False):
    return {'source_health': {'entrypoint_count': 1, 'declared_script_entrypoint_count': 1,
                            'declared_plugin_entrypoint_count': int(plugin)},
            'answers': {'1_scope': {'domain_profile': {'kind': kind, 'confidence': 0.9}}}}


def test_declared_cli_and_transform_library_are_compatible():
    source = report('python_transform_library')
    classification = classify_project_case({'project': 'acme__sample', 'artifacts': {'project_map_report': source}})
    assert classification['project_stratum'] == 'cli_local_tool'
    assert classification['project_archetype_scope'] == 'internal_capability'
    assert classification['identity_profile_tension'] is False
    recognition = recognize_project(project='acme__sample', project_report=source, classification=classification)
    assert recognition['status'] == 'recognized'


def test_cli_capability_does_not_waive_stateful_execution_risk():
    source = report('python_transform_library')
    classification = classify_project_case({'project': 'acme__sample', 'artifacts': {'project_map_report': source}})
    classification['risk_profiles'] = ['deterministic', 'stateful']
    recognition = recognize_project(project='acme__sample', project_report=source, classification=classification)
    assert recognition['status'] == 'recognized'
    assert recognition['pilot_route']['status'] == 'analysis_only_stop'
    assert 'risk_profile_not_allowed' in recognition['pilot_route']['blocking_reasons']


def test_plugin_and_packaging_conflicts_still_need_review():
    for kind, plugin in [('python_transform_library', True)]:
        source = report(kind, plugin=plugin)
        classification = classify_project_case({'project': 'acme__sample', 'artifacts': {'project_map_report': source}})
        assert classification['identity_profile_tension'] is True
        assert recognize_project(project='acme__sample', project_report=source, classification=classification)['status'] == 'ambiguous'
