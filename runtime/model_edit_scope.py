"""Explicit bounded same-class repair units; unrelated edits stay forbidden."""
import ast
import hashlib

from .narrow_type_evidence_binding import content_digest


def same_class_edit_scope(source, target):
    path, _, symbol=target.partition(':')
    parts=symbol.split('.')
    if len(parts)!=2:
        raise ValueError('same_class_repair_target_required')
    tree=ast.parse(source)
    owners=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==parts[0]]
    if len(owners)!=1:
        raise ValueError('unique_repair_class_required')
    nodes=[n for n in owners[0].body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    names=[n.name for n in nodes]
    if len(names)!=len(set(names)) or names.count(parts[1])!=1 or len(names)>32:
        raise ValueError('unambiguous_bounded_class_required')
    result={'schema_version':'same_class_edit_scope.v1','target':target,
        'file_sha256':hashlib.sha256(source.encode('utf-8')).hexdigest(),
        'eligible_related_targets':[path+':'+parts[0]+'.'+name for name in names if name!=parts[1]],
        'maximum_related_targets':2,'scope_origin':'explicit_policy_and_current_source',
        'limitations':'One file, one existing class, primary method and at most two existing sibling methods. '
            'Preserve signatures, annotations, decorators, doctests and all other bytes. Native acceptance required.'}
    result['digest']=content_digest(result)
    return result


def validate_related_targets(scope, targets):
    if (not isinstance(targets,list) or len(targets)>scope['maximum_related_targets']
            or any(not isinstance(t,str) or t not in scope['eligible_related_targets'] for t in targets)
            or len(set(targets))!=len(targets)):
        raise ValueError('bounded_same_class_related_targets_required')
    return targets


def apply_related_replacements(original, patched, target, scope, planned, rows):
    if scope!=same_class_edit_scope(original,target):
        raise ValueError('same_class_edit_scope_changed')
    validate_related_targets(scope,planned)
    if (not isinstance(rows,list) or len(rows)!=len(planned)
            or any(not isinstance(r,dict) or set(r)!={'target','replacement_source'} for r in rows)
            or [r['target'] for r in rows]!=planned):
        raise ValueError('related_replacements_must_match_design')
    from .upstream_llm_candidates import _replacement
    for row in rows:
        if not isinstance(row['replacement_source'],str) or len(row['replacement_source'])>8000:
            raise ValueError('bounded_related_function_required')
        try:
            patched=_replacement(patched,row['target'],row['replacement_source'])
        except ValueError as exc:
            if str(exc)=='replacement_semantic_noop':
                raise ValueError('related_replacement_semantic_noop') from exc
            raise
    return patched
