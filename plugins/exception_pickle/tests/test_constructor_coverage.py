"""Do not silently discard constructor state outside the proposed recipe."""
import pickle
import sys
import types
import uuid

import pytest

from plugins.exception_pickle.src.patch import exception_pickle_reconstruction_patch


RECIPE = {'required_constructor_inputs': ['status', 'channel'],
          'reconstruction_method': '__reduce__', 'state_strategy': 'reuse_direct_assignments'}


@pytest.mark.parametrize('extra', [', retryable=False', ', *, retryable=False',
                                   ', retryable', ', *extra', ', **extra'])
def test_unrepresented_constructor_inputs_do_not_produce_lossy_patch(extra):
    variadic_state = '        self.extra = extra\n' if '*' in extra and 'extra' in extra else ''
    source = f'''class DeliveryFailure(ValueError):
    def __init__(self, status, channel{extra}):
        self.status = status
        self.channel = channel
{variadic_state}        super().__init__(f'{{status}}@{{channel}}')
'''
    assert exception_pickle_reconstruction_patch(source, class_name='DeliveryFailure', recipe=RECIPE) is None


@pytest.mark.parametrize('capture', ['self.extra = extra', 'self.extra = locals()',
                                    'self.extra = vars()', 'self.extra = eval("extra")'])
def test_observed_variadic_state_is_not_silently_discarded(capture):
    source = f'''class DeliveryFailure(ValueError):
    def __init__(self, status, channel, *extra):
        self.status = status
        self.channel = channel
        {capture}
        super().__init__(status, channel)
'''
    assert exception_pickle_reconstruction_patch(source, class_name='DeliveryFailure', recipe=RECIPE) is None


def test_ignored_variadics_retain_existing_supported_shape():
    source = '''class DeliveryFailure(ValueError):
    def __init__(self, status, channel, *unused, **ignored):
        self.status = status
        self.channel = channel
        super().__init__(status, channel)
'''
    assert exception_pickle_reconstruction_patch(source, class_name='DeliveryFailure', recipe=RECIPE) is not None


def test_frozen_retryable_counterexample_is_declined_by_registered_contract():
    from runtime.competency_knowledge import invoke_knowledge
    source = '''class DeliveryFailure(ValueError):
    def __init__(self, status, channel, retryable=False):
        self.status = status
        self.channel = channel
        self.retryable = retryable
        super().__init__(f'{status}@{channel}')
'''
    request = {'operation': 'propose_patch', 'source': source, 'class_name': 'DeliveryFailure', 'recipe': RECIPE}
    assert invoke_knowledge('exception_pickle', request) == {'status': 'not_applicable', 'patch': None}
    assert request['source'] == source


@pytest.mark.parametrize('keyword_only', [False, True])
def test_explicitly_covered_default_parameter_preserves_round_trip(keyword_only):
    separator = ', *, ' if keyword_only else ', '
    source = f'''class DeliveryFailure(ValueError):
    def __init__(self, status, channel{separator}retryable=False):
        self.status = status
        self.channel = channel
        self.retryable = retryable
        super().__init__(f'{{status}}@{{channel}} retry={{retryable}}')
'''
    recipe = {**RECIPE, 'required_constructor_inputs': ['status', 'channel', 'retryable'],
              'allow_keyword_only_state_reducer': keyword_only}
    patch = exception_pickle_reconstruction_patch(source, class_name='DeliveryFailure', recipe=recipe)
    assert patch is not None
    name = 'pickle_coverage_' + uuid.uuid4().hex
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(patch['source'], module.__dict__)
        original = module.DeliveryFailure(421, 'batch', retryable=True)
        restored = pickle.loads(pickle.dumps(original))
        assert type(restored) is type(original)
        assert vars(restored) == vars(original)
        assert restored.args == original.args
        assert str(restored) == str(original)
    finally:
        sys.modules.pop(name, None)


def test_uncovered_keyword_only_is_declined_even_with_state_reducer_permission():
    source = '''class DeliveryFailure(ValueError):
    def __init__(self, status, channel, *, retryable=False):
        self.status = status
        self.channel = channel
        self.retryable = retryable
        super().__init__(status, channel)
'''
    assert exception_pickle_reconstruction_patch(source, class_name='DeliveryFailure',
            recipe={**RECIPE, 'allow_keyword_only_state_reducer': True}) is None
