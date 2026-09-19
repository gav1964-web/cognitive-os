"""Bounded source declarations for callees and method consumers; no execution."""
import ast
import hashlib
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .programmer_python_symbols import qualified_function_matches
from .project_native_failure_module_resolution import _python_module_path
from .stage_finalization_workspace import owned_path


def dependency_context(project, target, *, maximum_chars=7000):
    project=Path(project).resolve()
    path=owned_path(project,target.partition(':')[0])
    source=path.read_text(encoding='utf-8')
    tree=ast.parse(source)
    matches=qualified_function_matches(tree,target.partition(':')[2])
    if len(matches)!=1:
        raise ValueError('unique_dependency_context_target_required')
    function=matches[0]
    pending=[]
    # Peers consume constructor state; a method excerpt alone omits that contract.
    owners=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and function in n.body]
    if len(owners)==1:
        owner=owners[0]
        for base in owner.bases:
            if isinstance(base,ast.Name):
                pending.extend((path,n,base.id) for n in tree.body if isinstance(n,ast.ClassDef) and n.name==base.id)
        pending.extend((path,n,owner.name+'.'+getattr(n,'name','class_assignment')) for n in owner.body
                       if n is not function and isinstance(n,(ast.FunctionDef,ast.Assign,ast.AnnAssign)))
    calls={n.func.id for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    calls.update(n.value.id for n in ast.walk(function) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name))
    local={n.name:n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    for name in sorted(calls):
        if name in local and local[name] is not function:
            pending.append((path,local[name],name))
    unresolved=[]
    for statement in tree.body:
        if not isinstance(statement,ast.ImportFrom) or statement.level or not statement.module:
            continue
        for alias in statement.names:
            if (alias.asname or alias.name) not in calls:
                continue
            imported=_python_module_path(project,statement.module.split('.'))
            if imported is None:
                unresolved.append(statement.module+':'+alias.name)
                continue
            imported=owned_path(project,imported.relative_to(project).as_posix())
            if imported.stat().st_size>1_000_000:
                unresolved.append(statement.module+':'+alias.name)
                continue
            try:
                module_tree=ast.parse(imported.read_text(encoding='utf-8'))
            except (SyntaxError,UnicodeError):
                unresolved.append(statement.module+':'+alias.name)
                continue
            found=[n for n in module_tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==alias.name]
            if len(found)!=1:
                unresolved.append(statement.module+':'+alias.name)
                continue
            node=found[0]
            pending.append((imported,node,alias.name))
            # Return types such as named tuples carry part of the call contract.
            returns=getattr(node,'returns',None)
            names={n.id for n in ast.walk(returns) if isinstance(n,ast.Name)} if returns else set()
            pending.extend((imported,n,n.name) for n in module_tree.body if isinstance(n,ast.ClassDef) and n.name in names)
    rows,omitted,seen=[],[],set()
    size=0
    for current,node,name in pending:
        identity=(current,node.lineno)
        if identity in seen:
            continue
        seen.add(identity)
        text=current.read_text(encoding='utf-8')
        excerpt=ast.get_source_segment(text,node) or ''
        label=current.relative_to(project).as_posix()+':'+name
        if not excerpt or size+len(excerpt)>maximum_chars or len(rows)>=12:
            omitted.append(label)
            continue
        rows.append({'target':label,'file_sha256':hashlib.sha256(current.read_bytes()).hexdigest(),
            'source':excerpt,'line':node.lineno,'complete_declaration':True})
        size+=len(excerpt)
    result={'schema_version':'source_dependency_context.v1','target':target,
        'target_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'declarations':rows,
        'omitted':omitted,'unresolved':sorted(set(unresolved)),
        'limitations':'Static direct imports, local declarations and same-class consumers only. '
            'Dynamic dispatch, reexports, relative imports and external dependencies may be absent. '
            'Annotations are declared interfaces, not runtime type proof. No patch authority.'}
    result['digest']=content_digest(result)
    return result
