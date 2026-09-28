"""Bounded source identities for cross-module development traces (no imports)."""
import ast
import hashlib
import types
from pathlib import Path

try:  # Standalone -I probe and normal package consumer use the same code.
    from .repair_target_trace_probe import code_digest, compiled_identities
except ImportError:
    from repair_target_trace_probe import code_digest, compiled_identities


LIMITATIONS = (
    'Execution linked to one failing assertion is candidate-location evidence, not proof of root cause. '
    'Only source-verified top-level Python functions are eligible; generator callbacks may be nominated. '
    'The observed entrypoint must be synchronous and non-generator. No argument values are captured. '
    'Edges connect nearest eligible stack ancestors, possibly through library or nested helper frames; '
    'they are execution ancestry, not complete data flow or deferred callback registration provenance. '
    'Only explicitly selected source files are inspected; outside code is not nominated. '
    'Two identical trusted-copy replays are required; not hostile-code attestation. '
    'Nomination grants no patch authority.')


def function_catalog(project, source_files, target):
    if (not isinstance(source_files, (list, tuple)) or not 1 <= len(source_files) <= 64
            or len(set(source_files)) != len(source_files)):
        raise ValueError('bounded_unique_source_files_required')
    project = Path(project).resolve()
    catalog, identities, total = {}, {}, 0
    for relative in sorted(source_files):
        path = project / relative
        if (not isinstance(relative, str) or relative != Path(relative).as_posix()
                or Path(relative).is_absolute() or '..' in Path(relative).parts
                or not path.resolve().is_relative_to(project) or path.suffix != '.py'
                or any(p in {'tests', 'test'} for p in Path(relative).parts)
                or path.stem.startswith('test_') or path.stem.endswith('_test')):
            raise ValueError('owned_production_python_source_required')
        if any(p.is_symlink() for p in [path, *path.parents] if p != project and p.is_relative_to(project)):
            raise ValueError('symlink_not_supported')
        data = path.read_bytes()
        total += len(data)
        if len(data) > 1_000_000 or total > 4_000_000:
            raise ValueError('function_source_budget_exceeded')
        source = data.decode('utf-8')
        tree = ast.parse(source)
        compiled = compile(source, relative, 'exec', dont_inherit=True)
        identities[relative] = compiled_identities(compiled)
        codes = [c for c in compiled.co_consts if isinstance(c, types.CodeType)]
        names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or names.count(node.name) != 1:
                continue
            first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            matches = [c for c in codes if c.co_name == node.name and c.co_firstlineno == first]
            if len(matches) != 1:
                continue
            code = matches[0]
            name = relative + ':' + node.name
            catalog[name] = {'target': name, 'line_start': node.lineno, 'line_end': node.end_lineno,
                'code_line': first, 'code_digest': code_digest(code),
                'file_sha256': hashlib.sha256(data).hexdigest(),
                'callable_kind': 'generator' if code.co_flags & 0x20 else 'function',
                'source': ast.get_source_segment(source, node)}
    if len(catalog) > 512 or target not in catalog or catalog[target]['callable_kind'] != 'function':
        raise ValueError('ordinary_observed_function_required_or_catalog_over_budget')
    return catalog, identities


def probe_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('repair_function_trace_probe.py', 'repair_function_catalog.py',
                         'repair_target_trace_probe.py')}
