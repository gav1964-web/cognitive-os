"""Installed capability contract and local policy agree on both supported modes."""
import json
from pathlib import Path

import pytest
from jsonschema import validate

from plugins.python_transform_contracts.src.main import run


@pytest.mark.parametrize('contract',['python_text_to_valid_python.v1','python_text_preserves_ast.v1'])
def test_installed_property_proposal_matches_declared_schema(contract):
    root=Path(__file__).resolve().parents[1]
    payload={'operation':'acceptance_tests','contract':contract,'module':'sample','function':'format_source',
             'keyword_literals':{},'seed':'result = ()\n'}
    validate(payload,json.loads((root/'schemas/input.json').read_text()))
    result=run(payload)
    validate(result,json.loads((root/'schemas/output.json').read_text()))
    assert result['status']=='proposed' and result['variant_count']==2
    assert result['source_executed'] is False
