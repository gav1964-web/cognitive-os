"""Source-bound predictions for native acceptance on the unchanged baseline.

Classification is authored by SpecWriter and checked by its semantic auditor.
Native matching verifies predictions, not the truth of the requested semantics.
"""

KINDS = {'preservation': 'passed', 'feature_gap': 'failed', 'feature_control': 'passed'}


def classification(row):
    """Separate baseline intent from case_plan.kind; retain unambiguous old data."""
    value = row.get('classification', row.get('kind'))
    if 'classification' in row and 'kind' in row and row['classification'] != row['kind']:
        return None
    return value if isinstance(value, str) and value in KINDS else None


def validate(artifact, goal, sources, *, required=False):
    rows = artifact.get('baseline_expectations')
    if rows is None and not required:
        return []  # Historical contracts remain readable, without the new claim.
    if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
        return ['baseline_expectations requires 1..256 source/goal-bound rows']
    issues = []
    paths = {t.get('path') for t in artifact.get('tests', [])}
    for row in artifact.get('case_plan', []):
        if isinstance(row, dict) and row.get('kind') == 'preservation' and '::' not in row.get('node', ''):
            issues.append('preservation case_plan needs a full path::node to bind baseline evidence')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            issues.append('baseline_expectations rows must be objects')
            continue
        node = row.get('node')
        if (not isinstance(node, str) or '::' not in node
                or node.partition('::')[0] not in paths or node in seen):
            issues.append('baseline expectation requires a unique new-test path::node')
        else:
            seen.add(node)
        if classification(row) is None or not isinstance(row.get('reason'), str) or not row['reason'].strip():
            issues.append('baseline_expectations.classification requires preservation/feature_gap/feature_control and reason; case_plan.kind instead uses feature/preservation/boundary; conflicting legacy kind is invalid')
        quote = row.get('goal_quote')
        if not isinstance(quote, str) or not quote.strip() or quote not in goal:
            issues.append('baseline expectation goal_quote must exactly cite the user goal')
        evidence = row.get('source_evidence')
        if not isinstance(evidence, list) or not evidence:
            issues.append('baseline expectation requires original source_evidence')
            continue
        for ref in evidence:
            if (not isinstance(ref, dict) or not isinstance(ref.get('quote'), str)
                    or not ref['quote'].strip() or not any(
                        s.get('path') == ref.get('path') and ref['quote'] in s.get('content', '')
                        for s in sources)):
                issues.append('baseline expectation source quote must occur in supplied original source')
    return list(dict.fromkeys(issues))


def identity(node):
    """Map pytest path/class nodeids to the runner's JUnit identities."""
    path, _, rest = node.partition('::')
    if not path.endswith('.py') or not rest:
        return None
    prefix, _, params = rest.partition('[')
    parts = prefix.split('::')
    classname = '.'.join([path[:-3].replace('/', '.'), *parts[:-1]])
    return classname + '::' + parts[-1] + ('[' + params if params else '')


def matches(node, observed):
    key = identity(node)
    return key is not None and (key == observed or ('[' not in key and observed.startswith(key + '[')))


def compare(artifact, outcomes):
    """Require an unambiguous prediction for every collected new test."""
    rows = artifact.get('baseline_expectations')
    if 'baseline_expectations' not in artifact:
        return {'status': 'legacy_unassessed', 'issues': [], 'cases': []}
    if not isinstance(rows, list) or any(not isinstance(r, dict) or
            not isinstance(r.get('node'), str) or classification(r) is None for r in rows):
        return {'status': 'rejected', 'issues': ['invalid baseline expectation rows'], 'cases': []}
    cases, issues, used = [], [], set()
    for name, observed in outcomes.items():
        candidates = [(i, r) for i, r in enumerate(rows) if matches(r['node'], name)]
        if len(candidates) != 1:
            issues.append(f'{name}: needs exactly one prediction, got {len(candidates)}; split mixed parameter cases')
            continue
        i, row = candidates[0]
        used.add(i)
        kind = classification(row)
        expected = KINDS[kind]
        cases.append({'node': name, 'kind': kind, 'expected': expected, 'observed': observed})
        if observed != expected:
            issues.append(f'{name}: {kind} expected {expected}, observed {observed}')
    for i, row in enumerate(rows):
        if i not in used:
            issues.append(f'{row["node"]}: prediction did not bind uniquely to a collected test')
    for row in artifact.get('case_plan', []):
        if not isinstance(row, dict) or row.get('kind') != 'preservation':
            continue
        node = row.get('node', '')
        # Existing regression tests have their own all-green baseline gate.
        bound = [c for c in cases if matches(node, c['node'])]
        if any(c['kind'] != 'preservation' for c in bound):
            issues.append(f'{node}: preservation case_plan cannot be relabeled as a feature')
    return {'status': 'rejected' if issues else 'matched', 'issues': issues, 'cases': cases}
