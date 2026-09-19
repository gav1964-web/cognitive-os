"""Trace an authorized native failure and optionally request one advisory nomination."""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from runtime.repair_target_nomination import (
    trace_failure_methods, nomination_context, nomination_messages, validate_nomination,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--python', type=Path)
    parser.add_argument('--authorize-native-trace', action='store_true', required=True)
    parser.add_argument('--request-model', action='store_true')
    args = parser.parse_args()
    project, work = args.project.resolve(), args.work_dir.resolve()
    if work.is_relative_to(project) or project.is_relative_to(work):
        parser.error('work directory must be outside the source project')
    work.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (work / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    packet = json.loads(args.packet.read_text(encoding='utf-8-sig'))
    save('declaration', {'scope': 'assisted development, not independent certification',
        'maximum_logical_model_calls': int(args.request_model), 'format_retries': 0,
        'source_apply': False, 'observation_packet_digest': packet.get('packet_digest')})
    result = {'status': 'blocked', 'logical_model_calls': 0, 'execution_authorized': False, 'source_apply': False}
    try:
        trace = trace_failure_methods(project=project, packet=packet, work_dir=work / 'trace',
            authorized=args.authorize_native_trace, python_executable=args.python)
        context = nomination_context(project=project, packet=packet, trace=trace)
        save('context', context)
        result['status'] = 'context_ready'
        if args.request_model:
            telemetry = []

            def capture(row):
                telemetry.append(row)
                save('telemetry', telemetry)

            config = LocalInferenceConfig.from_l45_env()
            config = replace(config, max_output_tokens=1200, telemetry_sink=capture,
                fallbacks=tuple(replace(f, max_output_tokens=1200, telemetry_sink=capture) for f in config.fallbacks))
            messages = nomination_messages(context)
            save('request', {'messages': messages, 'configured_model': config.model,
                'fallbacks': [f.model for f in config.fallbacks], 'maximum_output_tokens_per_transport': 1200})
            result['logical_model_calls'] = 1
            save('result', {**result, 'status': 'model_requested'})
            payload = call_json_chat(messages, config=config)
            save('response', payload)
            result['nomination'] = validate_nomination(payload, project=project, packet=packet, trace=trace, context=context)
            result['status'] = result['nomination']['status']
    except (LocalInferenceError, OSError, ValueError, TypeError, KeyError, SyntaxError) as exc:
        result.update(status='blocked', reason=str(exc)[:240])
    save('result', result)
    print(json.dumps({'status': result['status'], 'logical_model_calls': result['logical_model_calls'],
        'reason': result.get('reason'), 'receipt': str(work / 'result.json')}, ensure_ascii=False))
    return int(result['status'] == 'blocked')


if __name__ == '__main__':
    raise SystemExit(main())
