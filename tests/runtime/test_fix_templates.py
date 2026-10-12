"""Learned fix templates: anti-unification, executability, matching and git mining."""
import ast
import subprocess

from runtime.fix_template_learning import learn, suggest
from runtime.fix_template_mining import edits_from_sources, mine_repository
from runtime.fix_template_tree import anti_unify_edit, from_ast, match, substitute, unparse


def stmt(code):
    return from_ast(ast.parse(code).body[0])


def edit(before, after, project='p'):
    return {'project': project, 'before': stmt(before), 'after': stmt(after)}


def test_two_null_guard_fixes_generalize_to_one_template():
    pair = anti_unify_edit((stmt('x = a.get("k")'), stmt('x = a.get("k", None) or {}')),
                           (stmt('y = b.get("k")'), stmt('y = b.get("k", None) or {}')))
    assert pair is not None
    binding = match(pair[0], stmt('zz = cfg.get("k")'))
    assert binding is not None
    assert unparse(substitute(pair[1], binding)) == "zz = cfg.get('k', None) or {}"


def test_after_needing_unbound_value_is_rejected():
    assert anti_unify_edit((stmt('VERSION = "1.0"'), stmt('VERSION = "1.1"')),
                           (stmt('VERSION = "2.0"'), stmt('VERSION = "2.3"'))) is None


def test_learned_template_is_applied_to_new_code_and_skips_noops():
    records = [edit('if value == None:\n    pass', 'if value is None:\n    pass', 'a'),
               edit('if item == None:\n    pass', 'if item is None:\n    pass', 'b')]
    templates = learn(records, min_concrete=4)
    assert templates and max(len(t.projects) for t in templates) == 2
    found = suggest(templates, stmt('if other == None:\n    pass'))
    assert found and unparse(found[1]).startswith('if other is None')
    assert suggest(templates, stmt('if other is None:\n    pass')) is None


def test_single_statement_edits_are_aligned_inside_functions():
    before = 'def f(d):\n    x = 1\n    return d["k"]\n'
    after = 'def f(d):\n    x = 1\n    return d.get("k")\n'
    edits = edits_from_sources(before, after)
    assert [(unparse(b), unparse(a)) for b, a in edits] == [("return d['k']", "return d.get('k')")]


def test_mining_reads_only_fix_commits_from_history(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    def git(*args):
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', *args], check=True,
                       capture_output=True)
    git('init', '-q')
    (repo / 'm.py').write_text('def f(d):\n    return d["k"]\n', encoding='utf-8')
    git('add', '.'); git('commit', '-qm', 'initial')
    (repo / 'm.py').write_text('def f(d):\n    return d.get("k")\n', encoding='utf-8')
    git('commit', '-qam', 'Fix KeyError in f')
    (repo / 'm.py').write_text('def f(d):\n    return d.get("key")\n', encoding='utf-8')
    git('commit', '-qam', 'rename key')
    records = mine_repository(repo, 'demo')
    assert [(r['subject'], unparse(r['after'])) for r in records] == [('Fix KeyError in f', "return d.get('k')")]


def test_templates_matching_much_unchanged_code_are_pruned():
    from runtime.fix_template_learning import prune_by_clean_code
    records = [edit('if value == None:\n    pass', 'if value is None:\n    pass', 'a'),
               edit('if item == None:\n    pass', 'if item is None:\n    pass', 'b')]
    templates = learn(records, min_concrete=4)
    clean = [stmt(f'if v{i} == None:\n    pass') for i in range(5)]
    assert prune_by_clean_code(templates, clean[:1]) and not prune_by_clean_code(templates, clean)


def test_same_named_holes_of_two_templates_are_not_conflated():
    first = (stmt('from m import a, b'), stmt('from m import a'))
    second = (stmt('from n import c, d'), stmt('from n import c'))
    third = (stmt('from p import e, f'), stmt('from p import e'))
    merged = anti_unify_edit(first, second)
    again = anti_unify_edit(merged, anti_unify_edit(second, third))
    binding = match(again[0], stmt('from q import x, y'))
    assert unparse(substitute(again[1], binding)) == 'from q import x'


def test_templates_round_trip_through_json():
    import json
    from runtime.fix_template_tree import from_json, to_json
    template = anti_unify_edit((stmt('log.info("a %s" % x)'), stmt('log.info("a %s", x)')),
                               (stmt('logger.warning("b %d" % n)'), stmt('logger.warning("b %d", n)')))
    for part in template:
        assert from_json(json.loads(json.dumps(to_json(part)))).key == part.key
    sample = stmt('x = b"ab" + 1j + ...')
    assert from_json(to_json(sample)).key == sample.key
