"""Explain a saved review without confusing a model opinion with validation."""
from .claim_review_proposals import checked_proposal
from .claim_review_decisions import checked_decisions
from .single_claim_review import checked_job
from .narrow_type_evidence_binding import content_digest


def inspect_review(receipt, *, decisions=None):
    if (not isinstance(receipt, dict) or receipt.get('schema_version') != 'single_claim_review_receipt.v1'
            or receipt.get('digest') != content_digest({k: v for k, v in receipt.items() if k != 'digest'})
            or receipt.get('status') not in ('reviewed', 'failed')):
        raise ValueError('invalid_claim_review_receipt')
    job = receipt['job']
    source_status, source_error = 'current', None
    try:
        checked_job(job)
    except ValueError as exc:
        source_status, source_error = 'unavailable_for_current_review', str(exc)
    raw = receipt.get('raw_response')
    raw = raw if isinstance(raw, dict) else {}
    valid, validation_error = False, receipt.get('reason')
    if receipt['status'] == 'reviewed':
        try:
            checked_proposal(receipt)
            valid = True
        except ValueError as exc:
            validation_error = str(exc)
    parts = raw.get('parts')
    parts = parts if isinstance(parts, list) else []
    complete = (''.join(row['text'] for row in parts) == job['original_claim']['text']
                if parts and all(isinstance(row, dict) and isinstance(row.get('text'), str) for row in parts)
                else None)
    telemetry = receipt.get('telemetry', [])
    usage_known = bool(telemetry) and all(row.get('usage_reported') is True for row in telemetry)
    result = {'schema_version': 'claim_review_inspection.v1', 'receipt_digest': receipt['digest'],
              'claim': job['original_claim']['text'], 'claim_namespace': job['claim_namespace'],
              'source_status': source_status,
              'source_error': source_error, 'contract_status': 'passed' if valid else 'failed',
              'validation_error': validation_error,
              'model_verdict': raw.get('verdict') if isinstance(raw.get('verdict'), str) else None,
              'effective_verdict': receipt['result']['verdict'] if valid else None,
              'model_reason': raw.get('reason'), 'proposed_text': raw.get('proposed_text'),
              'parts': parts, 'coverage': receipt['result']['coverage'] if valid and job['schema_version'].endswith(('.v3', '.v4')) else raw.get('coverage', []),
              'derived_assessment': job['schema_version'].endswith(('.v3', '.v4')),
              'text_alignment': receipt.get('text_alignment') if valid else None,
              'assessment_reason': receipt['result']['reason'] if valid else None,
              'text_coverage_complete': complete,
              'aggregation': receipt.get('aggregation') if valid else None,
              'usage_known': usage_known,
              'reported_tokens': sum(row.get('total_tokens') or 0 for row in telemetry),
              'semantic_verified': False, 'execution_authorized': False,
              'return_flag_analysis': job.get('return_flag_analysis'),
              'mechanism_audit': receipt.get('mechanism_audit') if valid else None,
              'return_property_analysis': job.get('return_property_analysis'),
              'return_property_audit': receipt.get('return_property_audit') if valid else None,
              'reviewer_decision': None}
    if decisions is not None:
        ledger = checked_decisions(decisions, report_digest=job['source_report_digest'])
        matching = [event for event in ledger['events'] if event['proposal']['digest'] == receipt['digest']]
        if matching:
            event = matching[-1]
            result['reviewer_decision'] = {key: event[key] for key in
                ('disposition', 'reviewer', 'reason', 'accepted_text', 'recorded_at')}
    return result


def render_review(inspection):
    """Russian review report; model output is always labelled as an opinion."""
    labels = {'supported': 'подтверждено', 'refuted': 'опровергнуто', 'uncertain': 'неопределённо'}
    opinion = labels.get(inspection['model_verdict'], 'ответ не получен или некорректен')
    effective = labels.get(inspection['effective_verdict'], 'предложение не прошло проверку')
    lines = ['# Проверка утверждения', '', inspection['claim'], '',
             ('Модель оценивает части; общий вердикт рассчитывает код.' if inspection.get('derived_assessment')
              else f'Мнение модели: **{opinion}**.'),
             'Контракт ответа: ' + ('соблюдён.' if inspection['contract_status'] == 'passed' else 'не пройден.'),
             f'Итог по оценкам модели: **{effective}**.',
             'Проверка контракта и цитат не подтверждает смысловую правильность.', '']
    if inspection.get('claim_namespace') == 'final':
        lines += ['Проверяется утверждение итогового описания, после редактирования черновика.', '']
    if inspection.get('return_flag_analysis'):
        lines += ['Вход включает проверенную Boolean-модель конечного фрагмента функции. '
                  'Её условные примеры не доказывают достижимость состояния в полном проекте.', '']
    property_analysis = inspection.get('return_property_analysis')
    if property_analysis:
        lines += ['Проверяемое свойство и фрагмент текста зафиксированы рецензентом до ответа модели.',
                  'Анализ нормальных возвратов: ' + property_analysis['analysis']['status'] + '.',
                  'Область: Boolean/None-входы и обычные словари. Связь поля со смыслом утверждения '
                  'требует отдельного review; неизвестный анализ не является опровержением.', '']
        for finding in (inspection.get('return_property_audit') or {}).get('findings', []):
            if finding['downgraded']:
                lines += [f"Часть {finding['part_index'] + 1}: подтверждение понижено до неопределённости.", '']
    audit = inspection.get('mechanism_audit')
    if audit:
        lines += ['Связи утверждений с условиями предложены моделью. Проверена их '
                  'структурная согласованность, а не истинность.', '']
        for finding in audit['findings']:
            lines += [f"Часть {finding['part_index'] + 1}: " + ', '.join(finding['codes'])
                      + (' — подтверждение понижено до неопределённости.' if finding['downgraded'] else '.'), '']
    if inspection['model_reason']:
        lines += ['Объяснение модели:', '', str(inspection['model_reason']), '']
    elif inspection.get('assessment_reason'):
        lines += ['Основание расчёта: ' + inspection['assessment_reason'], '']
    if inspection['validation_error']:
        lines += ['Причина отказа: ' + str(inspection['validation_error']), '']
    if inspection['source_status'] != 'current':
        lines += ['Текущие источники не подтверждены: ' + str(inspection['source_error']), '']
    if inspection['aggregation'] and inspection['aggregation']['model_verdict_overridden']:
        lines += ['Общий вердикт изменён по оценкам частей и полноте контекста.', '']
    if (inspection.get('text_alignment') or {}).get('status') == 'boundary_whitespace_aligned':
        lines += ['Пробелы на границах частей восстановлены по исходному утверждению; '
                  'изменения сохранены отдельно, исходный ответ модели неизменен.', '']
    elif inspection['text_coverage_complete'] is False:
        lines += ['Части ответа не воспроизводят исходное утверждение полностью и дословно.', '']
    for index, part in enumerate(inspection['parts'], 1):
        if isinstance(part, dict):
            verdict = part.get('verdict') if isinstance(part.get('verdict'), str) else None
            lines += [f"{index}. {part.get('text', '')} — мнение модели: {labels.get(verdict, 'невалидно')}."]
    if inspection['parts']:
        lines.append('')
    for item in inspection['coverage'] if isinstance(inspection['coverage'], list) else []:
        if isinstance(item, dict) and item.get('status') == 'missing':
            lines += [f"Недостающий контекст ({item.get('id')}): {item.get('reason', '')}", '']
    if inspection['proposed_text']:
        lines += ['Предложенный текст (сам по себе не считается принятым):', '',
                  str(inspection['proposed_text']), '']
    decision = inspection['reviewer_decision']
    if decision:
        labels_decision = {'accepted': 'принято', 'rejected': 'отклонено', 'deferred': 'отложено'}
        lines += [f"Решение рецензента {decision['reviewer']}: {labels_decision[decision['disposition']]}. ",
                  decision['reason'], '']
    tokens = str(inspection['reported_tokens']) if inspection['usage_known'] else 'полный расход неизвестен'
    lines += [f'Токены по телеметрии: {tokens}.', '']
    return '\n'.join(lines)
