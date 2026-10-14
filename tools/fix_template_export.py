"""Export learned detector-anchored templates for selected rules into a competency KB.

Templates are learned on all anchored edits of a rule; only templates supported by at
least two projects are kept. Provenance (source digest, edit/project counts) and the
leave-one-project-out evaluation of the rule are stored next to them. No LLM.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

from fix_template_detector_study import load  # noqa: E402
from runtime.fix_template_learning import learn  # noqa: E402
from runtime.fix_template_tree import concrete_size, template_text, to_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True)
    parser.add_argument('--rule', action='append', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--min-concrete', type=int, default=4)
    args = parser.parse_args()
    work = Path(args.work)
    records = load(work)
    study = json.loads((work / 'detector_study.json').read_text(encoding='utf-8'))['rules']
    digest = hashlib.sha256((work / 'anchored.jsonl').read_bytes()).hexdigest()
    rules = {}
    for rule in args.rule:
        rows = [r for r in records if r['rule'] == rule]
        templates = [t for t in learn(rows, min_concrete=args.min_concrete) if len(t.projects) >= 2]
        templates.sort(key=lambda t: (concrete_size(t.before), len(t.support)), reverse=True)
        evaluation = {k: v for k, v in study[rule].items() if k != 'examples'}
        rules[rule] = {
            'detector': {'tool': 'ruff', 'rule': rule},
            'provenance': {'anchored_edits': len(rows), 'projects': sorted({r['project'] for r in rows}),
                           'source': 'artifacts/fix_templates_20261003/detector/anchored.jsonl',
                           'source_sha256': digest},
            'evaluation_leave_one_project_out': evaluation,
            'templates': [{'support': len(t.support), 'projects': len(t.projects),
                           'before_text': template_text(t.before), 'after_text': template_text(t.after),
                           'before': to_json(t.before), 'after': to_json(t.after)} for t in templates]}
        print(rule, 'edits', len(rows), 'templates kept', len(templates))
    document = {'schema_version': 'learned_fix_templates.v1', 'learner': 'runtime.fix_template_learning',
                'selection': 'most concrete matching template first', 'rules': rules}
    Path(args.output).write_text(json.dumps(document, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
