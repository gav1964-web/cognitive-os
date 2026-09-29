"""Out-of-process support controller; only signed messages cross the boundary.

The controller, policy and mail keys live outside the replaceable COS release.
It never imports code from that release. Execution uses fresh child processes.
"""
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .remote_support_protocol import digest, envelope, load, owned, publish, save, verify
from .remote_support_release import apply_patch, inventory, run_check, snapshot, validate_policy
from .remote_support_accounting import reserve as reserve_usage, reconcile as reconcile_usage


@contextmanager
def locked(home):
    path = Path(home) / 'controller.lock'
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if __import__('os').name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if __import__('os').name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class SupportSupervisor:
    def __init__(self, home, outbox, key):
        self.home, self.outbox, self.key = Path(home).resolve(), Path(outbox).resolve(), key
        if self.outbox.is_relative_to(self.home) or self.home.is_relative_to(self.outbox):
            raise ValueError('support_mailbox_must_be_separate')
        if len(key) < 32:
            raise ValueError('support_key_too_short')

    def _save(self, state):
        save(self.home / 'state.json', state)

    def _policy(self, state):
        policy = load(self.home / 'policy.json')
        if digest(policy) != state['policy_digest']:
            raise ValueError('support_policy_changed')
        return policy

    def _reply(self, state, kind, payload):
        incoming = state.get('pending')
        message = envelope(kind, state['incident'], payload, self.key, sender='cos',
                           reply_to=incoming['id'] if incoming else None)
        save(self.home / 'messages' / (message['id'] + '.json'), message)
        state['last'] = message['id']
        if incoming:
            state['seen'][incoming['id']] = {'digest': incoming['digest'], 'reply': message['id']}
            state.pop('pending')
        self._save(state)  # Persist reply identity before delivery; retry never repeats work.
        publish(self.outbox, message)
        return message

    def _remaining(self, state, policy):
        return min(policy['max_seconds'] - state['seconds'], policy['expires_at'] - time.time())

    def _run(self, state, policy, release, expected, command, label):
        reserve = min(policy['commands'][command]['timeout'], self._remaining(state, policy))
        if reserve <= 0:
            raise ValueError('support_time_budget')
        allowance = max(0, policy['max_tokens'] - state['tokens'] - state['unknown_reserved'])
        hold = reserve_usage(state, policy, allowance)
        state['seconds'] += reserve
        state['inflight_check'] = {'label': label, 'reserved_seconds': reserve}
        if hold:
            state['inflight_check']['accounting'] = hold
        self._save(state)  # A process crash retains the reservation, never free retries.
        result = run_check(release, policy['commands'][command],
            self.home / 'checks' / (label + '.log'), expected, reserve,
            {'task': policy['task'], 'checkpoint': policy['checkpoint'], 'phase': command,
             'execution': policy.get('execution'),
             'budget': {'remaining_tokens': allowance, 'accounting': policy.get('accounting')},
             'task_digest': state['task_digest'], 'checkpoint_digest': state['checkpoint_digest']})
        state['seconds'] += result['seconds'] - reserve
        state['checks'][label] = result
        worker = result.get('worker_result') or {}
        usage = worker.get('usage', {'reported': 0, 'unknown_reserved': 0})
        if (not isinstance(usage, dict) or set(usage) != {'reported', 'unknown_reserved'}
                or any(type(v) is not int or v < 0 for v in usage.values())):
            if not hold:
                raise ValueError('support_worker_usage_invalid')
            result.update(passed=False, accounting_error='support_worker_usage_invalid')
        if hold:
            reconcile_usage(state, policy, hold, result)
        else:
            state['tokens'] += usage['reported']
            state['unknown_reserved'] += usage['unknown_reserved']
        if state['tokens'] + state['unknown_reserved'] > policy['max_tokens']:
            result.update(passed=False, budget_exceeded=True)
        if (result.get('execution_finished') is not False
                and result.get('accounting', {}).get('status') != 'unresolved'):
            state.pop('inflight_check')
        self._save(state)
        return result

    def start(self, source, policy):
        """Freeze a locally authorized task, then execute it before asking for help."""
        validate_policy(policy)
        source = Path(source).resolve()
        from .remote_support_exchange import validate_location
        validate_location(policy.get('execution'), self.home, self.outbox, source)
        if self.home.is_relative_to(source) or source.is_relative_to(self.home):
            raise ValueError('support_source_must_be_separate')
        self.home.mkdir(parents=True, exist_ok=False)
        with locked(self.home):
            expected = inventory(source, policy['files'])
            snapshot(source, self.home / 'releases' / 'baseline', expected)
            save(self.home / 'policy.json', policy)
            save(self.home / 'active.json', {'release': 'baseline', 'hashes': expected})
            state = {'incident': uuid.uuid4().hex, 'status': 'starting', 'policy_digest': digest(policy),
                     'baseline': expected, 'attempts': 0, 'messages': 0, 'seconds': 0,
                     'tokens': policy['prior_usage']['reported'],
                     'unknown_reserved': policy['prior_usage']['unknown_reserved'], 'seen': {}, 'checks': {},
                     'task_digest': digest(policy['task']), 'checkpoint_digest': digest(policy['checkpoint'])}
            self._save(state)
            work = snapshot(self.home / 'releases/baseline', self.home / 'initial', expected)
            result = self._run(state, policy, work, expected, 'resume', 'initial-task')
            if result['passed']:
                state['status'] = 'completed'
                return self._reply(state, 'result', self._receipt(state, policy, 'task_completed'))
            if not self._reproduced(result, policy):
                state['status'] = 'needs_operator'
                return self._reply(state, 'result', self._receipt(state, policy, 'unclassified_task_failure'))
            state['status'] = 'waiting'
            contents = {name: owned(self.home / 'releases/baseline', name).read_text(encoding='utf-8')
                        for name in policy['export']}
            return self._reply(state, 'incident', {
                'task': policy['task'], 'checkpoint': policy['checkpoint'],
                'task_digest': state['task_digest'], 'checkpoint_digest': state['checkpoint_digest'],
                'base': digest(expected), 'source_hashes': expected, 'sources': contents,
                'editable': policy['editable'], 'failure': result,
                'limits': {k: policy[k] for k in ('max_attempts', 'max_messages', 'max_tokens', 'expires_at')},
                'remaining_tokens': max(0, policy['max_tokens'] - state['tokens'] - state['unknown_reserved']),
                'prior_usage': policy['prior_usage'],
                'instruction': 'Return context_request or patch against this baseline; no remote commands.'})

    @staticmethod
    def _reproduced(result, policy):
        return (result['returncode'] == 1 and not result['timed_out']
                and result['source_unchanged'] and result['context_unchanged']
                and policy['failure_marker'] in result['output'])

    def _receipt(self, state, policy, reason):
        return {'status': state['status'], 'reason': reason, 'attempts': state['attempts'],
                'checks': state['checks'], 'task_digest': state['task_digest'],
                'checkpoint_digest': state['checkpoint_digest'], 'seconds': state['seconds'],
                'usage': {'reported': state['tokens'], 'unknown_reserved': state['unknown_reserved'],
                          'prior': policy['prior_usage']},
                'inflight_check': state.get('inflight_check'),
                'rollback_scope': 'release_pointer_only; external_task_effects_require_reconciliation',
                'active': load(self.home / 'active.json')}

    def recover(self):
        """Never repeat an interrupted task with possibly completed side effects."""
        with locked(self.home):
            state = load(self.home / 'state.json')
            policy = self._policy(state)
            if state['status'] in ('starting', 'processing', 'activating', 'resuming'):
                save(self.home / 'active.json', {'release': 'baseline', 'hashes': state['baseline']})
                state['status'] = 'needs_operator'
                return self._reply(state, 'result', self._receipt(state, policy, 'interrupted_outcome_unknown'))
            if state.get('last'):
                reply = load(self.home / 'messages' / (state['last'] + '.json'))
                publish(self.outbox, reply)
                return reply

    def receive(self, message):
        verify(message, self.key, sender='assistant')
        with locked(self.home):
            state = load(self.home / 'state.json')
            policy = self._policy(state)
            if message['incident'] != state['incident']:
                raise ValueError('support_wrong_incident')
            known = state['seen'].get(message['id'])
            if known:
                if known['digest'] != digest(message):
                    raise ValueError('support_message_id_collision')
                reply = load(self.home / 'messages' / (known['reply'] + '.json'))
                publish(self.outbox, reply)
                return reply
            if state['status'] != 'waiting' or message['reply_to'] != state['last']:
                raise ValueError('support_out_of_order')
            if message['kind'] not in ('context_request', 'patch'):
                raise ValueError('support_unexpected_kind')
            limit_reached = (state['messages'] >= policy['max_messages']
                             or self._remaining(state, policy) <= 0)
            usage = message['payload'].get('usage', {})
            if (set(usage) != {'reported', 'unknown_reserved'}
                    or any(type(v) is not int or v < 0 for v in usage.values())):
                raise ValueError('support_usage_required')
            state['tokens'] += usage['reported']
            state['unknown_reserved'] += usage['unknown_reserved']
            state['messages'] += 1
            state['pending'] = {'id': message['id'], 'digest': digest(message)}
            state['status'] = 'processing'
            self._save(state)
            if limit_reached:
                state['status'] = 'exhausted'
                return self._reply(state, 'result', self._receipt(state, policy, 'support_limit'))
            if state['tokens'] + state['unknown_reserved'] > policy['max_tokens']:
                state['status'] = 'exhausted'
                return self._reply(state, 'result', self._receipt(state, policy, 'support_token_limit'))
            try:
                if message['kind'] == 'context_request':
                    return self._context(state, policy, message['payload'])
                return self._patch(state, policy, message['payload'])
            except (ValueError, KeyError, TypeError, SyntaxError, OSError) as exc:
                save(self.home / 'active.json', {'release': 'baseline', 'hashes': state['baseline']})
                state['status'] = 'exhausted' if state['attempts'] >= policy['max_attempts'] else 'waiting'
                if (state.get('inflight_check') or (policy.get('accounting') and state['unknown_reserved'])
                        or str(exc).startswith('support_accounting_')):
                    state['status'] = 'needs_operator'
                return self._reply(state, 'result', self._receipt(state, policy, str(exc)))

    def reconcile_interrupted(self, *, worker_stopped=False):
        """Local operator attests termination; this never resumes task effects."""
        if worker_stopped is not True:
            raise ValueError('support_worker_termination_confirmation_required')
        with locked(self.home):
            state = load(self.home / 'state.json')
            policy = self._policy(state)
            check = state.get('inflight_check', {})
            hold = check.get('accounting')
            if state['status'] != 'needs_operator':
                raise ValueError('support_reconcile_requires_interrupted_state')
            if not hold:
                if state.get('reconciled_check'):
                    return load(self.home / 'messages' / (state['last'] + '.json'))
                raise ValueError('support_no_interrupted_accounting')
            result = {'passed': False, 'timed_out': False, 'execution_finished': True}
            reconcile_usage(state, policy, hold, result)
            reason = 'interrupted_usage_unresolved'
            if result['accounting']['status'] == 'reconciled':
                state['reconciled_check'] = {**check, 'reconciliation': result['accounting']}
                state.pop('inflight_check')
                reason = 'interrupted_usage_reconciled_outcome_requires_review'
            state['checks']['interrupted-accounting'] = result
            self._save(state)
            return self._reply(state, 'result', self._receipt(state, policy, reason))

    def _context(self, state, policy, payload):
        paths = payload.get('paths', [])
        check = payload.get('check')
        if not isinstance(paths, list) or len(paths) > 12 or (not paths and check is None):
            raise ValueError('support_context_count')
        if check is not None and check not in ('reproduce', 'regression'):
            raise ValueError('support_diagnostic_not_authorized')
        if any(name not in policy['export'] for name in paths):
            raise ValueError('support_context_not_authorized')
        root = self.home / 'releases/baseline'
        if inventory(root, policy['files']) != state['baseline']:
            raise ValueError('support_baseline_changed')
        diagnostic = None
        if check:
            label = 'diagnostic-' + str(state['messages'])
            work = snapshot(root, self.home / label, state['baseline'])
            diagnostic = self._run(state, policy, work, state['baseline'], check, label)
        state['status'] = 'needs_operator' if state.get('inflight_check') else 'waiting'
        return self._reply(state, 'context', {'base': digest(state['baseline']),
            'diagnostic': diagnostic,
            'remaining_tokens': max(0, policy['max_tokens'] - state['tokens'] - state['unknown_reserved']),
            'sources': {name: owned(root, name).read_text(encoding='utf-8') for name in paths}})

    def _patch(self, state, policy, payload):
        if state['attempts'] >= policy['max_attempts']:
            raise ValueError('support_attempt_limit')
        state['attempts'] += 1
        self._save(state)
        expected = state['baseline']
        baseline = self.home / 'releases/baseline'
        attempt = self.home / 'attempts' / str(state['attempts'])
        before = snapshot(baseline, attempt / 'before', expected)
        candidate = snapshot(baseline, attempt / 'candidate', expected)
        patched = apply_patch(candidate, expected, payload, policy)
        prefix = str(state['attempts']) + '-'
        reproduced = self._run(state, policy, before, expected, 'reproduce', prefix + 'before')
        if not self._reproduced(reproduced, policy):
            raise ValueError('support_defect_not_reproduced')
        for command in ('reproduce', 'regression'):
            result = self._run(state, policy, candidate, patched, command, prefix + command)
            if not result['passed']:
                raise ValueError('support_candidate_' + command + '_failed')
        release_name = 'repair-' + str(state['attempts'])
        release = snapshot(candidate, self.home / 'releases' / release_name, patched)
        state['status'] = 'activating'
        self._save(state)
        save(self.home / 'active.json', {'release': release_name, 'hashes': patched})
        state['status'] = 'resuming'
        self._save(state)
        result = self._run(state, policy, release, patched, 'resume', prefix + 'resume')
        if not result['passed']:
            raise ValueError('support_resume_failed')
        state['status'] = 'completed'
        return self._reply(state, 'result', self._receipt(state, policy, 'task_completed_after_repair'))

    def poll(self, inbox):
        """Bounded inbox pass, suitable for an external scheduler. No network IO."""
        inbox = Path(inbox).resolve()
        if inbox.is_relative_to(self.home) or self.home.is_relative_to(inbox):
            raise ValueError('support_mailbox_must_be_separate')
        result = {'replies': [], 'rejected': []}
        # Recovery and redelivery happen even when no new message arrived.
        self.recover()
        for path in sorted(inbox.glob('*.json'))[:64]:
            try:
                message = verify(load(owned(inbox, path.name)), self.key, sender='assistant')
                state = load(self.home / 'state.json')
                if message['id'] in state['seen']:
                    self.receive(message)  # Collision checks and lost reply redelivery.
                    continue
                result['replies'].append(self.receive(message)['id'])
            except (ValueError, KeyError, TypeError, OSError) as exc:
                result['rejected'].append({'file': path.name, 'reason': str(exc)})
            finally:
                # Retain input evidence without letting the first batch starve new mail.
                try:
                    archive = owned(inbox, 'processed/' + uuid.uuid4().hex + '-' + path.name)
                    archive.parent.mkdir(exist_ok=True)
                    owned(inbox, path.name).rename(archive)
                except (ValueError, OSError) as exc:
                    result['rejected'].append({'file': path.name, 'reason': 'archive_failed:' + str(exc)})
        return result
