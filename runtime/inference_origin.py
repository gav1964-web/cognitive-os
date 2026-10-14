"""Keep configured and responding model identities distinct in role artifacts."""
from dataclasses import replace


def capture_origin(config):
    records = []

    def record(event):
        records.append(event)
        if config.telemetry_sink:
            config.telemetry_sink(event)

    return replace(config, telemetry_sink=record), records


def response_origin(config, records):
    responses = [row for row in records if row.get('final_content_state') == 'present'
                 and not row.get('provider_failure')]
    latest = responses[-1] if responses else {}
    failures = [{key: row.get(key) for key in ('requested_model', 'http_status', 'reason_code')}
                for row in records if row.get('event') == 'attempt_failed']
    return {'requested_model': config.model, 'model': latest.get('model', config.model),
            'model_reported': latest.get('model_reported', False),
            'resolved_provider': latest.get('provider_label', config.provider_label),
            'fallback_used': bool(latest.get('fallback_used', False)),
            'route_failures': failures[-6:]}
