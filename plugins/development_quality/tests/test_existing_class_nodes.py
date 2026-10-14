"""Existing class nodeids retain their actual owner; native collection is final."""
import pytest

from plugins.development_quality.src.main import validate
from plugins.development_quality.src.contrast_cases import _nodes, validate_contrasts


@pytest.mark.parametrize('header,base', [
    ('import unittest', 'unittest.TestCase'),
    ('import unittest as ut', 'ut.TestCase'),
    ('from unittest import TestCase as Case', 'Case'),
    ('import unittest\nclass Base(unittest.TestCase):\n    pass', 'Base'),
])
def test_selected_unittest_class_node_is_admitted(header, base):
    source = {'path': 'tests/test_old.py', 'content':
        header+'\nclass ExistingChecks('+base+'):\n    def test_value(self):\n        self.assertEqual(actual(), 2)\n'}
    node = 'tests/test_old.py::ExistingChecks::test_value'
    value = {'tests': [{'path':'tests/test_new.py','content':'def test_new():\n    assert actual() == 3\n'}],
        'regression_tests':[node], 'case_plan':[
            {'kind':'feature','node':'test_new','behavior':'new'},
            {'kind':'boundary','node':'test_new','behavior':'edge'},
            {'kind':'preservation','node':node,'behavior':'existing'}],
        'contrast_pairs':[{'left':'test_new','right':node,'distinction':'new vs preserved'}]}
    assert validate('spec_writer', value, [source]) == []
    assert validate_contrasts(value, [source]) == []
    value['regression_tests'] = []
    assert validate('spec_writer', value, [source])
    value['regression_tests'] = [node]
    assert validate('spec_writer', value, [])
    value['case_plan'][-1]['node'] = 'tests/test_old.py::OtherChecks::test_value'
    assert validate('spec_writer', value, [source])


def test_classes_are_not_flattened_or_inferred_from_method_name():
    source = ('class TestOne:\n    def test_value(self):\n        pass\n'
              'class TestTwo:\n    def test_value(self):\n        pass\n'
              'class Helper:\n    def test_value(self):\n        pass\n')
    assert _nodes('tests/test_old.py',source) == {
        'tests/test_old.py::TestOne::test_value', 'tests/test_old.py::TestTwo::test_value'}
    assert _nodes('tests/test_old.py', 'class Broken(') == set()
