"""Receipt evidence checks. Hashes bind observations; they do not certify the observer."""
from __future__ import annotations

import hashlib
import json
import math
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
ROUTES = ("direct_agent", "short_chain", "full_chain")
MAX_ARTIFACT_BYTES = 10_000_000
MAX_RECEIPT_BYTES = 100_000_000


def finite_nonnegative(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and 0 <= value <= 1.7976931348623157e308 and math.isfinite(value))


def payload_digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def artifact_bytes(root: Path, name: str) -> bytes:
    """Read only bounded ordinary files under an explicit evidence directory."""
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('artifact_path_invalid')
    parts = PurePosixPath(name).parts
    if (PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
            or '..' in parts or ':' in name
            or any(p.lower() in {'.git', '.agents', '.codex', 'config.json', 'secret.key'}
                   or p.lower().startswith('.env') for p in parts)):
        raise ValueError('artifact_path_forbidden')
    root = root.absolute()
    path = root / name
    for current in (path, *path.parents):
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('artifact_link_forbidden')
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('artifact_not_owned_file')
    with path.open('rb') as stream:
        data = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError('artifact_byte_budget_exceeded')
    return data


def evidence_errors(receipt: dict, artifact_root: Path | None) -> list[str]:
    errors, contents = [], {}
    artifacts = receipt.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts or len(artifacts) > 1000:
        return ['invalid_artifact_evidence']
    if artifact_root is None:
        errors.append('artifact_root_required')
    total = 0
    for row in artifacts:
        if (not isinstance(row, dict) or not isinstance(row.get('path'), str)
                or not DIGEST_PATTERN.fullmatch(str(row.get('digest') or ''))):
            errors.append('invalid_artifact_evidence')
            continue
        if row['path'] in contents:
            errors.append('duplicate_artifact_path')
        if artifact_root is None:
            continue
        try:
            data = artifact_bytes(artifact_root, row['path'])
            total += len(data)
            if total > MAX_RECEIPT_BYTES:
                errors.append('receipt_byte_budget_exceeded')
                break
            if 'sha256:' + hashlib.sha256(data).hexdigest() != row['digest']:
                errors.append('artifact_digest_mismatch')
            contents[row['path']] = data
        except (OSError, ValueError):
            errors.append('artifact_unreadable_or_forbidden')
    attempts = receipt.get('llm_attempts')
    if not isinstance(attempts, list) or not attempts:
        errors.append('llm_attempt_history_required')
    else:
        generated = []
        for row in attempts:
            if not isinstance(row, dict) or not row.get('provider_label') or not row.get('requested_model'):
                errors.append('invalid_llm_attempt')
                continue
            event = row.get('event', 'response')
            if event == 'response':
                if not isinstance(row.get('model'), str) or not row['model'].strip() or row.get('model_reported') is not True:
                    errors.append('actual_model_unverified')
                else:
                    generated.append(row['model'])
            elif event not in {'attempt_failed', 'route_skipped'}:
                errors.append('invalid_llm_attempt_event')
        if receipt.get('status') == 'completed' and not generated:
            errors.append('completed_receipt_without_model_response')
        if generated and any(model != receipt.get('model') for model in generated):
            errors.append('actual_model_mismatch')
    trace = receipt.get('llm_trace')
    if not isinstance(trace, str) or trace not in contents:
        errors.append('llm_trace_artifact_required')
    else:
        try:
            if json.loads(contents[trace]) != attempts:
                errors.append('llm_trace_history_mismatch')
        except (ValueError, UnicodeError):
            errors.append('llm_trace_invalid')
    return errors


def validate_receipt(receipt: dict, manifest: dict, policy: dict, *, artifact_root=None) -> list[str]:
    errors = []
    task = next((r for r in manifest.get('tasks', []) if r['task_id'] == receipt.get('task_id')), None)
    route = receipt.get('route')
    if task is None:
        errors.append('unknown_task')
    if route not in ROUTES:
        errors.append('unknown_route')
    if receipt.get('manifest_digest') != manifest.get('manifest_digest'):
        errors.append('manifest_digest_mismatch')
    for field in ('prompt_digest', 'input_digest'):
        if not DIGEST_PATTERN.fullmatch(str(receipt.get(field) or '')):
            errors.append('invalid_' + field)
        if task and receipt.get(field) != task.get(field):
            errors.append(field + '_mismatch')
    if receipt.get('status') not in {'completed', 'blocked', 'failed'}:
        errors.append('invalid_status')
    for field in ('executor', 'model'):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            errors.append('missing_' + field)
    for field in ('runtime_seconds', 'estimated_cost'):
        if not finite_nonnegative(receipt.get(field)):
            errors.append('invalid_' + field)
    usage = receipt.get('token_usage')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input', 'output')):
        errors.append('invalid_token_usage')
    for field in ('manual_corrections', 'acceptance_checks'):
        if not isinstance(receipt.get(field), list):
            errors.append(field + '_must_be_list')
    corrections = receipt.get('manual_corrections')
    for row in corrections if isinstance(corrections, list) else []:
        if not isinstance(row, dict) or not row.get('kind') or not finite_nonnegative(row.get('minutes')):
            errors.append('invalid_manual_correction')
    if not isinstance(receipt.get('judge_payload'), dict):
        errors.append('judge_payload_must_be_object')
    safety = receipt.get('safety')
    if not isinstance(safety, dict) or type(safety.get('source_mutation_detected')) is not bool:
        errors.append('incomplete_safety_evidence')
    contract = policy.get('route_contracts', {}).get(route, {})
    if any(v.lower() in str(receipt.get('executor', '')).lower() for v in contract.get('forbidden_executors', [])):
        errors.append('forbidden_route_executor')
    if contract.get('may_use_cognitive_os') is False and receipt.get('uses_cognitive_os') is not False:
        errors.append('direct_route_cognitive_os_use_forbidden')
    errors.extend(evidence_errors(receipt, artifact_root))
    try:
        payload_digest(receipt)
    except (ValueError, TypeError, OverflowError):
        errors.append('receipt_not_finite_json')
    return sorted(set(errors))
