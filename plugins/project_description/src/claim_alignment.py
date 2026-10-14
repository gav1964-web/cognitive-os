"""V4 boundary whitespace alignment; never rewrite words or source quotations."""
from copy import deepcopy

from .lean_claim import validate_lean

SPACE = ' \t\r\n'


def align_parts(parts, original):
    if (not isinstance(parts, list) or not 1 <= len(parts) <= 8
            or any(not isinstance(p, dict) or not isinstance(p.get('text'), str)
                   or not p['text'].strip() for p in parts)):
        raise ValueError('claim_v4_invalid_parts')
    normalized = deepcopy(parts)
    changes, spans, cursor = [], [], 0
    exact = ''.join(p['text'] for p in parts) == original
    for index, part in enumerate(parts):
        raw = part['text']
        core = raw
        if not exact:
            if index:
                core = core.lstrip(SPACE)
            if index < len(parts) - 1:
                core = core.rstrip(SPACE)
        start = cursor
        if not core or not original.startswith(core, cursor):
            raise ValueError('claim_parts_do_not_cover_original_text')
        cursor += len(core)
        if not exact and index < len(parts) - 1:
            gap_start = cursor
            while cursor < len(original) and original[cursor] in SPACE:
                cursor += 1
            model_gap = raw[len(raw.rstrip(SPACE)):] + parts[index + 1]['text'][:len(parts[index + 1]['text']) - len(parts[index + 1]['text'].lstrip(SPACE))]
            if cursor == gap_start and model_gap:
                # Do not turn '1 00' into '100' or 'can not' into 'cannot'.
                raise ValueError('claim_alignment_invented_separator')
        text = original[start:cursor]
        normalized[index]['text'] = text
        spans.append({'start': start, 'end': cursor})
        if text != raw:
            changes.append({'part': index, 'raw_text': raw, 'aligned_text': text})
    if cursor != len(original):
        raise ValueError('claim_parts_do_not_cover_original_text')
    return normalized, {'status': 'exact' if exact else 'boundary_whitespace_aligned',
                        'spans': spans, 'changes': changes,
                        'word_changes_allowed': False, 'semantic_verified': False}


def validate_aligned(response, evidence, claim, required):
    if not isinstance(response, dict):
        raise ValueError('claim_v4_invalid_result')
    parts, alignment = align_parts(response.get('parts'), claim['text'])
    projected = deepcopy(response)
    projected['parts'] = parts
    result = validate_lean(projected, evidence, claim, required)
    result['text_alignment'] = alignment
    return result
