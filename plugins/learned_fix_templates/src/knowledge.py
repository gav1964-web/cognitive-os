"""Owned KB: learned templates per rule, with provenance and evaluation."""
from __future__ import annotations

import json
from pathlib import Path

from runtime.fix_template_tree import from_json

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge' / 'templates.json'


def load_document() -> dict:
    document = json.loads(KNOWLEDGE.read_text(encoding='utf-8'))
    if document.get('schema_version') != 'learned_fix_templates.v1':
        raise ValueError('invalid_learned_fix_templates_schema')
    return document


def load_rules() -> dict:
    """Rule -> {'templates': [... with parsed before_tree/after_tree], ...} in KB order."""
    rules = {}
    for rule, row in load_document()['rules'].items():
        templates = [{**t, 'before_tree': from_json(t['before']), 'after_tree': from_json(t['after'])}
                     for t in row['templates']]
        rules[rule] = {**row, 'templates': templates}
    return rules
