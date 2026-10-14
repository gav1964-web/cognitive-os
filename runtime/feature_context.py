"""Role source selection; explicit SpecWriter reads override background filtering."""
import ast
from .feature_workspace import merge_reads, cited_sources, read_sources
from .feature_extension import extension_context
from .feature_case_catalog import case_catalog, contract_sources
from .feature_prompts import JSON_CASES


def select_context(payload, *, role, ctx, artifacts, extra, role_reads, fresh_reads,
                   recent_paths, extension, spec_format, project, expected, observed):
    if role != 'analyzer':
        owner = 'analyzer' if role == 'architect' else 'architect'
        scope = set(artifacts[owner]['scope'])
        payload['sources'] = merge_reads([r for r in ctx['sources'] if r['path'] in scope
                              or r['path'].startswith('tests/')], role_reads)
        if role in ('programmer', 'reviewer'):
            payload['sources'] = merge_reads([r for r in ctx['sources'] if r['path'] in scope], role_reads)
        if role == 'spec_writer':
            if extension:
                payload['extension_contract'] = extension_context(extension)
            payload['artifacts'] = {k: v for k, v in artifacts.items() if k != 'analyzer'}
            cited = cited_sources(ctx['sources'], artifacts['analyzer'].get('evidence', []))
            selected = role_reads
            payload['sources'] = merge_reads(cited, selected)
            if extension:
                inherited_regressions = {n.partition('::')[0] for n in extension['spec']['regression_tests']}
                payload['sources'] = [r for r in payload['sources']
                    if r['path'] not in inherited_regressions or r['path'] in recent_paths]
                payload['extension_contract']['context_note'] = 'Inherited passing regression source is omitted unless explicitly requested by SpecWriter; it will still run unchanged.'
            if spec_format == 'json_calls':
                payload['call_contracts'] = case_catalog(project, expected, scope)
                if not payload['call_contracts']:
                    raise ValueError('feature_no_declared_json_entrypoints')
                payload['sources'] = merge_reads(contract_sources(project, expected,
                    payload['call_contracts']), role_reads)
                payload['observed_regression_files'] = observed['files']
                payload['role_task'] = JSON_CASES
        if role == 'reviewer':
            payload['artifacts'] = {k: v for k, v in artifacts.items() if k != 'analyzer'}
            # Review the implementation against constraints, not the
            # architect's suggested implementation pseudocode.
            payload['artifacts']['architect'] = {k: v for k, v in
                payload['artifacts']['architect'].items()
                if k in ('scope', 'preserve', 'risks', 'acceptance')}
            if payload.get('verification', {}).get('passed') is True:
                payload['verification'] = {k: v for k, v in payload['verification'].items()
                    if k not in ('output_tail', 'junit', 'candidate_hashes')}
            cited = cited_sources(ctx['sources'], artifacts['analyzer'].get('evidence', []))
            regressions = {p.partition('::')[0] for p in payload['artifacts']['spec_writer']['regression_tests']}
            payload['sources'] = role_reads or [r for r in cited if r['path'] not in regressions]
            payload['regression_context_note'] = 'Explicit Reviewer reads supersede initial Analyzer excerpts; all retained source and regression files remain available by read. Full candidate tests, patch and exact outcomes are supplied.'
        if role == 'programmer':
            payload['artifacts'] = {k: v for k, v in artifacts.items() if k != 'analyzer'}
            cited = cited_sources(ctx['sources'], artifacts['analyzer'].get('evidence', []))
            requested = fresh_reads if (extra or {}).get('feedback') else role_reads
            payload['sources'] = merge_reads([r for r in cited if r['path'] in scope], requested)
            payload['source_context_note'] = 'Initial source includes Analyzer-cited ranges in the writable scope; request any additional range needed for an exact patch. All retained source remains readable.'
        if role in ('programmer', 'reviewer'):
            accepted = payload['artifacts']['spec_writer']
            if accepted.get('test_authoring', {}).get('python_scaffolding') == 'runtime.feature_case_compiler':
                # The frozen Python already contains every case; avoid
                # transmitting the same fixtures twice to consumers.
                payload['artifacts']['spec_writer'] = {k: v for k, v in accepted.items() if k != 'cases'}

    # Exact on-disk names remain available, separate from planned new files.
    if role != 'analyzer':
        payload['catalog'] = [{k: r[k] for k in ('path', 'lines')} for r in ctx['catalog']]
    if role == 'spec_writer':
        payload['sources'] = merge_reads(payload['sources'], role_reads)
        payload['sources'] = complete_test_fragments(project, expected, payload['sources'])
        payload['source_context_note'] = (
            'Includes cited evidence and all explicit SpecWriter read ranges. Other '
            'source remains available by exact catalog path; request missing evidence. '
            'Draft tests in feedback are unaccepted artifacts, not on-disk files.')
    return payload


def complete_test_fragments(project, expected, sources):
    """AST admission needs parseable evidence, not a slice starting inside a suite."""
    additions, completed = [], set()
    for row in sources:
        if not row['path'].startswith('tests/') or not row['path'].endswith('.py'):
            continue
        try:
            ast.parse(row['content'])
        except SyntaxError:
            if row['path'] in completed:
                continue
            full = read_sources(project, expected, [{'path': row['path']}], max_bytes=65000)[0]
            if not full['eof']:
                raise ValueError('feature_test_context_requires_complete_source')
            ast.parse(full['content'])
            additions.append(full)
            completed.add(row['path'])
    return merge_reads(sources, additions)
