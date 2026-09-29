from plugins.development_quality.src.contrast_cases import validate_contrasts


def spec():
    return {'tests': [{'path':'tests/test_change.py', 'content':
        'def test_accept():\n    assert operation(0) == 0\n'
        'def test_reject():\n    assert operation(-1) is None\n'}],
        'regression_tests': [], 'contrast_pairs':[{'left':'test_accept','right':'test_reject',
                                                  'distinction':'zero valid, negative unavailable'}]}


def test_real_opposite_examples_are_resolved_without_claiming_semantic_proof():
    assert validate_contrasts(spec(), []) == []


def test_no_fabricated_or_duplicate_test_reference():
    value = spec()
    value['contrast_pairs'][0]['right'] = 'missing'
    assert validate_contrasts(value, [])
    value['contrast_pairs'][0]['right'] = 'test_accept'
    assert validate_contrasts(value, [])


def test_existing_controls_need_selected_actual_source():
    value = spec()
    value['contrast_pairs'][0]['right'] = 'tests/test_old.py::test_preserved'
    source = [{'path':'tests/test_old.py','content':'def test_preserved():\n    assert operation(1) == 1\n'}]
    assert validate_contrasts(value, source)
    value['regression_tests'] = ['tests/test_old.py']
    assert validate_contrasts(value, source) == []
    assert validate_contrasts(value, [])


def test_ambiguous_short_names_require_qualification():
    value = spec()
    value['tests'].append({'path':'tests/test_other.py','content':'def test_accept():\n    assert actual()\n'})
    assert validate_contrasts(value, [])
    value['contrast_pairs'][0]['left'] = 'tests/test_change.py::test_accept'
    assert validate_contrasts(value, []) == []


def test_methods_and_parameter_cases_are_supported():
    value = spec()
    value['tests'] = [{'path':'tests/test_change.py',
                      'content':'class TestInput:\n    def test_value(self, case):\n        assert actual(case)\n'}]
    value['contrast_pairs'] = [{'left':'tests/test_change.py::TestInput::test_value[valid]',
                              'right':'tests/test_change.py::TestInput::test_value[invalid]',
                              'distinction':'different observable results; parametrization checked natively'}]
    assert validate_contrasts(value, []) == []


def test_legacy_artifacts_and_malformed_pairs():
    assert validate_contrasts({}, []) == []
    for pairs in ([], 'test', [{}], [{'left':1,'right':2,'distinction':3}]):
        assert validate_contrasts({'contrast_pairs':pairs}, [])
