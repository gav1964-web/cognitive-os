"""Evaluate detector-anchored fix templates per ruff rule (leave-one-project-out, no LLM).

For each rule with enough anchored edits in several projects and each held-out project:
  history   templates learned on other projects are applied at the anchored statement;
            correct = AST-identical to the human fix. Baseline: ruff's own autofix.
  head      templates are applied at statements of the held-out project's current code
            that carry the rule; a suggestion is detector-verified when the diagnostic
            disappears and no new one appears. Unanchored: the same templates applied to
            every statement of those files (what happens without a detector).
"""
import argparse
import ast
import json
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.fix_template_detector import (detector_verified, replace_statement, run_ruff,  # noqa: E402
                                           statements_with_rule)
from runtime.fix_template_learning import learn, suggest  # noqa: E402
from runtime.fix_template_mining import production_python, statement_pairs  # noqa: E402
from runtime.fix_template_tree import from_ast, iter_statements, unparse  # noqa: E402


def _tree(code):
    try:
        return from_ast(ast.parse(code).body[0])
    except (SyntaxError, IndexError, ValueError, RecursionError):
        return None


def _safe_unparse(tree):
    try:
        return unparse(tree)
    except (AttributeError, TypeError, ValueError):
        return None


def load(work):
    records = []
    for line in (work / 'anchored.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        row['before_tree'], row['after_tree'] = _tree(row['before']), _tree(row['after'])
        if row['before_tree'] and row['after_tree']:
            records.append({**row, 'before': row['before_tree'], 'after': row['after_tree'],
                            'before_text': row['before'], 'after_text': row['after']})
    return records


def autofix_correct(work, rule, tests, scratch):
    """Does ruff --fix for this rule reproduce the human statement?"""
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    names = {}
    for k, record in enumerate(tests):
        if record['ruff_fixable']:
            target = scratch / f'{k}.py'
            target.write_text((work / record['old_file']).read_text(encoding='utf-8'), encoding='utf-8')
            names[k] = target
    if not names:
        return 0, 0
    run_ruff(scratch, select=rule, ignore='', fix=True)
    hits = 0
    for k, target in names.items():
        old = (work / tests[k]['old_file']).read_text(encoding='utf-8')
        fixed = target.read_text(encoding='utf-8')
        hits += any(from_ast(b).key == tests[k]['before'].key and from_ast(a).key == tests[k]['after'].key
                    for b, a in statement_pairs(old, fixed))
    return len(names), hits


def head_snapshot(repo, dest, max_files=600):
    if dest.exists():
        return
    dest.mkdir(parents=True)
    import subprocess
    files = [f for f in subprocess.run(['git', '-C', str(repo), 'ls-files', '*.py'], capture_output=True,
                                       encoding='utf-8', errors='replace').stdout.splitlines() if production_python(f)]
    for k, name in enumerate(files[:max_files]):
        try:
            (dest / f'{k}.py').write_text((Path(repo) / name).read_text(encoding='utf-8'), encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue


def head_check(templates, folder, diags, rule, scratch, cap):
    sites = suggested = verified = unanchored = 0
    for index, name in enumerate(sorted(diags)):
        source = (folder / name).read_text(encoding='utf-8')
        try:
            module = from_ast(ast.parse(source))
        except (SyntaxError, ValueError, RecursionError):
            continue
        if index < 60:  # unanchored sample: every statement of the first files, no detector
            unanchored += sum(1 for s in iter_statements(module) if suggest(templates, s))
        for node in statements_with_rule(source, diags[name], rule):
            sites += 1
            found = suggest(templates, from_ast(node))
            if not found or suggested >= cap:
                continue
            suggested += 1
            code = _safe_unparse(found[1])
            rewritten = replace_statement(source, node, code) if code else None
            verified += bool(rewritten) and detector_verified(source, rewritten, node, rule, scratch)
    return {'sites': sites, 'suggested': suggested, 'verified': verified, 'unanchored_suggestions': unanchored}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True)
    parser.add_argument('--repo', action='append', required=True, help='name=path, for current-code checks')
    parser.add_argument('--min-edits', type=int, default=8)
    parser.add_argument('--min-projects', type=int, default=3)
    parser.add_argument('--max-train', type=int, default=250)
    parser.add_argument('--head-cap', type=int, default=20)
    parser.add_argument('--min-concrete', type=int, default=4)
    args = parser.parse_args()
    work = Path(args.work).resolve()
    repos = dict(r.split('=', 1) for r in args.repo)
    records = load(work)
    by_rule = defaultdict(list)
    for r in records:
        by_rule[r['rule']].append(r)
    eligible = {rule: rows for rule, rows in by_rule.items()
                if len(rows) >= args.min_edits and len({r['project'] for r in rows}) >= args.min_projects}
    print('records', len(records), 'rules', len(by_rule), 'eligible', len(eligible), flush=True)
    head_diags = {}
    report = {'records': len(records), 'rules_total': len(by_rule), 'rules': {}}
    for rule, rows in sorted(eligible.items(), key=lambda kv: -len(kv[1])):
        projects = sorted({r['project'] for r in rows})
        stats = defaultdict(int)
        examples = []
        for project in projects:
            train = [r for r in rows if r['project'] != project]
            random.Random(rule + project).shuffle(train)
            templates = learn(train[:args.max_train], min_concrete=args.min_concrete)
            tests = [r for r in rows if r['project'] == project]
            stats['test_edits'] += len(tests)
            for r in tests:
                found = suggest(templates, r['before'])
                if found:
                    stats['suggested'] += 1
                    hit = found[1].key == r['after'].key
                    stats['correct'] += hit
                    if len(examples) < 4:
                        examples.append({'project': project, 'correct': hit, 'before': r['before_text'],
                                         'human': r['after_text'], 'suggested': _safe_unparse(found[1])})
            fixable, fix_hits = autofix_correct(work, rule, tests, work / 'scratch' / 'autofix')
            stats['autofix_applicable'] += fixable
            stats['autofix_correct'] += fix_hits
            if project in repos and templates:
                folder = work / 'head' / project
                head_snapshot(Path(repos[project]), folder)
                if project not in head_diags:
                    head_diags[project] = run_ruff(folder)
                for key, value in head_check(templates, folder, head_diags[project], rule,
                                             work / 'scratch' / 'verify', args.head_cap).items():
                    stats['head_' + key] += value
        report['rules'][rule] = {'edits': len(rows), 'projects': len(projects),
                                 'ruff_fixable_share': round(sum(r['ruff_fixable'] for r in rows) / len(rows), 3),
                                 **stats, 'examples': examples}
        print(rule, dict(stats), flush=True)
        (work / 'detector_study.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
