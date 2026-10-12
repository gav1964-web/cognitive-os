"""Evaluate learned fix templates on repositories with real git history (no LLM).

Protocols:
  cross_project  leave-one-project-out: learn on other projects' fix edits, suggest on
                 the held-out project's fix 'before' statements; correct = AST-identical
                 to the human 'after'. False alarms: suggestions on held-out HEAD statements.
  temporal       pooled chronological split: learn on the earliest 70% of edits (all
                 projects), test on the latest 30%; same metrics.
Writes a JSON report; read-only for the analysed repositories.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.fix_template_learning import learn, prune_by_clean_code, suggest  # noqa: E402
from runtime.fix_template_mining import head_statements, mine_repository  # noqa: E402
from runtime.fix_template_tree import template_text, unparse  # noqa: E402


def _text(tree):
    try:
        return unparse(tree)
    except Exception:
        return '<unprintable>'


def evaluate(templates, tests, head, *, min_projects):
    applied = correct = 0
    examples = []
    for record in tests:
        found = suggest(templates, record['before'], min_projects=min_projects)
        if not found:
            continue
        applied += 1
        hit = found[1].key == record['after'].key
        correct += hit
        if len(examples) < 12:
            examples.append({'project': record['project'], 'correct': hit, 'before': _text(record['before']),
                             'human_after': _text(record['after']), 'suggested': _text(found[1]),
                             'template_projects': len(found[0].projects), 'template_support': len(found[0].support)})
    alarms = sum(1 for s in head if suggest(templates, s, min_projects=min_projects))
    return {'test_edits': len(tests), 'suggested': applied, 'correct': correct,
            'head_statements': len(head), 'head_suggestions': alarms, 'examples': examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', action='append', required=True, help='name=path of a full-history git clone')
    parser.add_argument('--output', required=True)
    parser.add_argument('--head-sample', type=int, default=4000)
    parser.add_argument('--min-concrete', type=int, default=6)
    parser.add_argument('--max-clean-ratio', type=float, default=1.0)
    args = parser.parse_args()
    repos = dict(item.split('=', 1) for item in args.repo)
    started = time.monotonic()
    records, heads = [], {}
    for name, path in repos.items():
        mined = mine_repository(Path(path), name)
        records.extend(mined)
        statements = head_statements(Path(path))
        random.Random(name).shuffle(statements)
        heads[name] = statements[:args.head_sample]
        print('mined', name, len(mined), 'edits;', len(heads[name]), 'head statements', flush=True)
    report = {'repos': repos, 'edits': len(records), 'per_project': {}, 'min_concrete': args.min_concrete}
    for name in repos:
        report['per_project'][name] = sum(r['project'] == name for r in records)
    cross = {}
    for name in repos:
        train = [r for r in records if r['project'] != name]
        test = [r for r in records if r['project'] == name]
        templates = learn(train, min_concrete=args.min_concrete)
        clean = [s for other, h in heads.items() if other != name for s in h]
        pruned = prune_by_clean_code(templates, clean, max_ratio=args.max_clean_ratio)
        cross[name] = {'templates': len(templates), 'templates_after_clean_filter': len(pruned)}
        for k in (1, 2):
            cross[name][f'min_projects_{k}'] = evaluate(templates, test, heads[name], min_projects=k)
        cross[name]['clean_filtered'] = evaluate(pruned, test, heads[name], min_projects=1)
        print('cross', name, {k: (v['suggested'], v['correct'], v['head_suggestions'])
                              for k, v in cross[name].items() if isinstance(v, dict)}, flush=True)
    report['cross_project'] = cross
    ordered = sorted(records, key=lambda r: r['time'])
    cut = int(len(ordered) * 0.7)
    templates = learn(ordered[:cut], min_concrete=args.min_concrete)
    pooled_head = [s for h in heads.values() for s in h]
    pruned = prune_by_clean_code(templates, pooled_head, max_ratio=args.max_clean_ratio)
    report['temporal'] = {'train_edits': cut, 'templates': len(templates),
                          'min_projects_1': evaluate(templates, ordered[cut:], pooled_head, min_projects=1),
                          'min_projects_2': evaluate(templates, ordered[cut:], pooled_head, min_projects=2),
                          'templates_after_clean_filter': len(pruned),
                          'clean_filtered': evaluate(pruned, ordered[cut:], pooled_head, min_projects=1)}
    report['top_templates'] = [
        {'projects': sorted(t.projects), 'support': len(t.support), 'before': template_text(t.before), 'after': template_text(t.after)}
        for t in sorted(templates, key=lambda t: (len(t.projects), len(t.support)), reverse=True)[:25]]
    report['seconds'] = round(time.monotonic() - started, 1)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('edits', 'per_project', 'seconds')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
