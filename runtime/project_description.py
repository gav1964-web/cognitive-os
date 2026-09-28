"""Registered evidence -> model explanation -> validated citations and receipt."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

from .competency_knowledge import ROOT, invoke_knowledge
from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat, load_llm_profiles


def description_model_config():
    """Independent task profile; explicit connection/model overrides retain precedence."""
    from .llm_failover import fallback_configs
    base = LocalInferenceConfig.from_l45_env()
    profile = load_llm_profiles()['profiles'].get('project_description')
    if not profile:
        return base
    key_env = os.environ.get('COGNITIVE_OS_DESCRIPTION_API_KEY_ENV', profile.get('api_key_env', 'COGNITIVE_OS_L45_API_KEY'))
    return replace(base,
                   base_url=os.environ.get('COGNITIVE_OS_DESCRIPTION_BASE_URL', os.environ.get('COGNITIVE_OS_L45_BASE_URL', profile['base_url'])).rstrip('/'),
                   model=os.environ.get('COGNITIVE_OS_DESCRIPTION_MODEL', os.environ.get('COGNITIVE_OS_L45_MODEL', profile['model'])),
                   provider_label=profile['provider_label'], api_key=os.environ.get(key_env) or None,
                   timeout_seconds=float(os.environ.get('COGNITIVE_OS_DESCRIPTION_TIMEOUT', profile['timeout_seconds'])),
                   response_format=bool(profile.get('response_format', False)),
                   max_output_tokens=profile.get('max_output_tokens'),
                   fallbacks=fallback_configs(profile, LocalInferenceConfig))


def _validate_description(result, ids):
    keys = {'purpose', 'scenarios', 'data_flow', 'unknowns', 'confidence'}
    if not isinstance(result, dict) or set(result) != keys:
        raise ValueError('description_invalid_fields')
    claims = [result['purpose']]
    for key, minimum, maximum in [('scenarios', 1, 8), ('data_flow', 1, 3)]:
        rows = result[key]
        if not isinstance(rows, list) or not minimum <= len(rows) <= maximum:
            raise ValueError('description_invalid_' + key)
        claims.extend(rows)
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {'text', 'evidence_ids'}:
            raise ValueError('description_invalid_claim')
        if not isinstance(claim['text'], str) or not claim['text'].strip() or len(claim['text']) > 2000:
            raise ValueError('description_invalid_text')
        refs = claim['evidence_ids']
        if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or x not in ids for x in refs):
            raise ValueError('description_unknown_evidence')
    if (not isinstance(result['confidence'], str) or result['confidence'] not in {'high', 'medium', 'low'}
            or not isinstance(result['unknowns'], list) or len(result['unknowns']) > 3
            or any(not isinstance(x, str) or len(x) > 2000 for x in result['unknowns'])):
        raise ValueError('description_invalid_uncertainty')
    return result


def _sources_current(evidence):
    root = Path(evidence['root']).resolve()
    for row in evidence['sources']:
        path = (root / row['path']).resolve()
        if (not path.is_relative_to(root) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
            return False
    return True


def describe_project(project_dir: Path, *, root: Path = ROOT, language: str = 'ru',
                     owner_notes: list[str] | None = None, config=None, chat=None, behavior_checks=None,
                     review_context_profile='default'):
    """No inspected-project execution or mutation; failed analysis has no invented fallback."""
    if review_context_profile not in ('default', 'expanded'):
        raise ValueError('description_unknown_review_context_profile')
    contribution = invoke_knowledge('project_description', {'project_root': str(project_dir.resolve())}, root=root)
    evidence = contribution['evidence']
    behavior = None
    if behavior_checks is not None:
        behavior = invoke_knowledge('project_description', {'project_root':evidence['root'],
            'action':'behavior_checks','evidence':evidence,'behavior_checks':behavior_checks}, root=root)
    notes = [{'id': f'owner{i + 1}', 'text': text, 'authority': 'owner_statement'}
             for i, text in enumerate(owner_notes or [])]
    if any(not isinstance(row['text'], str) or len(row['text']) > 4000 for row in notes) or len(notes) > 10:
        raise ValueError('description_invalid_owner_notes')
    messages = [
        {'role': 'system', 'content': contribution['instruction'] + ('\n'+behavior['instruction'] if behavior else '')},
        {'role': 'user', 'content': json.dumps({'language': language,
                                               'surface_index': [{'id': r['id'], 'path': r['path'], **r['surface']}
                                                                 for r in evidence['sources'] if r.get('primary')],
                                               'evidence': evidence,
                                               **({'behavior_facts':behavior['behavior_facts']} if behavior else {})}, ensure_ascii=False)},
    ]
    telemetry = []
    base = config or description_model_config()
    output_budget = base.max_output_tokens or 3500
    configured = replace(base, telemetry_sink=telemetry.append, max_output_tokens=output_budget,
                         fallbacks=tuple(replace(c, telemetry_sink=telemetry.append, max_output_tokens=output_budget)
                                         for c in base.fallbacks))
    report = {'schema_version': 'project_description.v1', 'status': 'failed',
              'review_context_profile': review_context_profile,
              'evidence': evidence, 'owner_notes': notes, 'language': language,
              'request_sha256': hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
              'request': messages, 'telemetry': telemetry, 'description': None,
              'verification': {'citation_ids_only': True, 'semantic_review_required': True},
              'source_application': False}
    if behavior:
        report['behavior_facts'] = behavior['behavior_facts']
    try:
        raw = (chat or call_json_chat)(messages, config=configured)
        report['raw_response'] = raw
        from .description_shape import normalize_description
        draft, shape = normalize_description(raw, evidence, root=root)
        report['shape_normalization'] = {'draft': shape}
        if not _sources_current(evidence):
            raise ValueError('description_source_changed_during_request')
        from .project_description_review import review_description
        description = review_description(report, contribution['review_instruction'] + ('\n'+behavior['review_instruction'] if behavior else ''), draft,
            root=root, chat=chat or call_json_chat, config=configured,
            validate=_validate_description, current=_sources_current)
        if not _sources_current(report['evidence']):
            raise ValueError('description_source_changed_during_request')
        from .description_grounding import description_grounding
        report['claim_grounding'] = description_grounding(description, report['evidence'], root=root)
    except (LocalInferenceError, ValueError, OSError) as exc:
        report['reason'] = str(exc)
        return report
    report.update(status='described', description=description)
    return report


def render_description(report):
    if report['status'] != 'described':
        return '# Описание проекта\n\nОписание не получено: ' + report.get('reason', 'unknown') + '\n'
    description = report['description']
    from .description_grounding import description_grounding
    grounding = description_grounding(description, report['evidence'])
    ungrounded = {row['claim_id'] for row in grounding['claims'] if row['status'] != 'implementation_cited'}
    def claim_text(claim, claim_id):
        suffix = ' (Подтверждение реализацией не установлено.)' if claim_id in ungrounded else ''
        return claim['text'] + suffix
    rows = ['# Описание проекта', '', claim_text(description['purpose'], 'purpose'), '']
    if report['owner_notes']:
        rows.extend(['## Подтверждено владельцем', ''])
        rows.extend('- ' + note['text'] for note in report['owner_notes'])
        rows.append('')
    for key, title in [('scenarios', 'Что может делать пользователь'),
                       ('data_flow', 'Как проходят данные')]:
        if description[key]:
            rows.extend(['## ' + title, ''])
            rows.extend('- ' + claim_text(claim, f'{key}.{i}') for i, claim in enumerate(description[key]))
            rows.append('')
    if description['unknowns']:
        rows.extend(['## Что нужно уточнить', ''])
        rows.extend('- ' + text for text in description['unknowns'])
        rows.append('')
    if report.get('unverified_removals'):
        from .project_description_review import draft_claims
        from .description_shape import report_draft
        pending = {row['id']: row['text'] for row in draft_claims(report_draft(report))}
        rows.extend(['## Требует проверки полноты', '',
                     'Следующие утверждения сняты review без ссылок на опровергающие фрагменты:', ''])
        rows.extend('- ' + pending[key] for key in report['unverified_removals'])
        rows.append('')
    findings = report.get('review_audit', {}).get('findings', [])
    if any(finding.get('matches') for finding in findings):
        rows.extend(['## Проверка обоснований review', '',
                     'В исходниках найдены значения, фигурирующие в спорных обоснованиях. '
                     'Совпадение текста не доказывает возможность; требуется проверка смысла и условий.', ''])
        for finding in findings:
            if finding.get('matches'):
                terms = ', '.join(dict.fromkeys(match['term'] for match in finding['matches']))
                rows.append(f"- {finding['claim_id']}: {terms}")
        rows.append('')
    rows.extend(['## Основания описания', '',
                 'Статическое чтение исходников и документации; приложение не запускалось.', ''])
    used = {ref for claim in [description['purpose'], *description['scenarios'],
                              *description['data_flow']]
            for ref in claim['evidence_ids']}
    rows.extend(f"- `{r['id']}`: `{r['path']}`" for r in report['evidence']['sources'] if r['id'] in used)
    rows.extend(f"- `{r['id']}`: уточнение владельца — {r['text']}" for r in report['owner_notes'] if r['id'] in used)
    rows.extend(['', 'Пропуски и сокращения контекста, хеши и ссылки для каждого утверждения сохранены в JSON отчёте.', ''])
    return '\n'.join(rows)
