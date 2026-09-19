"""Observed constructor-method calls are distinct from arbitrary dynamic dispatch."""
import pytest

from runtime.project_native_failure_target_binding import _direct_test_call_targets


@pytest.mark.parametrize('change', ['none', 'parameter_shadow', 'local_shadow', 'global_shadow',
    'inheritance', 'custom_new', 'method_rebound', 'test_patch', 'opaque_observer'])
def test_fresh_constructor_observed_method_requires_static_dispatch(tmp_path, change):
    source = 'class Transform:\n    def render(self):\n        return "bad"\n'
    header = 'from logic import Transform\n'
    parameter, setup, expression = '', '', 'Transform().render()'
    if change == 'parameter_shadow':
        parameter = 'Transform'
    if change == 'local_shadow':
        setup = '    Transform = replacement\n'
    if change == 'global_shadow':
        header += 'Transform = replacement\n'
    if change == 'inheritance':
        source = source.replace('class Transform:', 'class Transform(Base):')
    if change == 'custom_new':
        source += '    def __new__(cls):\n        return replacement\n'
    if change == 'method_rebound':
        source += '    render = replacement\n'
    if change == 'test_patch':
        setup = '    monkeypatch.setattr(Transform, "render", replacement)\n'
    if change == 'opaque_observer':
        header += 'from external import observe\n'
        expression = 'observe(Transform().render())'
    (tmp_path / 'logic.py').write_text(source)
    (tmp_path / 'test_logic.py').write_text(header + f'def test_render({parameter}):\n'
        + setup + '    result = ' + expression + '\n    assert result == "good"\n')
    targets = _direct_test_call_targets(tmp_path, ['test_logic.py::test_render'])
    assert targets == (['logic.py:Transform.render'] if change == 'none' else [])
