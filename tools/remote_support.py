"""Local file-transport controller; no mail account or model is contacted."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.remote_support_protocol import envelope, load, publish, verify
from runtime.remote_support_supervisor import SupportSupervisor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', required=True, help='Pre-provisioned secret outside mailboxes')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('start', 'receive', 'recover', 'poll', 'reconcile'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--home', required=True)
        cmd.add_argument('--outbox', required=True)
        if name == 'start':
            cmd.add_argument('--source', required=True)
            cmd.add_argument('--policy', required=True)
        if name == 'receive':
            cmd.add_argument('--message', required=True)
        if name == 'poll':
            cmd.add_argument('--inbox', required=True)
        if name == 'reconcile':
            cmd.add_argument('--worker-stopped', action='store_true',
                             help='Local operator confirms the interrupted worker has terminated')
    reply = commands.add_parser('reply')
    reply.add_argument('--request', required=True)
    reply.add_argument('--payload', required=True)
    reply.add_argument('--kind', choices=['context_request', 'patch'], required=True)
    reply.add_argument('--outbox', required=True)
    args = parser.parse_args()
    key_path = Path(args.key_file).resolve()
    for area in ('outbox', 'inbox', 'source'):
        value = getattr(args, area, None)
        if value and key_path.is_relative_to(Path(value).resolve()):
            raise ValueError('support_key_must_be_outside_exchange_and_release')
    key = key_path.read_bytes()
    if args.command == 'reply':
        request = verify(load(args.request), key, sender='cos')
        message = envelope(args.kind, request['incident'], load(args.payload), key,
                           sender='assistant', reply_to=request['id'])
        path = publish(args.outbox, message)
        print(json.dumps({'message': str(path), 'id': message['id']}))
        return
    supervisor = SupportSupervisor(args.home, args.outbox, key)
    if args.command == 'start':
        result = supervisor.start(args.source, load(args.policy))
    elif args.command == 'receive':
        result = supervisor.receive(load(args.message))
    elif args.command == 'poll':
        print(json.dumps(supervisor.poll(args.inbox), ensure_ascii=False))
        return
    elif args.command == 'reconcile':
        result = supervisor.reconcile_interrupted(worker_stopped=args.worker_stopped)
    else:
        result = supervisor.recover()
    print(json.dumps({'id': result['id'], 'kind': result['kind'],
                      'status': result['payload'].get('status', 'waiting')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
