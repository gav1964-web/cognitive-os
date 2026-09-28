"""Exercise the registered proposal contract and retained reconstruction behavior."""
from copy import deepcopy

from plugins.exception_pickle.src.knowledge import decorate_profile, load_boundary_records, load_exception_pickle_patterns
from runtime.competency_knowledge import invoke_knowledge


SOURCE = '''class Broken(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(str(code))
'''


def test_proposal_contract_preserves_behavior_and_rejects_existing_hook():
    request = {'operation': 'propose_patch', 'source': SOURCE, 'class_name': 'Broken',
               'recipe': {'required_constructor_inputs': ['code'], 'reconstruction_method': '__reduce__',
                          'state_strategy': 'reuse_direct_assignments'}}
    result = invoke_knowledge('exception_pickle', request)
    assert result['status'] == 'proposed'
    namespace = {}
    exec(result['patch']['source'], namespace)
    error = namespace['Broken'](42)
    factory, args = error.__reduce__()
    restored = factory(*args)
    assert restored.args == error.args and restored.code == 42
    assert request['source'] == SOURCE
    assert invoke_knowledge('exception_pickle', {**request, 'source': result['patch']['source']}) == {
        'status': 'not_applicable', 'patch': None}


def test_local_kb_overlay_preserves_staged_absence_and_does_not_mutate_inputs():
    profile = load_boundary_records()[0]
    original = deepcopy(profile)
    assert decorate_profile(profile, active_patterns={'status': 'absent'}) == original
    active = decorate_profile(profile)
    assert active['status'] == 'active'
    assert active['hypothesis']['confidence'] == 0.97
    assert profile == original


def test_catalog_is_fresh_and_forbids_source_apply():
    first = load_exception_pickle_patterns()
    first['safety']['source_apply_allowed'] = True
    assert load_exception_pickle_patterns()['safety']['source_apply_allowed'] is False
    assert invoke_knowledge('exception_pickle', {'operation': 'patterns'})['catalog']['safety']['source_apply_allowed'] is False
