"""Static design-to-edit facts, not semantic approval or execution authority."""
import ast
import hashlib
import textwrap

from .narrow_type_evidence_binding import content_digest
from .programmer_python_symbols import qualified_function_matches


def candidate_repair_audit(source, target, replacement, design, packet):
    facts = design.get('reached_returns')
    if facts is None:
        return None
    if (hashlib.sha256(source.encode('utf-8')).hexdigest() != packet['target_source']['file_sha256']
            or design.get('target') != target or not design.get('branch_digest')
            or not isinstance(facts, list) or not 1 <= len(facts) <= 256
            or design.get('reached_return_ids') != [r['id'] for r in facts]):
        raise ValueError('candidate_repair_grounding_mismatch')
    matches = qualified_function_matches(ast.parse(source), target.partition(':')[2])
    if len(matches) != 1:
        raise ValueError('candidate_repair_target_not_unique')
    original = matches[0]
    proposed = ast.parse(textwrap.dedent(replacement).strip()).body
    if len(proposed) != 1 or not isinstance(proposed[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError('replacement_must_be_single_function')
    old_returns, new_returns = _returns(original), _returns(proposed[0])
    rows = []
    for fact in facts:
        found = [r for r in old_returns if r.lineno == fact['line']
                 and ast.get_source_segment(source, r) == fact['source']]
        if len(found) != 1:
            raise ValueError('candidate_reached_return_not_in_source')
        expression = ast.dump(found[0], include_attributes=False)
        rows.append({**fact, 'equivalent_return_count_in_candidate': sum(
            ast.dump(r, include_attributes=False) == expression for r in new_returns)})
    result = {'schema_version': 'repair_candidate_audit.v1', 'target': target,
        'source_sha256': packet['target_source']['file_sha256'], 'branch_digest': design['branch_digest'],
        'design_digest': content_digest(design), 'replacement_function_digest': content_digest(replacement),
        'reached_returns': rows, 'execution_authorized': False,
        'limitations': 'Syntactic return occurrences only; retained expressions may be under different guards. '
            'Removed expressions do not prove correct behavior. Native regression and Reviewer remain required.'}
    result['audit_digest'] = content_digest(result)
    return result


def _returns(function):
    result = []
    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if isinstance(node, ast.Return):
            result.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)
    for statement in function.body:
        visit(statement)
    return result
